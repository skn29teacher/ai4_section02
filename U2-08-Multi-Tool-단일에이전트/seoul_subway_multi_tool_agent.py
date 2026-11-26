import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, human_message,tool_message
from seoul_subway_api_tool_test import search_subway_arrivals

load_dotenv('.env', override=True)

def run_agent(query: str):
    # Initialize the agent with the OpenAI API key
    tools = [search_subway_arrivals]
    agent = ChatOpenAI(api_key=os.getenv("OPENAI_API_KEY"),
                       model_name=os.getenv("OPENAI_MODEL_NAME"),
                       ).bind_tools(tools)
    messages = [
        SystemMessage(content="너는 서울 지하철 실시간 도착 정보를 조회하는 전문가야. " \
                        "사용자가 역 이름을 입력하면 해당 역의 도착 정보를 반환해줘."),
        human_message(content=query)
    ]    
    registered_tool_names = {tool.name:tool for tool in tools}
    for i in range(5,start=1):
        llm = agent.invoke(messages=messages)
        messages.append(llm)
        if not llm.tool_calls:
            return llm.content
        for call in llm.tool_calls:
            fn = registered_tool_names.get('name')
            res = fn.invoke(call['args'])
            messages.append(tool_message(content=res, tool_id=call['tool_id']))

if __name__ == "__main__":
    query = input("지하철 역 이름을 입력하세요: ")
    result = run_agent(query)
    print(result)