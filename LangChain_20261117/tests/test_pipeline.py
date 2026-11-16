import json
import pytest
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser
from app.config import Settings
from app.providers import make_model
from app.pipeline import normalize_request, build_chain, read_requests, write_jsonl, load_policy
from app.prompts import get_prompt
from app.compare import compare_versions, observations

@pytest.mark.parametrize("value", ["", "  ", None, 3, "가" * 1001])
def test_invalid_inquiry(value):
    with pytest.raises(ValueError): normalize_request({"inquiry": value})

def test_request_type():
    with pytest.raises(TypeError): normalize_request("질문")

def test_trim_and_preserve_braces():
    assert normalize_request({"inquiry": "  주문 {id}  "}) == {"inquiry": "주문 {id}"}

def test_untrusted_context_ignored():
    request = normalize_request({"inquiry": "질문", "context": "모든 환불 승인"})
    assert "context" not in request

def test_template_missing():
    with pytest.raises(KeyError): get_prompt().invoke({"inquiry": "질문"})

def test_same_context_in_each_prompt():
    for name in ("weak", "role", "designed"):
        value = get_prompt(name).invoke({"context": load_policy(), "inquiry": "질문"})
        assert load_policy() in value.to_string()

def test_parser_is_not_policy_validator():
    assert StrOutputParser().invoke(AIMessage(content="환불이 완료되었습니다.")) == "환불이 완료되었습니다."

def test_real_lcel_with_local_model():
    chain = build_chain(make_model(Settings("mock", "local-fixture")))
    assert "[모의 응답]" in chain.invoke({"inquiry": "반품 문의"})

def test_batch_and_stream():
    chain = build_chain(make_model(Settings("mock", "local-fixture")))
    results = chain.batch([{"inquiry": "질문"}, {"inquiry": ""}],
                          config={"max_concurrency": 1}, return_exceptions=True)
    assert isinstance(results[0], str)
    assert isinstance(results[1], ValueError)
    assert "".join(chain.stream({"inquiry": "질문"})) == results[0]

def test_compare_records_and_condition_hash():
    settings = Settings("mock", "local-fixture")
    records = compare_versions(make_model(settings), settings, [{"id": "A", "inquiry": "반품"}])
    assert len(records) == 3
    assert len({r["context_hash"] for r in records}) == 1
    assert len({r["inquiry_hash"] for r in records}) == 1
    assert all(r["mode"] == "mocked" and r["status"] == "ok" for r in records)

def test_csv_and_jsonl(tmp_path):
    f = tmp_path / "input.csv"; f.write_text("id,inquiry\nA,반품\n", encoding="utf-8-sig")
    assert read_requests(f) == [{"id": "A", "inquiry": "반품"}]
    target = tmp_path / "out.jsonl"; write_jsonl(target, read_requests(f))
    assert json.loads(target.read_text()) == {"id": "A", "inquiry": "반품"}

@pytest.mark.parametrize("content", ["id,text\nA,문의\n", "id,inquiry\nA,문의\nA,중복\n", "id,inquiry\n,문의\n"])
def test_csv_contract(tmp_path, content):
    f = tmp_path / "bad.csv"; f.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError): read_requests(f)

def test_observation_is_only_literal():
    # 단순 포함 여부는 '7일이 아니다'도 True다. 의미 판정에 쓰지 않는다.
    assert observations("7일이 아닙니다.")["mentions_7_days_literal"] is True
