# bind_tools() 바인딩 AIMessage.tool_calls 동적생성
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI  # OpenAI

load_dotenv('.env',override=True)

@tool
def get_cluster_load(cluster_name: str) ->dict:
    '''클러스터명(prod-a, prod-b, staging)의 cpu 및 메모리 사용률을 조회합니다.'''
    data = {
        'prod-a':{'cpu_pct':68.5, 'mem_pct':74.0},
        'prod-b':{'cpu_pct':58.5, 'mem_pct':54.0},
        'staging':{'cpu_pct':38.5, 'mem_pct':34.0},
    }
    key = cluster_name.lower()
    return {"cluster":key, **data.get(key, {'cpu_pct':0.0, 'mem_pct':0.0})}

if __name__ =='__main__':
    base_llm = ChatOpenAI(model='gpt-4o-mini',temperature=0)
    bound_llm = base_llm.bind_tools([get_cluster_load])
    query = 'prod-a 클러스터의 현재 cpu와 메모리 사용률을 확인해줘'
    messages = [HumanMessage(content=query)]
    ai_msg = bound_llm.invoke(messages)
    messages.append(ai_msg)
    
    print('AIMessage.content:',ai_msg.content)
    print('AIMessage.tool_calls:',ai_msg.tool_calls)  
    
    fns = {'get_cluster_load': get_cluster_load}
    # 함수바인딩후 함수실행  그리고 최종 llm 답변
    for call in ai_msg.tool_calls:
        rs = fns[call['name']].invoke(call['args'])        
        messages.append(
            ToolMessage(
                content=str(rs),
                tool_call_id=call['id'],
            )
        )

    final_msg = base_llm.invoke(messages)
    print('최종 답변:', final_msg.content)
      
