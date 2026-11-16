import argparse
from app.config import Settings, ROOT
from app.providers import make_model, friendly_error
from app.pipeline import load_cases, write_jsonl
from app.compare import compare_versions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--repeats", type=int, default=1, choices=[1, 2, 3])
    args = parser.parse_args()
    settings = Settings.read(args.mock)
    rows = compare_versions(make_model(settings), settings, load_cases(), args.repeats)
    out = ROOT / "outputs" / f"comparison_{settings.provider}.jsonl"
    write_jsonl(out, rows)
    print("case version status seconds chars")
    for r in rows:
        print(r["case_id"], r["version"], r["status"], r["elapsed_seconds"],
              r.get("observations", {}).get("characters", "-"))
    print("저장:", out)
    print("모의 결과로 프롬프트 품질 우열을 판단하지 않습니다." if settings.provider == "mock" else "원문 답변을 정책과 대조하세요. 관측값은 의미 품질 점수가 아닙니다.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(friendly_error(error))
