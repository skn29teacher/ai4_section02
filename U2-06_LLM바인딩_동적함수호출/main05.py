# tool_choice 정책 제어와 다중/병렬 동적 호출
import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(".env", override=True)


@tool
def get_region_latency(region: str) -> dict:
    """리전(ap-northeast-2, us-east-1, eu-central-1)의 평균 네트워크 지연(ms)을 조회합니다."""
    latencies = {
        "ap-northeast-2": 14,
        "us-east-1": 148,
        "eu-central-1": 215,
    }
    r = region.lower()
    return {"region": r, "latency_ms": latencies.get(r, 99)}


def run_with_choice(query: str, tool_choice: str = "auto") -> str:
    tools = [get_region_latency]
    registry = {t.name: t for t in tools}
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools, tool_choice=tool_choice)

    messages = [HumanMessage(content=query)]
    ai_msg = llm.invoke(messages)
    messages.append(ai_msg)

    if not ai_msg.tool_calls:
        return ai_msg.content

    print(f"[5차시 | tool_choice={tool_choice}] tool_calls 개수: {len(ai_msg.tool_calls)}")
    for call in ai_msg.tool_calls:
        out = registry[call["name"]].invoke(call["args"])
        print(f"  -> {call['name']}({call['args']}) => {out}")
        messages.append(ToolMessage(content=json.dumps(out, ensure_ascii=False), tool_call_id=call["id"]))
    
    return llm.invoke(messages).content


if __name__ == "__main__":
    print(run_with_choice("서울(ap-northeast-2)과 버지니아(us-east-1) 지연시간을 함께 비교해줘.", "auto"))
    print("-" * 60)
    print(run_with_choice("도구 없이 일반 인사만 해줘. 단 ap-northeast-2 지연시간도 함께 알려줘.", "required"))