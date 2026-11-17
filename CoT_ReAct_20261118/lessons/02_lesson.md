# 2차시 · CoT의 원리와 짧은 풀이 프롬프트 작성

## 설명이 길다고 계산이 정확해지는 것은 아니다

CoT는 중간 계산이나 문제 분해의 예시를 프롬프트에 넣어 다단계 문제 해결을 유도하는 접근이다. few-shot CoT에서는 비슷한 문제의 계산 근거와 답을 함께 보여준다. zero-shot 방식에서는 예시 없이 풀이 구조를 요청한다. 오늘은 이 차이를 “정답만”, “핵심 계산과 짧은 검증”, “교사 작성 계산 예시 포함”으로 구현한다.

모델이 출력한 풀이는 사용자를 위한 설명이다. 설명이 실제 내부 계산을 충실하게 반영한다고 보장할 수 없고, 현대 추론 모델은 별도 지시 없이도 내부 추론을 사용할 수 있다. 그러므로 비공개 사고 전문 대신 계산식·단위·짧은 검증 요약·최종 숫자를 요청하고, 맞는지는 별도로 확인한다. 어떤 모델에서든 CoT가 반드시 더 좋아진다는 결론도 내리지 않는다.

| 전략 값 | 요청할 출력 | 비교할 점 |
| --- | --- | --- |
| direct | 마지막 답 한 줄 | 간결하지만 틀린 이유를 화면만으로 알기 어려움 |
| summary | 계산식 1~3개와 검증 요약 | 수량 관계를 설명하지만 계산 정확성을 보장하지 않음 |
| fewshot | 다른 예시의 형식을 참고한 짧은 풀이 | 예시가 길이·문체·풀이 구조를 동시에 바꿀 수 있음 |

## 작성 파일: 프롬프트와 메시지 변환

```python
def build_prompt(strategy):
    common = ('수학 문장제에 답하세요. 비공개 내부 사고를 요구하지 않습니다. '
              '사용자에게 필요한 계산식과 짧은 검증 요약만 보여주세요. '
              '최종 숫자는 마지막 줄에 #### 숫자 형식으로 쓰세요.')
    instructions = {
        'direct': '풀이 없이 마지막 답 한 줄만 쓰세요.',
        'summary': '문제의 수량과 단위를 확인하고 핵심 계산식 1~3개 및 한국어 검증 요약을 쓰세요.',
        'fewshot': ('아래 예시처럼 짧은 계산 근거와 답을 쓰세요. 예시는 교사 작성입니다.\n'
                    '예: 14개 중 4개를 쓰고 나머지를 3원씩 팔았다.\n'
                    '계산: (14-4)*3=30\n검증: 남은 10개에 개당 가격을 곱했다.\n#### 30'),
    }
    if strategy not in instructions:
        raise ValueError('알 수 없는 프롬프트 전략')
    return ChatPromptTemplate.from_messages([
        ('system', common + '\n' + instructions[strategy]), ('user', '{question}')
    ])
```

공통 지시문은 system 역할에, 원본 문제는 user 역할의 `{question}`에 둔다. `strategy`는 프롬프트를 고르는 Python 값이며 모델이 결정하지 않는다. `instructions` dict에서 선택한 문자열만 system에 붙인다. few-shot 예시는 교사가 별도로 만든 문제이므로 이번 비교 문제의 정답을 미리 넣지 않는다.

`ChatPromptTemplate.from_messages`는 아직 모델을 호출하지 않는다. `.invoke({"question": ...})`도 이 객체에서는 변수 채우기만 한다. 같은 이름의 invoke라도 호출 대상이 프롬프트인지 전체 체인인지에 따라 실행 범위가 다르다.

```python
def to_messages(prompt_value):
    return [{'role': 'assistant' if m.type == 'ai' else 'user' if m.type == 'human' else m.type,
             'content': m.content} for m in prompt_value.to_messages()]
```

템플릿 결과의 메시지는 LangChain 객체다. HTTP API에 보내기 위해 `role`·`content` dict의 목록으로 바꾼다. `human`은 `user`, `ai`는 `assistant`로 바꾸며 `system`은 그대로 둔다. 반환형은 JSON으로 직렬화 가능한 `list[dict]`다. 모든 role을 user로 바꾸면 system 지시와 대화 이력을 잃는다.

## 모델 없이 렌더링 결과 비교

```bash
python main.py --session 2
```

화면에는 각 전략의 system·user 메시지가 실제 줄바꿈으로 표시된다. 같은 원본 문제가 세 번 나타나고 `answer`의 정답 설명 전체는 프롬프트에 없다. 교사 예시의 `#### 30`은 예시 답이며 대상 문제의 정답 필드를 넘긴 것이 아니다. 대상 문제에도 같은 수식을 기계적으로 적용하지 않도록 수량 관계를 읽는다.

변수명을 `{questions}`로 바꾸고 입력 dict는 `question`으로 유지하면 `KeyError`가 난다. 이는 API 장애가 아니라 템플릿 입력 이름 불일치다. 키를 일치시키면 해결된다. 전략 문구를 바꾼 뒤에는 2차시를 다시 실행해 실제 메시지에서 바뀐 부분을 확인한다.

다음 차시는 이 메시지를 실제 API 또는 모의 모델에 연결한다. 이때부터 체인 전체의 invoke는 모델 호출까지 진행한다.
