# LangChain 프롬프트·LCEL 프로젝트 교안

**2026-11-17 · 단일 에이전트 추론 및 AI 오케스트레이션 · U2-01**

고객 문의와 회사 정책을 바탕으로 상담원 검토용 답변 초안을 만드는 프로젝트다. Python dict·함수·파일 처리의 기초를 재사용하고, 메시지·프롬프트·체인이라는 새 연결 방식을 익힌다. 실제 학습자의 숙달 여부는 관찰하지 않았으므로 필요한 개념을 본문에서 다시 설명한다.

`LangChain_8Sessions_Visual.html`은 이미지·표·코드를 한곳에서 읽는 통합 교안이다. 왼쪽 차시 이동, 코드 복사/접기, 프롬프트 미리보기를 제공한다. 인터넷 연결 없이 열 수 있으며 HTML 미리보기는 모델을 호출하지 않는다. `course/01_README.md`부터 `08_README.md`는 차시별 이론서다. PDF는 같은 내용을 출력용으로 제공한다.

## 하루 수업 구성

1차시 50분, 총 400분은 공식 교시 길이가 제시되지 않아 적용한 설계 가정이다. 휴식은 별도다. API 대기와 설치·복구를 실습 시간에 포함한다.

| 차시 | 핵심 이론 | 실습 결과 |
|---|---|---|
| 1 | 모델·API·프레임워크·가상환경 | 패키지 설치, API 없이 템플릿 첫 실행 |
| 2 | 메시지 역할·변수·입력 계약 | 메시지 구성과 누락 오류 확인 |
| 3 | Role·Instruction·Context | 같은 맥락을 받는 세 프롬프트 설계 |
| 4 | Runnable·순차 합성·출력 파서 | Prompt→Model→Parser LCEL |
| 5 | 검증·정규화·책임 분리 | RunnableLambda 전처리 체인 |
| 6 | invoke·batch·stream·동시성 | 일괄·스트리밍, Groq 선택 연결 |
| 7 | 조건 통제·관측값·품질 해석 | 3개 문의×3개 버전 비교 기록 |
| 8 | 파일 계약·오류 격리·통합 | CSV 입력→초안/오류 JSONL 저장 |

## 시작 환경

Python 3.11 이상을 가정하며 제작 실행환경은 Python 3.12다. 프로젝트 루트에서 다음을 실행한다. 설치 버전은 제작 시 로컬 검증한 조합이다. 다른 OS와 원격 모델까지 모두 통합 검증한 것은 아니다.

```bash
python -m venv .venv
```

| 터미널 | 가상환경 활성화 |
|---|---|
| Windows CMD | `.venv\Scripts\activate.bat` |
| PowerShell | `.\.venv\Scripts\Activate.ps1` |
| Linux/macOS | `source .venv/bin/activate` |

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m sessions.s01
```

PowerShell 활성화가 차단되면 `.\.venv\Scripts\python.exe`로 Python 명령을 직접 실행할 수 있다. 설치·실행 시 이 폴더를 시작 위치로 유지한다.

| 패키지 | 검증 버전 | 역할 |
|---|---|---|
| langchain-core | 1.8.1 | 템플릿·메시지·Runnable·파서 |
| langchain-openai | 1.8.0 | OpenAI 통합 |
| python-dotenv | 1.2.4 | .env 로드 |
| langchain-groq | 1.2.0 | 선택 Groq 통합 |

`requirements-lock.txt`는 제작환경의 전체 버전 기록이다. 기본 설치는 `requirements.txt`, Groq 선택 설치는 `requirements-groq.txt`, 개발용 테스트는 `requirements-dev.txt`를 사용한다. Windows의 다른 Python 버전에서는 휠 지원 여부가 달라질 수 있다.

## 실제 API 설정과 호출량

`.env.example`을 `.env`로 복사하고 제공받은 OpenAI API 키와 계정에서 허용된 모델 ID를 입력한다. 실제 비밀키는 교안이나 코드에 포함하지 않는다. 모델·temperature·출력 토큰 한도 지원은 선택한 모델에서 확인한다. 기본은 OpenAI이며 Groq는 6차시 이후 선택 경로다.

| 차시의 대표 실제 명령 | 최대 호출 수 |
|---|---:|
| s01~s03 | 0 |
| s04 | 1 |
| s05 | 1 |
| s06 기본 batch | 3 |
| s06 --stream | 1 |
| s07 기본 비교 | 9 |
| s08 기본 통합 | 3 |
| 합계: 위 명령을 각각 한 번 실행 | 18 |

재실행·s04 수동 모드·반복 비교·추가 문의는 호출량을 늘린다. 출력 한도는 요청당 500토큰 설정이며 문자 수 제한과 다르다. 입력 토큰은 실제 렌더링한 정책·문의·메시지를 기준으로 달라진다. 단가와 모델이 미정이므로 비용 총액을 만들지 않는다. 키를 제공받았다는 사실만으로 모든 모델이 허용되는 것도 아니다.

## API 없이 구조 실습하기

```bash
python -m sessions.s04 --mock
python -m sessions.s05 --mock
python -m sessions.s06 --mock
python -m sessions.s06 --mock --stream
python -m sessions.s07 --mock
python -m sessions.s08 --mock
```

모의 모드는 실제 LangChain 템플릿·체인을 실행하고 모델만 고정 응답으로 대체한다. 출력 앞에 `[모의 응답]`을 붙이며 모든 문의에 같은 내용을 반환한다. 실제 품질·속도·토큰 비용 검증으로 사용하지 않는다.

## 소프트웨어 검증

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

입력·메시지·체인·batch/stream·CSV·비교 기록의 코드 테스트다. 학생의 시험·채점 활동이 아니다. 제작 시 19개 테스트와 전체 차시의 모의 CLI 실행을 확인했다. 실제 OpenAI/Groq API는 호출하지 않았다.

## 파일 사용과 다음 수업

`outputs`의 JSONL 파일은 VS Code에서 열 수 있다. 한 줄이 결과 한 건이다. 7차시 비교 파일은 같은 공급자로 재실행하면 덮어쓰고, 8차시 통합 결과는 실행시각별 새 폴더에 저장한다. 실습 데이터와 정책은 모두 합성이다.

11월 18일 CoT·ReAct, 19일 Structured Output, 20일 Prompt Injection, 23일부터 Tool Calling으로 이어진다. 이번 수업의 `inquiry` 입력 계약과 비교 기록을 다음 수업에서 재사용할 수 있다. 11월 17일 교안에 후속 주제의 구현을 미리 넣지는 않았다.
