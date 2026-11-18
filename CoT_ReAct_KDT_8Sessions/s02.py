"""같은 질문에 정답 지시와 풀이 예시를 각각 결합한다."""
import argparse
import json
from lesson import ROOT, COT, prompt

DIRECT = '''
"당신은 수학 문제 해결 전문가입니다. "
        "사용자가 제시한 문제의 모든 조건을 정확하게 파악하고 "
        "필요한 계산을 수행하여 정답을 구하세요. "
        "문제에 포함된 수량, 비율, 계산 기준 및 조건의 적용 순서를 "
        "혼동하지 않도록 주의하세요. "
        "중간 계산 과정이나 풀이 설명은 출력하지 마세요. "
        "최종 정답만 간결하고 명확하게 출력하세요. "
        "여러 항목을 묻는 경우 모든 항목의 정답을 빠짐없이 제시하세요. "
        "문제에 주어진 정보만 사용하고 임의로 조건을 추가하지 마세요."
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