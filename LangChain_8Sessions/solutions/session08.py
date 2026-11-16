from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from common.prompts import validate_input, build_chain
from common.runtime import cli, make_model, run_safely

def validate_request(data):
    clean = validate_input(data)
    request_id = data.get('request_id')
    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError('request_id가 필요합니다.')
    if len(request_id) > 80:
        raise ValueError('request_id 길이 제한 초과')
    return {'request_id':request_id.strip(), **clean}

def build_service(model):
    return (RunnableLambda(validate_request)
            | RunnablePassthrough.assign(answer=build_chain(model))
            | RunnableLambda(lambda x: {k:x[k] for k in ['request_id','notice','answer']}))

def main():
    args = cli()
    service = build_service(make_model(args.mock,args.provider))
    print(service.invoke({'request_id':'R08','audience':'신규 협력사','tone':'격식 있게',
                          'notice':'자료 제출 기한은 미정입니다. 담당자에게 확인하세요.'}))

if __name__ == '__main__':
    run_safely(main)
