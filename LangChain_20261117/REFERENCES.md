# 참고 자료와 사용 고지

교안의 설명·도식·업무 데이터·실습코드는 이 수업의 흐름에 맞춰 자체 작성했다. 지정 자료에서는 개념과 API 사용 방식을 확인했으며 원문 이미지·실질적인 예제 코드를 복제하지 않았다. 아래 자료 확인일은 2026-11-16이다.

| 자료 | 확인한 범위와 연결 |
|---|---|
| [테디노트 ChatPromptTemplate](https://github.com/teddylee777/langchain-kr/blob/main/02-Prompt/05-ChatPromptTemplate.ipynb) | 역할·변수 기반 템플릿 원문 확인; 2~3차시 개념 대조 |
| [braincrew-lab RunnableLambda](https://github.com/braincrew-lab/langchain-tutorial/blob/main/06-Modules/12-LangChain-Expression-Language/03-RunnableLambda.ipynb) | dict 입력 래퍼·사용자 정의 함수 연결 원문 확인; 5차시 자체 전처리 설계 |
| [Microsoft 계열 고급 프롬프트 교재](https://github.com/SatheeshKrth/generative-ai/blob/main/05-advanced-prompts/README.md) | 맥락·지시 구체화와 비교 개념 대조. CoT 등 후속 내용은 이번 실습에 편입하지 않음 |
| [LangChain 공식 RunnableSequence 구현](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/runnables/base.py) | 순차 합성·batch·stream 동작 설명 대조 |
| [ChatPromptTemplate 공식 API](https://reference.langchain.com/python/langchain-core/prompts/chat/ChatPromptTemplate) | 메시지와 변수·ChatPromptValue 자료형 확인 |
| [RunnableSequence 공식 API](https://reference.langchain.com/python/langchain-core/runnables/base/RunnableSequence) | invoke/batch/stream·블로킹 컴포넌트 설명 확인 |
| [ChatOpenAI 공식 통합](https://docs.langchain.com/oss/python/integrations/chat/openai) | 공급자 패키지·키·모델 설정 확인 |
| [ChatGroq 공식 통합](https://docs.langchain.com/oss/python/integrations/chat/groq) | 선택 공급자 통합 설정 확인 |
| [Groq 요금 FAQ](https://console.groq.com/docs/billing-faqs), [제한](https://console.groq.com/docs/rate-limits) | 무료 플랜 존재와 요청·토큰 제한 확인. 계정별 한도는 수업 전 재확인 |
| [OpenAI API 가격표](https://developers.openai.com/api/docs/pricing) | 가격 확인 경로. 선택 모델이 미정이므로 특정 단가·예상 총액을 확정하지 않음 |

테디노트·braincrew-lab 자료는 저장소별 이용 조건과 상업적 강의 관련 별도 문구를 확인한 뒤 원문 재사용 여부를 결정해야 한다. 이 교안은 일반 개념과 공식 API에 기반한 자체 설명·코드·도식을 제공한다. LangChain 패키지는 해당 패키지 라이선스에 따라 설치해 사용한다. 원 저장소 전체의 재배포 권한을 부여하는 패키지가 아니다.
