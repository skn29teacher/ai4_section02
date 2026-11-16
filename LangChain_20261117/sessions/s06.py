import argparse
from app.config import Settings
from app.providers import make_model, friendly_error
from app.pipeline import build_chain, load_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--stream", action="store_true")
    args = parser.parse_args()
    settings = Settings.read(args.mock)
    chain = build_chain(make_model(settings))
    inputs = [{"inquiry": c["inquiry"]} for c in load_cases()]
    print("실행:", settings.provider, settings.model)
    if args.stream:
        for chunk in chain.stream(inputs[0]):
            print(chunk, end="", flush=True)
        print()
    else:
        # batch는 공급자 Batch API가 아니다. 요청 3개, 동시성 1로 순차 처리한다.
        results = chain.batch(inputs, config={"max_concurrency": 1}, return_exceptions=True)
        for index, result in enumerate(results, 1):
            print(index, friendly_error(result) if isinstance(result, Exception) else result)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(friendly_error(error))
