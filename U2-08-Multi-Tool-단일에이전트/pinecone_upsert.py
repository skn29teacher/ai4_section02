import math
import os
from typing import Literal
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field
from pinecone import Pinecone

load_dotenv('.env',override=True)

OPENAI_API_KEY=os.get("OPENAI_API_KEY")
OPENAI_EMBEDDING_MODEL=os.get("OPENAI_EMBEDDING_MODEL")
PINECONE_API_KEY=os.get("PINECONE_API_KEY")
PINECONE_INDEX_NAME=os.get("PINECONE_INDEX_NAME")
PINECONE_NAMESPACE=os.get("PINECONE_NAMESPACE")

# 사내 지식베이스 문서 (상품 가이드 + 환불/보증 정책)
KNOWLEDGE_DOCS = [
    {
        "id": "kb-01",
        "doc_type": "catalog",
        "sku": "SKU-101",
        "text": "SKU-101 저소음 적축 무선 기계식 키보드: 사무실·도서관 환경에 적합한 조용한 타건감, 블루투스 5.1 및 2.4GHz 동글 지원, 맥/윈도우 겸용.",
    },
    {
        "id": "kb-02",
        "doc_type": "catalog",
        "sku": "SKU-102",
        "text": "SKU-102 USB-C 8-in-1 PD 멀티 허브: 4K 60Hz HDMI 출력, 100W PD 충전 패스스루, SD카드 리더 및 기가비트 유선랜 탑재. 외근·출장용 추천.",
    },
    {
        "id": "kb-03",
        "doc_type": "catalog",
        "sku": "SKU-103",
        "text": "SKU-103 알루미늄 각도조절 노트북 스탠드: 17인치 노트북까지 거치 가능, 발열 해소 통풍 설계, 거북목 예방용 데스크 셋업 추천.",
    },
    {
        "id": "kb-04",
        "doc_type": "policy",
        "sku": "NONE",
        "text": "환불 및 반품 규정: 상품 배송 완료 후 7일 이내(days_since_delivery <= 7)에만 단순 변심 환불이 가능합니다. 배송 완료 후 7일이 초과된 주문은 단순 변심 환불이 불가합니다.",
    },
    {
        "id": "kb-05",
        "doc_type": "policy",
        "sku": "NONE",
        "text": "VIP 및 대량 구매 안내: 동일 상품 2개 이상 주문 시 무료 당일 출고 대상이며, 재고가 0개인 품절 상품은 예약 주문을 받지 않습니다.",
    },
]
def upsert_knowledge_docs()->None:
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY가 설정되어 있지 않습니다.")
    embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL,api_key=OPENAI_API_KEY)
    vectors = embeddings.embed_documents( [doc['text'] for doc in KNOWLEDGE_DOCS] )

    records = [
        {
            'id':doc['id'],
            'values':vec,
            'metadata':{
                "doc_type":doc['doc_type'],
                'sku':doc['sku'],
                'text':doc['text']
            },
        }
        
        for doc, vec in zip(KNOWLEDGE_DOCS,vectors)
    ]
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index = pc.Index(PINECONE_INDEX_NAME)
    upsert_kwargs = {'vectors':records}
    if PINECONE_NAMESPACE:
        upsert_kwargs['namespace'] = PINECONE_NAMESPACE
    res = index.upsert(**upsert_kwargs)
    print("upsert 완료",res)

if __name__=="__main__":
    upsert_knowledge_docs()
