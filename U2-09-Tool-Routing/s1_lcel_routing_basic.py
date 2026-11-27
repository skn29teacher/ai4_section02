# 라우팅
    # 입력 데이터의 조건을 판별해서 서로다른 후속 체임(Runnable) 중 하나를 동적으로 선택 실행
# LCEL 3대 라우팅 빌딩 블럭
    # RunnablePassThrough : 입력 데이터를 그대로 다음 체임으로 전달
    # RunnableBranch(조건함수1,체인1), (조건함수2,체인2)... if else else 구조로 동작
    # RunnableLambda : 파이썬 조건로직으로 분기대상을 반환하는 커스텀 라우터함수를 LCEL 파이프라인에 적용
