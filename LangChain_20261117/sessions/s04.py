import argparse
from langchain_core.output_parsers import StrOutputParser
from app.config import Settings
from app.providers import make_model, friendly_error
from app.prompts import get_prompt
from app.pipeline import load_policy, load_cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--manual", action="store_true")
    args = parser.parse_args()
    settings = Settings.read(args.mock)
    model = make_model(settings)
    prompt = get_prompt().partial(context=load_policy())
    inputs = {"inquiry": load_cases()[0]["inquiry"]}
    output_parser = StrOutputParser()
    print(settings.provider, settings.model)
    if args.manual:
        value = prompt.invoke(inputs)
        message = model.invoke(value)
        result = output_parser.invoke(message)
        print("타입:", type(value).__name__, type(message).__name__, type(result).__name__)
    else:
        chain = prompt | model | output_parser
        result = chain.invoke(inputs)
    print(result)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        raise SystemExit(friendly_error(error))
