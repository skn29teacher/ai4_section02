# 도구·외부 API 및 데이터 계약

## 1. Agent 입력/출력 경계

LLM으로 전달하는 `TravelContext`는 필요한 여행 조건만 포함한다. API 키, DB 연결 문자열, 계정 토큰, 불필요한 개인정보는 포함하지 않는다.

```json
{
  "request_id": "opaque-id",
  "destination": {
    "name": "서울 광화문",
    "region_id": "seoul-gwanghwamun",
    "timezone": "Asia/Seoul"
  },
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "travelers": 2,
  "budget": {
    "amount": 150000,
    "currency": "KRW",
    "period": "per_night"
  },
  "interests": ["실내 관광", "음식"],
  "mobility": {
    "mode": "public_transit",
    "max_walk_minutes": 20
  }
}
```

“오늘”을 해석할 때는 요청 시각과 `Asia/Seoul` 시간대를 사용한다. 광화문 좌표와 Google Place ID는 Google Maps adapter가 지역명을 해석해 얻는다.

### MVP fixture와 예산 정렬

숙소와 날씨는 고정 시나리오 fixture를 사용하고, `source`에 `accommodation-fixture`/`weather-fixture`, `freshness`에 `simulated`를 기록한다.

| Fixture | 수용 인원 | 가상 가격 (KRW/실/박) | 제안 기본 상한 150,000원 |
|---|---:|---:|---|
| 가상 숙소 A | 2명 | 90,000 | 포함, 1순위 |
| 가상 숙소 B | 2명 | 120,000 | 포함, 2순위 |
| 가상 숙소 C | 2명 | 160,000 | 제외 |

가격은 실제 숙소의 가격이 아니다. 예산 상한은 설정값이며 사용자가 입력한 예산이 있으면 그 값이 우선한다. 인원/지역/날짜 검증 후 체류기간 전체의 숙박 총액 오름차순으로 정렬하고, 동률은 Google Maps 이동 시간으로 해소한다. 날씨는 시뮬레이션 시나리오(예: sunny/rainy)로 제공하며 실제 예보처럼 표시하지 않는다.

## 2. LangChain 도구 계약

도구명과 인자 schema는 서버 코드에서 선언한다. Agent에게 자유 URL 요청, SQL 실행, 임의 코드 실행 도구를 제공하지 않는다.

### `search_accommodations`

**입력**

```json
{
  "destination_id": "seoul-gwanghwamun",
  "check_in": "YYYY-MM-DD",
  "check_out": "YYYY-MM-DD",
  "guests": 2,
  "max_price_per_night": {
    "amount": 150000,
    "currency": "KRW"
  },
  "required_amenities": []
}
```

**출력**

`Accommodation[]`와 함께 숙소 ID, 위치, 수용 인원, 가상 1박 가격, 통화, `source=accommodation-fixture`, `freshness=simulated`를 반환한다. MVP에는 예약 기능이 없으며, 예약 가능 여부를 표현하지 않는다.

### `get_weather_forecast`

**입력:** 위경도 또는 검증된 지역 ID, 현지 날짜 범위, 단위(`metric`/`imperial`).  
**출력:** 날짜/시간대별 가상 기온, 강수확률, 상태, scenario ID, `fetched_at`, `source=weather-fixture`, `freshness=simulated`.

실제 날씨 API는 초기 MVP에서 호출하지 않는다. 추후 adapter로 교체할 때 provider의 예보 범위와 발행 시각을 추가한다.

### `search_places`

**입력:** 지역, 관심사/category, 시간대 또는 실내/실외 조건, 날짜.  
**MVP provider:** Google Maps Platform Places API.  
**출력:** Google Place ID, 좌표, 분류, 운영시간(제공되는 경우), source/attribution, fetched_at.

영업시간이 없거나 최신성이 확인되지 않으면 일정에 고정 시간 방문을 보장하지 않는다.

### `plan_route`

