# 서울 지하철 실시간 도착 MCP

이 프로젝트는 서울 열린데이터광장의 역별 실시간 도착정보를 조회하고, 프로젝트의 내부 여유시간을 적용해 탑승 후보를 계산합니다. 서울시 API가 제공하는 정보에는 열차별 예상 도착 초, 방면, 종착역, 정보 생성 시각이 포함됩니다. [서울시 실시간 도착정보 API 명세](https://data.seoul.go.kr/dataList/openApiView.do?infId=OA-12764&srvType=A)

## 1. 설치와 키 설정

```powershell
Set-Location 'C:\AIO_P4_S2\U2-07_MCP\prj'
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install 'mcp[cli]==2.3.0' 'httpx>=0.28,<1' 'openai>=2,<3' 'pydantic>=2,<3' 'python-dotenv>=1,<2'
if (-not (Test-Path -LiteralPath '.\.env')) { Copy-Item -LiteralPath '.\.env.example' -Destination '.\.env' }
```

`.env`에 `SEOUL_REAL_SUBWAY_API_KEY`를 설정합니다. 커스텀 에이전트를 실행하려면 `OPENAI_API_KEY`도 설정합니다. 기본 모델은 `gpt-4o`이며 `OPENAI_MODEL`로 변경할 수 있습니다.

## 2. Inspector에서 서버 실행

```powershell
mcp dev commercial_mcp_server.py
```

Inspector에서 **Connect**를 누른 뒤 다음 도구와 리소스를 확인합니다. 기존 MCP 설정에서 사용하던 서버 파일 경로를 그대로 사용할 수 있습니다.

- `get_subway_arrivals`는 `station_name`으로 해당 역의 열차별 실시간 도착정보를 조회합니다.
- `get_server_time`은 탑승 판정에 사용하는 MCP 서버의 현재 한국 표준시를 반환합니다.
- `assess_subway_boarding`의 필수 입력은 출발역 `station_name`과 최종 목적지 `destination_station`입니다. 독산역에서 수원역까지 가려면 `독산`과 `수원`을 입력합니다. `line`을 생략하면 노선을 자동으로 선택합니다. 승강장까지 5분 걸린다면 `walking_seconds`에 `300`을 입력합니다. 생략하면 승강장에 있는 상황으로 계산합니다.
- `policy://subway-boarding`은 서울시 API에 없는 프로젝트 내부 기준표입니다.

STDIO 호스트에 직접 등록할 때는 다음과 같이 실행합니다.

```toml
[mcp_servers.seoul_subway]
command = "C:\\AIO_P4_S2\\U2-07_MCP\\prj\\.venv\\Scripts\\python.exe"
args = ["C:\\AIO_P4_S2\\U2-07_MCP\\prj\\commercial_mcp_server.py"]
cwd = "C:\\AIO_P4_S2\\U2-07_MCP\\prj"
startup_timeout_sec = 20
tool_timeout_sec = 60

[mcp_servers.seoul_subway.env]
PYTHONUTF8 = "1"
```

## 3. 커스텀 에이전트 실행

```powershell
.\.venv\Scripts\python.exe -X utf8 .\custom_agent.py
.\.venv\Scripts\python.exe -X utf8 .\custom_agent.py "독산역에서 수원역까지 가려면 몇 시에 탈 수 있어?"
```

OpenAI 모델은 질문에서 도구 인자를 추출합니다. 지하철 API 호출과 계산은 MCP 서버에서 처리하며, 에이전트는 서버가 반환한 요약을 출력합니다.

프로젝트 실습 기준에서 기본 여유는 45초입니다. 역삼역 2호선 선릉 방면의 여유는 60초입니다. 서버의 현재 KST에 이동 시간과 내부 여유를 더해 탑승 판단 기준 시각을 구합니다. 각 열차 예측의 생성 시각을 기준으로 남은 초를 계산해, 해당 시각 이후에 도착하는 첫 열차를 선택합니다. 조회 범위가 판단 기준 시각보다 짧으면 응답에서 확인되는 마지막 도착 예측을 표시합니다. 도착 예측이 120초보다 오래됐거나 조회가 실패하면 해당 상태를 표시합니다.

등록된 직통 구간은 독산역에서 수원역까지의 1호선 일반열차와 역삼역에서 선릉역까지의 2호선입니다. 실시간 도착정보에서 목적지가 바로 다음 역으로 확인되는 구간도 조회할 수 있습니다. 선택한 열차의 유효한 도착 예측이 있으면 KST 예상 탑승 시각을 표시합니다.

서울시 API의 JSON 응답을 직접 확인하려면 다음을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 .\check_public_data_api.py
```
