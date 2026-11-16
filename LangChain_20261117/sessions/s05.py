import argparse
from app.config import Settings
from app.providers import make_model, friendly_error
from app.pipeline import build_chain


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--inquiry", default="  미사용 상품의 반품 조건을 알려주세요.  ")
    args = parser.parse_args()
    settings = Settings.read(args.mock)
    chain = build_chain(make_model(settings))
    print("입력:", repr(args.inquiry))
    print(chain.invoke({"inquiry": args.inquiry}))

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(friendly_error(error))