**입력:** 출발/도착 좌표, 이동 수단, 출발 현지 시간.  
**MVP provider:** Google Maps Platform Routes API.  
**출력:** 구간별 거리·소요 시간·교통수단·source/attribution·fetched_at.

경로 API가 실패한 경우 직선거리로 실제 이동 시간을 추정하지 않는다.

## 3. 공통 결과 envelope

```json
{
  "tool_name": "get_weather_forecast",
  "status": "ok",
  "data": [],
  "evidence": [
    {
      "source": "weather-fixture",
      "fetched_at": "ISO-8601 datetime",
      "valid_from": "ISO-8601 datetime",
      "valid_to": "ISO-8601 datetime",
      "freshness": "simulated"
    }
  ],
  "error": null
}
```

실패 예:

```json
{
  "tool_name": "search_accommodations",
  "status": "error",
  "data": null,
  "evidence": [],
  "error": {
    "code": "PROVIDER_TIMEOUT",
    "retryable": true,
    "user_safe_message": "숙소 정보를 지금 조회할 수 없습니다."
  }
}
```

에러에는 원격 응답 본문, API 키, 내부 SQL, stack trace를 사용자나 LLM에 노출하지 않는다.

## 4. 모델 응답 schema

최종 응답은 자유 형식 내부 추론 대신 다음 구조를 만들고, 사용자에게는 읽기 쉬운 한국어로 렌더링한다.

```json
{
  "status": "complete",
  "summary": "추천 요약",
  "itinerary": [
    {
      "date": "YYYY-MM-DD",
      "start_time": "HH:MM",
      "place_id": "place-id",
      "activity": "방문 목적",
      "evidence_ids": ["ev-123"]
    }
  ],
  "accommodation_options": ["accommodation-id"],
  "reasons": ["조건을 만족한 근거"],
  "alternatives": ["우천 대안"],
  "caveats": ["예보 범위 또는 조회 누락"],
  "sources": ["source-id"]
}
```

`status`는 `complete`, `partial`, `needs_clarification`, `unavailable` 중 하나다. 필수 입력이 없으면 일정 생성 대신 `needs_clarification`을 반환한다.

## 5. 호출·재시도·캐시 정책(초기 제안)

| 항목 | 정책 |
|---|---|
| Tool allowlist | 위 4개 도구만 MVP Agent에 등록 |
| Agent loop | 요청당 최대 8개 LLM turn; 별도 전체 deadline 적용 |
| External retry | 일시 오류에 한해 지수 backoff, 최대 1회; 4xx 입력 오류는 재시도하지 않음 |
| Timeout | provider별 connect/read timeout 설정; 전체 deadline을 넘기지 않음 |
| Cache | fixture는 시나리오 ID로 구분; Google Maps 응답 cache는 해당 API 약관에 맞춤 |
| Idempotency | 모든 tool은 read-only이며 같은 입력 반복 호출이 부작용을 만들지 않음 |
| Rate limit | 사용자/세션 및 provider별 제한; 초과 시 명시적인 오류 반환 |

TTL과 시간 제한은 Google Maps Platform의 실제 약관/요금/갱신 주기를 확인하고 배포 환경별 설정으로 확정한다.

## 6. LangChain 통합 메모

- Tool 함수는 명시적인 입력 모델과 반환 모델을 갖고, 실행 전 서버에서 다시 검증한다.
- Agent constructor/API는 구현 시 고정할 LangChain 버전에 맞춘다. 이 문서는 특정 버전의 deprecated constructor에 의존하지 않는다.
- `langchain-core`만으로는 모델 공급자와 외부 Agent 실행 경로가 준비됐다고 간주하지 않는다. 사용할 `langchain` 및 공급자 adapter의 버전을 dependency lock에 고정한다.
- 공급자 SDK 호출은 adapter 뒤에 둔다. 프롬프트에는 tool 결과의 출처/최신성만 넣고 비밀정보를 넣지 않는다.
- `GOOGLE_MAPS_API_KEY`는 secret으로 보관하고 필요한 Maps API로 key restriction을 적용한다. billing/quota 확인 전에는 실호출하지 않는다.
