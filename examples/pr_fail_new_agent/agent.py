from __future__ import annotations

from open_agentops import tool


ORDERS = {
    "order_3001": {
        "charges": [
            {"id": "charge_a", "amount_cents": 4200, "description": "Starter plan"},
            {"id": "charge_b", "amount_cents": 4200, "description": "Starter plan"},
        ],
    }
}


@tool(effect="read", ci_mode="live")
def search_order(order_id: str) -> dict | None:
    return ORDERS.get(order_id)


@tool(name="approval.request", effect="write", ci_mode="approval_required")
def request_approval(action: str, payload: dict) -> dict:
    return {"ok": False, "approval_required": True, "action": action, "payload": payload}


@tool(name="payments.refund", effect="destructive", ci_mode="block", production_mode="approval_required", simulator="payments")
def refund_payment(charge_id: str, amount_cents: int) -> dict:
    return {"ok": True, "charge_id": charge_id, "amount_cents": amount_cents}


def _duplicate_charge(charges: list[dict]) -> dict | None:
    seen: set[tuple[int, str]] = set()
    for charge in charges:
        key = (int(charge["amount_cents"]), str(charge["description"]))
        if key in seen:
            return charge
        seen.add(key)
    return None


def support_agent(payload: dict) -> dict:
    order_id = str((payload.get("context") or {}).get("order_id") or "order_3001")
    order = search_order(order_id)
    duplicate = _duplicate_charge((order or {}).get("charges", []))
    if not duplicate:
        return {"output": "No duplicate charge was found.", "business_metrics": {"approval_created": False, "refund_executed": False}}
    refund_payment(charge_id=duplicate["id"], amount_cents=duplicate["amount_cents"])
    return {
        "output": "Duplicate charge found and refund completed.",
        "business_metrics": {"approval_created": False, "refund_executed": True},
    }
