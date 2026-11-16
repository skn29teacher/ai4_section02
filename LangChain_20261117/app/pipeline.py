import csv
import json
from pathlib import Path
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from app.config import ROOT
from app.prompts import get_prompt


def load_policy():
    return (ROOT / "data/policy.txt").read_text(encoding="utf-8").strip()


def normalize_request(row):
    if not isinstance(row, dict):
        raise TypeError("입력은 dict여야 합니다.")
    value = row.get("inquiry")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("inquiry는 공백이 아닌 문자열이어야 합니다.")
    value = value.strip()
    if len(value) > 1000:
        raise ValueError("inquiry는 1000자 이내여야 합니다.")
    # 원문의 의미·숫자·중괄호는 바꾸지 않는다.
    return {"inquiry": value}


def build_chain(model, version="designed"):
    # 운영자가 관리하는 정책은 시작 시 고정한다. 고객 CSV에서 context를 받지 않는다.
    prompt = get_prompt(version).partial(context=load_policy())
    return RunnableLambda(normalize_request) | prompt | model | StrOutputParser()


def load_cases():
    return json.loads((ROOT / "data/cases.json").read_text(encoding="utf-8"))


def read_requests(path):
    path = Path(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"id", "inquiry"} <= set(reader.fieldnames):
            raise ValueError("CSV 헤더에는 id,inquiry가 필요합니다.")
        rows = list(reader)
    if len(rows) > 100:
        raise ValueError("수업용 CSV는 최대 100행입니다.")
    ids = [r["id"].strip() for r in rows]
    if any(not x for x in ids) or len(ids) != len(set(ids)):
        raise ValueError("id는 공백 없이 고유해야 합니다.")
    return [dict(r, id=r["id"].strip()) for r in rows]


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 한국어를 그대로 저장한다. 같은 경로 재실행 시 덮어쓴다.
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
