"""설정과 공급자 생성. --mock에서는 원격 호출을 수행하지 않는다."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

ROOT = Path(__file__).resolve().parents[1]

class SetupError(ValueError):
    pass

def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mock', action='store_true', help='명시적인 합성 응답; 원격 API 검증 아님')
    parser.add_argument('--provider', choices=['openai', 'groq'])
    parser.add_argument('--stream', action='store_true', help='7교시 선택 실습')
    return parser.parse_args()

def settings(provider=None):
    load_dotenv(ROOT / '.env', override=False)
    provider = provider or os.getenv('LLM_PROVIDER', 'openai')
    if provider not in ('openai', 'groq'):
        raise SetupError('LLM_PROVIDER는 openai 또는 groq여야 합니다.')
    prefix = provider.upper()
    key = os.getenv(prefix + '_API_KEY', '').strip()
    model = os.getenv(prefix + '_MODEL', '').strip()
    if not key or key.startswith('replace-'):
        raise SetupError(prefix + '_API_KEY를 .env에 설정하세요. 키를 출력하지 마세요.')
    if not model:
        raise SetupError(prefix + '_MODEL을 .env에 설정하세요.')
    return provider, key, model

def mock_reply(prompt_value):
    # LLM 추론을 흉내 내는 규칙 기반 답변이 아니다. 항상 같은 합성 응답이다.
    if not hasattr(prompt_value, 'to_messages'):
        raise TypeError('모델 앞에는 ChatPromptValue가 필요합니다.')
    return AIMessage(content='[MOCK: 품질평가 제외] 제목: 합성 안내\n핵심: 합성 내용\n행동: 담당자 확인')

def make_model(mock=False, provider=None):
    if mock:
        return RunnableLambda(mock_reply)
    provider, key, model = settings(provider)
    # 자동 재시도를 꺼서 수업 호출 수를 예측한다. 오류 시 명시적 재실행만 한다.
    if provider == 'openai':
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model, api_key=key, temperature=0,
                          max_tokens=350, timeout=30, max_retries=0,
                          use_responses_api=False)
    from langchain_groq import ChatGroq
    return ChatGroq(model=model, api_key=key, temperature=0,
                    max_tokens=350, timeout=30, max_retries=0)

def error_label(exc):
    if isinstance(exc, SetupError):
        return str(exc)
    if isinstance(exc, NotImplementedError):
        return '시작 코드의 구현이 필요합니다. WORKBOOK의 7·8교시 요구사항을 확인하세요.'
    if isinstance(exc, KeyError):
        return '템플릿 변수 누락: input_variables와 입력 dict의 키를 비교하세요.'
    status = getattr(exc, 'status_code', None)
    return {
        400: '400: 모델의 파라미터 지원·입력 형식을 확인하세요.',
        401: '401: 해당 공급자의 API 키와 만료 여부를 확인하세요.',
        403: '403: 프로젝트·모델 접근 권한을 확인하세요.',
        404: '404: 계정에서 사용 가능한 모델 ID를 확인하세요.',
        429: '429: 요청/토큰 한도 또는 할당량을 확인하고 수동 재실행하세요. 자동 전환하지 않습니다.',
    }.get(status, '실행 실패: 네트워크·타임아웃·설치 버전을 확인하세요. 비밀값은 출력하지 않습니다.')

def run_safely(work):
    try:
        work()
    except Exception as exc:
        print(error_label(exc))
        raise SystemExit(1) from None
