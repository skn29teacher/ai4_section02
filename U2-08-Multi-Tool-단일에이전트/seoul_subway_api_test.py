import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv


SUBWAY_API_URL = "http://swopenapi.seoul.go.kr/api/subway"


def get_arrivals(station_name: str, api_key: str) -> dict:
    station_name = station_name.strip().removesuffix("역").strip()
    if not station_name:
        raise ValueError("역 이름을 입력해 주세요.")

    key_segment = quote(api_key, safe="")
    station_segment = quote(station_name, safe="")
    url = f"{SUBWAY_API_URL}/{key_segment}/json/realtimeStationArrival/0/10/{station_segment}"

    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("서울시 지하철 API 응답 형식이 올바르지 않습니다.")

    result = payload.get("errorMessage") or payload
    code = result.get("code") if isinstance(result, dict) else None
    if code is None:
        raise ValueError("서울시 지하철 API 응답에 결과 코드가 없습니다.")
    if code not in ("INFO-000", "INFO-200"):
        detail = result.get("message") or "요청 처리에 실패했습니다."
        raise ValueError(f"서울시 지하철 API 오류 ({code}) {detail}".replace(api_key, "***"))

    return payload


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"), override=True)
    api_key = os.getenv("SEOUL_SUBWAY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit(".env에 SEOUL_SUBWAY_API_KEY를 설정해 주세요.")

    print("역 이름을 입력하세요 [독산역]: ", end="", file=sys.stderr, flush=True)
    station_name = input().strip() or "독산역"

    try:
        payload = get_arrivals(station_name, api_key)
    except httpx.HTTPStatusError as exc:
        raise SystemExit(f"서울시 지하철 API 요청 실패 (HTTP {exc.response.status_code})") from None
    except httpx.RequestError:
        raise SystemExit("서울시 지하철 API 서버에 연결하지 못했습니다.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SystemExit("서울시 지하철 API 응답을 JSON으로 읽을 수 없습니다.") from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
