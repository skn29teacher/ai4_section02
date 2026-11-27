# 도메인별 전용 @tool 및 외부 FastAPI 벡엔드 구성
# 분기 파이프라인을 위한 도구 그룹화
    # 라우터가 선택할수 있도록 기능군별로 명확히 그룹화
    # SEARCH_TOOLS = [search_store_docs]
    # READ_API_TOOLS = [api_get_product, api_get_order]
    # ACTION_API_TOOLS = [api_get_product,api_get_order, api_create_order,api_refund_order]

import math
import os
import threading
import time
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().with_name(".env"), override=True)

API_HOST = "127.0.0.1"
API_PORT = 8010
API_BASE_URL = f"http://{API_HOST}:{API_PORT}"

# ==============================================================================
# 1. 모의 외부 REST API (FastAPI)
# ==============================================================================
api_app = FastAPI(title="Routing Lab Store API")

PRODUCTS_DB = {
    "SKU-101": {"sku": "SKU-101", "name": "저소음 무선 기계식 키보드", "price": 129000, "stock": 6},
    "SKU-102": {"sku": "SKU-102", "name": "USB-C 8-in-1 멀티 허브", "price": 49000, "stock": 12},
    "SKU-103": {"sku": "SKU-103", "name": "알루미늄 노트북 스탠드", "price": 39000, "stock": 0},
}

ORDERS_DB = {
    "ORD-5001": {"order_id": "ORD-5001", "sku": "SKU-101", "quantity": 1, "total": 129000, "status": "DELIVERED", "days_passed": 3},
    "ORD-5002": {"order_id": "ORD-5002", "sku": "SKU-102", "quantity": 2, "total": 98000, "status": "DELIVERED", "days_passed": 14},
}


class OrderReq(BaseModel):
    sku: str
    quantity: int


class RefundReq(BaseModel):
    order_id: str
    reason: str


@api_app.get("/products/{sku}")
def get_product(sku: str):
    item = PRODUCTS_DB.get(sku.upper())
    if not item:
        raise HTTPException(status_code=404, detail="상품 없음")
    return item


@api_app.post("/orders")
def create_order(req: OrderReq):
    item = PRODUCTS_DB.get(req.sku.upper())
    if not item:
        raise HTTPException(status_code=404, detail="상품 없음")
    if item["stock"] < req.quantity:
        raise HTTPException(status_code=409, detail=f"재고 부족 (현재 {item['stock']}개)")
    item["stock"] -= req.quantity
    oid = f"ORD-{5000 + len(ORDERS_DB) + 1}"
    record = {
        "order_id": oid,
        "sku": item["sku"],
        "quantity": req.quantity,
        "total": item["price"] * req.quantity,
        "status": "CONFIRMED",
        "remaining_stock": item["stock"],
    }
    ORDERS_DB[oid] = record
    return record


@api_app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = ORDERS_DB.get(order_id.upper())
    if not order:
        raise HTTPException(status_code=404, detail="주문 없음")
    return order


@api_app.post("/orders/refund")
def refund_order(req: RefundReq):
    order = ORDERS_DB.get(req.order_id.upper())
    if not order:
        raise HTTPException(status_code=404, detail="주문 없음")
    if order["status"] == "REFUNDED":
        raise HTTPException(status_code=409, detail="이미 환불됨")
    order["status"] = "REFUNDED"
    return {"order_id": order["order_id"], "status": "REFUNDED", "reason": req.reason, "refund_amount": order["total"]}


def start_mock_api_background() -> None:
    """실습 편의를 위해 FastAPI 서버를 데몬 스레드로 1회 구동합니다."""
    try:
        httpx.get(f"{API_BASE_URL}/products/SKU-101", timeout=0.5)
        return
    except Exception:
        pass

    config = uvicorn.Config(api_app, host=API_HOST, port=API_PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(0.8)


# ==============================================================================
# 2. 그룹별 @tool 정의 (검색 / 조회 API / 실행 API)
# ==============================================================================
KB_DOCS = [
    {"id": "doc-1", "type": "catalog", "text": "SKU-101 저소음 무선 기계식 키보드: 사무실·도서관 추천, 조용한 적축, 맥/윈도우 지원."},
    {"id": "doc-2", "type": "catalog", "text": "SKU-102 USB-C 8-in-1 멀티 허브: 출장·외근 추천, 4K HDMI, 100W PD 충전, 랜포트 지원."},
    {"id": "doc-3", "type": "catalog", "text": "SKU-103 알루미늄 노트북 스탠드: 거북목 방지, 각도 조절, 17인치 거치 가능."},
    {"id": "doc-4", "type": "policy", "text": "환불 정책: 배송 완료 후 7일 이내(days_passed <= 7) 주문만 단순 변심 환불 가능. 7일 초과 시 환불 불가."},
]


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b)) / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) + 1e-12)


class SearchInput(BaseModel):
    query: str = Field(..., description="검색할 상품 특징 또는 스토어 정책 질문")
    top_k: int = Field(default=2, ge=1, le=4)


@tool(args_schema=SearchInput)
def search_store_docs(query: str, top_k: int = 2) -> list[dict]:
    """상품 카탈로그 추천 정보와 환불/배송 정책 문서를 벡터 검색합니다."""
    emb = OpenAIEmbeddings(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    qv = emb.embed_query(query)
    dvs = emb.embed_documents([d["text"] for d in KB_DOCS])
    ranked = sorted(
        [{"id": d["id"], "type": d["type"], "score": round(_cos(qv, dv), 4), "text": d["text"]} for d, dv in zip(KB_DOCS, dvs)],
        key=lambda x: x["score"],
        reverse=True,
    )
    return ranked[:top_k]


@tool
def api_get_product(sku: str) -> dict:
    """외부 API에서 상품 코드(sku)의 실시간 가격과 재고 수량을 조회합니다."""
    r = httpx.get(f"{API_BASE_URL}/products/{sku.strip()}", timeout=5.0)
    return r.json() if r.status_code == 200 else {"error": r.json(), "status": r.status_code}


@tool
def api_get_order(order_id: str) -> dict:
    """외부 API에서 주문 번호(order_id)의 상태와 배송 경과일(days_passed)을 조회합니다."""
    r = httpx.get(f"{API_BASE_URL}/orders/{order_id.strip()}", timeout=5.0)
    return r.json() if r.status_code == 200 else {"error": r.json(), "status": r.status_code}


@tool
def api_create_order(sku: str, quantity: int) -> dict:
    """외부 API를 호출해 상품(sku)을 수량(quantity)만큼 실제로 주문합니다."""
    r = httpx.post(f"{API_BASE_URL}/orders", json={"sku": sku.strip(), "quantity": quantity}, timeout=5.0)
    return r.json() if r.status_code == 200 else {"error": r.json(), "status": r.status_code}


@tool
def api_refund_order(order_id: str, reason: str) -> dict:
    """외부 API를 호출해 주문 번호(order_id)에 대한 환불을 실제로 접수합니다."""
    r = httpx.post(f"{API_BASE_URL}/orders/refund", json={"order_id": order_id.strip(), "reason": reason.strip()}, timeout=5.0)
    return r.json() if r.status_code == 200 else {"error": r.json(), "status": r.status_code}


SEARCH_TOOLS = [search_store_docs]
READ_API_TOOLS = [api_get_product, api_get_order]
ACTION_API_TOOLS = [api_get_product, api_get_order, api_create_order, api_refund_order]
ALL_TOOLS = [search_store_docs, api_get_product, api_get_order, api_create_order, api_refund_order]


if __name__ == "__main__":
    uvicorn.run(api_app, host=API_HOST, port=API_PORT)
