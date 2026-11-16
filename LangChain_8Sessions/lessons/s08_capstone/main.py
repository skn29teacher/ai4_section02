"""8교시 독립 수행용. 공개 계약을 만족하도록 build_service를 작성하세요."""
from common.runtime import cli, make_model, run_safely

def build_service(model):
    # 입력: dict(request_id, audience, tone, notice)
    # 출력: dict(request_id, notice, answer), answer는 문자열
    # request_id는 비어 있지 않은 문자열, notice 등은 common.prompts의 규칙 적용
    raise NotImplementedError('입력 검증, 원문/ID 보존, answer 생성 LCEL을 설계하세요.')

def main():
    args = cli()
    service = build_service(make_model(args.mock,args.provider))
    result = service.invoke({'request_id':'R08','audience':'신규 협력사',
                             'tone':'격식 있게','notice':'자료 제출 기한은 미정입니다. 담당자에게 확인하세요.'})
    print(result)

if __name__ == '__main__':
    run_safely(main)
