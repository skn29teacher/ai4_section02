import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from app import (
    Settings,
    answer_question,
    analyze_intent,
    create_chat_model,
    dummy_weather_api,
)


def make_settings() -> Settings:
    return Settings(
        provider="gemini",
        gemini_api_key="test-key",
        gemini_model="test-gemini",
        openai_api_key="test-openai-key",
        openai_model="test-openai",
        intent_max_tokens=128,
        agent_max_tokens=256,
        max_react_steps=2,
    )


class FakeModel:
    def __init__(self, content):
        self.content = content
        self.last_response = None

    def invoke(self, messages):
        self.last_response = SimpleNamespace(
            content=self.content,
            usage_metadata={"input_tokens": 10, "output_tokens": 20},
        )
        return self.last_response


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
                "model": "test-openai",
                "api_key": "test-openai-key",
                "max_tokens": 256,
                "max_retries": 0,
            },
        )
        self.assertEqual(len(created_models), 2)

    def test_dummy_weather_tool_returns_json_fixture_with_source(self):
        result = json.loads(
            dummy_weather_api.invoke(
                {
                    "location": "서울",
                    "travel_date": "2026-11-18",
                    "weather_need": "강수 여부",
                }
            )
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

    def test_non_weather_intent_does_not_create_or_run_react_agent(self):
        model = FakeModel(
            json.dumps(
                {
                    "weather_related": False,
                    "location": None,
                    "date": None,
                    "weather_need": "",
                }
            )
        )

        def agent_factory(*args):
            raise AssertionError("ReAct agent should not be created")

        result = answer_question(
            "광화문 근처 맛집 추천해줘",
            settings=make_settings(),
            model_factory=lambda provider, max_tokens, settings: model,
            agent_factory=agent_factory,
        )

        self.assertEqual(result["status"], "not_weather_intent")
        self.assertEqual(result["api_calls"], 1)
        self.assertEqual(result["react_tool_calls"], 0)

    def test_weather_intent_runs_react_tool_and_returns_structured_dummy_data(self):
        model = FakeModel(
            json.dumps(
                {
                    "weather_related": True,
                    "location": "서울",
                    "date": "2026-11-19",
                    "weather_need": "비 예보",
                },
                ensure_ascii=False,
            )
        )

        class FakeAgent:
            def invoke(self, inputs, config):
                tool_result = dummy_weather_api.invoke(
                    {
                        "location": "서울",
                        "travel_date": "2026-11-19",
                        "weather_need": "비 예보",
                    }
                )
                return {
                    "messages": [
                        SimpleNamespace(
                            type="tool",
                            name=dummy_weather_api.name,
                            content=tool_result,
                            usage_metadata=None,
                        ),
                        SimpleNamespace(
                            type="ai",
                            name=None,
                            content="가상 날씨 정보입니다.",
                            usage_metadata={
                                "input_tokens": 12,
                                "output_tokens": 8,
                            },
                        ),
                    ]
                }

        result = answer_question(
            "내일 서울 비 예보 알려줘",
            settings=make_settings(),
            model_factory=lambda provider, max_tokens, settings: model,
            agent_factory=lambda model: FakeAgent(),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["api_calls"], 2)
        self.assertEqual(result["react_tool_calls"], 1)
        self.assertTrue(result["weather_data"]["is_dummy"])
        self.assertEqual(result["weather_data"]["source"], "dummy_weather.json")
        self.assertEqual(result["token_usage"]["total_tokens"], 50)

    def test_weather_without_location_asks_before_agent_call(self):
        model = FakeModel(
            json.dumps(
                {
                    "weather_related": True,
                    "location": None,
                    "date": None,
                    "weather_need": "비 예보",
                }
            )
        )

        def agent_factory(*args):
            raise AssertionError("ReAct agent should not be created")

        result = answer_question(
            "비 올까?",
            settings=make_settings(),
            model_factory=lambda provider, max_tokens, settings: model,
            agent_factory=agent_factory,
        )

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["react_tool_calls"], 0)
        self.assertEqual(result["clarification_question"], "지역명을 알려주세요.")


if __name__ == "__main__":
    unittest.main()
