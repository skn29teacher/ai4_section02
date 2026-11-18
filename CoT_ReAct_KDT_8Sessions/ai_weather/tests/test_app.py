import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app import (
    ConfigurationError,
    Settings,
    answer_question,
    analyze_intent,
    create_chat_model,
    dummy_weather_api,
    _generate_final_answer,
)


def make_settings() -> Settings:
    return Settings(
        provider="gemini",
        gemini_api_key="test-key",
        gemini_model="test-gemini",
        openai_api_key="test-openai-key",
        openai_model="gpt-5-nano",
        intent_max_tokens=128,
        final_max_tokens=256,
    )


class FakeModel:
    def __init__(self, content):
        self.content = content
        self.last_response = None
        self.invoke_count = 0
        self.last_messages = None

    def invoke(self, messages):
        self.invoke_count += 1
        self.last_messages = messages
        self.last_response = SimpleNamespace(
            content=self.content,
            usage_metadata={"input_tokens": 10, "output_tokens": 20},
        )
        return self.last_response


def make_model_factory(intent_model, final_model):
    def factory(provider, max_tokens, settings):
        return final_model if provider == "openai" else intent_model

    return factory


class AppTests(unittest.TestCase):
    def test_create_chat_model_uses_shared_openai_adapter_for_both_providers(self):
        created_models = []

        class FakeChatOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                created_models.append(self)

        fake_module = SimpleNamespace(ChatOpenAI=FakeChatOpenAI)
        settings = make_settings()

        with patch.dict("sys.modules", {"langchain_openai": fake_module}):
            gemini_model = create_chat_model("gemini", 128, settings)
            openai_model = create_chat_model("openai", 256, settings)

        self.assertIsInstance(gemini_model, FakeChatOpenAI)
        self.assertIsInstance(openai_model, FakeChatOpenAI)
        self.assertEqual(
            gemini_model.kwargs,
            {
                "model": "test-gemini",
                "api_key": "test-key",
                "max_tokens": 128,
                "max_retries": 0,
                "base_url": (
                    "https://generativelanguage.googleapis.com/v1beta/openai/"
                ),
            },
        )
        self.assertEqual(
            openai_model.kwargs,
            {
                "model": "gpt-5-nano",
                "api_key": "test-openai-key",
                "max_tokens": 256,
                "max_retries": 0,
                "reasoning_effort": "minimal",
            },
        )
        self.assertEqual(len(created_models), 2)

    def test_empty_openai_answer_reports_finish_reason_and_reasoning_usage(self):
        class EmptyResponseModel:
            def invoke(self, messages):
                return SimpleNamespace(
                    content="",
                    response_metadata={"finish_reason": "length"},
                    usage_metadata={
                        "output_tokens": 384,
                        "output_token_details": {"reasoning": 384},
                    },
                )

        with self.assertRaisesRegex(
            RuntimeError,
            "finish_reason=length, output_tokens=384, reasoning_tokens=384",
        ):
            _generate_final_answer(
                "오늘 점심메뉴 추천해줘",
                "direct_answer",
                {"weather_related": False, "tools": None},
                None,
                EmptyResponseModel(),
            )

    def test_openai_final_answer_key_is_required_before_intent_request(self):
        settings = make_settings()
        settings = Settings(
            provider=settings.provider,
            gemini_api_key=settings.gemini_api_key,
            gemini_model=settings.gemini_model,
            openai_api_key="",
            openai_model=settings.openai_model,
            intent_max_tokens=settings.intent_max_tokens,
            final_max_tokens=settings.final_max_tokens,
        )

        with self.assertRaises(ConfigurationError):
            answer_question("서울 날씨 알려줘", settings=settings)

    def test_dummy_weather_function_returns_json_fixture_data(self):
        result = dummy_weather_api(
            location="서울",
            travel_date="2026-11-18",
            weather_need="강수 여부",
        )

        self.assertEqual(result["location"], "서울")
        self.assertEqual(result["date"], "2026-11-18")
        self.assertEqual(result["source"], "dummy_weather.json")
        self.assertTrue(result["is_dummy"])

    def test_intent_analysis_resolves_relative_date_without_exposing_reasoning(self):
        model = FakeModel(
            json.dumps(
                {
                    "weather_related": True,
                    "tools": "weather",
                    "location": "부산",
                    "date": "내일",
                    "weather_need": "비와 우산 필요 여부",
                },
                ensure_ascii=False,
            )
        )

        intent, _ = analyze_intent(
            "내일 부산에 비 오면 우산 챙길까?",
            model,
            today=date(2026, 11, 18),
        )

        self.assertEqual(intent["date"], "2026-11-19")
        self.assertEqual(intent["location"], "부산")
        self.assertNotIn("reasoning", intent)

    def test_non_weather_intent_does_not_call_weather_function(self):
        intent_model = FakeModel(
            json.dumps(
                {
                    "weather_related": False,
                    "tools": None,
                    "location": None,
                    "date": None,
                    "weather_need": "",
                }
            )
        )
        final_model = FakeModel("광화문 근처의 식당 정보를 찾아보세요.")

        result = answer_question(
            "광화문 근처 맛집 추천해줘",
            settings=make_settings(),
            model_factory=make_model_factory(intent_model, final_model),
        )

        self.assertEqual(result["status"], "not_weather_intent")
        self.assertEqual(result["api_calls"], 2)
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(result["final_provider"], "openai")
        self.assertEqual(result["message"], final_model.content)
        self.assertEqual(intent_model.invoke_count, 1)
        self.assertEqual(final_model.invoke_count, 1)
        self.assertEqual(result["token_usage"]["total_tokens"], 60)

    def test_unknown_tool_name_is_rejected(self):
        intent_model = FakeModel(
            json.dumps(
                {
                    "weather_related": True,
                    "tools": "news",
                    "location": "서울",
                    "date": "2026-11-19",
                    "weather_need": "비 예보",
                },
                ensure_ascii=False,
            )
        )
        final_model = FakeModel("should not be called")

        result = answer_question(
            "내일 서울 비 예보 알려줘",
            settings=make_settings(),
            model_factory=make_model_factory(intent_model, final_model),
        )

        self.assertEqual(result["status"], "intent_error")
        self.assertEqual(result["tool_calls"], 0)
        self.assertIsNone(result["weather_data"])
        self.assertEqual(final_model.invoke_count, 0)

    def test_missing_tool_field_is_rejected(self):
        intent_model = FakeModel(
            json.dumps(
                {
                    "weather_related": False,
                    "location": None,
                    "date": None,
                    "weather_need": "",
                }
            )
        )
        final_model = FakeModel("should not be called")

        result = answer_question(
            "광화문 근처 맛집 추천해줘",
            settings=make_settings(),
            model_factory=make_model_factory(intent_model, final_model),
        )

        self.assertEqual(result["status"], "intent_error")
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(final_model.invoke_count, 0)

    def test_weather_intent_routes_to_function_and_returns_structured_data(self):
        intent_model = FakeModel(
            json.dumps(
                {
                    "weather_related": True,
                    "tools": "weather",
                    "location": "서울",
                    "date": "2026-11-19",
                    "weather_need": "비 예보",
                },
                ensure_ascii=False,
            )
        )
        final_model = FakeModel("내일 서울의 가상 날씨 정보입니다.")

        result = answer_question(
            "내일 서울 비 예보 알려줘",
            settings=make_settings(),
            model_factory=make_model_factory(intent_model, final_model),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["api_calls"], 2)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(result["final_provider"], "openai")
        self.assertEqual(result["message"], final_model.content)
        self.assertTrue(result["weather_data"]["is_dummy"])
        self.assertEqual(result["weather_data"]["source"], "dummy_weather.json")
        self.assertEqual(result["intent_analysis"]["tools"], "weather")
        self.assertEqual(result["token_usage"]["total_tokens"], 60)
        final_context = json.loads(final_model.last_messages[1].content)
        self.assertTrue(final_context["tool_result"]["is_dummy"])

    def test_weather_without_location_asks_before_function_call(self):
        intent_model = FakeModel(
            json.dumps(
                {
                    "weather_related": True,
                    "tools": "weather",
                    "location": None,
                    "date": None,
                    "weather_need": "비 예보",
                }
            )
        )
        final_model = FakeModel("어느 지역의 날씨를 확인할까요?")

        result = answer_question(
            "비 올까?",
            settings=make_settings(),
            model_factory=make_model_factory(intent_model, final_model),
        )

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["tool_calls"], 0)
        self.assertEqual(result["api_calls"], 2)
        self.assertEqual(result["message"], final_model.content)
        self.assertEqual(result["clarification_question"], "지역명을 알려주세요.")


if __name__ == "__main__":
    unittest.main()
