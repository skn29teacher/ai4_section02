import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool

load_dotenv('.env', override=True)

@tool
def multiply(a:int, b:int)->int:
    '''두 정수를 곱합니다.'''
    return a * b

llm = ChatOpenAI(model='gpt-4o-mini',temperature=0)
llm_with_tools = llm.bind_tools([multiply])
response =  llm_with_tools.invoke("7과 8을 곱한 결과를 알려줘")
print(response)
print("="*80)
print(response.tool_calls)