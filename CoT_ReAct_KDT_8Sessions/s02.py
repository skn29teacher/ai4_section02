"""같은 질문에 정답 지시와 풀이 예시를 각각 결합한다."""
import argparse
import json
from lesson import ROOT, COT, prompt

DIRECT = '''
"당신은 수학 문제 해결 전문가입니다. "
        "문제에 주어진 조건을 정확하게 파악하세요. "
        "계산에 필요한 정보를 구분하고, "
        "계산 과정을 순서대로 수행하세요. "
        "각 단계에서 사용한 계산식과 단위를 명확하게 표시하고, "
        "마지막에 최종 정답을 제시하세요."
'''
WORKED = COT + "\n마지막 줄은 '답: 숫자 단위'로 작성한다. 예: 답: 3자루"


def records():
    return json.loads((ROOT / "data/problems.json").read_text(encoding="utf-8"))


def variants(row):
    return {name: prompt(instruction, row["question"])
            for name, instruction in [("direct", DIRECT), ("cot", WORKED)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--row", choices=[0, 3], type=int, default=0)
    args = parser.parse_args()
    row = next(r for r in records() if r["row_index"] == args.row)
    for name, messages in variants(row).items():
        print(name)
        for message in messages:
            print(message["role"], message["content"], sep="\n")
