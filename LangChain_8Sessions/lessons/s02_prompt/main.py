from common.prompts import make_prompt
from common.data import first_input
from common.runtime import run_safely

def main():
    prompt = make_prompt()
    print('필수 변수:', sorted(prompt.input_variables))
    value = prompt.invoke(first_input())
    for message in value.to_messages():
        print(message.type, ':', message.content)
    formal = prompt.partial(tone='격식 있게')
    print('partial 후:', sorted(formal.input_variables))
    print(formal.invoke({'audience':'협력사', 'notice':'금요일까지 자료를 보내 주세요.'}).to_messages()[-1].content)

if __name__ == '__main__':
    run_safely(main)
