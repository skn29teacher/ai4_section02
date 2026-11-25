import json
import httpx
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(".env", override=True)
BASE_URL = "http://127.0.0.1:8000"


@tool
def fetch_order_via_rest(order_id: str) -> dict:
    """주문 번호(order_id)로 외부 REST API에서 주문 상태와 금액을 조회합니다."""
    resp = httpx.get(f"{BASE_URL}/api/orders/{order_id}", timeout=5.0)
    if resp.status_code != 200:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


@tool
def submit_refund_via_rest(order_id: str, reason: str) -> dict:
    """주문 번호(order_id)와 사유(reason)로 외부 REST API에 환불을 접수합니다."""
    resp = httpx.post(
        f"{BASE_URL}/api/orders/refund",
        json={"order_id": order_id, "reason": reason},
        timeout=5.0,
    )
    if resp.status_code != 200:
        return {"error": resp.text, "status_code": resp.status_code}
    return resp.json()


def run_direct_tool_agent(query: str) -> str:
    tools = [fetch_order_via_rest, submit_refund_via_rest]
    registry = {t.name: t for t in tools}
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)

    messages = [
        SystemMessage(content="주문 조회 및 환불 처리는 제공된 REST API 도구를 호출해 안내하세요."),
        HumanMessage(content=query),
    ]

    for _ in range(5):
        ai_msg = llm.invoke(messages)
        messages.append(ai_msg)
        if not ai_msg.tool_calls:
            return ai_msg.content
        for call in ai_msg.tool_calls:
            out = registry[call["name"]].invoke(call["args"])
            print(f"  [@tool 직접 호출] {call['name']}({call['args']}) -> {out}")
            messages.append(ToolMessage(content=json.dumps(out, ensure_ascii=False), tool_call_id=call["id"]))
    return "반복 초과"


if __name__ == "__main__":
    print(run_direct_tool_agent("ORD-1001 주문 상태 알려주고, ORD-1002는 '중복 주문' 사유로 환불 접수해줘."))