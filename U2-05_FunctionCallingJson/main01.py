# @tool 이나 프레임웍크 추상화를 제거, 순수 OpenAI SDK 레벨에서 
# tool선언 -> tool_calls추출 -> role="tool" 
# 3단계로 되어 있는 왕복루프를 눈으로 직접확인

import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv('.env',override=True)

#1.실제 실행될 함수(모델은 이 함수의 존재와 구현을 모름)
def calculate_shipping_free(weight_kg:float, is_express: bool = False)->dict:
    """택배 무개와 당일/빠른 배송 여부를 받아 예상 배송비를 계산"""
    base_fee = 3000 if weight_kg <=3.0 else 3000+(weight_kg-3.0)*1000
    express_fee = 2500 if is_express else 0
    total_fee = int(round(base_fee+express_fee))
    return {
        'weight_kg':weight_kg,
        'is_express':is_express,
        "shipping_fee_krw" : total_fee
    }
#2.API에 전달할 tool 선언
tools = [
{
    "type": "function",
    "function": {
        "name": "calculate_shipping_fee",
        "description": "택배 무게(kg)와 빠른 배송 여부를 기준으로 배송비를 계산합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "weight_kg": {
                    "type": "number",
                    "description": "택배 무게 (단위: kg)",
                },
                "is_express": {
                    "type": "boolean",
                    "description": "빠른 배송 여부 (기본값 false)",
                },
            },
            "required": ["weight_kg"],
        },
    },
}    
]