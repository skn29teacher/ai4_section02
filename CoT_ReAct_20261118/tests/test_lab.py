import json
import os
import unittest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError
from app.core import (load_records, parse_final, build_prompt, to_messages,
                      calculate, parse_action, run_react)
from app.providers import RemoteChat, ScriptedChat, CallLimit
from app.report import text_block
from main import run_strategy


class LabTests(unittest.TestCase):
    def test_data_location(self):
        rows = load_records()
        self.assertEqual(len(rows), 6)
        self.assertEqual([x['row_index'] for x in rows], list(range(6)))
        self.assertTrue(all(x['dataset_id'] == 'D04' and x['split'] == 'test' for x in rows))

    def test_prompt_excludes_gold(self):
        row = load_records()[0]
        for strategy in ('direct', 'summary', 'fewshot'):
            messages = to_messages(build_prompt(strategy).invoke({'question': row['question']}))
            text = json.dumps(messages, ensure_ascii=False)
            self.assertNotIn(row['answer'], text)
            self.assertEqual(messages[-1]['content'], row['question'])

    def test_missing_prompt_variable(self):
        with self.assertRaises(KeyError): build_prompt('summary').invoke({})

    def test_decimal_and_reference(self):
        self.assertEqual(parse_final('검증\n#### 70,000'), Decimal('70000'))
        self.assertIsNone(parse_final('답은 18입니다'))
        self.assertIsNone(parse_final('#### 18원'))
        self.assertEqual(parse_final(load_records()[0]['answer'].replace('\\n', '\n')), Decimal('18'))

    def test_calculator(self):
        self.assertEqual(calculate('(16-3-4)*2'), '18')
        self.assertEqual(calculate('0.1+0.2'), '0.3')
        self.assertEqual(calculate('-3 + 2'), '-1')
        for expression in ('__import__("os")', '2**1000', 'x+1', 'True', '1;2', '1e20', '1'*121):
            with self.subTest(expression=expression), self.assertRaises((ValueError, SyntaxError)):
                calculate(expression)
        with self.assertRaises(ArithmeticError): calculate('1/0')

    def test_action_contract(self):
        self.assertEqual(parse_action('Plan: 수량\nAction: calculator\nAction Input: 2+2'), '2+2')
        self.assertIsNone(parse_action('검증\n#### 4'))
        for text in ('Action: web\nAction Input: 2', 'Observation: 100',
                     '#### 4\nAction: calculator\nAction Input: 2+2',
                     'Action: calculator\nAction Input: 2\nAction Input: 3'):
            with self.assertRaises(ValueError): parse_action(text)

    def test_all_rows_scripted(self):
        for row in load_records():
            for strategy in ('direct', 'summary', 'fewshot', 'react'):
                with self.subTest(id=row['id'], strategy=strategy):
                    item = run_strategy(row, strategy, ScriptedChat(row['id']), 3)
                    self.assertTrue(item['correct'])
                    if strategy == 'react':
                        self.assertEqual([e['kind'] for e in item['events']], ['model', 'tool', 'model'])

    def test_react_error_then_repair(self):
        answers = iter(['Action: calculator\nAction Input: 1/0',
                        'Action: calculator\nAction Input: 2+2','#### 4'])
        result = run_react('demo', lambda messages: next(answers), 3)
        self.assertEqual(result['status'], 'finished')
        self.assertEqual(result['events'][1]['kind'], 'tool_error')

    def test_repeat_limit_and_early_final(self):
        result = run_react('demo', lambda messages: 'Action: calculator\nAction Input: 2+2', 2)
        self.assertEqual(result['status'], 'max_turns')
        result = run_react('demo', lambda messages: '#### 4', 2)
        self.assertEqual(result['status'], 'finished')
        self.assertFalse(any(x['kind'] == 'tool' for x in result['events']))

    def test_api_failure_retains_events(self):
        calls = iter(['Action: calculator\nAction Input: 2+2', CallLimit('limit')])
        def chat(messages):
            value = next(calls)
            if isinstance(value, Exception): raise value
            return value
        result = run_react('demo', chat)
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(result['events']), 2)

    def test_html_text(self):
        text = '첫 줄\n\n둘째 줄 <script> & ' + r'문자 \n 보존'
        html = text_block('결과', text)
        self.assertIn('첫 줄\n\n둘째 줄', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn(r'문자 \n 보존', html)

    def make_remote(self, provider):
        env = {provider.upper()+'_API_KEY':'TEST-NOT-REAL', provider.upper()+'_MODEL':'model-test'}
        with patch.dict(os.environ, env, clear=True), patch('app.providers.load_dotenv'):
            return RemoteChat(provider, max_calls=1)

    def test_provider_payloads_and_parsing(self):
        messages = [{'role':'system','content':'system'}, {'role':'user','content':'question'},
                    {'role':'assistant','content':'action'}, {'role':'user','content':'Observation: 4'}]
        for provider in ('openai','groq','gemini'):
            with self.subTest(provider=provider):
                chat = self.make_remote(provider)
                url, headers, payload = chat.prepare(messages)
                self.assertTrue(url.startswith('https://'))
                self.assertNotIn('TEST-NOT-REAL', url)
                if provider == 'gemini':
                    self.assertEqual(payload['contents'][1]['role'], 'model')
                    response = {'candidates':[{'finishReason':'STOP','content':{'parts':[
                        {'thought':True,'text':'private'}, {'text':'#### 4'}]}}]}
                else:
                    self.assertEqual(payload['model'], 'model-test')
                    response = {'choices':[{'finish_reason':'stop','message':{'content':'#### 4'}}]}
                self.assertEqual(chat.extract(response)[0], '#### 4')
                with self.assertRaises(ValueError): chat.extract({})
                handle = MagicMock()
                handle.__enter__.return_value.read.return_value = json.dumps(response).encode()
                with patch('app.providers.request.urlopen', return_value=handle) as transport:
                    self.assertEqual(chat(messages), '#### 4')
                    with self.assertRaises(CallLimit): chat(messages)
                    self.assertEqual(transport.call_count, 1)

    def test_configuration_and_429(self):
        with patch.dict(os.environ, {}, clear=True), patch('app.providers.load_dotenv'):
            with self.assertRaises(ValueError): RemoteChat('gemini')
            with self.assertRaises(ValueError): RemoteChat('unknown')
        chat = self.make_remote('groq')
        with patch('app.providers.request.urlopen', side_effect=HTTPError('https://example.invalid',429,'rate',{'Retry-After':'5'},None)) as transport:
            with self.assertRaisesRegex(RuntimeError, 'HTTP 429'): chat([{'role':'user','content':'test'}])
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(chat.calls, 1)


if __name__ == '__main__':
    unittest.main()
