import re
from datetime import date, datetime, timedelta, timezone

from .models import ParseResult, TravelIntent

DESTINATION = "서울 광화문"
DEFAULT_TRAVELERS = 2
DEFAULT_NIGHTS = 1
DEFAULT_MAX_PRICE_PER_NIGHT = 150_000
KOREA = timezone(timedelta(hours=9), name="Asia/Seoul")

_OUT_OF_SCOPE_REGIONS = ("부산", "제주", "강릉", "대구", "인천", "대전", "광주")
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})[-./](\d{1,2})[-./](\d{1,2})(?!\d)")
_YEAR_KOREAN_DATE = re.compile(r"(?<!\d)(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
_KOREAN_DATE = re.compile(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일")
_TRAVELERS = re.compile(r"([+-]?\d+)\s*명")
_NIGHTS = re.compile(r"([+-]?\d+)\s*박")
_BUDGET = re.compile(r"(?<![\d,])([+-]?\d[\d,]*)\s*(만\s*원|원)")
_RAIN_REQUEST = re.compile(r"(?:^|\s)비(?:\s*(?:예보|오는|올)|를\s*고려)|비가|우천|rain", re.I)


def _parse_travel_date(question: str, today: date) -> date | None:
    lowered = question.lower()
    if "모레" in question:
        return today + timedelta(days=2)
    if "내일" in question:
        return today + timedelta(days=1)
    if "오늘" in question:
        return today

    match = _YEAR_KOREAN_DATE.search(question)
    if match:
        try:
            return date(*(int(part) for part in match.groups()))
        except ValueError:
            return None

    match = _ISO_DATE.search(question)
    if match:
        try:
            return date(*(int(part) for part in match.groups()))
        except ValueError:
            return None

    match = _KOREAN_DATE.search(question)
    if match:
        try:
            month, day = (int(part) for part in match.groups())
            return date(today.year, month, day)
        except ValueError:
            return None

    if "today" in lowered:
        return today
    if "tomorrow" in lowered:
        return today + timedelta(days=1)
    return None


def _parse_budget(question: str) -> int | None:
    match = _BUDGET.search(question)
    if not match:
        return None
    amount = int(match.group(1).replace(",", ""))
    return amount * 10_000 if "만" in match.group(2) else amount


def parse_intent(
    question: str,
    now: datetime | None = None,
    default_max_price_per_night: int = DEFAULT_MAX_PRICE_PER_NIGHT,
) -> ParseResult:
    if default_max_price_per_night <= 0:
        raise ValueError("기본 예산은 0원보다 커야 합니다.")
    if not question.strip():
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="여행 날짜와 서울 광화문 여행 여부를 알려주세요.",
            clarification_questions=("여행 날짜가 언제인가요?",),
        )

    today = (now or datetime.now(KOREA)).astimezone(KOREA).date()
    if any(region in question for region in _OUT_OF_SCOPE_REGIONS):
        return ParseResult(
            status="unsupported_region",
            intent=None,
            message="현재 MVP는 서울 광화문 권역만 지원합니다.",
        )

    if "광화문" not in question and "gwanghwamun" not in question.lower():
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="현재 MVP 지원 지역은 서울 광화문입니다.",
            clarification_questions=("서울 광화문 여행을 계획하시는 게 맞나요?",),
        )

    travel_date = _parse_travel_date(question, today)
    if travel_date is None:
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="여행 날짜를 확인할 수 없습니다.",
            clarification_questions=("여행 날짜가 언제인가요?",),
        )
    if travel_date < today:
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="지난 날짜는 추천할 수 없습니다.",
            clarification_questions=("오늘 이후의 여행 날짜를 알려주세요.",),
        )

    assumptions: list[str] = []
    traveler_match = _TRAVELERS.search(question)
    travelers = int(traveler_match.group(1)) if traveler_match else DEFAULT_TRAVELERS
    if traveler_match is None:
        assumptions.append(f"인원 기본값 {DEFAULT_TRAVELERS}명")
    if travelers < 1:
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="여행 인원은 1명 이상이어야 합니다.",
            clarification_questions=("여행 인원은 몇 명인가요?",),
        )

    nights_match = _NIGHTS.search(question)
    nights = int(nights_match.group(1)) if nights_match else DEFAULT_NIGHTS
    if nights_match is None:
        assumptions.append(f"숙박 기본값 {DEFAULT_NIGHTS}박")
    if nights < 1:
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="숙박은 1박 이상으로 지정해 주세요.",
            clarification_questions=("몇 박 숙박하시나요?",),
        )

    max_price = _parse_budget(question)
    if max_price is None:
        max_price = default_max_price_per_night
        assumptions.append(f"예산 기본값 {max_price:,}원/실/박")
    if max_price <= 0:
        return ParseResult(
            status="needs_clarification",
            intent=None,
            message="숙박 예산은 0원보다 커야 합니다.",
            clarification_questions=("1실 1박 예산은 얼마인가요?",),
        )

    rainy = bool(_RAIN_REQUEST.search(question))
    indoor = rainy or any(token in question for token in ("실내", "indoor"))
    intent = TravelIntent(
        destination=DESTINATION,
        travel_date=travel_date,
        travelers=travelers,
        nights=nights,
        max_price_per_night=max_price,
        weather_scenario="rainy" if rainy else "sunny",
        indoor_preference=indoor,
        assumptions=tuple(assumptions),
    )
    return ParseResult(
        status="complete",
        intent=intent,
        message="여행 조건을 확인했습니다.",
    )
