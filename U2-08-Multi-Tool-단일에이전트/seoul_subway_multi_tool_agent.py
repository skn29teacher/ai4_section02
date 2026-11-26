import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from seoul_subway_api_tool_test import search_subway_arrivals


def run_agent(query: str) -> str:
    load_dotenv(Path(__file__).with_name(".env"), override=True)
    tools = [search_subway_arrivals]
    agent = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-5-nano").bind_tools(tools)
    messages = [
        SystemMessage(
            content=(
                "사용자가 입력한 역의 실시간 도착 정보를 search_subway_arrivals 도구로 조회해.\n"
                "realtimeArrivalList의 각 항목을 한 줄씩 안내해. "
                "방향과 행선지는 updnLine과 trainLineNm, 도착 상태는 arvlMsg2의 원문을 사용해. "
                "열차 종류는 btrainSttus, 열차 번호는 btrainNo에서 가져와.\n"
                "arvlMsg3는 열차의 보고 위치이므로 다음 역으로 표시하지 마. "
                "도착 시간은 추정하지 말고 조회 가능한 범위만 안내해.\n"
                "목록이 비어 있으면 도착 정보가 없다고 안내하고, 도구가 error를 반환하면 그 내용을 알려줘."
            ),
        ),
        HumanMessage(content=query),
    ]
    tool_registry = {tool.name: tool for tool in tools}

    for _ in range(5):
        ai_message = agent.invoke(messages)
        messages.append(ai_message)
        if not ai_message.tool_calls:
            return ai_message.text

        for call in ai_message.tool_calls:
            tool = tool_registry.get(call["name"])
            try:
                if tool is None:
                    raise ValueError(f"등록되지 않은 도구입니다 ({call['name']}).")
                result = tool.invoke(call["args"])
            except httpx.HTTPStatusError as exc:
                result = {"error": f"서울시 지하철 API 요청 실패 (HTTP {exc.response.status_code})"}
            except httpx.RequestError:
                result = {"error": "서울시 지하철 API 서버에 연결하지 못했습니다."}
            except (json.JSONDecodeError, UnicodeDecodeError):
                result = {"error": "서울시 지하철 API 응답을 JSON으로 읽을 수 없습니다."}
            except ValueError as exc:
                result = {"error": str(exc)}

            messages.append(
                ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call["id"])
            )

    return "도구 호출 횟수 제한에 도달했습니다."


if __name__ == "__main__":
    query = input("지하철 역 이름을 입력하세요: ")
    result = run_agent(query)
    print(result)
