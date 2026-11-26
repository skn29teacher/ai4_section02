# langchain tool 생성
import json

from langchain_core.tools import tool

from subway_arrival_cache import cached_arrivals


@tool("search_subway_arrivals", description="서울시 지하철 실시간 도착 정보를 조회합니다. 역 이름을 입력하면 해당 역의 도착 정보를 반환합니다.")
def search_subway_arrivals(station_name: str) -> dict:
    """서울시 지하철 실시간 도착 정보를 조회합니다. 역 이름을 입력하면 해당 역의 도착 정보를 반환합니다."""

    return cached_arrivals(station_name)

if __name__ == "__main__":
    result = search_subway_arrivals.invoke({"station_name": "독산"})
    print(json.dumps(result, ensure_ascii=False, indent=2))
