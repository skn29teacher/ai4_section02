"""ROOT에서 python -m tests.check_submission 실행. 학습자 7·8교시 코드만 검사."""
from common.runtime import make_model
from common.data import first_input
from lessons.s07_independent.main import build_batch_chain
from lessons.s08_capstone.main import build_service

def main():
    batch = build_batch_chain(make_model(mock=True))
    values = batch.batch([first_input(),first_input()],config={'max_concurrency':1})
    assert len(values)==2 and all(isinstance(x,str) and x for x in values)
    service = build_service(make_model(mock=True))
    data = {'request_id':'NEW09',**first_input()}
    out = service.invoke(data)
    assert set(out)=={'request_id','notice','answer'}
    assert out['request_id']==data['request_id'] and out['notice']==data['notice']
    assert isinstance(out['answer'],str) and out['answer']
    for changed in [{'notice':' '},{'request_id':''}]:
        try:
            service.invoke({**data,**changed})
        except (ValueError,TypeError):
            pass
        else:
            raise AssertionError('잘못된 입력을 거절해야 합니다.')
    print('PASS: 로컬 입출력 계약. 실제 모델 품질·독립 설명은 별도 평가합니다.')

if __name__ == '__main__':
    main()
