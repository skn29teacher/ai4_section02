# 검색도구 입축력 설계
    # LLM이 자연어 질의를 던지면, 검색도구는 유사도 점수(score), 메타데이터(doc_type) 원문(text)을 함께 반환해야 
    # 모델이 근거 기반으로 판단할 수 있음
# 유사도 점수(score) 코사인 유사도 / 맨허튼 거리
    # 벡터 라는 수백차원의 방향성이 있는 데이터로 구성되어 있는 집합에서 단어사이의 거리
# faultback(폴백)
    # 실패시 동작하는 함수나 기능
    # pinecone 이 검색에 시패했을 경우 사용자가 유사도계산 함수를 만들어서 제공

from pinecone_upsert import *

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
    '''스토어 상품 가이드(sku 정보, 추천용도)와 환불 배송 정책 문서를 벡터 유사도로 검색합니다.'''
    embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL,api_key=OPENAI_API_KEY)
    q_vec = embeddings.embed_query(query)
    # 1) PINECONE_API_KEY가 설정된 경우 실제 Pinecone index.query 사용
    # PINECONE_API_KEY = None  # faultback 테스트
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