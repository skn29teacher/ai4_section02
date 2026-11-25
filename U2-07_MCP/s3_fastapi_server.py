from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="external order & inventory api")

ORDERS = {
    "ORD_1001":{'order-id':'ORD-1001', 'item':'big bag','amount_krw':100},
    "ORD_1002":{'order-id':'ORD-1002', 'item':'USB-C type','amount_krw':200}
}

class RefundRequest(BaseModel):
    order_id:str
    reason:str

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    order = ORDERS.get(order_id.upper())
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/api/orders/refund")
def request_refund(req: RefundRequest):
    order = ORDERS.get(req.order_id.upper())
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": req.order_id.upper(),
        "refund_status": "ACCEPTED",
        "reason": req.reason,
        "refund_amount_krw": order["amount_krw"],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)