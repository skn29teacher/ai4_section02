import json
import logging
import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Annotated, Literal

import httpx
from dotenv import load_dotenv
from mcp.server import MCPServer
from pydantic import BaseModel, Field, StringConstraints, ValidationError

from seoul_subway_api import SUBWAY_API_KEY_NAME, arrival_url

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
# The provider puts API keys in the request path.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

PROJECT_ROOT = os.path.dirname(os.path.realpath(__file__))
KST = timezone(timedelta(hours=9))
DATA_SOURCE = "서울 열린데이터광장 실시간 지하철 도착정보"
POLICY_VERSION = "subway-boarding-v3"
DEFAULT_BUFFER_SECONDS = 45
ROUTE_BUFFERS = {("역삼", "1002", "선릉"): 60}
MAX_PREDICTION_AGE_SECONDS = 120
MAX_CLOCK_SKEW_SECONDS = 5
LINE_NAMES = {
    **{str(1000 + number): f"{number}호선" for number in range(1, 10)},
    "1032": "GTX-A",
    "1061": "중앙선",
    "1063": "경의중앙선",
    "1065": "공항철도",
    "1067": "경춘선",
    "1075": "수인분당선",
    "1077": "신분당선",
    "1081": "경강선",
    "1092": "우이신설선",
    "1093": "서해선",
}
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
WalkingSeconds = Annotated[
    int, Field(strict=True, ge=0, description="승강장까지의 이동 시간(초). 생략하면 승강장 기준 0초")
]


@dataclass(frozen=True)
class DirectRoute:
    next_station: str
    terminals: frozenset[str] | None = None


DIRECT_ROUTES = {
    ("독산", "1001", "수원"): DirectRoute(
        next_station="금천구청",
        terminals=frozenset({"수원", "병점", "서동탄", "천안", "신창"}),
    ),
    ("역삼", "1002", "선릉"): DirectRoute(next_station="선릉"),
}


@asynccontextmanager
async def server_lifespan(_server: MCPServer[None]) -> AsyncGenerator[None, None]:
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"), encoding="utf-8-sig")
    yield


mcp = MCPServer(
    "Seoul-Subway-Arrival-Assistant",
    dependencies=["mcp[cli]==2.3.0"],
    lifespan=server_lifespan,
    instructions=(
        "현재 기준 시각을 확인하려면 get_server_time을 사용하세요. "
        "역별 실시간 도착정보에는 get_subway_arrivals를 사용하세요. "
        "출발역과 목적지가 주어지면 assess_subway_boarding으로 "
        "내부 여유시간을 적용한 탑승 후보를 확인하세요."
    ),
)


class ApiStatus(BaseModel):
    code: str


class ApiArrival(BaseModel):
    statnNm: str
    subwayId: str | int
    updnLine: str | None = None
    trainLineNm: str | None = None
    bstatnNm: str | None = None
    btrainSttus: str | None = None
    btrainNo: str | int | None = None
    barvlDt: int | None = None
    recptnDt: datetime | None = None
    arvlMsg2: str | None = None
    arvlMsg3: str | None = None
    arvlCd: str | int | None = None
    lstcarAt: str | int | None = None


class ApiResponse(BaseModel):
    errorMessage: ApiStatus | None = None
    code: str | None = None
    realtimeArrivalList: list[ApiArrival] | None = None


class Arrival(BaseModel):
    line_id: str
    line_name: str
    next_station: str | None
    direction: str | None
    destination: str | None
    train_type: str | None = None
    train_number: str | None
    remaining_seconds: int | None
    reported_at: datetime | None
    status_message: str | None
    reported_location: str | None
    last_train: bool | None

    def describe(self) -> str:
        route = f"{self.line_name} {self.next_station or '방면 미확인'}"
        if self.next_station:
            route += " 방면"
        if self.direction:
            route += f" ({self.direction})"
        if self.destination:
            route += f" · {self.destination}행"
        if self.train_number:
            route += f" · 열차 {self.train_number}"
        if self.last_train:
            route += " · 막차"
        if self.remaining_seconds is None:
            status = f" · {self.status_message}" if self.status_message else ""
            return f"{route}{status} · 남은 시간 확인 불가"
        if self.remaining_seconds == 0:
            return f"{route} · 진입 또는 도착"
        return f"{route} · 약 {self.remaining_seconds}초 후 도착"


