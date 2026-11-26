# 검색도구 입축력 설계
    # LLM이 자연어 질의를 던지면, 검색도구는 유사도 점수(score), 메타데이터(doc_type) 원문(text)을 함께 반환해야 
    # 모델이 근거 기반으로 판단할 수 있음
# 유사도 점수(score) 코사인 유사도 / 맨허튼 거리
    # 벡터 라는 수백차원의 방향성이 있는 데이터로 구성되어 있는 집합에서 단어사이의 거리
# faultback(폴백)
    # 실패시 동작하는 함수나 기능
    # pinecone 이 검색에 시패했을 경우 사용자가 유사도계산 함수를 만들어서 제공

import math
import os
from typing import Literal
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv('.env',override=True)

