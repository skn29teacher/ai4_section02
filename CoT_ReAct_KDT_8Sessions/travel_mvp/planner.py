from collections import Counter
from datetime import datetime
from typing import Any

from .intent import DEFAULT_MAX_PRICE_PER_NIGHT, parse_intent
from .models import Accommodation, Place, TravelIntent
from .providers import (
    AccommodationRepository,
    MapsProvider,
    MockAccommodationRepository,
    MockGoogleMapsProvider,
    MockWeatherProvider,
    ProviderUnavailable,
    WeatherProvider,
)


def _timestamp(now: datetime | None) -> str:
    return (now or datetime.now().astimezone()).isoformat(timespec="seconds")


def _rank_accommodations(
    options: list[Accommodation],
    intent: TravelIntent,
    maps: MapsProvider,
    first_place: Place | None,
) -> tuple[list[Accommodation], dict[str, int], list[str]]:
    route_minutes: dict[str, int] = {}
    route_errors: list[str] = []
    price_counts = Counter(item.nightly_price * intent.nights for item in options)
    if first_place is not None and any(count > 1 for count in price_counts.values()):
        price_groups: dict[int, list[Accommodation]] = {}
        for option in options:
            total_price = option.nightly_price * intent.nights
            price_groups.setdefault(total_price, []).append(option)

        for group in price_groups.values():
            if len(group) < 2:
                continue
            group_failed = False
            for option in group:
                try:
                    route_minutes[option.accommodation_id] = (
                        maps.route_from_accommodation(
                            option.accommodation_id, first_place.place_id
                        )
                    )
                except ProviderUnavailable:
                    group_failed = True
            if group_failed:
                for option in group:
                    route_minutes.pop(option.accommodation_id, None)
                route_errors.append(
                    "동일 예산 후보의 지도 경로를 모두 확인하지 못해 해당 후보는 fixture ID 순으로 정렬했습니다."
                )

    ranked = sorted(
        options,
        key=lambda item: (
            item.nightly_price * intent.nights,
            route_minutes.get(item.accommodation_id, float("inf")),
            item.accommodation_id,
        ),
    )
    return ranked, route_minutes, route_errors


def _accommodation_data(
    accommodation: Accommodation,
    intent: TravelIntent,
    route_minutes: int | None,
) -> dict[str, Any]:
    return {
        "id": accommodation.accommodation_id,
        "name": accommodation.name,
        "capacity": accommodation.capacity,
        "nightly_price_krw": accommodation.nightly_price,
        "total_price_krw": accommodation.nightly_price * intent.nights,
        "route_to_first_stop_minutes": route_minutes,
        "source": accommodation.source,
        "freshness": accommodation.freshness,
        "reason": (
            "수용 인원과 1박 예산 조건을 충족하며, "
            "숙박 총액이 낮은 순으로 정렬했습니다."
        ),
    }


def _itinerary(
    places: list[Place],
    maps: MapsProvider,
) -> tuple[list[dict[str, Any]], list[str]]:
    stops: list[dict[str, Any]] = []
    caveats: list[str] = []
    for index, place in enumerate(places):
        leg_minutes = None
        if index:
            previous = places[index - 1]
            try:
                leg_minutes = maps.route_between(
                    previous.place_id, place.place_id
                )
            except ProviderUnavailable:
                caveats.append(
                    f"{previous.name}에서 {place.name}까지의 경로를 조회하지 못했습니다."
                )
        stops.append(
            {
                "order": index + 1,
                "place_id": place.place_id,
                "name": place.name,
                "category": place.category,
                "travel_minutes_from_previous": leg_minutes,
                "source": place.source,
                "freshness": place.freshness,
            }
        )
    return stops, caveats


