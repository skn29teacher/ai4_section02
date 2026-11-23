# Function Calling JSON Schema

import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv('.env',override=True)
client = OpenAI()

def estimate_cloud_cost(instance_size:str, hours:int, region:str="ap-northeast-2")->dict:
    hourly_rates = {'small':0.05,'medium':0.15,"large":0.40}
    rate = hourly_rates.get(instance_size, 0.15)
    return {
        'instance_size':instance_size,
        'hours':hours,
        'region':region,
        'estimated_usd':round(rate*hours,2)
    }

# 모호한 스키마 vs 명시적 단위,설명 스키마 비교
WEAK_SHEMA=[
    {
        'type':'function',
        'function':{
            'name':'estimate_cloud_cost',
            'description':'비용계산',
            'parameters':{
                'instance_size':{'type':'string'},
                'hours':{'type':'integer'},
                'region':{'type':'string'},
            },
            'required':['instance_size','hours']
        }
    }
]

CLEAR_SHEMA=[
    {
        
    }
]