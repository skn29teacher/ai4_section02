# AI Weather

사용자 질문을 모델이 한 번 분석해 JSON으로 반환하고, JSON의 `tools` 값이 `"weather"`이면 Python 날씨 함수를 직접 호출하는 간단한 CLI입니다. LangChain agent/tool chain은 사용하지 않습니다. 날씨 함수는 현재 실제 API 대신 [dummy_weather.json](./dummy_weather.json)을 반환합니다.

## 설치

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 API 키와 모델명을 설정합니다. 기본 provider는 Gemini입니다. Gemini도 `ChatOpenAI` 인터페이스를 사용하지만 Google의 OpenAI-compatible endpoint와 Gemini API key로 호출하므로 OpenAI 유료 API로 전달되지 않습니다. 무료 모델과 quota는 계정 및 지역에 따라 달라질 수 있습니다.

## 실행

```powershell
.\.venv\Scripts\python.exe app.py "내일 서울 비 오면 우산 챙겨야 해?"
```

OpenAI는 명시적으로 선택한 경우에만 호출합니다.

```powershell
.\.venv\Scripts\python.exe app.py --provider openai "내일 서울 비 오면 우산 챙겨야 해?"
```

## 처리 흐름

1. 선택된 모델이 질문 의도를 분석하고 `weather_related`, `tools`, 지역, 날짜, 관심사를 JSON으로 반환합니다.
2. 프로그램이 JSON을 검증합니다. `tools`가 `"weather"`이고 지역이 있으면 `dummy_weather_api()`를 직접 호출합니다.
3. 함수 결과를 `weather_data`에 넣어 JSON으로 출력합니다. 날씨 질문이 아니거나 지역이 없으면 함수를 호출하지 않습니다.

모델 응답 예:

```json
{
  "weather_related": true,
  "tools": "weather",
  "location": "서울",
  "date": "2026-11-19",
  "weather_need": "비와 우산 필요 여부"
}
```

결과 JSON의 `api_calls`는 모델 요청 수이고, `tool_calls`는 직접 실행한 Python 함수 수입니다. `weather_data.is_dummy`가 `true`이면 가상 데이터입니다.

## 비용 제어

- Gemini가 기본 provider이며 실패해도 OpenAI로 자동 전환하지 않습니다.
- intent 응답 길이는 `INTENT_MAX_TOKENS`로 제한합니다.
- 날씨와 무관한 질문은 JSON 분류 뒤 날씨 함수를 호출하지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

테스트는 실제 API 키나 모델 요청 없이 실행됩니다.
