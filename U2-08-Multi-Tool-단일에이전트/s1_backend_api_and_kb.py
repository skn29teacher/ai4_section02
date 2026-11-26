# 단일에이전트의 multi-tool 패턴
# 사용자의도에 따라서 검색만 할지, 외부 api만 부를지, 검색후 api를 연쇄 호출할지 모델이 스스로 계획 하도록 만드는 구조
# 도구에 따라서 3분류 설계
    # 상품추천가이드, 환불/보증규정, 호환성 안내같은 비정형 텍스트 검색
    # 실시간 재고, 가격, 배송상태 조회
    # 재고 차감, 주문생성, 환불접수 등 외부시스템 상태 변경
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# 모의 데이터
INVENTORY_DB = {
    "SKU-101": {
        "sku": "SKU-101",
        "name": "저소음 적축 무선 기계식 키보드",
        "category": "keyboard",
        "price_krw": 129000,
        "stock": 8,
    },
    "SKU-102": {
        "sku": "SKU-102",
        "name": "USB-C 8-in-1 PD 멀티 허브",
        "category": "hub",
        "price_krw": 49000,
        "stock": 15,
    },
    "SKU-103": {
        "sku": "SKU-103",
        "name": "알루미늄 각도조절 노트북 스탠드",
        "category": "stand",
        "price_krw": 39000,
        "stock": 0,
    },
}

# 실시간 주문 DB (모의)
ORDERS_DB = {
    "ORD-5001": {
        "order_id": "ORD-5001",
        "sku": "SKU-101",
        "quantity": 1,
        "total_krw": 129000,
        "status": "DELIVERED",
        "days_since_delivery": 3,
    },
    "ORD-5002": {
        "order_id": "ORD-5002",
        "sku": "SKU-102",
        "quantity": 2,
        "total_krw": 98000,
        "status": "DELIVERED",
        "days_since_delivery": 12,
    },
}

class OrderCreateBody(BaseModel):
    sku : str
    quantity : int = Field(..., gt=0)

class RefundCreateBody(BaseModel):
    order_id : str
    reason : str

app = FastAPI(title='Simulation', version="1.0.0")

# 상품조회
@app.get("/api/products/{sku}")
def read_product(sku:str):
    item = INVENTORY_DB.get(sku.upper())
    if not item:
        raise HTTPException(status_code=404, detail=f'존재하지 않는 상품코드입니다.{sku}')
    return item
# 주문등록
@app.post("/api/orders")
def create_order(body: OrderCreateBody) -> dict:    
    item = INVENTORY_DB.get(body.sku)

    if item['stock'] < body.quantity:
        raise HTTPException(status_code=406, detail=f"재고부족 요청:{body.quantity} 현재 재고:{item["stock"]}")   
    item['stock'] -= body.quantity

    
    if not item:
        raise HTTPException(status_code=404, detail=f"존재하지 않는 상품코드 {body.sku}")       
    
    new_order_id = f"ORD-{5000+ len(ORDERS_DB) + 1}"
    order_record = {
        "order_id": new_order_id,
        "sku": body.sku,
        "quantity": body.quantity,
        "total_krw": item['price_krw'] * body.quantity,
        "status": "CONFIRMED",
        "remaining_stock" : item['stock'],
    }
    ORDERS_DB[new_order_id] = order_record
    return order_record


# 주문조회
@app.get("/api/orders/{order_id}")
def read_order(order_id:str):
    order = ORDERS_DB.get(order_id.upper())
    if not order:
        raise HTTPException(status_code=404, detail=f'존재하지 않는 주문 번호입니다.{order_id}')
    return order 

# 환불등록
@app.post("/api/orders/refund")
def refund_order(body:RefundCreateBody):
    order = ORDERS_DB.get(body.order_id.upper())
    order['status'] = 'REFUNDED'
    return {
        'order_id' : order['order_id'],
        'refund_status':"REFUNDED",
        'reason' : body.reason,
        'refunded_krw' : order['total_krw']
    }

if __name__=="__main__":
    uvicorn.run(app, host="127.0.0.1",port=8000)