from datetime import datetime
from pathlib import Path

import streamlit as st
from openai import APIConnectionError, AuthenticationError, OpenAIError, RateLimitError

from seoul_subway_multi_tool_agent import AgentStage, run_agent
from subway_arrival_cache import SEOUL_TZ, arrival_timing, station_snapshot


STEPS: dict[AgentStage, tuple[int, str]] = {
    "selecting_tool": (1, "에이전트가 조회 도구를 선택하는 중"),
    "fetching_arrivals": (2, "서울시 API에서 도착정보를 조회하는 중"),
    "writing_answer": (3, "조회 결과를 받아 답변을 작성하는 중"),
}
TRACK_STOPS = ("이전 구간", "직전 역", "조회역", "출발")
ARRIVAL_POSITIONS = {"0": 2, "1": 2, "2": 3, "3": 1, "4": 1, "5": 1}
TRAIN_ICON = '<span class="subway-train" aria-hidden="true"></span>'
LOADING_TRACK = f'<div class="subway-loading" aria-hidden="true">{TRAIN_ICON}</div>'


def lookup_station(station: str) -> tuple[dict | None, str, str | None]:
    status = st.status("도착역 입력 확인", expanded=True)
    loading = st.empty()
    loading.html(LOADING_TRACK)
    progress = st.progress(0.0)
    payload = None
    answer = ""
    error = None

    def report(stage: AgentStage, result: dict | None) -> None:
        nonlocal payload
        step, label = STEPS[stage]
        status.update(label=f"{step}/{len(STEPS)} · {label}", expanded=True)
        progress.progress((step - 1) / len(STEPS))
        status.text(label)
        if result is not None and (payload is None or "error" not in result):
            payload = result

    try:
        answer = run_agent(station, on_progress=report)
    except AuthenticationError:
        error = "OpenAI 인증에 실패했습니다. 상위 폴더의 .env에서 OPENAI_API_KEY를 확인해 주세요."
    except RateLimitError:
        error = "OpenAI 요청 한도에 도달했습니다. 잠시 후 다시 조회해 주세요."
    except APIConnectionError:
        error = "OpenAI 연결에 실패했거나 응답 시간이 초과됐습니다."
    except OpenAIError:
        error = "OpenAI가 요청을 처리하지 못했습니다."
    except ValueError as exc:
        error = str(exc)

    loading.empty()
    progress.empty()
    if payload is not None and "error" in payload:
        error = str(payload["error"])
    if error:
        status.update(label="조회 중 오류가 발생했습니다", state="error", expanded=False)
    elif payload is None:
        status.update(label="도착정보를 받지 못했습니다", state="error", expanded=False)
    else:
        status.update(label="도착정보 조회 완료", state="complete", expanded=False)
    return payload, answer, error


def reported_position(row: dict) -> int | None:
    code = str(row.get("arvlCd"))
    message = str(row.get("arvlMsg2") or "")
    if code == "99" and message.startswith("[") and "번째 전역" in message:
        return 1 if message.startswith("[1]") else 0
    return ARRIVAL_POSITIONS.get(code)


def arrival_track(position: int | None, *, animated: bool = False, show_icon: bool = True) -> str:
    track_class = "subway-track subway-track-estimated" if animated else "subway-track"
    markers = [f'<div class="{track_class}" aria-hidden="true">']
    if animated:
        markers.append(TRAIN_ICON)

    for index, stop in enumerate(TRACK_STOPS):
        active = index == position
        css_class = "subway-stop subway-stop-active" if active else "subway-stop"
        icon = TRAIN_ICON if active and show_icon else ""
        markers.append(f'<div class="{css_class}">{icon}<span>{stop}</span></div>')
    markers.append("</div>")
    return "".join(markers)


countdown_track = st.components.v2.component(
    "subway_countdown_track",
    html=(
        arrival_track(None, animated=True)
        + '<p class="subway-countdown" role="timer" aria-label="예상 도착시간"></p>'
    ),
    js=Path(__file__).with_name("subway_countdown.js").read_text(encoding="utf-8"),
    isolate_styles=False,
)


