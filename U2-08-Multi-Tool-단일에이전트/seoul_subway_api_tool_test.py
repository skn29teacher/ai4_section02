# langchain tool 생성
import json
import os

import os

from langchain_core.tools import tool
from seoul_subway_api_test import get_arrivals
from dotenv import load_dotenv


@tool("search_subway_arrivals", description="서울시 지하철 실시간 도착 정보를 조회합니다. 역 이름을 입력하면 해당 역의 도착 정보를 반환합니다.")
def search_subway_arrivals(station_name: str) -> dict:
    """서울시 지하철 실시간 도착 정보를 조회합니다. 역 이름을 입력하면 해당 역의 도착 정보를 반환합니다."""    

    load_dotenv(".env", override=True)
    api_key = os.getenv("SEOUL_SUBWAY_API_KEY", "").strip()
    if not api_key:
        raise ValueError(".env에 SEOUL_SUBWAY_API_KEY를 설정해 주세요.")
    return get_arrivals(station_name, api_key)

if __name__ == "__main__":
    result = search_subway_arrivals.invoke({"station_name": "독산"})
    print(json.dumps(result, ensure_ascii=False, indent=2))