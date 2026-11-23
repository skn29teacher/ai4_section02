# Pydantic / Python 타입힌트 기반 자동 스키마 변환
# Pydantic BasseModel Field(description=...) 를 정의해서 model_json_schema()로 표준
# JSON Schema 생성하거나 또는 @tool(args_schema=...) / bind_tools(...) 연결해서
# 타입검증과 스키마를 동시에 만족

# 직접작성한 dict 스키마dhk @tool /pydantic 이 만든 스키마 가 같은 JSON Schema형태를 api에게 넘긴다
