from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from common.prompts import make_prompt, validate_input
from common.data import first_input
from common.runtime import make_model

def observe(title, action):
    try:
        action()
    except (KeyError, ValueError, TypeError) as exc:
        print(title, type(exc).__name__)
        return
    raise AssertionError('예상한 오류가 발생하지 않았습니다: ' + title)

def main():
    observe('변수 누락', lambda: make_prompt().invoke({'notice':'점검'}))
    observe('공백 입력', lambda: validate_input({**first_input(), 'notice':'  '}))
    observe('타입 오류', lambda: validate_input({**first_input(), 'notice':123}))
    # JSON 리터럴 중괄호는 {{ }}로 이스케이프한다.
    fixed = ChatPromptTemplate.from_template('예시: {{"title": "공지"}}\n내용: {notice}')
    print(fixed.invoke({'notice':'점검'}).to_messages()[0].content)
    chain = RunnableLambda(validate_input) | make_prompt() | make_model(mock=True) | StrOutputParser()
    print('수정 후:', chain.invoke(first_input()))

if __name__ == '__main__':
    main()
