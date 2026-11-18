# AI Weather

Gemini(또는 설정된 intent provider)가 질문을 JSON으로 분류하고, JSON의 `tools` 값이 `"weather"`이면 Python 날씨 함수를 직접 호출합니다. 함수 결과와 원 질문을 OpenAI에 전달해 최종 답변을 생성합니다. LangChain agent/tool chain은 사용하지 않으며, 날씨 함수는 현재 실제 API 대신 [dummy_weather.json](./dummy_weather.json)을 반환합니다.

## 설치

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 Gemini와 OpenAI 키 및 모델명을 모두 설정해야 합니다. 기본 intent provider는 Gemini입니다. Gemini도 `ChatOpenAI` 인터페이스를 사용하지만 Google의 OpenAI-compatible endpoint와 Gemini API key로 호출됩니다. 최종 답변은 항상 OpenAI를 호출하므로 각 정상 요청마다 OpenAI 사용 비용이 발생합니다. Gemini 무료 사용 가능 모델과 quota는 계정 및 지역에 따라 달라질 수 있습니다.

## 실행

```powershell
.\.venv\Scripts\python.exe app.py "내일 서울 비 오면 우산 챙겨야 해?"
```

`--provider openai`를 지정하면 의도 분석과 최종 답변 모두 OpenAI를 호출합니다.

```powershell
.\.venv\Scripts\python.exe app.py --provider openai "내일 서울 비 오면 우산 챙겨야 해?"
```

## 처리 흐름

1. 선택된 intent 모델이 질문을 분석하고 `weather_related`, `tools`, 지역, 날짜, 관심사를 JSON으로 반환합니다.
2. 프로그램이 JSON을 검증합니다. `tools`가 `"weather"`이고 지역이 있으면 `dummy_weather_api()`를 직접 호출합니다.
3. 원 질문, intent JSON, 함수 결과(있으면)를 OpenAI에 전달해 최종 답변을 생성합니다. 비날씨 질문도 OpenAI가 답하고, 지역이 빠진 날씨 질문은 OpenAI가 지역을 묻습니다.
4. 최종 답변과 함수 결과를 JSON으로 출력합니다.

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

결과 JSON의 `provider`/`model`은 intent 모델, `final_provider`/`final_model`은 OpenAI 최종 답변 모델입니다. `api_calls`는 두 단계의 모델 요청 수이고, `tool_calls`는 직접 실행한 Python 함수 수입니다. `weather_data.is_dummy`가 `true`이면 가상 데이터입니다.

## 비용 제어

- Gemini가 기본 intent provider입니다. intent 분석 실패를 OpenAI로 재시도하지는 않지만, 정상 분류된 질문에는 최종 답변용 OpenAI 호출이 항상 발생합니다.
- intent 응답 길이는 `INTENT_MAX_TOKENS`로 제한합니다.
- OpenAI 최종 답변 길이는 `FINAL_MAX_TOKENS`로 제한합니다.
- `gpt-5` 계열 모델은 reasoning token이 답변 예산을 소진하지 않도록 `reasoning_effort=minimal`로 호출합니다.
- 날씨와 무관한 질문은 JSON 분류 뒤 날씨 함수를 호출하지 않습니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

테스트는 실제 API 키나 모델 요청 없이 실행됩니다.
