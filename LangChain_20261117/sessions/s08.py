import argparse
from datetime import datetime
from app.config import ROOT, Settings
from app.providers import make_model, friendly_error
from app.pipeline import build_chain, read_requests, write_jsonl


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--input", type=str, default=str(ROOT / "data/requests.csv"))
    parser.add_argument("--limit", type=int, default=3, choices=range(1, 6))
    args = parser.parse_args()
    requests = read_requests(args.input)[:args.limit]
    settings = Settings.read(args.mock)
    chain = build_chain(make_model(settings))
    results, errors = [], []
    for row in requests:
        try:
            draft = chain.invoke({"inquiry": row["inquiry"]})
            results.append({"id": row["id"], "draft": draft, "provider": settings.provider,
                            "model": settings.model, "mode": "mocked" if args.mock or settings.provider == "mock" else "remote"})
        except Exception as error:
            errors.append({"id": row["id"], "error": friendly_error(error)})
            if getattr(error, "status_code", None) == 429:
                break  # 공급자 한도에서는 이후 항목도 호출하지 않는다.
    run = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    folder = ROOT / "outputs" / f"run_{run}"
    write_jsonl(folder / "drafts.jsonl", results)
    write_jsonl(folder / "errors.jsonl", errors)
    print(f"성공 {len(results)} / 오류 {len(errors)} / 선택 {len(requests)}")
    print("결과:", folder)
    print("초안을 검토한 뒤 사용하세요.")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(friendly_error(error))
