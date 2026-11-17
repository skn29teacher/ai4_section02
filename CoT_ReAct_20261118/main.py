"""python main.py --session 1 ... --session 8"""
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.runnables import RunnableLambda
from app.core import (ROOT, load_records, parse_final, build_prompt, to_messages,
                      calculate, parse_action, run_react)
from app.providers import RemoteChat, ScriptedChat, CallLimit
from app.report import save_report


def make_result(row, strategy, chat, output, metrics=None):
    predicted = parse_final(output['text'])
    expected = parse_final(row['answer'].replace('\\n', '\n'))
    finished = output['status'] == 'finished'
    return {'record': row, 'strategy': strategy, 'mode': 'mock' if chat.provider == 'mock' else 'live',
            'provider': chat.provider, 'model': chat.model, **output,
            'predicted': str(predicted) if predicted is not None else None,
            'expected': str(expected) if expected is not None else None,
            'correct': bool(predicted == expected) if finished and predicted is not None and expected is not None else None,
            'metrics': metrics or []}


def run_strategy(row, strategy, chat, max_turns):
    before = len(chat.metrics)
    try:
        if strategy == 'react':
            output = run_react(row['question'], chat, max_turns)
        else:
            chain = build_prompt(strategy) | RunnableLambda(to_messages) | RunnableLambda(chat)
            text = chain.invoke({'question': row['question']})
            output = {'status': 'finished', 'text': text, 'events': []}
    except (ValueError, RuntimeError, CallLimit) as exc:
        output = {'status': 'error', 'text': str(exc), 'events': []}
    return make_result(row, strategy, chat, output, chat.metrics[before:])


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


def main():
    load_dotenv(ROOT / '.env', override=False)
    p = argparse.ArgumentParser(description='GSM8K CoT·ReAct 8차시 실습')
    p.add_argument('--session', type=int, choices=range(1, 9), required=True)
    p.add_argument('--id', default='gsm8k-main-test-0000')
    p.add_argument('--count', type=int, choices=range(1, 7), default=1)
    p.add_argument('--provider', choices=('openai', 'groq', 'gemini'), default=os.getenv('LLM_PROVIDER', 'groq'))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--live', action='store_true')
    mode.add_argument('--mock', action='store_true')
    p.add_argument('--strategy', choices=('direct', 'summary', 'fewshot'), default='summary')
    p.add_argument('--max-turns', type=int, choices=range(1, 6), default=3)
    p.add_argument('--max-calls', type=int, choices=range(1, 31), default=8)
    p.add_argument('--max-tokens', type=int, default=800)
    p.add_argument('--input', type=Path)
    args = p.parse_args()
    rows = load_records()
    selected = next((row for row in rows if row['id'] == args.id), None)
    if selected is None: p.error('표본에 없는 ID입니다.')
    if args.session == 8:
        if args.input is None: p.error('--input results/파일.json 을 지정하세요.')
        items = json.loads(args.input.read_text(encoding='utf-8'))
        print(save_report(8, items))
        return
    if args.session in (1, 2, 4, 7):
        chat = ScriptedChat(selected['id'])
        if args.session == 1:
            text = f'표본 {len(rows)}개\n선택 ID: {selected["id"]}\nquestion만 모델 입력에 사용; answer는 실행 후 대조'
        elif args.session == 2:
            text = '\n\n'.join(strategy + '\n' + '\n'.join(m['role'] + ': ' + m['content'] for m in to_messages(build_prompt(strategy).invoke({'question': selected['question']}))) for strategy in ('direct', 'summary', 'fewshot'))
        elif args.session == 4:
            text = f'계산식: (16-3-4)*2\n실제 로컬 계산 결과: {calculate("(16-3-4)*2")}\n모델 호출 없음'
        else: text = failure_demo()
        items = [make_result(selected, 'local', chat, {'status': 'local_only', 'text': text, 'events': []})]
        items[0]['mode'], items[0]['provider'], items[0]['model'] = 'local_only', 'none', 'none'
    else:
        remote = RemoteChat(args.provider, args.max_calls, args.max_tokens) if args.live else None
        print(f'실행: {args.provider if args.live else "mock 교사 대본"}; '
              f'{"OpenAI 유료 호출" if args.live and args.provider == "openai" else "원격 호출은 계정 요금/무료 한도 확인 필요" if args.live else "API 호출 없음"}')
        items = []
        targets = rows[:args.count] if args.session == 6 else [selected]
        strategies = ('direct', 'summary', 'react') if args.session == 6 else ('react',) if args.session == 5 else (args.strategy,)
        for row in targets:
            for strategy in strategies:
                chat = remote if args.live else ScriptedChat(row['id'])
                item = run_strategy(row, strategy, chat, args.max_turns)
                items.append(item)
                print(row['id'], strategy, item['status'], item['predicted'])
                if item['status'] == 'error': break
            if items[-1]['status'] == 'error': break
    path = save_report(args.session, items)
    print('결과 HTML:', path)


if __name__ == '__main__':
    main()
