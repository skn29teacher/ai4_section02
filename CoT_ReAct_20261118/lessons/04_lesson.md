# 4차시 · ReAct의 Action 규약과 실제 계산기

## 도구 호출을 글로 쓰는 것과 실행하는 것은 다르다

ReAct는 다음 행동을 선택하고 실행 결과를 관찰하며 문제 해결을 이어가는 패턴이다. 계산 결과가 필요한 순간에 프로그램이 도구를 실행해 관찰값을 넣는다. 모델이 “계산 결과는 18이다”라고 쓴 문장은 실제 계산기 실행 증거가 아니다.

오늘의 간소화한 텍스트 규약은 아래와 같다. `Plan`은 다음 작업의 짧은 목적이며 비공개 내부 사고 전문이 아니다. native Function Calling API가 아니라 프로그램이 텍스트를 해석하는 교육용 프로토콜이다.

```text
Plan: 남은 달걀을 판매한 금액을 계산한다.
Action: calculator
Action Input: (16-3-4)*2
```

프로그램이 만드는 관찰값은 다음과 같다.

```text
Observation:
계산식: (16-3-4)*2
결과: 18
```

## app/core.py: 허용된 식만 계산하기

가장 작은 고정 계산은 `(16-3-4)*2`다. 그러나 모델이 보내는 문자열을 실행하려면 허용 범위가 필요하다. `eval(expression)`은 함수 호출 같은 Python 코드까지 실행할 수 있으므로 사용하지 않는다. AST는 문자열을 구문 트리로 읽되 코드를 실행하지 않는다. 그 트리에서 숫자·사칙연산·단항 부호만 직접 처리한다.

```python
def calculate(expression):
    # eval 없이 숫자와 + - * / 괄호만 계산한다.
    if not isinstance(expression, str) or len(expression) > 120:
        raise ValueError('계산식은 120자 이하 문자열이어야 합니다.')
    tree = ast.parse(expression.strip(), mode='eval')
    if len(list(ast.walk(tree))) > 48:
        raise ValueError('계산식이 너무 복잡합니다.')

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = Decimal(str(node.value))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add): value = a + b
            elif isinstance(node.op, ast.Sub): value = a - b
            elif isinstance(node.op, ast.Mult): value = a * b
            else: value = a / b
        else:
            raise ValueError('숫자·사칙연산·괄호만 허용합니다.')
        if not value.is_finite() or abs(value) > Decimal('1e12'):
            raise ValueError('계산 범위를 벗어났습니다.')
        return value

    return format(visit(tree.body), 'f')
```

`ast.parse(..., mode="eval")`의 eval은 파싱 모드 이름이며 Python 내장 `eval()`을 호출하는 것이 아니다. `tree.body`부터 `visit`가 내려가며 값들을 계산한다. `(16-3-4)*2`의 맨 위는 곱셈이고 왼쪽은 뺄셈 트리다. 왼쪽이 9, 오른쪽이 2가 되면 마지막 곱셈이 18을 만든다.

| 검사/분기 | 처리 의미 |
| --- | --- |
| 최대 120자·AST 노드 48개 | 지나치게 큰 입력을 계산 전에 제한 |
| Constant + int/float | 숫자를 Decimal로 바꿈. bool은 제외 |
| UnaryOp | `-3`, `+2` 같은 부호 처리 |
| BinOp + Add/Sub/Mult/Div | 두 자식 값을 먼저 계산한 후 사칙연산 |
| 그 밖의 노드 | 함수 호출·변수·거듭제곱 등 거부 |
| 중간 결과 절댓값 1e12 초과 | 과도한 숫자를 제한 |

`Decimal(str(node.value))`로 0.1 같은 표본의 소수를 처리한다. 모든 실수 표현을 완전한 기호수학으로 계산하는 도구는 아니다. 반환은 JSON/메시지에 넣기 쉬운 숫자 문자열이다. 0으로 나누면 `ArithmeticError` 계열 예외가 난다. 여기서 오류가 났다고 0을 계산값으로 반환하지 않는다.

## 행동 형식도 검사하기

```python
def parse_action(text):
    # 모델이 Observation을 작성하면 실제 도구 결과로 오인하지 않도록 거부한다.
    if re.search(r'^Observation\s*:', text, re.M):
        raise ValueError('Observation은 프로그램만 작성합니다.')
    if re.search(r'^####', text, re.M) and re.search(r'^Action(?: Input)?\s*:', text, re.M):
        raise ValueError('행동과 최종 답을 동시에 내면 안 됩니다.')
    if parse_final(text) is not None:
        return None
    names = re.findall(r'^Action:\s*([^\n]+)$', text, re.M)
    inputs = re.findall(r'^Action Input:\s*([^\n]+)$', text, re.M)
    if len(names) != 1 or len(inputs) != 1 or names[0].strip() != 'calculator':
        raise ValueError('Action: calculator 와 Action Input: 계산식 한 쌍이 필요합니다.')
    return inputs[0].strip()
```

정규식의 `^`는 줄 시작이고 `re.M`은 여러 줄 각각의 시작을 검사한다. `findall` 결과가 한 쌍인지 검사하므로 Action을 두 개 써서 모호해진 응답을 실행하지 않는다. 허용 도구는 calculator 하나다. 모델이 직접 Observation을 쓴 경우도 거부하여 가짜 관찰이 실제 실행값처럼 보이지 않게 한다.

`None`은 “파싱 실패”가 아니라 **정상적인 최종 답**을 뜻한다. 이 반환 계약은 5차시 반복문에서 종료 분기로 사용된다. 파싱 실패는 `ValueError`로 구별한다.

## API 없이 도구 실행

```bash
python main.py --session 4
```

예상 결과는 실제 로컬 계산 `18`이다. 원본 0행의 question과 함께 보이지만 이 차시는 식을 고정하여 도구 자체를 이해하는 단계다. 다른 문제를 자동 해석해 식을 선택하는 것은 5차시 모델의 역할이다. 화면의 mode는 local_only이며 모델 호출은 없다.
