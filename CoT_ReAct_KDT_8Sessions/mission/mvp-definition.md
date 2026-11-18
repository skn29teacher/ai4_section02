# MVP 정의 및 확정 결정

## 결정 요약

| 항목 | MVP 결정 |
|---|---|
| 대상 지역 | 대한민국 서울 광화문 권역으로 고정 |
| 숙소 정보 | 실제 상호가 아닌 가상 숙소 fixture 사용 |
| 날씨 정보 | 실제 예보가 아닌 시나리오별 가상 날씨 fixture 사용 |
| 지도·장소·경로 | Google Maps Platform을 provider로 사용. 테스트에서는 같은 interface의 mock 사용 |
| 예산 | KRW 가상 예산 사용. 1실·1박 150,000원은 조정 가능한 제안 기본값이며 제품 확인 후 확정 |
| 최적/추천 순위 | 유효한 hard constraint 후보 중 숙박 총액이 낮은 순. 동률일 때 Google Maps 경로 시간이 짧은 후보 우선 |
| 최신성 목표 | 운영 목표는 실시간. 최초 MVP의 숙소/날씨는 가상 자료이며 실시간으로 표시하지 않음 |
| 예약·결제 | MVP에서 제외. 검색·추천만 제공 |

## 예산 fixture 초안

아래는 개발/테스트용으로 제안하는 값이다. 실제 숙소의 가격이나 상호가 아니다.

| Fixture ID | 화면 표시명 | 수용 인원 | 가상 1박 가격 | 150,000원 상한 |
|---|---|---:|---:|---|
| `hotel-fixture-001` | 가상 숙소 A | 2명 | 90,000 KRW | 포함 |
| `hotel-fixture-002` | 가상 숙소 B | 2명 | 120,000 KRW | 포함 |
| `hotel-fixture-003` | 가상 숙소 C | 2명 | 160,000 KRW | 제외; 원하면 초과 대안으로 별도 표시 |

기본 1박 예제의 추천 순서는 A → B다. 투숙 인원·날짜 등 hard constraint를 먼저 적용하고, 숙박 총액이 예산 상한을 넘는 후보를 기본 추천에서 제외한다. 경로 시간은 숙소 가격을 대체하는 점수가 아니라 같은 가격일 때의 tie-breaker다. 150,000원은 제안된 초기 설정값으로, 제품 확인 후 조정 가능하게 구현한다. 예산 값과 fixture는 설정/fixture 파일에서 교체 가능하게 만든다.

## 날씨 fixture 초안

날씨 결과는 test scenario별 고정 데이터로 제공한다. 예: `sunny`(강수확률 10%)와 `rainy`(강수확률 80%) 시나리오. 각 결과의 source는 `weather-fixture`로 표시하고 `freshness=simulated`를 반환한다. 실제 예보처럼 표현하지 않는다.

## 데이터 교체 정책

애플리케이션 서비스는 `AccommodationRepository`와 `WeatherProvider` interface에만 의존한다. 최초 구현은 `MockAccommodationRepository`와 `MockWeatherProvider`를 사용하고, 추후 실데이터 제공자가 확정되면 같은 DTO를 반환하는 adapter로 교체한다. Google Maps 호출도 `PlacesProvider` interface 뒤에 두며, 단위/통합 테스트에서는 mock 응답을 사용한다.

운영 모드에서 실제 Google Maps 요청을 사용하는 경우 Maps 데이터의 출처와 조회 시각을 표시한다. 숙소/날씨 fixture는 실제 데이터 adapter로 전환하기 전까지 계속 `simulated`로 표시한다.

## MVP 성공 기준

- 서울 광화문 이외의 지역을 실데이터 지원 지역처럼 처리하지 않고, 범위 밖 질문에는 지원 범위 안내 또는 확인 질문을 한다.
- 가상 숙소 3개 중 인원 조건에 맞고 예산 상한 내인 A, B만 기본 추천하며 A를 먼저 표시한다.
- 숙소/날씨 가상 결과는 모든 응답과 보고서에서 시뮬레이션임을 표시한다.
- 일정 순서와 경로 정보는 Google Maps provider에서 받은 결과 또는 테스트 mock에 근거한다.
- API 키가 없거나 호출이 실패하면 Google Maps 결과를 만들어내지 않고 경로 정보가 없음을 표시한다.
- 예약 또는 결제 동작이 존재하지 않는다.

## 운영 전 확인할 사항

- Google Maps Platform 프로젝트, 사용 API, billing, key restriction, quota/비용 상한.
- 가상 숙소/날씨 fixture의 정확한 파일 형식과 test scenario 목록.
- 기본 예산 150,000 KRW/실/박의 적정성 및 사용자가 입력한 예산 우선 처리 규칙.
- Google Maps 응답의 저장·표시 조건과 attribution 요구사항.
