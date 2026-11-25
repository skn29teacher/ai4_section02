from pathlib import Path

import httpx
from dotenv import dotenv_values
import json

from seoul_subway_api import SUBWAY_API_KEY_NAME, arrival_url

STATION_NAME = "독산"


def main() -> int:
    env_path = Path(__file__).resolve().with_name(".env")
    config = dotenv_values(env_path, encoding="utf-8-sig")
    service_key = (config.get(SUBWAY_API_KEY_NAME) or "").strip()
    if not service_key:
        raise SystemExit(f".env에 {SUBWAY_API_KEY_NAME}를 설정하세요.")

    try:
        response = httpx.get(
            arrival_url(service_key, STATION_NAME, end_index=5),
            timeout=httpx.Timeout(10.0, connect=5.0),
        )
    except httpx.RequestError as exc:
        raise SystemExit(f"서울시 지하철 API 요청에 실패했습니다 ({type(exc).__name__}).") from None

    print(
        json.dumps( json.loads(response.text), indent=2, ensure_ascii=False),
        end=""
        )
    return 0 if response.is_success else 1


if __name__ == "__main__":
    raise SystemExit(main())
