"""데이터 → 프롬프트 → 제한된 계산 → ReAct 반복."""
import ast
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from langchain_core.prompts import ChatPromptTemplate

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://huggingface.co/datasets/openai/gsm8k/tree/main'


def load_records():
    records = json.loads((ROOT / 'data/gsm8k_sample.json').read_text(encoding='utf-8'))
    if not records:
        raise ValueError('데이터가 비어 있습니다.')
    for row in records:
        if not all(isinstance(row.get(k), str) and row[k] for k in ('id', 'question', 'answer')):
            raise ValueError('id/question/answer 문자열이 필요합니다.')
    return records


def parse_final(text):
    # 마지막 줄의 #### 숫자만 허용: 단위·백분율은 수업 범위 밖이다.
    match = re.search(r'(?:^|\n)####\s+(-?\d[\d,]*(?:\.\d+)?)\s*$', text.strip())
    if not match:
        return None
    try:
        value = Decimal(match.group(1).replace(',', ''))
        return value if value.is_finite() else None
    except InvalidOperation:
        return None


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


def to_messages(prompt_value):
    return [{'role': 'assistant' if m.type == 'ai' else 'user' if m.type == 'human' else m.type,
             'content': m.content} for m in prompt_value.to_messages()]


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


REACT_SYSTEM = '''수학 문제를 해결하세요. 내부 사고 대신 다음 작업의 짧은 목적만 적으세요.
계산이 필요하면 정확히 다음 세 줄로 응답하세요.
Plan: 다음 계산의 목적 한 문장
Action: calculator
Action Input: 숫자와 + - * / 괄호만 있는 계산식
Observation은 직접 작성하지 마세요. 프로그램의 실행 결과를 받은 후 답하세요.
충분한 근거가 모이면 짧은 검증 요약과 마지막 줄 #### 숫자로 종료하세요.
다른 도구·코드·마크다운 코드펜스는 쓰지 마세요.'''


def run_react(question, chat, max_turns=3):
    if not 1 <= max_turns <= 5:
        raise ValueError('max_turns는 1~5입니다.')
    messages = [{'role': 'system', 'content': REACT_SYSTEM}, {'role': 'user', 'content': question}]
    events = []
    for turn in range(1, max_turns + 1):
        try:
            text = chat(messages)
        except (RuntimeError, ValueError) as exc:
            return {'status': 'error', 'text': str(exc), 'events': events}
        events.append({'kind': 'model', 'turn': turn, 'text': text})
        messages.append({'role': 'assistant', 'content': text})
        try:
            expression = parse_action(text)
            if expression is None:
                return {'status': 'finished', 'text': text, 'events': events}
            value = calculate(expression)
            observation = f'계산식: {expression}\n결과: {value}'
            events.append({'kind': 'tool', 'turn': turn, 'text': observation})
        except (ValueError, SyntaxError, ArithmeticError) as exc:
            observation = f'도구/형식 오류: {exc}'
            events.append({'kind': 'tool_error', 'turn': turn, 'text': observation})
        messages.append({'role': 'user', 'content': 'Observation:\n' + observation})
    return {'status': 'max_turns', 'text': '반복 상한으로 중단: 최종 답 미완료', 'events': events}
