import unittest
from datetime import date, datetime, timedelta, timezone

from travel_mvp.intent import parse_intent
from travel_mvp.models import Accommodation
from travel_mvp.planner import plan_trip
from travel_mvp.providers import (
    MockAccommodationRepository,
    MockGoogleMapsProvider,
    MockWeatherProvider,
    ProviderUnavailable,
)

KOREA = timezone(timedelta(hours=9), name="Asia/Seoul")
FIXED_NOW = datetime(2026, 11, 18, 12, 0, tzinfo=KOREA)


class IntentParserTests(unittest.TestCase):
    def test_extracts_trip_fields_and_korean_budget(self):
        parsed = parse_intent(
            "내일 광화문 3명 2박, 숙소 15만원 이하, 비 오는 날 실내 코스",
            now=FIXED_NOW,
        )

        self.assertEqual(parsed.status, "complete")
        self.assertEqual(parsed.intent.travel_date, date(2026, 11, 19))
        self.assertEqual(parsed.intent.travelers, 3)
        self.assertEqual(parsed.intent.nights, 2)
        self.assertEqual(parsed.intent.max_price_per_night, 150_000)
        self.assertEqual(parsed.intent.weather_scenario, "rainy")
        self.assertTrue(parsed.intent.indoor_preference)

    def test_missing_date_requests_clarification_before_tools(self):
        parsed = parse_intent("서울 광화문 여행을 추천해줘", now=FIXED_NOW)

        self.assertEqual(parsed.status, "needs_clarification")
        self.assertIsNone(parsed.intent)
        self.assertTrue(parsed.clarification_questions)

    def test_planner_does_not_call_providers_before_clarifying(self):
        class MustNotCall:
            def search(self, intent):
                raise AssertionError("provider should not be called")

            def forecast(self, travel_date, scenario):
                raise AssertionError("provider should not be called")

            def search_places(self, indoor_only):
                raise AssertionError("provider should not be called")

            def route_between(self, origin_id, destination_id):
                raise AssertionError("provider should not be called")

            def route_from_accommodation(self, accommodation_id, place_id):
                raise AssertionError("provider should not be called")

        result = plan_trip(
            "광화문 여행을 추천해줘",
            now=FIXED_NOW,
            accommodations=MustNotCall(),
            weather=MustNotCall(),
            maps=MustNotCall(),
        )

        self.assertEqual(result["status"], "needs_clarification")
        self.assertEqual(result["sources"], [])

    def test_out_of_scope_region_is_not_rewritten_to_gwanghwamun(self):
        parsed = parse_intent("내일 부산 여행을 추천해줘", now=FIXED_NOW)

        self.assertEqual(parsed.status, "unsupported_region")
        self.assertIsNone(parsed.intent)

    def test_explicit_korean_year_date_is_preserved(self):
        parsed = parse_intent(
            "2027년 3월 5일 광화문 여행",
            now=FIXED_NOW,
        )

        self.assertEqual(parsed.intent.travel_date, date(2027, 3, 5))

    def test_budget_comparison_word_does_not_select_rainy_scenario(self):
        parsed = parse_intent(
            "내일 광화문 숙소 비용을 비교해줘",
            now=FIXED_NOW,
        )

        self.assertEqual(parsed.intent.weather_scenario, "sunny")

    def test_negative_budget_requests_clarification(self):
        parsed = parse_intent(
            "내일 광화문 숙소 예산 -1만원",
            now=FIXED_NOW,
        )

        self.assertEqual(parsed.status, "needs_clarification")
        self.assertIsNone(parsed.intent)


class PlannerTests(unittest.TestCase):
    def test_builds_simulated_recommendation_and_budget_ranking(self):
        result = plan_trip(
            "내일 광화문 2명 1박, 숙소 15만원 이하, 비 예보를 고려해줘",
            now=FIXED_NOW,
        )

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["travel_date"], "2026-11-19")
        self.assertEqual(
            [item["id"] for item in result["accommodations"]],
            ["hotel-fixture-001", "hotel-fixture-002"],
        )
        self.assertTrue(
            all(item["freshness"] == "simulated" for item in result["accommodations"])
        )
        self.assertEqual(result["weather"]["scenario"], "rainy")
        self.assertTrue(all(item["freshness"] == "simulated" for item in result["itinerary"]))
        self.assertEqual(result["booking_and_payment"], "not_supported")

    def test_defaults_are_disclosed_in_response(self):
        result = plan_trip("내일 광화문으로 가고 싶어요", now=FIXED_NOW)

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["travelers"], 2)
        self.assertEqual(result["nights"], 1)
        self.assertTrue(any("기본값" in item for item in result["assumptions"]))

    def test_equal_budget_uses_mock_maps_route_time_as_tiebreaker(self):
        class SamePriceRepository:
            def search(self, intent):
                return [
                    Accommodation("hotel-fixture-001", "가상 숙소 A", 2, 90_000),
                    Accommodation("hotel-fixture-002", "가상 숙소 B", 2, 90_000),
                ]

        result = plan_trip(
            "내일 광화문 2명 1박 15만원 이하",
            now=FIXED_NOW,
            accommodations=SamePriceRepository(),
        )

        self.assertEqual(
            [item["id"] for item in result["accommodations"]],
            ["hotel-fixture-002", "hotel-fixture-001"],
        )
        self.assertEqual(
            [item["route_to_first_stop_minutes"] for item in result["accommodations"]],
            [9, 13],
        )

    def test_configured_default_budget_is_used_and_disclosed(self):
        result = plan_trip(
            "내일 광화문 여행",
            now=FIXED_NOW,
            default_max_price_per_night=100_000,
        )

        self.assertEqual(result["max_price_per_night_krw"], 100_000)
        self.assertEqual(
            [item["id"] for item in result["accommodations"]],
            ["hotel-fixture-001"],
        )
        self.assertTrue(any("100,000원/실/박" in item for item in result["assumptions"]))

    def test_maps_failure_returns_partial_without_inventing_route_time(self):
        class MapsUnavailable(MockGoogleMapsProvider):
            def route_between(self, origin_id, destination_id):
                raise ProviderUnavailable("unavailable")

        result = plan_trip(
            "내일 광화문 2명 1박, 비 오는 날 실내 코스",
            now=FIXED_NOW,
            maps=MapsUnavailable(),
        )

        self.assertEqual(result["status"], "partial")
        self.assertIsNone(result["itinerary"][1]["travel_minutes_from_previous"])
        self.assertTrue(any("경로를 조회하지 못했습니다" in item for item in result["caveats"]))

    def test_fails_closed_for_no_matching_accommodation(self):
        result = plan_trip(
            "내일 광화문 4명 1박, 숙소 5만원 이하",
            now=FIXED_NOW,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["accommodations"], [])
        self.assertTrue(any("조건에 맞는 숙소가 없습니다" in item for item in result["caveats"]))


if __name__ == "__main__":
    unittest.main()
