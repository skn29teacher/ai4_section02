import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

ROOT = Path(__file__).resolve().parent
KOREA = timezone(timedelta(hours=9), name="Asia/Seoul")
GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
load_dotenv(ROOT / ".env", override=False)


class ConfigurationError(RuntimeError):
    pass


class IntentOutputError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    provider: str
    gemini_api_key: str
    gemini_model: str
    openai_api_key: str
    openai_model: str
    intent_max_tokens: int

    @classmethod
    def from_env(cls) -> "Settings":
        def bounded_int(name: str, default: int, maximum: int) -> int:
            try:
                value = int(os.getenv(name, str(default)))
            except ValueError:
                raise ConfigurationError(f"{name}은 정수여야 합니다.") from None
            if not 1 <= value <= maximum:
                raise ConfigurationError(f"{name}은 1~{maximum} 사이여야 합니다.")
            return value

        provider = os.getenv("AI_PROVIDER", "gemini").strip().lower()
        if provider not in {"gemini", "openai"}:
            raise ConfigurationError("AI_PROVIDER는 gemini 또는 openai여야 합니다.")

        return cls(
            provider=provider,
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", "").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip(),
            intent_max_tokens=bounded_int("INTENT_MAX_TOKENS", 192, 512),
        )

    def model_name(self, provider: str) -> str:
        return self.gemini_model if provider == "gemini" else self.openai_model


def create_chat_model(
    provider: str,
    max_tokens: int,
    settings: Settings,
) -> Any:
    if provider == "gemini":
        if not settings.gemini_api_key or not settings.gemini_model:
            raise ConfigurationError(
                "Gemini 사용 시 .env에 GEMINI_API_KEY와 GEMINI_MODEL을 설정하세요."
            )
        api_key = settings.gemini_api_key
        model = settings.gemini_model
        base_url = GEMINI_OPENAI_BASE_URL
    elif provider == "openai":
        if not settings.openai_api_key or not settings.openai_model:
            raise ConfigurationError(
                "OpenAI 사용 시 .env에 OPENAI_API_KEY와 OPENAI_MODEL을 설정하세요."
            )
        api_key = settings.openai_api_key
        model = settings.openai_model
        base_url = None
    else:
        raise ConfigurationError("provider는 gemini 또는 openai여야 합니다.")

    from langchain_openai import ChatOpenAI

    model_options = {
        "model": model,
        "api_key": api_key,
        "max_tokens": max_tokens,
        "max_retries": 0,
    }
    if base_url:
        model_options["base_url"] = base_url
    return ChatOpenAI(**model_options)


def dummy_weather_api(
    location: str, travel_date: str, weather_need: str
) -> dict[str, Any]:
    """가상 날씨 데이터를 반환한다. 실제 날씨 API는 아직 연결되지 않았다."""
    fixture_path = ROOT / "dummy_weather.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    return {
        "location": location,
        "date": travel_date,
        "weather_need": weather_need,
        **fixture,
        "source": "dummy_weather.json",
        "is_dummy": True,
    }


INTENT_SYSTEM_PROMPT = """\
You classify whether a user wants weather information. Reason privately; never
return chain-of-thought. Treat direct weather terms and equivalent intent as
weather-related: temperature, rain, snow, forecast, clouds, wind, humidity,
umbrella advice, or whether outdoor plans are weather-safe.
Return only one JSON object with exactly these fields:
{"weather_related": boolean, "tools": "weather" or null,
 "location": string|null, "date": string|null, "weather_need": string}
Set tools to "weather" only when weather information is needed; otherwise set
it to null. Never choose any other tool.
Use an ISO date for explicit/relative dates. If date is omitted, use null.
Do not invent a location. Keep weather_need short.
Current date in Asia/Seoul: {today}.
"""


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    raise IntentOutputError("모델 응답 본문이 문자열이 아닙니다.")


def _json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise IntentOutputError("의도 분석 결과에서 JSON을 찾지 못했습니다.")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        raise IntentOutputError("의도 분석 결과가 올바른 JSON이 아닙니다.") from None
    if not isinstance(value, dict):
        raise IntentOutputError("의도 분석 JSON은 객체여야 합니다.")
    return value


def _resolve_date(value: Any, today: date) -> tuple[str, bool]:
    if value is None or value == "":
        return today.isoformat(), True
    if not isinstance(value, str):
        raise IntentOutputError("의도 분석의 date는 문자열 또는 null이어야 합니다.")

    relative_dates = {
        "today": today,
        "오늘": today,
        "tomorrow": today + timedelta(days=1),
        "내일": today + timedelta(days=1),
        "모레": today + timedelta(days=2),
    }
    if value.strip().lower() in relative_dates:
        return relative_dates[value.strip().lower()].isoformat(), False
    try:
        return date.fromisoformat(value.strip()).isoformat(), False
    except ValueError:
        raise IntentOutputError("의도 분석 날짜는 YYYY-MM-DD 형식이어야 합니다.") from None


