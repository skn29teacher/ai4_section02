# AI Weather

질문의 의도를 먼저 분석하고, 날씨 관련 질문일 때만 LangChain ReAct agent가 날씨 tool을 호출하는 간단한 CLI입니다. 모델 호출은 `ChatOpenAI` 어댑터로 통일합니다. OpenAI 선택 시 OpenAI API를, Gemini 선택 시 Google의 OpenAI-compatible endpoint를 호출합니다. 현재 tool은 실제 API 대신 [dummy_weather.json](./dummy_weather.json)을 JSON으로 반환합니다.

## 설치

프로젝트 루트에서 아래 명령을 실행합니다.

```powershell
cd ai_weather
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env`에 Gemini/OpenAI 키와 모델명을 설정합니다. 예제의 Gemini 모델은 현재 Google 문서가 신규 프로젝트용으로 권장하는 `gemini-3.5-flash-lite`입니다. Gemini 선택 시 Gemini API key를 사용해 `https://generativelanguage.googleapis.com/v1beta/openai/`로 요청하므로 OpenAI 유료 API로 전달되지 않습니다. Gemini를 기본 provider로 사용하므로 `AI_PROVIDER=gemini`를 유지하면 됩니다. 무료 사용 가능 모델과 quota는 계정 및 지역에 따라 달라질 수 있으니 사용 전에 [Google Gemini 모델 목록](https://ai.google.dev/gemini-api/docs/models)과 [가격/무료 티어 안내](https://ai.google.dev/gemini-api/docs/pricing)를 확인하세요.

## 실행

```powershell
.\.venv\Scripts\python.exe app.py "내일 서울 비 오면 우산 챙겨야 해?"
```

OpenAI는 유료 provider이므로 자동 fallback하지 않습니다. 직접 선택할 때만 사용합니다.

```powershell
.\.venv\Scripts\python.exe app.py --provider openai "내일 서울 비 오면 우산 챙겨야 해?"
```

실행 결과는 JSON입니다. `weather_data.source`와 `is_dummy`는 가상 fixture 응답임을 표시합니다. 날씨 의도가 없거나 지역이 빠진 질문은 ReAct tool을 호출하지 않습니다.

## 비용 절감 동작

- Gemini를 기본 provider로 사용합니다. OpenAI는 `.env`의 `AI_PROVIDER=openai` 또는 실행 시 `--provider openai`로 명시해야 합니다.
- Gemini가 실패해도 유료 OpenAI로 자동 전환하지 않습니다.
- 두 provider는 동일한 `ChatOpenAI` 인터페이스와 ReAct agent 호출 흐름을 사용하며, Gemini 요청만 Google 호환 endpoint로 보냅니다.
- 날씨 의도 분류는 최대 `INTENT_MAX_TOKENS`, ReAct 답변은 최대 `AGENT_MAX_TOKENS`를 사용합니다.
- `MAX_REACT_STEPS`로 ReAct 반복을 제한하며, 날씨 관련성이 없으면 분류 후 agent를 실행하지 않습니다.
- 결과 JSON에 provider, 모델, API 호출 수, 사용량 metadata를 포함합니다.

## 의도 분석과 tool 동작

의도 분석은 내부적으로 질문을 단계적으로 분류하지만, chain-of-thought는 출력하지 않습니다. `weather_related`, 지역, 날짜, 날씨 관심사를 JSON으로 반환합니다. 날씨 관련 의미(기온, 비/눈, 예보, 바람, 습도, 우산 필요 여부, 야외 활동 적합성 등)가 확인되면 `dummy_weather_api`를 ReAct tool로 호출합니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

테스트는 API key나 실제 모델 호출 없이 실행됩니다.
