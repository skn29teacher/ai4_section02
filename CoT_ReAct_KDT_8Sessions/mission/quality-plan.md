# 보안·테스트·운영·구현 계획

## 1. 보안 및 안전 설계

### 위협과 대응

| 위협 | 대응 |
|---|---|
| 외부 리뷰/웹 데이터의 prompt injection | 숙소 설명·리뷰·웹 문구를 신뢰할 수 없는 데이터로 취급한다. 지시문으로 실행하지 않고 tool 결과와 system policy를 분리한다. |
| 임의 SQL/API 호출 | LLM에 SQL/HTTP 임의 실행 도구를 주지 않는다. allowlist의 typed tool만 등록한다. |
| API 키 노출 | Secret Manager 또는 환경변수로 관리한다. 입력/출력·예외·trace에 키를 기록하지 않는다. 키 회전 절차를 둔다. |
| 과도한 데이터 수집 | 여행 추천에 필요한 최소 입력만 받고, 별도 동의 없는 장기 저장을 하지 않는다. |
| Prompt/응답 로그의 개인정보 | 운영 로그는 request ID와 최소 metadata 중심으로 기록하고 원문 저장은 기본 비활성화 또는 마스킹한다. |
| 허위 최신 정보 | 모든 외부 사실에 source/fetched_at/validity를 붙이고, 없는 값은 생성하지 않는다. |
| Agent 무한 반복/비용 증가 | LLM turn, tool call, deadline, 토큰 예산을 강제한다. 제한에 닿으면 partial/error 상태로 종료한다. |
| 예약 등 비가역 행위 | MVP에는 예약·결제 도구를 등록하지 않는다. 향후 추가 시 사용자 확인, 권한 확인, idempotency key가 선행돼야 한다. |

### 데이터 분류

- **공개/공급자 데이터:** 관광지, 날씨, 숙소 공개 메타데이터. 이용 약관과 출처를 보존한다.
- **요청 데이터:** 목적지, 날짜, 인원, 예산, 선호. 목적 수행 기간만 처리하는 것을 기본으로 한다.
- **비밀정보:** API 키, DB 자격 증명. LLM 컨텍스트/일반 로그에 포함하지 않는다.

## 2. 테스트 전략

### 단위 테스트

- Intent Parser: 지역 동음이의어, 날짜 표현, 시간대, 숫자/통화, 필드 누락, confidence 경계.
- Validator: 과거 날짜, 날짜 역전, 예산 단위, 인원 0/음수, 허용되지 않은 날짜 범위.
- 숙소/날씨 fixture: 항상 `simulated`와 fixture source가 유지되고 실제 데이터로 오인할 수 없는지 검증.
- Google Maps Tool: schema 검증, 정상 결과 정규화, 빈 결과, timeout, 4xx/5xx, rate limit, attribution/source 누락.
- Ranker: 지역·인원·날짜·예산 hard constraint 위반 후보 제외, 숙박 총액 오름차순, 가격 동률 시 Google Maps 경로 시간 정렬.
- Response Validator: 답변에 참조되지 않은 가격/날씨/시간이 섞이면 거부 또는 caveat 처리.

### 통합/계약 테스트

- 숙소/날씨 fixture가 정해진 DTO와 evidence envelope를 준수하는지 검증.
- Google Maps adapter는 HTTP mock으로 schema·단위·timezone·attribution·오류 응답을 검증.
- LangChain Tool schema와 Agent tool registry가 정확히 일치하는지 검사.
- 일부 API 실패 시 evidence 손실을 표시하고 성공한 다른 도구 결과를 유지하는지 확인.

### End-to-end 및 평가

