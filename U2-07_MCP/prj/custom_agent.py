import asyncio
import json
import os
import sys

from dotenv import dotenv_values
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError
from mcp.types import PaginatedRequestParams, TextContent
from openai import AsyncOpenAI, OpenAIError

from seoul_subway_api import SUBWAY_API_KEY_NAME

QUESTION = "독산역 1호선. 승강장까지 5분 걸리고 수원역까지 가려는데 몇시에 열차를 탈수 있을까?"
SUBWAY_TOOLS = {"get_server_time", "get_subway_arrivals", "assess_subway_boarding"}
SYSTEM_PROMPT = (
    "당신은 서울 지하철 도착정보 에이전트의 도구 인자를 추출합니다. "
    "현재 서버 시각만 물으면 get_server_time을 사용하세요. "
    "사용자가 역별 도착정보만 묻는 경우 get_subway_arrivals를 사용하세요. "
    "출발역과 최종 하차역이 주어지면 assess_subway_boarding을 호출하세요. "
    "출발역은 station_name, 최종 하차역은 destination_station에 넣으세요. "
    "노선과 승강장까지의 이동 시간은 사용자가 명시했을 때만 넣고, 이동 시간은 초로 변환하세요. "
    "누락된 역·노선·시간을 추측하지 마세요. "
    "서버 시각, 도착 시각, 탑승 판단은 서버 도구 결과를 사용하세요."
)


async def discover_tools(session: ClientSession) -> list[dict]:
    tools = []
    page = await session.list_tools()
    while True:
        for tool in page.tools:
            if tool.name in SUBWAY_TOOLS:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema,
                    },
                })
        if not page.next_cursor:
            return tools
        page = await session.list_tools(params=PaginatedRequestParams(cursor=page.next_cursor))


async def run_agent(
    session: ClientSession, client: AsyncOpenAI, model: str, question: str = QUESTION
) -> str:
    await session.initialize()
    tools = await discover_tools(session)
    if {tool["function"]["name"] for tool in tools} != SUBWAY_TOOLS:
        raise RuntimeError("서울 지하철 MCP 도구를 찾지 못했습니다.")

    completion = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        tools=tools,
        tool_choice="auto",
        parallel_tool_calls=False,
    )
    choice = completion.choices[0]
    if not choice.message.tool_calls:
        if choice.finish_reason != "stop":
            raise RuntimeError(f"모델 응답이 중단되었습니다 ({choice.finish_reason}).")
        return "역별 도착정보를 조회하려면 역 이름을, 탑승 후보를 찾으려면 출발역과 최종 목적지를 알려주세요."

    calls = choice.message.tool_calls
    if len(calls) != 1 or calls[0].type != "function" or calls[0].function.name not in SUBWAY_TOOLS:
        raise RuntimeError("지하철 MCP 도구 호출을 확인할 수 없습니다.")
    call = calls[0]
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError:
        raise RuntimeError("지하철 MCP 도구 인자를 읽을 수 없습니다.") from None
    if not isinstance(arguments, dict):
        raise RuntimeError("지하철 MCP 도구 인자는 JSON 객체여야 합니다.")

    result = await session.call_tool(call.function.name, arguments)
    if result.is_error:
        detail = "\n".join(block.text for block in result.content if isinstance(block, TextContent))
        raise RuntimeError(detail or "서울 지하철 MCP에서 조회에 실패했습니다.")
    if not isinstance(result.structured_content, dict):
        raise RuntimeError("서울 지하철 MCP가 결과를 반환하지 않았습니다.")
    summary = result.structured_content.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise RuntimeError("서울 지하철 MCP의 결과 요약을 읽을 수 없습니다.")
    return summary


async def main() -> None:
    project_root = os.path.dirname(os.path.realpath(__file__))
    config = dotenv_values(os.path.join(project_root, ".env"), encoding="utf-8-sig")
    api_key = (os.getenv("OPENAI_API_KEY", config.get("OPENAI_API_KEY")) or "").strip()
    if not api_key:
        raise RuntimeError("프로젝트의 .env에 OPENAI_API_KEY를 설정하세요.")
    model = (os.getenv("OPENAI_MODEL", config.get("OPENAI_MODEL")) or "").strip() or "gpt-4o"

    child_env = {"PYTHONUTF8": "1"}
    if SUBWAY_API_KEY_NAME in os.environ:
        child_env[SUBWAY_API_KEY_NAME] = os.environ[SUBWAY_API_KEY_NAME]
    server = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(project_root, "commercial_mcp_server.py")],
        cwd=project_root,
        env=child_env,
    )
    question = " ".join(sys.argv[1:]).strip() or QUESTION
    async with (
        AsyncOpenAI(api_key=api_key, timeout=45.0, max_retries=1) as client,
        stdio_client(server) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream, read_timeout_seconds=60.0) as session,
    ):
        answer = await run_agent(session, client, model, question)

    print(answer)


def error_message(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        return "\n".join(error_message(cause) for cause in error.exceptions)
    if isinstance(error, OpenAIError):
        return f"OpenAI 모델 호출에 실패했습니다 ({type(error).__name__})."
    return str(error) or type(error).__name__


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (RuntimeError, OpenAIError, MCPError, OSError, ExceptionGroup) as exc:
        sys.exit(f"에이전트 실행 오류 {error_message(exc)}")
