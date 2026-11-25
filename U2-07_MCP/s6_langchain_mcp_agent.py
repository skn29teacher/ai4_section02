# mcp 세션 + LLM API  + 외부 API 연동 결합된 에이전트

import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage
from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env", override=True)

async def run_mcp_llm_agent(user_query:str)->str:
    server_params =  StdioServerParameters(
        command=sys.executable,
        args=[str(SCRIPT_DIR / "s5_order_mcpserver.py")],
    )
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream,write_stream) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            tool_map = {tool.name: tool for tool in mcp_tools}
            tool_schemas = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.input_schema,
                    },
                }
                for tool in mcp_tools
            ]

            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tool_schemas)
            messages = [
                SystemMessage(content="주문 및 환불 업무는 MCP 서버에서 제공된 도구를 사용해 처리하세요."),
                HumanMessage(content=user_query),
            ]

            for _ in range(5):
                ai_msg = await llm.ainvoke(messages)
                messages.append(ai_msg)
                if not ai_msg.tool_calls:
                    return ai_msg.content

                for call in ai_msg.tool_calls:
                    tool = tool_map[call["name"]]
                    result = await session.call_tool(tool.name, arguments=call["args"])
                    tool_out = result.model_dump_json(by_alias=True, exclude_none=True)
                    print(f"  [MCP Tool 실행] {call['name']}({call['args']}) -> {tool_out}")
                    messages.append(ToolMessage(content=tool_out, tool_call_id=call["id"]))

            return "최대 반복 횟수 초과"
if __name__ == "__main__":
    q = "ORD_1001의 상품명과 금액을 확인하고, ORD_1002는 '배송 지연 우려'로 환불 접수해줘."
    print(asyncio.run(run_mcp_llm_agent(q)))        