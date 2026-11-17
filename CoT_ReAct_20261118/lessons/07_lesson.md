# 7차시 · 실패를 관찰하고 반복을 멈추기

## 예외는 다음 동작을 결정하는 정보다

ReAct에서는 계산식이 틀리거나, 허용하지 않은 도구를 요청하거나, 최종 답 없이 같은 작업을 반복할 수 있다. 이러한 상황을 같은 실패 문자열로 숨기면 어느 부분을 고쳐야 하는지 알기 어렵다. 오늘은 합성 실패 입력으로 형식 검사·계산·반복 상한을 구분한다. 실제 외부 시스템을 변경하지 않는다.

| 관찰된 증상 | 원인 위치 | 이 코드의 처리 |
| --- | --- | --- |
| Action: web | parse_action | 허용 도구가 아니므로 tool_error |
| Observation: 999를 모델이 작성 | parse_action | 가짜 관찰로 거부 |
| 1/0 | calculate | 계산 예외를 Observation 오류로 전달 |
| 2**1000 | calculate | 거듭제곱 AST 거부 |
| 정답 없이 계산만 반복 | run_react | max_turns 후 중단 |
| 429 | RemoteChat.__call__ | 한도 오류 표시, 자동 재시도/유료 전환 없음 |
| 공개 답 없이 출력 상한 도달 | RemoteChat.extract | 완료 응답으로 쓰지 않음 |

## main.py의 실패 재현 함수

```python
def failure_demo():
    results = []
    for expression in ('(16-3-4)*2', '1/0', '__import__("os")', '2**1000'):
        try: value = calculate(expression)
        except (ValueError, SyntaxError, ArithmeticError) as exc: value = type(exc).__name__
        results.append(f'{expression} → {value}')
    for text in ('Action: web\nAction Input: 2+2', 'Observation: 999', '#### 18'):
        try: value = parse_action(text)
        except ValueError as exc: value = str(exc)
        results.append(f'{text}\n판정: {value}')
    repeated = lambda messages: 'Plan: 다시 계산한다.\nAction: calculator\nAction Input: 2+2'
    outcome = run_react('반복 상한 재현', repeated, max_turns=2)
    results.append('반복 도구 호출 중단 상태: ' + outcome['status'])
    return '\n\n'.join(results)
```

처음 for문은 같은 calculate 함수에 정상·실패 식을 보낸다. 예외를 잡은 뒤 예외 클래스 이름을 보여주므로 계산기 입력 문제를 API 문제로 착각하지 않는다. 두 번째 for문은 행동 파서를 검사한다. 마지막 lambda는 언제나 같은 Action을 내보내는 합성 모델이다. 2회만 허용하면 계산을 두 번 실행한 후 `max_turns`로 종료한다.

`__import__("os")`라는 입력은 AST 단계에서 거부된다. Python 함수 호출이 실제 실행된 것이 아니다. 문자열을 보여주는 실습과 실행하는 실습을 구분한다. 정답이 없는데 상한에 닿았다면 모델이 틀린지·규약을 따르지 못했는지·예산이 부족했는지 기록을 보고 해석한다.

```bash
python main.py --session 7
python -m unittest discover -s tests -v
```

첫 명령은 원격 호출 0회이며 정상 계산 18, 허용하지 않은 노드 오류, 가짜 관찰 거부, 반복 상한 종료가 출력된다. 두 번째는 소프트웨어 검증이다. 학생 시험이나 채점표가 아니다. 테스트는 실제 함수의 결과·API 요청 변환·실패 복구·정보 경계를 검사한다.

## 호출 예산과 재시도 정책

RemoteChat은 상한을 확인한 뒤 요청 횟수를 증가시킨다. 429에서 무한 재시도하면 같은 원인을 반복하고 수업 시간을 낭비할 수 있다. 이 교안은 자동 재시도 0회로 두고 Retry-After 안내를 보고 수동으로 재실행한다. 무료 한도가 찼을 때는 호출을 줄이거나 명시적으로 모의 실행을 선택한다. 다른 공급자로 바꾸면 데이터 전송 대상·모델·요금이 바뀌므로 `--provider`를 직접 선택한다.

실제 외부 API는 계정·모델·엔드포인트가 있어야 검증할 수 있다. 로컬 테스트의 성공을 세 원격 서비스의 성공으로 해석하지 않는다. 다음 차시는 이러한 상태와 원본 근거를 한 화면에 저장한다.
