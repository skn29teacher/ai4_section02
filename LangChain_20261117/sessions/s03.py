from app.pipeline import load_policy, load_cases
from app.prompts import get_prompt


def main():
    case = load_cases()[0]
    data = {"context": load_policy(), "inquiry": case["inquiry"]}
    for version in ("weak", "role", "designed"):
        print("\n===", version, "API 호출 없음 ===")
        for message in get_prompt(version).invoke(data).to_messages():
            print(f"[{message.type}] {message.content}")

if __name__ == "__main__":
    main()
