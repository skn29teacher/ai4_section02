"""선택한 문제의 계산 도구를 실행하고 단계별 결과를 출력한다."""

import argparse
import json

from lesson import calculate, prompt, react
from providers import RemoteChat
from s02 import records
from s03 import MODES


REACT_INSTRUCTION = """주어진 문제를 계산 도구로 푼다.
한 번에 JSON 객체 하나만 출력한다.
계산을 요청할 때는 {"action":"연산명","a":정수,"b":정수} 형식을 사용한다.
Observation은 계산 도구가 반환한 값이다. 다음 계산에 필요한 값을 이전 결과에서 가져온다.
계산을 마치면 {"final":"단위를 포함한 한국어 답"} 형식으로 답한다."""


def calculate_egg_sales(action, a, b):
    """달걀 수량, 백분율, 판매 수익을 계산한다."""
    if action == "percent":
        if type(a) is not int or type(b) is not int:
            raise ValueError("수량과 백분율은 정수여야 합니다.")
        if a < 0 or not 0 <= b <= 100:
            raise ValueError("수량은 0 이상, 백분율은 0~100이어야 합니다.")

        count, remainder = divmod(a * b, 100)
        if remainder:
            raise ValueError("계산 결과가 달걀 한 개 단위로 나누어지지 않습니다.")
        return count

    if action not in ("multiply", "subtract", "add"):
        raise ValueError(f"달걀 문제에서 지원하지 않는 연산입니다: {action}")

    return calculate(action, a, b)


def calculate_sprint_distance(action, a, b):
    """훈련 횟수와 거리를 곱한다."""
    if action != "multiply":
        raise ValueError(f"달리기 문제에서 지원하지 않는 연산입니다: {action}")

    return calculate(action, a, b)


def egg_sales_demo(inputs):
    """계산 요청을 보내고 실제 도구가 반환한 값을 다음 계산에 사용한다."""
    total = yield ("multiply", inputs["ducks"], inputs["eggs_per_duck"])
    given = yield ("percent", total, inputs["giveaway_percent"])
    remaining = yield ("subtract", total, given)
    hatching = yield ("percent", remaining, inputs["hatching_percent"])
    sold = yield ("subtract", remaining, hatching)
    revenue = yield ("multiply", sold, inputs["price_per_egg"])
    unsold = yield ("add", given, hatching)

    return f"판매 수익은 {revenue}달러, 미판매 달걀은 {unsold}개입니다."


def sprint_distance_demo(inputs):
    weekly_sprints = yield (
        "multiply",
        inputs["sessions_per_week"],
        inputs["sprints_per_session"],
    )
    distance = yield ("multiply", weekly_sprints, inputs["meters_per_sprint"])

    return f"주간 총거리는 {distance}미터입니다."


def make_demo_chat(steps):
    def chat(messages):
        last_message = messages[-1]["content"]

        try:
            if len(messages) == 2:
                action, a, b = next(steps)
            else:
                observation = int(last_message.removeprefix("Observation: "))
                action, a, b = steps.send(observation)
        except StopIteration as finished:
            return json.dumps({"final": finished.value}, ensure_ascii=False)

        return json.dumps({"action": action, "a": a, "b": b})

    return chat


def trace(row, remote, events):
    if row["row_index"] == 0:
        tool = calculate_egg_sales
        demo = egg_sales_demo
        rules = (
            "사용 가능한 연산은 multiply, subtract, add, percent이다. "
            "percent(a, b)는 수량 a의 b퍼센트를 계산한다. "
            "미판매 수량에는 이웃에게 준 달걀과 부화용 달걀이 모두 포함된다. "
            "최종 답에는 판매 수익과 미판매 수량을 모두 쓴다."
        )
    elif row["row_index"] == 3:
        tool = calculate_sprint_distance
        demo = sprint_distance_demo
        rules = (
            "사용 가능한 연산은 multiply이다. "
            "주간 전력 질주 횟수를 구한 뒤 한 번의 거리를 곱한다."
        )
    else:
        raise ValueError(f"지원하지 않는 행입니다: {row['row_index']}")

    messages = prompt(f"{REACT_INSTRUCTION}\n{rules}", row["question"])
    events.append(("선택한 계산 함수", tool.__name__))

    if remote is None:
        chat = make_demo_chat(demo(row["demo_inputs"]))
    else:
        chat = remote

    react(messages, chat, events, tool=tool, max_steps=8)
    return messages


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--row", type=int, choices=[0, 3], default=3)
    parser.add_argument("--provider", choices=MODES, default="demo")
    args = parser.parse_args()

    row = next(record for record in records() if record["row_index"] == args.row)    

    
    print("실행 모드", args.provider)
    print("입력 질문", row["question"], sep="\n")

    remote = None
    if args.provider != "demo":
        remote = RemoteChat(args.provider, max_calls=8)

    events = []
    try:
        trace(row, remote, events)
    finally:
        for label, body in events:
            print(label, body, sep="\n")