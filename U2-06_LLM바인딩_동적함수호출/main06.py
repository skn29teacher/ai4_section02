# 동적호출 실패 예외 처리 와 self-correction 루프
import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv(".env", override=True)


@tool
def allocate_gpu_memory(requested_gb: int) -> dict:
    """요청한 GPU 메모리(requested_gb, 1~80 사이 정수)를 할당합니다."""
    if not (1 <= requested_gb <= 80):
        raise ValueError(f"요청 용량 {requested_gb}GB는 허용 범위(1~80GB)를 벗어났습니다.")
    return {"allocated_gb": requested_gb, "status": "allocated"}


def run_self_correcting_tool_loop(query: str) -> str:
    tools = [allocate_gpu_memory]
    registry = {t.name: t for t in tools}
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools(tools)

    messages = [
        SystemMessage(
            content=(
                "GPU 메모리 할당은 allocate_gpu_memory 도구를 호출하세요. "
                "도구 실행 결과에 error가 있으면 허용 범위(1~80GB)를 안내하고 재입력을 요청하세요."
            )
        ),
        HumanMessage(content=query),
    ]

    for step in range(1, 5):
        ai_msg = llm.invoke(messages)
        messages.append(ai_msg)

        if not ai_msg.tool_calls:
            return ai_msg.content

        for call in ai_msg.tool_calls:
            try:
                payload = registry[call["name"]].invoke(call["args"])
            except Exception as exc:
                # 예외를 삼키지 않고 ToolMessage로 모델에 전달해 교정/안내를 유도
                payload = {"error": str(exc), "args": call["args"]}

            print(f"[6차시 | Step {step}] {call['name']}({call['args']}) -> {payload}")
            messages.append(ToolMessage(content=json.dumps(payload, ensure_ascii=False), tool_call_id=call["id"]))

    return "최대 반복 횟수에 도달했습니다."


if __name__ == "__main__":
    print(run_self_correcting_tool_loop("GPU 메모리 128GB 할당해줘."))