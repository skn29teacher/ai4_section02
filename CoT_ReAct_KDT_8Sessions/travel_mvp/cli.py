import argparse
import json

from .intent import DEFAULT_MAX_PRICE_PER_NIGHT
from .planner import plan_trip


def main() -> None:
    parser = argparse.ArgumentParser(
        description="가상 데이터 기반 서울 광화문 여행 추천 MVP"
    )
    parser.add_argument(
        "question",
        help="예: 내일 광화문 2명 1박, 숙소 15만원 이하, 비를 고려한 코스",
    )
    parser.add_argument(
        "--default-budget-per-night",
        type=int,
        default=DEFAULT_MAX_PRICE_PER_NIGHT,
        help="질문에 숙박 예산이 없을 때 적용할 조정 가능한 제안 기본값 (KRW)",
    )
    args = parser.parse_args()
    result = plan_trip(
        args.question,
        default_max_price_per_night=args.default_budget_per_night,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
