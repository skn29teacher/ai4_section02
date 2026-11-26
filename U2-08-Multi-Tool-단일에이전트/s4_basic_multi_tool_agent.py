# Multi-Tool 바인딩의 핵심:
#    검색 도구(`search_store_knowledge`)와 API 도구(`get_product_inventory`, `create_store_order`, `get_order_status`, `request_order_refund`)를 한 리스트로 묶어 `llm.bind_tools(TOOLS)`에 전달합니다.
#    도구가 많아질수록 각 `@tool`의 `docstring`에 **"언제 이 도구를 쓰고, 언제 다른 도구를 쓰는지"** 경계를 명확히 적어야 오호출(Tool Confusion)을 줄일 수 있습니다.

import json
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from s2_search_tool_test import search_store_knowledge
from s3_api_tool_test import (
    create_store_order,
    get_order_status,
    get_product_inventory,
    request_order_refund,
)

load_dotenv(".env", override=True)

TOOLS = [
    search_store_knowledge,
    get_product_inventory,
    create_store_order,
    get_order_status,
    request_order_refund,
]
TOOL_REGISTRY = {t.name: t for t in TOOLS}


def run_basic_multi_tool_agent(user_query: str) -> str:
    llm = ChatOpenAI(model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"), temperature=0).bind_tools(TOOLS)
    messages = [
        SystemMessage(
            content=(
                "당신은 테크 스토어 통합 AI 상담원입니다.\n"
                "- 상품 스펙/추천 조건/환불 규정은 `search_store_knowledge` 검색 도구로 확인하세요.\n"
                "- 실시간 재고, 주문 상태, 주문 생성, 환불 처리는 외부 API 도구를 호출하세요."
            )
        ),
        HumanMessage(content=user_query),
    ]

    for step in range(1, 7):
        ai_msg = llm.invoke(messages)
        messages.append(ai_msg)

        if not ai_msg.tool_calls:
            return ai_msg.content

        for call in ai_msg.tool_calls:
            name = call["name"]
            args = call["args"]
            print(f"  [Step {step}] 호출: {name}({args})")
            result = TOOL_REGISTRY[name].invoke(args)
            messages.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=call["id"],
                )
            )

    return "최대 반복 횟수 초과"


if __name__ == "__main__":
    q = "출장 갈 때 들고 다닐 멀티 허브 추천해 주고, 현재 재고 몇 개 남았는지 실시간으로 확인해줘."
    print("\n[최종 답변]\n", run_basic_multi_tool_agent(q))