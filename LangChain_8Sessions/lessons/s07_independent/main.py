"""WORKBOOK 7교시를 먼저 수행하세요. 해설은 solutions/session07.py."""
from common.runtime import cli, make_model, run_safely
from common.data import cases

def build_batch_chain(model):
    # 입력: audience, tone, notice / 출력: 안내문 str
    raise NotImplementedError('검증 → 템플릿 → 모델 → 문자열 파서를 직접 연결하세요.')

def main():
    args = cli()
    model = make_model(args.mock,args.provider)
    chain = build_batch_chain(model)
    inputs = [{k:v for k,v in x.items() if k != 'id'} for x in cases()[:2]]
    results = chain.batch(inputs, config={'max_concurrency':1})
    for result in results:
        print(result)
    if args.stream:
        for chunk in chain.stream(inputs[0]):
            print(chunk, end='', flush=True)
        print()

if __name__ == '__main__':
    run_safely(main)
