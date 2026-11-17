# CoT·ReAct 실습 · 2026-11-18

Python 3.11 이상. 압축을 풀고 main.py가 있는 폴더에서 실행합니다.

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
```

PowerShell은 `.\.venv\Scripts\python.exe`를 직접 실행할 수 있습니다. macOS/Linux는 `python3 -m venv .venv`와 `source .venv/bin/activate`를 사용합니다.

| 차시 | 내용 | 실행 |
| --- | --- | --- |
| 1 | GSM8K 원본과 입력 구분 | python main.py --session 1 |
| 2 | 프롬프트 3종 구성 | python main.py --session 2 |
| 3 | 풀이 응답 생성 | python main.py --session 3 --mock |
| 4 | 실제 로컬 계산 | python main.py --session 4 |
| 5 | ReAct 행동·관찰 | python main.py --session 5 --mock |
| 6 | 동일 문제 3방식 비교 | python main.py --session 6 --count 1 --mock |
| 7 | 오류와 반복 중단 | python main.py --session 7 |
| 8 | 저장 결과 재출력 | python main.py --session 8 --input results/실제파일.json |

실제 API는 --mock 대신 `--live --provider groq` 또는 `gemini`, `openai`를 선택합니다. .env에 선택한 공급자의 API_KEY·MODEL만 설정하세요. 기본 실행은 모의 대본이며 OpenAI 실제 호출은 유료입니다. Groq·Gemini는 계정/모델의 무료 사용 범위를 확인하세요.

결과는 results/의 HTML·JSON입니다. 본 교안은 `CoT_ReAct_8Sessions.html`·PDF와 lessons/의 차시별 문서입니다. 제공 데이터는 D04 GSM8K main/test 원본 0~5번 행이며 data/provenance.json에서 위치를 확인할 수 있습니다.
