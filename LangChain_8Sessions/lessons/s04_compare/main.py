import json
from datetime import datetime, timezone
from time import perf_counter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from common.prompts import make_prompt
from common.data import cases
from common.runtime import cli, make_model, settings, ROOT, error_label, run_safely

def experiment(model, inputs, metadata):
    baseline = ChatPromptTemplate.from_messages([
        ('system', '당신은 사내 안내문 작성자입니다.'),
        ('human', '독자: {audience}\n어조: {tone}\n사실: {notice}'),
    ])
    variants = [('A', baseline), ('B', make_prompt())]
    rows = []
    for i, case in enumerate(inputs):
        data = {k:v for k,v in case.items() if k != 'id'}
        # 시간 경과 순서 효과를 줄이기 위해 사례마다 A/B 실행 순서를 교차한다.
        order = variants if i % 2 == 0 else list(reversed(variants))
        for name, prompt in order:
            start = perf_counter()
            try:
                response = (prompt | model).invoke(data)
                output = StrOutputParser().invoke(response)
                status, error = 'ok', None
                usage = getattr(response, 'usage_metadata', None)
            except Exception as exc:
                output, usage = None, None
                status, error = 'error', error_label(exc)
            rows.append({**metadata, 'case_id':case['id'], 'variant':name,
                         'seconds':round(perf_counter()-start, 4), 'status':status,
                         'error':error, 'output':output, 'usage':usage,
                         'human_scores':{'facts':None,'format':None,'action':None}})
    return rows

def main():
    args = cli()
    if args.mock:
        metadata = {'provider':'mock', 'model':'constant-synthetic', 'quality_evaluation':False}
    else:
        provider, _, model_id = settings(args.provider)
        metadata = {'provider':provider, 'model':model_id, 'quality_evaluation':True,
                    'temperature':0, 'max_tokens':350}
    metadata['created_at'] = datetime.now(timezone.utc).isoformat()
    rows = experiment(make_model(args.mock,args.provider), cases(), metadata)
    out = ROOT / 'outputs'; out.mkdir(exist_ok=True)
    path = out / ('comparison_mock.json' if args.mock else 'comparison_live.json')
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('저장:', path.name, '기록 수:', len(rows))
    print('모의 결과는 품질 평가에서 제외하세요.' if args.mock else 'WORKBOOK 기준으로 사람이 점수를 입력하세요.')

if __name__ == '__main__':
    run_safely(main)