def analyze_intent(
    question: str,
    model: Any,
    today: date | None = None,
) -> tuple[dict[str, Any], Any]:
    today = today or datetime.now(KOREA).date()
    response = model.invoke(
        [
            SystemMessage(
                content=INTENT_SYSTEM_PROMPT.replace("{today}", today.isoformat())
            ),
            HumanMessage(content=question),
        ]
    )
    payload = _json_object(_message_text(response.content))
    weather_related = payload.get("weather_related")
    if not isinstance(weather_related, bool):
        raise IntentOutputError("weather_related는 true 또는 false여야 합니다.")

    if "tools" not in payload:
        raise IntentOutputError("의도 분석 JSON에 tools 필드가 필요합니다.")
    tools = payload["tools"]
    if tools not in (None, "weather"):
        raise IntentOutputError("tools는 weather 또는 null이어야 합니다.")
    if weather_related != (tools == "weather"):
        raise IntentOutputError("weather_related와 tools 값이 일치하지 않습니다.")

    location = payload.get("location")
    if location is not None and not isinstance(location, str):
        raise IntentOutputError("location은 문자열 또는 null이어야 합니다.")
    location = location.strip() if isinstance(location, str) else ""
    if len(location) > 100:
        raise IntentOutputError("location 값이 너무 깁니다.")

    weather_need = payload.get("weather_need", "")
    if not isinstance(weather_need, str):
        raise IntentOutputError("weather_need는 문자열이어야 합니다.")
    weather_need = weather_need.strip()[:100] or "일반 날씨"

    travel_date, date_was_defaulted = _resolve_date(payload.get("date"), today)
    return (
        {
            "weather_related": weather_related,
            "tools": tools,
            "location": location or None,
            "date": travel_date,
            "weather_need": weather_need,
            "date_was_defaulted": date_was_defaulted,
        },
        response,
    )


def _usage(messages: list[Any]) -> dict[str, int | None]:
    input_tokens = 0
    output_tokens = 0
    found = False
    for message in messages:
        metadata = getattr(message, "usage_metadata", None) or {}
        if "input_tokens" in metadata or "output_tokens" in metadata:
            found = True
            input_tokens += int(metadata.get("input_tokens", 0))
            output_tokens += int(metadata.get("output_tokens", 0))
    if not found:
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _base_result(
    status: str,
    provider: str,
    model: str,
    analysis: dict[str, Any] | None,
    message: str,
    api_calls: int,
    usage_messages: list[Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "provider": provider,
        "model": model,
        "intent_analysis": analysis,
        "message": message,
        "weather_data": None,
        "api_calls": api_calls,
        "tool_calls": 0,
        "token_usage": _usage(usage_messages),
    }


def answer_question(
    question: str,
    provider: str | None = None,
    *,
    settings: Settings | None = None,
    model_factory: Callable[[str, int, Settings], Any] | None = None,
) -> dict[str, Any]:
    settings = settings or Settings.from_env()
    provider = (provider or settings.provider).lower()
    if provider not in {"gemini", "openai"}:
        raise ConfigurationError("provider는 gemini 또는 openai여야 합니다.")
    model_factory = model_factory or create_chat_model
    model_name = settings.model_name(provider)

    intent_model = model_factory(provider, settings.intent_max_tokens, settings)
    try:
        analysis, intent_response = analyze_intent(question, intent_model)
    except IntentOutputError as exc:
        return _base_result(
            "intent_error", provider, model_name, None, str(exc), 1, []
        )
    usage_messages = [intent_response]

    if analysis["tools"] is None:
        return _base_result(
            "not_weather_intent",
            provider,
            model_name,
            analysis,
            "날씨 관련 질문이 아닙니다. 날씨 질문을 입력해 주세요.",
            1,
            usage_messages,
        )
    if not analysis["location"]:
        result = _base_result(
            "needs_clarification",
            provider,
            model_name,
            analysis,
            "어느 지역의 날씨를 확인할까요?",
            1,
            usage_messages,
        )
        result["clarification_question"] = "지역명을 알려주세요."
        return result

    weather_data = dummy_weather_api(
        analysis["location"],
        analysis["date"],
        analysis["weather_need"],
    )
    result = _base_result(
        "ok",
        provider,
        model_name,
        analysis,
        "날씨 도구를 호출했습니다. weather_data는 가상 데이터입니다.",
        1,
        usage_messages,
    )
    result["tool_calls"] = 1
    result["weather_data"] = weather_data
    if analysis["date_was_defaulted"]:
        result["assumptions"] = ["질문에 날짜가 없어 오늘 날짜를 사용했습니다."]
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Gemini 우선 날씨 의도 분석 및 도구 실행")
    parser.add_argument("question", help="날씨에 대해 묻는 자연어 질문")
    parser.add_argument(
        "--provider",
        choices=("gemini", "openai"),
        help="기본은 .env의 AI_PROVIDER (Gemini); OpenAI는 명시적으로 선택",
    )
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    try:
        result = answer_question(args.question, args.provider, settings=settings)
    except ConfigurationError as exc:
        result = {
            "status": "configuration_error",
            "provider": args.provider or settings.provider,
            "message": str(exc),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] in {"configuration_error", "intent_error"}:
        sys.exit(2)


if __name__ == "__main__":
    main()