def show_train(row: dict, *, card_index: int) -> None:
    direction = row.get("updnLine") or "방향 미제공"
    line_id = str(row.get("subwayId") or "")
    line = row.get("subwayNm")
    if not line and len(line_id) == 4 and line_id[:3] == "100" and line_id[3] in "123456789":
        line = f"{line_id[3]}호선"
    if not line and line_id:
        line = f"노선 {line_id}"

    with st.container(border=True):
        with st.container(horizontal=True, gap="small"):
            st.badge(direction, color="blue" if direction in ("상행", "내선") else "violet")
            if line:
                st.badge(line, color="gray")
            if str(row.get("lstcarAt")) == "1":
                st.badge("막차", color="orange")
        st.subheader(row.get("trainLineNm") or row.get("bstatnNm") or "행선지 미제공", anchor=False)
        st.text(row.get("arvlMsg2") or "도착 상태 미제공")
        position = reported_position(row)
        timing = arrival_timing(row, datetime.now(SEOUL_TZ))
        if timing and timing[1] > 0:
            eta, remaining = timing
            countdown_track(
                key=f"train_countdown_{card_index}",
                data={"position": position, "eta": eta, "remaining": remaining},
            )
        else:
            st.html(arrival_track(position, show_icon=timing is None))
            if timing is not None:
                st.caption("예상 시간 경과 · 도착 확인 중")
        details = [str(row[field]) for field in ("btrainSttus", "btrainNo", "recptnDt") if row.get(field)]
        if details:
            st.caption(" · ".join(details))


@st.fragment(run_every="5s")
def show_station_arrivals(station: str) -> None:
    snapshot = station_snapshot(station)
    payload = snapshot.payload
    rows = (payload or {}).get("realtimeArrivalList") or []
    station_name = str((rows[0].get("statnNm") if rows else None) or station)
    station_label = station_name if station_name.endswith("역") else f"{station_name}역"
    st.header(f"{station_label} 도착정보", anchor=False)

    if snapshot.fetched_at is not None:
        st.caption(f"마지막 정상 조회 {snapshot.fetched_at:%H:%M:%S} · 자동 조회 간격 {snapshot.interval}초")
    if snapshot.refreshing:
        st.caption("서울시 API 도착정보 갱신 중")
    if snapshot.error:
        if payload is None:
            st.error(snapshot.error)
        else:
            st.warning(f"{snapshot.error} 마지막 정상 조회 결과를 표시합니다.")

    if payload is None:
        if snapshot.refreshing:
            st.info("새 도착정보를 기다리고 있습니다.")
        return
    if not rows:
        st.info("현재 조회된 열차 도착정보가 없습니다.")
        return

    result = payload.get("errorMessage") or payload
    total = result.get("total")
    if isinstance(total, int) and total > len(rows):
        st.caption(f"전체 {total}건 중 {len(rows)}건 표시 · API가 보고한 열차 상태")
    else:
        st.caption(f"열차 {len(rows)}건 · API가 보고한 열차 상태")
    for index in range(0, len(rows), 2):
        for offset, (column, row) in enumerate(zip(st.columns(2), rows[index:index + 2])):
            with column:
                show_train(row, card_index=index + offset)


st.set_page_config(page_title="지하철 실시간 도착", page_icon="🚇", layout="wide")
st.html(Path(__file__).with_name("subway_animation.css"))
st.title("지하철 실시간 도착", anchor=False)
st.caption("서울 열린데이터광장 · 실시간 열차 도착정보")

with st.form("arrival_search", border=True):
    field, action = st.columns([4, 1], vertical_alignment="bottom")
    with field:
        station = st.text_input("도착역", value="독산역", placeholder="예: 독산역", key="station")
    with action:
        submitted = st.form_submit_button("실시간 조회", type="primary", width="stretch")

if submitted:
    st.session_state.pop("subway_selection", None)
    station = station.strip()
    if not station or station == "역":
        st.warning("도착역 이름을 입력해 주세요.")
    else:
        initial = station_snapshot(station, refresh=False)
        answer = ""
        if initial.fetched_at is None and not initial.refreshing and not initial.error:
            payload, answer, error = lookup_station(station)
            if error and (payload is None or "error" not in payload):
                st.warning(f"{error} 열차 정보는 별도로 조회합니다.")
            if payload is None or "error" in payload:
                answer = ""
            else:
                rows = payload.get("realtimeArrivalList") or []
                reported_station = rows[0].get("statnNm") if rows else None
                if reported_station and station_snapshot(reported_station, refresh=False).fetched_at is not None:
                    station = reported_station
        st.session_state["subway_selection"] = (station, answer)

if "subway_selection" in st.session_state:
    station, answer = st.session_state["subway_selection"]
    show_station_arrivals(station)
    if answer:
        with st.expander("첫 조회의 에이전트 답변", icon=":material/smart_toy:"):
            st.text(answer)
