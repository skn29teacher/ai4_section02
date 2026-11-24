# @tool 데코레이터 캡슐화와 스키마 자동 추출
import json
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv('.env',override=True)

@tool
def calc_sla_penalty(planned_hours:int, actual_hours:int, hourly_rate:int = 10000)->dict:
    '''예정처리시간(planned_hours) 대비 실제 소요시간(actual_hours) 초과분에 대한 SLA 패털티를 계산한다'''
    delay_hours = max(0, actual_hours - planned_hours)
    panalty_krw = delay_hours*hourly_rate
    return {
        'planned_hours':planned_hours,
        'actual_hours':actual_hours,
        'delay_hours':delay_hours,
        'panalty_krw':panalty_krw,
    }

if __name__ =='__main__':
    print('@tool 변환 결과')
    print('도구이름',calc_sla_penalty.name)
    print('도구설명',calc_sla_penalty.description)
    print('자동생성 JSON Schema : ')
    print(  json.dumps(calc_sla_penalty.args_schema.model_json_schema(),
                    #    indent=2,
                    #    ensure_ascii=False
                       )
        )
    
