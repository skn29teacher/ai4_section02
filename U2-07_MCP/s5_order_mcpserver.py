import httpx
try:
    from mcp.server.mcpserver import MCPServer
except ModuleNotFoundError as error:
    if error.name != "mcp.server.mcpserver":
        raise
    from mcp.server.fastmcp import FastMCP as MCPServer

mcp = MCPServer("OrderManageMCP")
BASE_URL = "http://127.0.0.1:8000"

@mcp.tool()
def mcp_get_order(order_id:str)->dict:
    """주문 번호(order_id)로 외부 REST API에서 주문 상태와 금액을 조회합니다."""
    resp = httpx.get(f"{BASE_URL}/api/orders/{order_id}", timeout=5.0)
    return resp.json() if resp.status_code == 200 else {"error": resp.text}

@mcp.tool()
def submit_refund_via_rest(order_id: str, reason: str) -> dict:
    """주문 번호(order_id)와 사유(reason)로 외부 REST API에 환불을 접수합니다."""
    resp = httpx.post(
        f"{BASE_URL}/api/orders/refund",
        json={"order_id": order_id, "reason": reason},
        timeout=5.0,
    )
    return resp.json() if resp.status_code == 200 else {"error": resp.text}  

# 2. MCP Resource: 클라이언트/모델이 참고할 정책 문서
@mcp.resource("policy://refund-rules")
def get_refund_policy() -> str:
    """사내 환불 정책 안내 문서를 반환합니다."""
    return "환불 규정: 배송 준비중(PREPARING) 상태는 즉시 환불 가능하며, 배송 완료 후 7일 이내 단순 변심 환불이 가능합니다."


# 3. MCP Prompt: 표준화된 응대 프롬프트 템플릿
@mcp.prompt()
def cs_response_template(order_id: str) -> str:
    """고객 주문 응대를 위한 표준 프롬프트를 생성합니다."""
    return f"주문 번호 {order_id}의 현재 상태와 환불 가능 여부를 친절한 한국어로 안내해 주세요."


if __name__ == "__main__":
    mcp.run(transport="stdio")