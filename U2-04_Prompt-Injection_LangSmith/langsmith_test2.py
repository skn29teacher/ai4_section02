import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, ToolMessage, SystemMessage

load_dotenv('.env', override=True)

@tool
def multiply(a:int, b:int)->int:
    '''두 정수를 곱합니다.'''
    return a * b

llm = ChatOpenAI(model='gpt-4o-mini',temperature=0)
llm_with_tools = llm.bind_tools([multiply])

message = [
    SystemMessage(
        content=(
            "당신은 계산을 정확히 하는 에이전트입니다. 필요한 도구는 반드시 제공되는 도구를 사용하고",
            "여러 단계가 필요하면 도구 결과를 확인한뒤 다음 도구를 호출하세요"
        )
    ),
    HumanMessage(
        content="단가 25,000원짜리 상품을 4개 사고 10%할일을 받은뒤 1달러당 1,400기준 달러금액도 알려줘"
    )
]

max_steps = 6
for step in range(max_steps):
    ai_msg =  llm_with_tools.invoke(message)
    message.append(ai_msg)
    # 도구 호출이 없으면 최종 답변단계
    if not ai_msg.tool_calls:
        print('최종답변\n',ai_msg.content)
        break
    print(f"[Step {step + 1} 요청된 도구의수 : {len(ai_msg.tool_calls)}]")
    