class StationArrivals(BaseModel):
    station_name: str
    checked_at: datetime
    data_source: str = DATA_SOURCE
    arrivals: list[Arrival]
    summary: str


class ServerTime(BaseModel):
    current_time: datetime
    timezone: Literal["Asia/Seoul"] = "Asia/Seoul"
    summary: str


class BoardingAssessment(BaseModel):
    station_name: str
    line_id: str
    next_station: str
    destination_station: str
    checked_at: datetime
    data_source: str = DATA_SOURCE
    policy_version: str = POLICY_VERSION
    walking_seconds: int
    buffer_seconds: int
    required_seconds: int
    platform_ready_at: datetime
    earliest_boarding_at: datetime
    status: Literal["boardable", "later_train", "wait", "no_arrivals", "insufficient_data"]
    first_arrival: Arrival | None = None
    recommended_arrival: Arrival | None = None
    estimated_boarding_at: datetime | None = None
    latest_predicted_arrival_at: datetime | None = None
    margin_seconds: int | None = None
    summary: str


def station_key(name: str) -> str:
    name = "".join(name.split())
    return name.removesuffix("역") if len(name) > 1 else name


def parse_line_id(line: str) -> str:
    normalized = "".join(line.split()).casefold()
    if len(normalized) == 4 and normalized.isascii() and normalized.isdecimal():
        return normalized
    for line_id, label in LINE_NAMES.items():
        if normalized == label.casefold():
            return line_id
    raise ValueError("노선 이름(예: 2호선) 또는 서울시 노선 ID(예: 1002)를 입력하세요.")


@mcp.tool()
def get_server_time() -> ServerTime:
    """탑승 판정에 사용하는 MCP 서버의 현재 한국 표준시를 반환합니다."""
    current_time = datetime.now(KST).replace(microsecond=0)
    return ServerTime(
        current_time=current_time,
        summary=f"서버 현재 시각 {current_time:%Y-%m-%d %H:%M:%S} KST",
    )


@mcp.resource("policy://subway-boarding", mime_type="application/json")
def boarding_policy() -> str:
    """서울시 API 응답에 없는 프로젝트 내부 탑승 여유시간 기준표."""
    return json.dumps(
        {
            "version": POLICY_VERSION,
            "default_buffer_seconds": DEFAULT_BUFFER_SECONDS,
            "route_buffers": [
                {
                    "station": station,
                    "line_id": line_id,
                    "next_station": next_station,
                    "buffer_seconds": seconds,
                }
                for (station, line_id, next_station), seconds in ROUTE_BUFFERS.items()
            ],
            "max_prediction_age_seconds": MAX_PREDICTION_AGE_SECONDS,
            "destination_routes": [
                {
                    "station": station,
                    "line_id": line_id,
                    "destination_station": destination,
                    "next_station": route.next_station,
                    "regular_train_terminals": sorted(route.terminals) if route.terminals is not None else None,
                }
                for (station, line_id, destination), route in DIRECT_ROUTES.items()
            ],
            "rule": "서버 시각에 이동 시간과 내부 여유를 더한 시각부터 탑승할 수 있는 첫 열차",
            "scope": "프로젝트 실습용 탑승 판단 기준",
        },
        ensure_ascii=False,
        indent=2,
    )


def estimate_remaining(row: ApiArrival, checked_at: datetime) -> tuple[int | None, datetime | None]:
    reported_at = row.recptnDt
    if reported_at is None:
        return None, None
    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=KST)
    age = (checked_at - reported_at).total_seconds()
    code = str(row.arvlCd)
    if not -MAX_CLOCK_SKEW_SECONDS <= age <= MAX_PREDICTION_AGE_SECONDS or code == "2":
        return None, reported_at
    if code in {"0", "1"}:
        return 0, reported_at
    if row.barvlDt is None:
        return None, reported_at
    remaining = row.barvlDt - ceil(max(0, age))
    return (remaining if remaining > 0 else None), reported_at


