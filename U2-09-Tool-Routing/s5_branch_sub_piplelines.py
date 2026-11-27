# 분기별 전용 tool 바인딩 체인(sub-pipeline)구축
# 최소권한 원칙(Last Privilege Tool Binding)
    # KNOWLEGE_SEARCH 분기에는 오직 SEARCH_TOOLS만 바인딩, 질문에 "환불해줘" 뉘앙스 살짝 섞여도
    # 쓰기 API(api_refund_order)자체가 바인딩 되지 않았기때문에 실수로 실행될 가능성이 없다

    # API_READ 분기는 READ_API_TOOLS만 바인딩
    # MULTI_STEP 분기에는 검색+조회+실행 도구를 모두 열어둔다
import json
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage,SystemMessage,ToolMessage
from langchain_core.runnables import RunnableBranch,RunnableLambda,RunnablePassthrough
from langchain_openai import ChatOpenAI

from s3_llm_intent_router import build_intent_router
from s4_backend_and_tools import(
    ACTION_API_TOOLS,
    ALL_TOOLS,
    READ_API_TOOLS,
    SEARCH_TOOLS,
    start_mock_api_background
)

load_dotenv('.env',override=True)

def make_tool_executor_chain(branch_name: str, allowed_tools: list, system_instruction: str):
    """특정 분기(Branch)에 허용된 도구 목록만 바인딩하는 전용 실행기를 생성합니다."""
    registry = {t.name: t for t in allowed_tools}

    def _run(state: dict) -> dict:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"),
            temperature=0,            
        )
        bound_llm = llm.bind_tools(allowed_tools) if allowed_tools else llm

        messages = [
            SystemMessage(content=system_instruction),
            HumanMessage(content=f"<untrusted_user_input>\n{state['query']}\n</untrusted_user_input>"),
        ]
        used_tools: list[str] = []

        for _ in range(6):
            ai_msg = bound_llm.invoke(messages)
            messages.append(ai_msg)

            # if not ai_msg.tool_calls:
            if not getattr(ai_msg, "tool_calls", None):
                return {
                    "route": branch_name,
                    "used_tools": used_tools,
                    "answer": ai_msg.content,
                }

            for call in ai_msg.tool_calls:
                t_name = call["name"]
                t_args = call["args"]
                used_tools.append(t_name)
                out = registry[t_name].invoke(t_args) if t_name in registry else {"error": "허용되지 않은 도구"}
                messages.append(
                    ToolMessage(
                        content=f"<untrusted_tool_output name='{t_name}'>\n{json.dumps(out, ensure_ascii=False)}\n</untrusted_tool_output>",
                        tool_call_id=call["id"],
                    )
                )

        return {"route": branch_name, "used_tools": used_tools, "answer": "반복 한도 초과"}

    return RunnableLambda(_run)