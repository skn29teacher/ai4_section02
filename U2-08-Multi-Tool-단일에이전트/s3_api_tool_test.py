# 외부 API 연동 도구(@tool) 구현 및 예외 정규화
# HTTP 예외의 구조화 반환:
    # API 호출도구가 raise HTT.... 프로그램 자체를 죽이면 에이전트 루프가 종료
    # 대신 {'ok':False, 'status_code':409 ...} 변환하면 LLM이 상황을 이해하고
    # 사용자에게 대안을 제시하거나 다른 도구를호출
# 입력 스키마 검증(pydantic)

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

API_BASE_URL = "http://127.0.0.1:8000"


class ProductSkuInput(BaseModel):
    sku: str = Field(..., description="조회할 상품 코드 (예: SKU-101, SKU-102, SKU-103)")


class OrderCreateInput(BaseModel):
    sku: str = Field(..., description="주문할 상품 코드 (예: SKU-101)")
    quantity: int = Field(..., ge=1, le=20, description="주문 수량 (1~20 정수)")


class OrderIdInput(BaseModel):
    order_id: str = Field(..., description="조회할 주문 번호 (예: ORD-5001)")


class RefundInput(BaseModel):
    order_id: str = Field(..., description="환불 접수할 주문 번호 (예: ORD-5001)")
    reason: str = Field(..., min_length=2, description="환불 사유")


@tool(args_schema=ProductSkuInput)
def get_product_inventory(sku: str) -> dict:
    """외부 API를 호출해 상품 코드(sku)의 실시간 가격과 현재 재고 수량을 조회합니다."""
    try:
        r = httpx.get(f"{API_BASE_URL}/api/products/{sku.strip()}", timeout=5.0)
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "status_code": r.status_code, "error": r.json()}
    except Exception as exc:
        return {"ok": False, "error": f"API 연결 실패: {exc}"}


@tool(args_schema=OrderCreateInput)
def create_store_order(sku: str, quantity: int) -> dict:
    """외부 API를 호출해 지정된 상품(sku)과 수량(quantity)으로 실제 주문을 생성하고 재고를 차감합니다."""
    try:
        r = httpx.post(
            f"{API_BASE_URL}/api/orders",
            json={"sku": sku.strip(), "quantity": quantity},
            timeout=5.0,
        )
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "status_code": r.status_code, "error": r.json()}
    except Exception as exc:
        return {"ok": False, "error": f"API 연결 실패: {exc}"}


@tool(args_schema=OrderIdInput)
def get_order_status(order_id: str) -> dict:
    """외부 API를 호출해 주문 번호(order_id)의 배송 상태, 결제 금액, 배송 후 경과 일수를 조회합니다."""
    try:
        r = httpx.get(f"{API_BASE_URL}/api/orders/{order_id.strip()}", timeout=5.0)
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "status_code": r.status_code, "error": r.json()}
    except Exception as exc:
        return {"ok": False, "error": f"API 연결 실패: {exc}"}


@tool(args_schema=RefundInput)
def request_order_refund(order_id: str, reason: str) -> dict:
    """외부 API를 호출해 주문 번호(order_id)에 대한 환불을 실제로 접수합니다."""
    try:
        r = httpx.post(
            f"{API_BASE_URL}/api/orders/refund",
            json={"order_id": order_id.strip(), "reason": reason.strip()},
            timeout=5.0,
        )
        if r.status_code == 200:
            return {"ok": True, "data": r.json()}
        return {"ok": False, "status_code": r.status_code, "error": r.json()}
    except Exception as exc:
        return {"ok": False, "error": f"API 연결 실패: {exc}"}


if __name__ == "__main__":
    print(get_product_inventory.invoke({"sku": "SKU-101"}))
    print(get_order_status.invoke({"order_id": "ORD-5001"}))