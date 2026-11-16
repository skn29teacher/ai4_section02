import pytest
from common.runtime import make_model
from common.data import first_input
from solutions.session07 import build_batch_chain
from solutions.session08 import build_service

def test_batch_and_stream_composition():
    chain=build_batch_chain(make_model(mock=True))
    data=first_input()
    outputs=chain.batch([data,data],config={'max_concurrency':1})
    assert len(outputs)==2 and all(isinstance(x,str) for x in outputs)
    assert ''.join(chain.stream(data)) == outputs[0]

def test_capstone_preserves_keys():
    inp={'request_id':'R01',**first_input()}
    out=build_service(make_model(mock=True)).invoke(inp)
    assert set(out)=={'request_id','notice','answer'}
    assert out['request_id']=='R01' and out['notice']==inp['notice']
    assert isinstance(out['answer'],str)

@pytest.mark.parametrize('request_id',[None,'',123, 'x'*81])
def test_capstone_rejects_bad_id_without_model(request_id):
    from langchain_core.runnables import RunnableLambda
    calls=[]
    service=build_service(RunnableLambda(lambda x:calls.append(x)))
    with pytest.raises(ValueError): service.invoke({'request_id':request_id,**first_input()})
    assert calls==[]
