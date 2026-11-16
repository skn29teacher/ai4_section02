import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from common.prompts import make_prompt, validate_input, build_chain, build_review_chain
from common.runtime import make_model, settings, SetupError, error_label
from common.data import first_input, cases
from lessons.s04_compare.main import experiment

def test_roles_variables_and_partial():
    p = make_prompt()
    assert set(p.input_variables) == {'audience','tone','notice'}
    assert [m.type for m in p.invoke(first_input()).to_messages()] == ['system','human']
    assert set(p.partial(tone='정중하게').input_variables) == {'audience','notice'}

def test_missing_variables_before_any_model_call():
    calls = []
    model = RunnableLambda(lambda x: calls.append(x))
    with pytest.raises(KeyError):
        (make_prompt() | model).invoke({'notice':'합성 공지'})
    assert calls == []

@pytest.mark.parametrize('value',[None,'','  ',123,True,[], '가'*1201])
def test_invalid_notice(value):
    with pytest.raises(ValueError):
        validate_input({**first_input(),'notice':value})

def test_whitespace_and_extra_fields():
    clean = validate_input({**first_input(),'notice':' 점검 ','secret':'unused'})
    assert clean['notice'] == '점검' and 'secret' not in clean

def test_chain_string_output():
    out = build_chain(make_model(mock=True)).invoke(first_input())
    assert isinstance(out,str) and '[MOCK:' in out

def test_review_receives_original_and_draft():
    seen=[]
    def spy(value):
        messages=value.to_messages(); seen.append(messages)
        return AIMessage(content='first draft' if len(seen)==1 else 'review')
    out=build_review_chain(RunnableLambda(spy)).invoke(first_input())
    assert out['notice'] == first_input()['notice']
    assert out['draft']=='first draft' and out['review']=='review'
    assert out['notice'] in seen[1][-1].content and out['draft'] in seen[1][-1].content

def test_comparison_has_pairing_and_no_auto_grading():
    rows=experiment(make_model(mock=True),cases(),{'quality_evaluation':False})
    assert len(rows)==6 and all(r['status']=='ok' for r in rows)
    assert {(r['case_id'],r['variant']) for r in rows} == {(c['id'],v) for c in cases() for v in ['A','B']}
    assert all(r['human_scores']['facts'] is None for r in rows)

def test_comparison_keeps_failed_calls():
    def fail(value): raise TimeoutError('synthetic')
    rows=experiment(RunnableLambda(fail),cases()[:1],{})
    assert len(rows)==2 and all(r['status']=='error' and r['output'] is None for r in rows)

def test_unknown_provider_stops():
    with pytest.raises(SetupError): settings('unknown')

def test_safe_error_no_secret():
    assert 'private-key' not in error_label(RuntimeError('private-key'))
