import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(".env", override=True)


@tool
def lookup_user_quota(user_id: str) -> dict:
    """사용자 ID(user_id)의 일일 API 호출 한도와 현재 사용량을 조회합니다."""
    quotas = {
        "U-100": {"daily_limit": 1000, "used": 640},
        "U-200": {"daily_limit": 5000, "used": 4890},
    }
    q = quotas.get(user_id.upper(), {"daily_limit": 500, "used": 120})
    return {"user_id": user_id.upper(), **q, "remaining": q["daily_limit"] - q["used"]}


@tool
def calc_overage_cost(overage_calls: int, unit_cost_krw: int = 50) -> dict:
    """초과 호출 건수(overage_calls)와 건당 단가(unit_cost_krw)로 추가 과금을 계산합니다."""
    safe_calls = max(0, overage_calls)
    return {"overage_calls": safe_calls, "unit_cost_krw": unit_cost_krw, "overage_krw": safe_calls * unit_cost_krw}


def execute_dynamic_agent(prompt: str, tools_list: list) -> str:
    # if/elif 분기 대신 이름 -> BaseTool 매핑 레지스트리 사용
    tool_registry = {t.name: t for t in tools_list}
    llm_with_tools = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools_list)

    messages = [
        SystemMessage(content="쿼터 조회와 초과 과금 계산은 제공된 도구를 동적으로 호출해 처리하세요."),
        HumanMessage(content=prompt),
    ]