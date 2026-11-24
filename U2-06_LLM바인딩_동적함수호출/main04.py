# Pydantic args_chema 결합과 정밀 인자 추출
import json
from typing import Literal
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv(".env", override=True)


class BackupScheduleSpec(BaseModel):
    target_db: Literal["orders_db", "logs_db", "analytics_db"] = Field(..., description="백업 대상 DB 이름")
    retention_days: int = Field(..., ge=1, le=365, description="보관 기간 (1일~365일 사이 정수)")
    compression: Literal["gzip", "zstd", "none"] = Field(..., description="압축 방식 (gzip, zstd, none)")


@tool(args_schema=BackupScheduleSpec)
def create_backup_plan(target_db: str, retention_days: int, compression: str) -> dict:
    """지정된 DB, 보관 기간, 압축 방식으로 백업 계획을 생성합니다."""
    return {
        "status": "scheduled",
        "target_db": target_db,
        "retention_days": retention_days,
        "compression": compression,
    }


if __name__ == "__main__":
    print("[4차시] Pydantic args_schema JSON Schema:")
    print(json.dumps(create_backup_plan.args_schema.model_json_schema(), indent=2, ensure_ascii=False))

    # chatopenai 객체생성
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0).bind_tools([create_backup_plan])
    query = "로그 DB를 zstd 압축으로 30일 보관하게 백업 계획 잡아줘."
    # humanmessage를 이용해서 ai_msg 생성
    ai_msg = llm.invoke([HumanMessage(content=query)])
    print("동적 추출된 args:", ai_msg.tool_calls)

    for call in ai_msg.tool_calls:
        # call이 가지고 있는 함수를 실행해서 
        res = create_backup_plan.invoke(call["args"])
        t_msg = ToolMessage(content=json.dumps(res, ensure_ascii=False), tool_call_id=call["id"])
        final_msg = llm.invoke([HumanMessage(content=query), ai_msg, t_msg])
        print("최종 답변:\n", final_msg.content)