async def fetch_arrivals(station_name: str) -> tuple[datetime, list[Arrival]]:
    service_key = os.getenv(SUBWAY_API_KEY_NAME, "").strip()
    if not service_key:
        raise RuntimeError(f"프로젝트 .env에 {SUBWAY_API_KEY_NAME}를 설정하세요.")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            response = await client.get(arrival_url(service_key, station_name, end_index=1000))
            response.raise_for_status()
        payload = ApiResponse.model_validate_json(response.content)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"서울시 지하철 API가 HTTP {exc.response.status_code}을 반환했습니다.") from None
    except httpx.RequestError as exc:
        raise RuntimeError(f"서울시 지하철 API에 연결할 수 없습니다 ({type(exc).__name__}).") from None
    except ValidationError:
        raise RuntimeError("서울시 지하철 API 응답 형식을 확인할 수 없습니다.") from None

    checked_at = get_server_time().current_time
    code = payload.errorMessage.code if payload.errorMessage else payload.code
    if code == "INFO-200":
        return checked_at, []
    if code != "INFO-000":
        if code == "INFO-100":
            raise RuntimeError("서울시 지하철 API 인증키가 유효하지 않습니다 (INFO-100).")
        raise RuntimeError("서울시 지하철 API가 도착정보를 반환하지 않았습니다.")

    arrivals = []
    for row in payload.realtimeArrivalList or []:
        if station_key(row.statnNm) != station_name:
            continue
        line_id = str(row.subwayId)
        _, _, direction_text = (row.trainLineNm or "").partition(" - ")
        next_station = station_key(direction_text.partition("방면")[0])
        remaining, reported_at = estimate_remaining(row, checked_at)
        last_train_flag = str(row.lstcarAt)
        arrivals.append(
            Arrival(
                line_id=line_id,
                line_name=LINE_NAMES.get(line_id, line_id),
                next_station=next_station or None,
                direction=row.updnLine,
                destination=row.bstatnNm,
                train_type=row.btrainSttus,
                train_number=str(row.btrainNo) if row.btrainNo is not None else None,
                remaining_seconds=remaining,
                reported_at=reported_at,
                status_message=row.arvlMsg2,
                reported_location=row.arvlMsg3,
                last_train=(last_train_flag == "1") if last_train_flag in {"0", "1"} else None,
            )
        )
    return checked_at, arrivals


@mcp.tool()
async def get_subway_arrivals(station_name: Name) -> StationArrivals:
    """역 이름으로 서울시의 실제 열차별 도착 예정 시간, 방면, 종착역을 조회합니다."""
    station = station_key(station_name)
    checked_at, arrivals = await fetch_arrivals(station)
    lines = [f"{station}역 실시간 도착정보 ({checked_at:%H:%M:%S} KST)"]
    lines.extend(f"- {arrival.describe()}" for arrival in arrivals)
    if not arrivals:
        lines.append("조회된 도착정보가 없습니다.")
    lines.append(f"출처 {DATA_SOURCE}")
    return StationArrivals(
        station_name=station, checked_at=checked_at, arrivals=arrivals, summary="\n".join(lines)
    )


def resolve_route(
    station: str, destination: str, requested_line: str | None, arrivals: list[Arrival]
) -> tuple[str, DirectRoute]:
    routes = {
        line_id: route
        for (start, line_id, end), route in DIRECT_ROUTES.items()
        if start == station and end == destination and requested_line in (None, line_id)
    }
    if not routes:
        routes = {
            arrival.line_id: DirectRoute(next_station=destination)
            for arrival in arrivals
            if arrival.next_station == destination and requested_line in (None, arrival.line_id)
        }
    if not routes:
        raise ValueError(f"{station}역에서 {destination}역까지 확인할 수 있는 직통 경로가 없습니다.")
    if len(routes) > 1:
        raise ValueError("이 구간은 탑승 가능한 노선이 여러 개입니다. 원하는 노선을 입력하세요.")
    return next(iter(routes.items()))