def plan_trip(
    question: str,
    *,
    now: datetime | None = None,
    accommodations: AccommodationRepository | None = None,
    weather: WeatherProvider | None = None,
    maps: MapsProvider | None = None,
    default_max_price_per_night: int = DEFAULT_MAX_PRICE_PER_NIGHT,
) -> dict[str, Any]:
    parsed = parse_intent(
        question,
        now=now,
        default_max_price_per_night=default_max_price_per_night,
    )
    if parsed.intent is None:
        return {
            "status": parsed.status,
            "message": parsed.message,
            "clarification_questions": list(parsed.clarification_questions),
            "sources": [],
        }

    intent = parsed.intent
    accommodations = accommodations or MockAccommodationRepository()
    weather = weather or MockWeatherProvider()
    maps = maps or MockGoogleMapsProvider()
    fetched_at = _timestamp(now)
    caveats: list[str] = []
    sources: list[dict[str, str]] = []

    try:
        options = accommodations.search(intent)
        sources.append(
            {
                "source": "accommodation-fixture",
                "fetched_at": fetched_at,
                "freshness": "simulated",
            }
        )
    except ProviderUnavailable:
        options = []
        caveats.append("가상 숙소 정보를 조회하지 못했습니다.")

    try:
        forecast = weather.forecast(intent.travel_date, intent.weather_scenario)
        weather_data = {
            "scenario": forecast.scenario,
            "condition": forecast.condition,
            "min_temperature_c": forecast.min_temperature_c,
            "max_temperature_c": forecast.max_temperature_c,
            "precipitation_probability": forecast.precipitation_probability,
            "source": forecast.source,
            "freshness": forecast.freshness,
        }
        sources.append(
            {
                "source": forecast.source,
                "fetched_at": fetched_at,
                "freshness": forecast.freshness,
            }
        )
    except ProviderUnavailable:
        weather_data = None
        caveats.append("가상 날씨 정보를 조회하지 못했습니다.")

    try:
        places = maps.search_places(intent.indoor_preference)
        if places:
            sources.append(
                {
                    "source": places[0].source,
                    "fetched_at": fetched_at,
                    "freshness": places[0].freshness,
                }
            )
        else:
            caveats.append("조건에 맞는 장소를 찾지 못했습니다.")
    except ProviderUnavailable:
        places = []
        caveats.append("지도 장소 정보를 조회하지 못했습니다.")

    ranked_options, hotel_route_minutes, ranking_caveats = _rank_accommodations(
        options, intent, maps, places[0] if places else None
    )
    caveats.extend(ranking_caveats)
    accommodation_data = [
        _accommodation_data(
            option,
            intent,
            hotel_route_minutes.get(option.accommodation_id),
        )
        for option in ranked_options
    ]
    itinerary, route_caveats = _itinerary(places, maps)
    caveats.extend(route_caveats)

    if not ranked_options:
        caveats.append("조건에 맞는 숙소가 없습니다. 예산이나 인원을 조정해 주세요.")
    if not places:
        caveats.append("장소 정보가 없어 방문 코스를 구성하지 못했습니다.")
    status = "partial" if caveats else "complete"

    assumptions = list(intent.assumptions)
    if intent.weather_scenario in ("sunny", "rainy"):
        assumptions.append(
            "숙소·날씨·장소·경로는 시뮬레이션 데이터이며 실제 정보가 아닙니다."
        )

    return {
        "status": status,
        "message": (
            "서울 광화문 여행 추천입니다."
            if status == "complete"
            else "일부 정보를 바탕으로 추천합니다. 누락된 항목을 확인해 주세요."
        ),
        "destination": intent.destination,
        "travel_date": intent.travel_date.isoformat(),
        "travelers": intent.travelers,
        "nights": intent.nights,
        "max_price_per_night_krw": intent.max_price_per_night,
        "weather": weather_data,
        "accommodations": accommodation_data,
        "itinerary": itinerary,
        "assumptions": assumptions,
        "caveats": caveats,
        "sources": sources,
        "booking_and_payment": "not_supported",
    }
