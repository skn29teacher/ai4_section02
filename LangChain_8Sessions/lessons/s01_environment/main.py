from importlib.metadata import version
from common.runtime import cli, make_model, run_safely
from langchain_core.prompts import ChatPromptTemplate

def main():
    args = cli()
    for name in ['langchain', 'langchain-core', 'langchain-openai']:
        print(name, version(name))
    prompt = ChatPromptTemplate.from_messages([
        ('system', '한국어로 한 문장만 답하세요.'),
        ('human', '{question}'),
    ])
    value = prompt.invoke({'question':'프롬프트 템플릿의 목적은 무엇인가요?'})
    print('렌더링 타입:', type(value).__name__)
    model = make_model(args.mock, args.provider)
    response = model.invoke(value)
    print('응답 타입:', type(response).__name__)
    print(response.content)

if __name__ == '__main__':
    run_safely(main)
