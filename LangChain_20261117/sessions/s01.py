import platform
from importlib.metadata import version
from langchain_core.prompts import ChatPromptTemplate


def main():
    print("Python:", platform.python_version())
    for package in ("langchain-core", "langchain-openai", "python-dotenv"):
        print(package, version(package))
    prompt = ChatPromptTemplate.from_template("고객 문의: {inquiry}")
    value = prompt.invoke({"inquiry": "미사용 상품을 반품하고 싶어요."})
    print("API 호출 없음 /", type(value).__name__)
    print(value.to_messages()[0].content)

if __name__ == "__main__":
    main()
