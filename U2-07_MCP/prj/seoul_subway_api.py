from urllib.parse import quote


SUBWAY_API_URL = "http://swopenapi.seoul.go.kr/api/subway"
SUBWAY_API_KEY_NAME = "SEOUL_REAL_SUBWAY_API_KEY"


def arrival_url(service_key: str, station_name: str, end_index: int) -> str:
    key_segment = quote(service_key, safe="")
    station_segment = quote(station_name, safe="")
    return f"{SUBWAY_API_URL}/{key_segment}/json/realtimeStationArrival/0/{end_index}/{station_segment}"