@mcp.tool()
async def assess_subway_boarding(
    station_name: Annotated[Name, Field(description="출발역 이름")],
    destination_station: Annotated[Name, Field(description="최종 하차역 이름")],
    walking_seconds: WalkingSeconds = 0,
    line: Annotated[Name | None, Field(description="특정 노선을 이용할 때 지정. 생략하면 자동 선택")] = None,
) -> BoardingAssessment:
    """출발역과 최종 목적지로 직통 열차를 찾아 내부 기준으로 탑승 후보를 결정합니다."""
    station = station_key(station_name)
    destination = station_key(destination_station)
    if station == destination:
        raise ValueError("출발역과 최종 목적지를 서로 다르게 입력하세요.")
    requested_line = parse_line_id(line) if line is not None else None
    checked_at, arrivals = await fetch_arrivals(station)
    line_id, route = resolve_route(station, destination, requested_line, arrivals)
    direction = route.next_station

    buffer_seconds = ROUTE_BUFFERS.get((station, line_id, direction), DEFAULT_BUFFER_SECONDS)
    required_seconds = walking_seconds + buffer_seconds
    platform_ready_at = checked_at + timedelta(seconds=walking_seconds)
    earliest_boarding_at = platform_ready_at + timedelta(seconds=buffer_seconds)
    matching = [
        arrival for arrival in arrivals
        if arrival.line_id == line_id
        and arrival.next_station == direction
        and (
            route.terminals is None
            or (
                arrival.train_type == "일반"
                and arrival.destination is not None
                and station_key(arrival.destination) in route.terminals
            )
        )
    ]
    predictions = sorted(
        (checked_at + timedelta(seconds=arrival.remaining_seconds), index)
        for index, arrival in enumerate(matching)
        if arrival.remaining_seconds is not None
    )

    assessment = BoardingAssessment(
        station_name=station,
        line_id=line_id,
        next_station=direction,
        destination_station=destination,
        checked_at=checked_at,
        walking_seconds=walking_seconds,
        buffer_seconds=buffer_seconds,
        required_seconds=required_seconds,
        platform_ready_at=platform_ready_at,
        earliest_boarding_at=earliest_boarding_at,
        status="no_arrivals",
        summary="",
    )
    route_label = f"{destination}역까지 · {direction} 방면"
    walking_label = f"이동 {walking_seconds}초" if walking_seconds else "승강장 기준 0초"
    lines = [
        f"{station}역 {LINE_NAMES.get(line_id, line_id)} {route_label}",
        f"서버 현재 시각 {checked_at:%Y-%m-%d %H:%M:%S} KST",
        f"{walking_label} + 내부 여유 {buffer_seconds}초 = 필요 {required_seconds}초",
        f"승강장 도착 예상 {platform_ready_at:%Y-%m-%d %H:%M:%S} KST",
        f"탑승 판단 기준 시각 {earliest_boarding_at:%Y-%m-%d %H:%M:%S} KST",
    ]
    if predictions:
        first_at, first_index = predictions[0]
        assessment.latest_predicted_arrival_at = predictions[-1][0]
        assessment.first_arrival = matching[first_index]
        lines.append(f"가장 가까운 예측 {first_at:%H:%M:%S} KST · {assessment.first_arrival.describe()}")
        candidate = next((item for item in predictions if item[0] >= earliest_boarding_at), None)
        if candidate is None:
            assessment.status = "wait"
            assessment.margin_seconds = int((first_at - earliest_boarding_at).total_seconds())
            lines.append(f"조회된 마지막 도착 예측 {assessment.latest_predicted_arrival_at:%H:%M:%S} KST")
            lines.append("기준 시각 이후에 도착하는 열차는 이번 실시간 응답의 조회 범위에 없습니다.")
        else:
            arrival_at, index = candidate
            assessment.status = "boardable" if index == first_index else "later_train"
            assessment.recommended_arrival = matching[index]
            assessment.estimated_boarding_at = arrival_at
            assessment.margin_seconds = int((arrival_at - earliest_boarding_at).total_seconds())
            lines.append(f"탑승 후보 · {assessment.recommended_arrival.describe()}")
            lines.append(f"예상 탑승 시각 {arrival_at:%Y-%m-%d %H:%M:%S} KST")
        lines.append(f"필요 시간 대비 {assessment.margin_seconds:+d}초")
    elif matching:
        assessment.status = "insufficient_data"
        lines.append("판정에 사용할 수 있는 최신 도착 예측이 없습니다.")
        lines.extend(f"- {arrival.describe()}" for arrival in matching)
    else:
        lines.append(f"현재 조회 범위에 {destination}역까지 운행하는 직통 열차가 없습니다.")
    lines.append(f"출처 {DATA_SOURCE} · 프로젝트 기준 {POLICY_VERSION}")
    assessment.summary = "\n".join(lines)
    return assessment


if __name__ == "__main__":
    mcp.run(transport="stdio")
