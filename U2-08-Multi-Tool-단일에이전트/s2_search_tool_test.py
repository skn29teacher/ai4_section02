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
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import BaseModel, Field

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


def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-12)


class StoreSearchInput(BaseModel):
    query: str = Field(..., description="검색할 상품 특징, 추천 조건 또는 스토어 정책 질문")
    doc_type: Literal["all", "catalog", "policy"] = Field(
        default="all",
        description="문서 유형 필터 ('catalog': 상품 안내, 'policy': 환불/배송 규정, 'all': 전체)",
    )
    top_k: int = Field(default=2, ge=1, le=5, description="반환할 상위 문서 개수")  # 1<=  <=5

@tool(args_schema=StoreSearchInput)
def search_store_knowledge(query:str, doc_type:str="all",top_k:int=2)->dict:
    '''스토어 상품 가이다(sku 정보, 추천용도)와 환불 배송 정책 문서를 벡터 유사도로 검색합니다.'''
    embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL,api_key=OPENAI_API_KEY)
    q_vec = embeddings.embed_query(query)
    # 1) PINECONE_API_KEY가 설정된 경우 실제 Pinecone index.query 사용
    if PINECONE_API_KEY:
        from pinecone import Pinecone

        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
        params = {"vector": q_vec, "top_k": top_k, "include_metadata": True}
        if PINECONE_NAMESPACE:
            params["namespace"] = PINECONE_NAMESPACE
        if doc_type != "all":
            params["filter"] = {"doc_type": {"$eq": doc_type}}

        res = index.query(**params)
        matches = [
            {
                "id": m["id"],
                "score": round(float(m["score"]), 4),
                "metadata": m.get("metadata", {}),
                "text": (m.get("metadata") or {}).get("text", ""),
            }
            for m in res.get("matches", [])
        ]
        return {"source": "pinecone", "count": len(matches), "matches": matches}

    # 2) PINECONE_API_KEY 미설정 시 로컬 벡터 유사도 검색 폴백
    candidates = [d for d in KNOWLEDGE_DOCS if doc_type == "all" or d["doc_type"] == doc_type]
    doc_vecs = embeddings.embed_documents([d["text"] for d in candidates])
    scored = []
    for doc, d_vec in zip(candidates, doc_vecs):
        scored.append(
            {
                "id": doc["id"],
                "score": round(_cosine_sim(q_vec, d_vec), 4),
                "metadata": {"doc_type": doc["doc_type"], "sku": doc["sku"]},
                "text": doc["text"],
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"source": "local_vector_fallback", "count": len(scored[:top_k]), "matches": scored[:top_k]}


if __name__ == "__main__":
    print(search_store_knowledge.invoke({"query": "사무실에서 조용히 쓸 무선 키보드 추천", "doc_type": "catalog", "top_k": 2}))
    print(search_store_knowledge.invoke({"query": "배송 완료 후 며칠까지 환불 가능한가요?", "doc_type": "policy", "top_k": 1}))