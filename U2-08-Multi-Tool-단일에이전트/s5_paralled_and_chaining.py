# 병렬 호출
    # 예 SKU-101 재고와 ORD-5001 주문 상태를 동시에 알려줘 -> 서로 의존성이 없어서 2개를 동시에 변환
# 순차 연쇄 호출
    # 예 사무실에 쓸 조용한 키보드 찾아서 재고가 있으면 1개 주문해줘
    # Turn 1 : 사무실 조용한 키보드 --> SKU-101
    # Turn 2 : SKU-101 상품검색 --> 재고 8개 확인
    # Turn 3 : 주문확정

from s4_basic_multi_tool_agent import run_basic_multi_tool_agent

if __name__ == "__main__":
    print('병렬 호출')
    q_parallel = 'SKU-101 실시간 재고랑 ORD-5001 주문상태 둘다 한번에 확인해줘'
    print(run_basic_multi_tool_agent(q_parallel))

    print('순차호출')
    q_parallel = '사무실에서 조용히 쓸 무선 키보드를 검색해서 찾은다음 재고가 있으면 1개 주문해줘'
    print(run_basic_multi_tool_agent(q_parallel))

