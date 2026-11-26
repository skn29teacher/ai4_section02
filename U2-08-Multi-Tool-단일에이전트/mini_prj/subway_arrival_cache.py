import json
import os
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from time import monotonic

import httpx
from dotenv import load_dotenv

from seoul_subway_api_test import get_arrivals, normalize_station_name


SEOUL_TZ = timezone(timedelta(hours=9))
DEFAULT_REFRESH = 60
NEAR_ARRIVAL_REFRESH = 30
MAX_SNAPSHOT_AGE = 120
MAX_CACHED_STATIONS = 128


def arrival_timing(row: dict, now: datetime) -> tuple[int, float] | None:
    reported = row.get("recptnDt")
    if str(row.get("arvlCd")) in {"0", "1", "2"} or not isinstance(reported, str) or len(reported) < 19:
        return None
    try:
        eta = int(str(row.get("barvlDt")))
        reported_at = datetime.fromisoformat(reported)
    except ValueError:
        return None

    if reported_at.tzinfo is None:
        reported_at = reported_at.replace(tzinfo=SEOUL_TZ)
    elapsed = (now - reported_at).total_seconds()
    if eta <= 0 or elapsed < 0:
        return None
    return eta, max(0.0, eta - elapsed)


def refresh_interval(payload: dict | None, now: datetime) -> int:
    for row in (payload or {}).get("realtimeArrivalList") or []:
        if str(row.get("arvlCd")) == "3":
            return NEAR_ARRIVAL_REFRESH
        timing = arrival_timing(row, now)
        if timing is not None and timing[1] == 0:
            return NEAR_ARRIVAL_REFRESH
    return DEFAULT_REFRESH


@dataclass(frozen=True)
class StationSnapshot:
    payload: dict | None = None
    fetched_at: datetime | None = None
    refreshing: bool = False
    error: str | None = None
    interval: int = DEFAULT_REFRESH


@dataclass
class _StationEntry:
    payload: dict | None = None
    fetched_at: datetime | None = None
    fetched_tick: float | None = None
    last_attempt: float | None = None
    pending: Future[StationSnapshot] | None = None
    error: str | None = None


_entries: OrderedDict[str, _StationEntry] = OrderedDict()
_lock = Lock()
_workers = ThreadPoolExecutor(max_workers=4, thread_name_prefix="subway-refresh")


def _snapshot(entry: _StationEntry, now: float, interval: int) -> StationSnapshot:
    payload = entry.payload
    if entry.fetched_tick is not None and now - entry.fetched_tick >= MAX_SNAPSHOT_AGE:
        payload = None
    return StationSnapshot(payload, entry.fetched_at, entry.pending is not None, entry.error, interval)


def _refresh_station(station: str, entry: _StationEntry) -> StationSnapshot:
    payload = None
    error = None
    try:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
        api_key = os.getenv("SEOUL_SUBWAY_API_KEY", "").strip()
        if not api_key:
            raise ValueError(".env에 SEOUL_SUBWAY_API_KEY를 설정해 주세요.")
        response = get_arrivals(station, api_key)
        rows = response.get("realtimeArrivalList")
        if rows is not None and (not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows)):
            raise ValueError("서울시 지하철 API의 열차 목록 형식이 올바르지 않습니다.")
        payload = response
    except httpx.HTTPStatusError as exc:
        error = f"서울시 지하철 API 요청 실패 (HTTP {exc.response.status_code})"
    except httpx.RequestError:
        error = "서울시 지하철 API 서버에 연결하지 못했습니다."
    except (json.JSONDecodeError, UnicodeDecodeError):
        error = "서울시 지하철 API 응답을 JSON으로 읽을 수 없습니다."
    except ValueError as exc:
        error = str(exc)
    except Exception:
        error = "서울시 지하철 도착정보를 갱신하지 못했습니다."

    with _lock:
        tick = monotonic()
        now = datetime.now(SEOUL_TZ)
        entry.last_attempt = tick
        entry.pending = None
        entry.error = error
        if payload is not None:
            entry.payload = payload
            entry.fetched_at = now
            entry.fetched_tick = tick
        interval = DEFAULT_REFRESH if error else refresh_interval(payload, now)
        return _snapshot(entry, tick, interval)


def _request_station(station_name: str, *, refresh: bool) -> tuple[StationSnapshot, Future[StationSnapshot] | None]:
    station = normalize_station_name(station_name)
    with _lock:
        entry = _entries.get(station)
        if entry is None:
            if not refresh:
                return StationSnapshot(), None
            if len(_entries) >= MAX_CACHED_STATIONS:
                idle_station = next((name for name, cached in _entries.items() if cached.pending is None), None)
                if idle_station is None:
                    return StationSnapshot(error="조회 요청이 많습니다. 잠시 후 다시 확인합니다."), None
                del _entries[idle_station]
            entry = _entries[station] = _StationEntry()
        _entries.move_to_end(station)

        tick = monotonic()
        interval = DEFAULT_REFRESH if entry.error else refresh_interval(entry.payload, datetime.now(SEOUL_TZ))
        due = entry.last_attempt is None or tick - entry.last_attempt >= interval
        if refresh and due and entry.pending is None:
            entry.pending = _workers.submit(_refresh_station, station, entry)
        return _snapshot(entry, tick, interval), entry.pending


def station_snapshot(station_name: str, *, refresh: bool = True) -> StationSnapshot:
    snapshot, _ = _request_station(station_name, refresh=refresh)
    return snapshot


def cached_arrivals(station_name: str) -> dict:
    snapshot, pending = _request_station(station_name, refresh=True)
    if snapshot.payload is None and pending is not None:
        snapshot = pending.result()
    if snapshot.payload is None:
        raise ValueError(snapshot.error or "서울시 지하철 도착정보를 받지 못했습니다.")
    return deepcopy(snapshot.payload)
