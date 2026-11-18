from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TravelIntent:
    destination: str
    travel_date: date
    travelers: int
    nights: int
    max_price_per_night: int
    weather_scenario: str
    indoor_preference: bool
    assumptions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParseResult:
    status: str
    intent: TravelIntent | None
    message: str
    clarification_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class Accommodation:
    accommodation_id: str
    name: str
    capacity: int
    nightly_price: int
    source: str = "accommodation-fixture"
    freshness: str = "simulated"


@dataclass(frozen=True)
class WeatherForecast:
    scenario: str
    condition: str
    min_temperature_c: int
    max_temperature_c: int
    precipitation_probability: float
    source: str = "weather-fixture"
    freshness: str = "simulated"


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str
    category: str
    indoor: bool
    source: str = "google-maps-mock"
    freshness: str = "simulated"
