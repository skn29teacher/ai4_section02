# 라우팅
    # 입력 데이터의 조건을 판별해서 서로다른 후속 체임(Runnable) 중 하나를 동적으로 선택 실행
# LCEL 3대 라우팅 빌딩 블럭
    # RunnablePassthrough : 입력 데이터를 그대로 다음 체인으로 전달
    # RunnableBranch(조건함수1,체인1), (조건함수2,체인2)... if else else 구조로 동작
    # RunnableLambda : 파이썬 조건로직으로 분기대상을 반환하는 커스텀 라우터함수를 LCEL 파이프라인에 적용
from langchain_core.runnables import RunnableBranch, RunnableLambda, RunnablePassthrough

# 1. 조건을 판별하는 함수
def classify_by_keyword(payload:dict) -> str:
    text = payload['query'].lower()  # 소문자 변환
    if any(k in text for k in ['환불','취소','주문']):
        return 'ACTION_BRANCH'
    elif any(k in text for k in ['재고','배송','상태']):
        return 'API_READ_BRANCH'
    elif any(k in text for k in ['규정','정책','추천','스펙']):
        return 'SEARCH_BRANCH'
    return 'GENERAL_BRANCH'

search_handler = RunnableLambda(lambda x: f"[검색 체인 실행] {x['query']} -> 지식베이스 검색 도구 연결")
api_read_handler = RunnableLambda(lambda x: f"[조회 API 체인 실행] {x['query']} -> 실시간 조회 API 도구 연결")
action_handler = RunnableLambda(lambda x: f"[실행 API 체인 실행] {x['query']} -> 트랜잭션 실행 도구 연결")
general_handler = RunnableLambda(lambda x: f"[검색 체인 실행] {x['query']} -> 도구없이 일반 답변")

routing_pipeline = (
    RunnablePassthrough.assign(route=RunnableLambda(classify_by_keyword))
    | RunnableBranch(
        (lambda x : x['route'] == 'SEARCH_BRANCH', search_handler),
        (lambda x : x['route'] == 'API_READ_BRANCH', api_read_handler),
        (lambda x : x['route'] == 'ACTION_BRANCH', action_handler),
        general_handler,
    )
)
if __name__ == "__main__":
    samples = [
        {'query': '환불 규정이 어떻게 되나요?'},
        {'query': 'SKU-101 현재 재고 상태 알려줘'},
        {'query': 'ORD-5001 주문 환불 접수해줘'},
        {'query': '안녕하세요 오늘 운영시간이 궁금해요'}
    ]
    for s in samples:
        print( routing_pipeline.invoke(s) )