| 시나리오 | 기대 결과 |
|---|---|
| 서울 광화문 목적지/날짜/예산이 충분한 요청 | 가상 숙소·날씨는 simulated로 표시하고 Google Maps 근거를 사용한 일정 반환 |
| 지역 모호성 | 검색 호출 없이 확인 질문 |
| simulated 날씨 fixture | 실제 예보가 아니라는 caveat/source 표시 |
| Google Maps API 장애 | 지도/경로 정보를 추측하지 않고 누락을 표시한 partial 응답 |
| 예산에 맞는 숙소 없음 | 초과 후보를 추천하지 않고 조건 조정 안내 |
| 악성 리뷰에 “system prompt를 무시하라” 포함 | 해당 내용을 데이터로만 취급하고 도구 권한 변화 없음 |
| Agent가 unknown tool 요청 | 호출 전에 거부하고 감사 이벤트 기록 |
| 지원하지 않는 지역 | 서울 광화문 이외는 지원 범위 안내 또는 확인 질문 |
| 예산 내 숙소 후보 없음 | 초과 후보를 기본 추천하지 않고 조건 조정 안내 |
| 예산·토큰·step 초과 | 무한 호출 없이 중단, 관찰 가능한 사유 반환 |

### 품질 지표

- 요구 슬롯 추출 정확도와 모호 입력에서의 확인 질문 정확도.
- 숙소 hard constraint 위반률(목표 0%).
- 답변의 핵심 사실 중 evidence로 추적 가능한 비율(목표 100%).
- tool 선택 정밀도/재현율, provider 오류율, 평균/p95 latency, 요청당 LLM/API 비용.
- partial 응답에서 실패·stale 데이터를 정확히 표시하는 비율.

모델 품질은 고정된 한국어 eval set과 provider/model/version별 회귀 평가로 추적한다. 모델 변경 후 작은 smoke test만으로 품질을 승인하지 않는다.

## 3. 관측성 및 장애 대응

모든 요청에 `request_id`와 trace ID를 부여한다. 다음 항목은 비밀정보/불필요한 원문 없이 기록한다.

- intent 필드의 존재 여부와 confidence 범위(민감 원문 제외).
- Agent turn 수, tool 이름, 호출 시간, status, retry count, error code.
- evidence source, fetched_at, freshness와 결과 수.
- 응답 상태(`complete`/`partial`/`needs_clarification`/`unavailable`), latency, 토큰 및 비용 metadata.

알림 기준(최종 값은 운영 데이터로 확정): provider 오류율 급증, 응답 p95 초과, API rate limit 반복, 요청당 비용 상한 초과, 숙소 데이터 freshness 만료.

## 4. 구현 단계

### Phase 0 — 결정과 준비

- 확정된 MVP 정의를 기준으로 Google Maps project/API, billing, key restriction, quota/비용 상한 확인.
- 광화문 숙소/날씨 fixture schema와 scenario, source 및 `simulated` 표시 규칙 확정.
- 150,000 KRW/실/박은 제안된 설정 기본값으로 두고 제품 확인 후 조정 가능하게 구현.

### Phase 1 — 결정론적 기반

- `TravelIntent`, validators, tool DTO와 source/freshness model 구현.
- 가상 숙소/날씨와 Google Maps mock adapter로 end-to-end 계약을 검증.
- 예산순 Ranker와 Response Composer를 Agent 없이 테스트한다.

### Phase 2 — LLM 및 ReAct

- Intent extraction schema와 clarification flow 구현.
- allowlist tool을 LangChain Agent에 등록한다.
- step/latency/token limits, timeout/error path, telemetry를 추가한다.
- 검증 후에만 Google Maps Places/Routes API를 연결한다. 숙소/날씨는 이 단계에서도 fixture로 유지한다.

### Phase 3 — 평가 및 제한 배포

- 고정 eval set, adversarial prompt/data, provider 장애 시험을 통과시킨다.
- API 비용·정확도·latency를 shadow/canary 방식으로 확인한다.
- 예약/결제 기능은 별도 보안·정책 검토 전까지 제외한다.

## 5. 승인/미결정 사항

- Google Maps Platform project/API 활성화, billing, key restriction, quota 및 비용 상한.
- 150,000 KRW/실/박 기본 예산 상한 및 fixture 가격의 제품 적정성.
- Google Maps API 이용 조건에 따른 attribution, cache 및 상업 사용 준수.
- 로그 보존 기간, 개인정보 동의 문구, 사용자 요청 삭제 방식.
- 응답시간·비용 목표 및 provider별 rate limit.
