"""동일 메시지 계약을 세 공급자의 REST 요청으로 바꾼다."""
import json
import os
import re
import time
from urllib import request, error, parse
from dotenv import load_dotenv
from app.core import ROOT, calculate


class CallLimit(RuntimeError):
    pass


class RemoteChat:
    def __init__(self, provider, max_calls=8, max_tokens=800):
        load_dotenv(ROOT / '.env', override=False)
        if provider not in ('openai', 'groq', 'gemini'):
            raise ValueError('provider는 openai/groq/gemini 중 하나입니다.')
        self.provider = provider
        prefix = provider.upper()
        self.key = os.getenv(prefix + '_API_KEY', '').strip()
        self.model = os.getenv(prefix + '_MODEL', '').strip()
        if not self.key or not self.model:
            raise ValueError(f'{prefix}_API_KEY 와 {prefix}_MODEL 설정이 필요합니다.')
        if not 1 <= max_calls <= 30 or not 128 <= max_tokens <= 4096:
            raise ValueError('호출 상한 1~30, 출력 상한 128~4096을 사용하세요.')
        self.max_calls, self.max_tokens = max_calls, max_tokens
        self.calls = 0
        self.metrics = []

    def prepare(self, messages):
        if self.provider == 'gemini':
            system = '\n'.join(m['content'] for m in messages if m['role'] == 'system')
            contents = [{'role': 'model' if m['role'] == 'assistant' else 'user',
                         'parts': [{'text': m['content']}]} for m in messages if m['role'] != 'system']
            url = 'https://generativelanguage.googleapis.com/v1beta/models/'
            url += parse.quote(self.model, safe='') + ':generateContent'
            return url, {'x-goog-api-key': self.key}, {
                'systemInstruction': {'parts': [{'text': system}]}, 'contents': contents,
                'generationConfig': {'maxOutputTokens': self.max_tokens}}
        base = 'https://api.openai.com/v1' if self.provider == 'openai' else 'https://api.groq.com/openai/v1'
        return base + '/chat/completions', {'Authorization': 'Bearer ' + self.key}, {
            'model': self.model, 'messages': messages, 'max_completion_tokens': self.max_tokens}

    def extract(self, data):
        if self.provider == 'gemini':
            candidates = data.get('candidates', [])
            if not candidates or candidates[0].get('finishReason') != 'STOP':
                raise ValueError('Gemini 응답 거절·잘림·빈 후보')
            parts = candidates[0].get('content', {}).get('parts', [])
            text = ''.join(p.get('text', '') for p in parts if not p.get('thought', False))
            usage = data.get('usageMetadata', {})
        else:
            choices = data.get('choices', [])
            if not choices or choices[0].get('finish_reason') != 'stop':
                raise ValueError('응답 거절·잘림·빈 후보: 출력 상한/모델 지원을 확인하세요.')
            text = choices[0]['message'].get('content') or ''
            usage = data.get('usage', {})
        if not text.strip():
            raise ValueError('공개 응답 텍스트가 비어 있습니다.')
        return text, usage

    def __call__(self, messages):
        if self.calls >= self.max_calls:
            raise CallLimit('명령 단위 호출 상한 도달; 자동 공급자 전환 없음')
        self.calls += 1  # 실패 요청도 호출 예산에 포함한다.
        url, headers, payload = self.prepare(messages)
        req = request.Request(url, data=json.dumps(payload).encode('utf-8'),
                              headers={**headers, 'Content-Type': 'application/json'}, method='POST')
        started = time.perf_counter()
        try:
            with request.urlopen(req, timeout=45) as response:
                data = json.load(response)
            text, usage = self.extract(data)
        except error.HTTPError as exc:
            # 응답 본문·요청 헤더를 출력하지 않아 키 노출을 피한다.
            retry = exc.headers.get('Retry-After', '없음')
            raise RuntimeError(f'HTTP {exc.code}; Retry-After={retry}; 설정/한도 확인 후 수동 재실행') from None
        except (error.URLError, TimeoutError):
            raise RuntimeError('연결 실패 또는 45초 타임아웃; 자동 재시도 없음') from None
        self.metrics.append({'seconds': round(time.perf_counter() - started, 3), 'usage': usage})
        return text


# 모의 모델용 교사 작성 대본: GSM8K 정답 필드를 읽지 않는다.
FIXTURES = {
    'gsm8k-main-test-0000': ('(16-3-4)*2', '남은 달걀 9개에 개당 2달러를 곱했다.'),
    'gsm8k-main-test-0001': ('2+2/2', '흰색은 파란색 2볼트의 절반이므로 1볼트를 더했다.'),
    'gsm8k-main-test-0002': ('80000*2.5-(80000+50000)', '매각가에서 매입비와 수리비를 뺐다.'),
    'gsm8k-main-test-0003': ('3*3*60', '주당 횟수에 회당 거리를 곱했다.'),
    'gsm8k-main-test-0004': ('20*3-15-25', '하루 필요량에서 이미 준 두 끼를 뺐다.'),
    'gsm8k-main-test-0005': ('8*5+8*(5*0.6)', '정가 8개와 할인 가격 8개의 금액을 더했다.'),
}


class ScriptedChat:
    def __init__(self, record_id):
        self.expression, self.summary = FIXTURES[record_id]
        self.model, self.provider = 'teacher-script-v1', 'mock'
        self.calls, self.metrics = 0, []

    def __call__(self, messages):
        self.calls += 1
        system = messages[0]['content']
        value = calculate(self.expression)
        if 'Action: calculator' in system and not messages[-1]['content'].startswith('Observation:'):
            return f'Plan: 필요한 수량과 가격을 계산한다.\nAction: calculator\nAction Input: {self.expression}'
        if '풀이 없이' in system:
            return f'#### {value}'
        return f'계산: {self.expression} = {value}\n검증: {self.summary}\n#### {value}'
