from langchain_core.output_parsers import StrOutputParser
from common.prompts import make_prompt
from common.data import first_input
from common.runtime import cli, make_model, run_safely

def main():
    args = cli()
    prompt = make_prompt()
    model = make_model(args.mock, args.provider)
    parser = StrOutputParser()
    value = prompt.invoke(first_input())
    response = model.invoke(value)  # 단계별 관찰: 1회
    parsed = parser.invoke(response)
    print(type(value).__name__, type(response).__name__, 'str 호환:', isinstance(parsed, str))
    chain = prompt | model | parser
    result = chain.invoke(first_input())  # LCEL 실행: 추가 1회
    print(result)

if __name__ == '__main__':
    run_safely(main)
