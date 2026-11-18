from datetime import date
from typing import Protocol

from .models import Accommodation, Place, TravelIntent, WeatherForecast


class ProviderUnavailable(RuntimeError):
    """읽기 전용 데이터 provider를 사용할 수 없을 때 발생한다."""


class AccommodationRepository(Protocol):
    def search(self, intent: TravelIntent) -> list[Accommodation]: ...


class WeatherProvider(Protocol):
    def forecast(self, travel_date: date, scenario: str) -> WeatherForecast: ...


class MapsProvider(Protocol):
    def search_places(self, indoor_only: bool) -> list[Place]: ...

    def route_between(self, origin_id: str, destination_id: str) -> int: ...

    def route_from_accommodation(self, accommodation_id: str, place_id: str) -> int: ...


class MockAccommodationRepository:
    _fixtures = (
        Accommodation("hotel-fixture-001", "가상 숙소 A", 2, 90_000),
        Accommodation("hotel-fixture-002", "가상 숙소 B", 2, 120_000),
        Accommodation("hotel-fixture-003", "가상 숙소 C", 2, 160_000),
        Accommodation("hotel-fixture-004", "가상 숙소 D", 1, 70_000),
    )

    def search(self, intent: TravelIntent) -> list[Accommodation]:
        return [
            item
            for item in self._fixtures
            if item.capacity >= intent.travelers
            and item.nightly_price <= intent.max_price_per_night
        ]


class MockWeatherProvider:
    _fixtures = {
        "sunny": WeatherForecast(
            scenario="sunny",
            condition="맑음",
            min_temperature_c=8,
            max_temperature_c=16,
            precipitation_probability=0.1,
        ),
        "rainy": WeatherForecast(
            scenario="rainy",
            condition="비",
            min_temperature_c=7,
            max_temperature_c=13,
            precipitation_probability=0.8,
        ),
    }

    def forecast(self, travel_date: date, scenario: str) -> WeatherForecast:
        try:
            return self._fixtures[scenario]
        except KeyError:
            raise ProviderUnavailable("날씨 시나리오를 찾을 수 없습니다.") from None


class MockGoogleMapsProvider:
    _outdoor_places = (
        Place("place-gyeongbokgung", "경복궁", "문화유산", False),
        Place("place-gwanghwamun-square", "광화문광장", "광장", False),
        Place("place-cheonggyecheon", "청계천", "산책", False),
    )
    _indoor_places = (
        Place("place-sejong-center", "세종문화회관", "공연·문화", True),
        Place("place-national-folk-museum", "국립민속박물관", "박물관", True),
        Place("place-history-museum", "대한민국역사박물관", "박물관", True),
    )
    _place_routes = {
        ("place-sejong-center", "place-national-folk-museum"): 18,
        ("place-national-folk-museum", "place-history-museum"): 12,
        ("place-gyeongbokgung", "place-gwanghwamun-square"): 9,
        ("place-gwanghwamun-square", "place-cheonggyecheon"): 14,
    }
    _hotel_routes = {
        ("hotel-fixture-001", "place-sejong-center"): 12,
        ("hotel-fixture-002", "place-sejong-center"): 8,
        ("hotel-fixture-001", "place-gyeongbokgung"): 13,
        ("hotel-fixture-002", "place-gyeongbokgung"): 9,
    }

    def search_places(self, indoor_only: bool) -> list[Place]:
        return list(self._indoor_places if indoor_only else self._outdoor_places)

    def route_between(self, origin_id: str, destination_id: str) -> int:
        try:
            return self._place_routes[(origin_id, destination_id)]
        except KeyError:
            raise ProviderUnavailable("경로 fixture를 찾을 수 없습니다.") from None

    def route_from_accommodation(
        self,
        accommodation_id: str,
        place_id: str,
    ) -> int:
        try:
            return self._hotel_routes[(accommodation_id, place_id)]
        except KeyError:
            raise ProviderUnavailable("경로 fixture를 찾을 수 없습니다.") from None
