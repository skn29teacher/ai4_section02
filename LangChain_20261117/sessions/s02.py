from langchain_core.prompts import ChatPromptTemplate


def main():
    prompt = ChatPromptTemplate.from_messages([
        ("system", "당신은 {role}입니다. 근거가 없으면 추가 정보를 요청하세요."),
        ("human", "{inquiry}")
    ])
    print("필수 변수:", sorted(prompt.input_variables))
    data = {"role": "상담원 초안 작성 도우미", "inquiry": "주문 {order_id}의 배송을 알려주세요."}
    for message in prompt.invoke(data).to_messages():
        print(message.type, "=>", message.content)
    try:
        prompt.invoke({"inquiry": "반품 문의"})
    except KeyError:
        print("의도한 오류 재현: role 값이 누락되었습니다.")

if __name__ == "__main__":
    main()
