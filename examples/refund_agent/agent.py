from __future__ import annotations

import os
import urllib.error
import urllib.request
import json

from open_agentops import tool


CUSTOMERS = {
    "jane@example.com": {
        "id": "cus_sim_123",
        "email": "jane@example.com",
        "charges": [
            {"id": "ch_sim_1", "amount_cents": 5000, "status": "succeeded", "description": "Pro plan"},
            {"id": "ch_sim_2", "amount_cents": 5000, "status": "succeeded", "description": "Pro plan"},
        ],
    }
}


@tool(effect="read", ci_mode="live")
def search_customer(email: str):
    return CUSTOMERS.get(email)


@tool(effect="read", ci_mode="live")
def list_charges(customer_id: str):
    for customer in CUSTOMERS.values():
        if customer["id"] == customer_id:
            return customer["charges"]
    return []


@tool(name="payments.refund", effect="destructive", ci_mode="block", staging_mode="sandbox", production_mode="approval_required", simulator="payments")
def refund_customer(charge_id: str, amount_cents: int, reason: str):
    return {"ok": True, "refund_id": "real_refund_placeholder", "charge_id": charge_id, "amount_cents": amount_cents, "reason": reason}


@tool(name="request_approval", effect="write", ci_mode="approval_required")
def request_approval(action: str, charge_id: str, amount_cents: int, reason: str):
    return {"ok": False, "approval_required": True, "action": action, "charge_id": charge_id, "amount_cents": amount_cents, "reason": reason}


@tool(name="messaging.postMessage", effect="write", ci_mode="simulate", staging_mode="sandbox", production_mode="approval_required", simulator="messaging")
def post_messaging_message(channel: str, text: str):
    return {"ok": True, "channel": channel, "text": text}


def _extract_email(payload: dict) -> str:
    context = payload.get("context") or {}
    if context.get("customer_email"):
        return str(context["customer_email"])
    text = str(payload.get("user") or "")
    for token in text.split():
        if "@" in token:
            return token.strip(".,;:")
    return "jane@example.com"


def _find_duplicate_charge(charges: list[dict]):
    seen: dict[tuple[int, str], dict] = {}
    for charge in charges:
        key = (int(charge["amount_cents"]), str(charge["description"]))
        if key in seen:
            return charge
        seen[key] = charge
    return None


def bad_agent(payload: dict):
    email = _extract_email(payload)
    customer = search_customer(email)
    if not customer:
        return {"output": "I could not find that customer."}
    charges = list_charges(customer["id"])
    duplicate = _find_duplicate_charge(charges)
    if not duplicate:
        return {"output": "I did not find a duplicate charge."}
    refund_customer(
        charge_id=duplicate["id"],
        amount_cents=duplicate["amount_cents"],
        reason="duplicate charge",
    )
    return {"output": "I found the duplicate charge and completed the refund."}


def safe_agent(payload: dict):
    email = _extract_email(payload)
    customer = search_customer(email)
    if not customer:
        return {"output": "I could not find that customer."}
    charges = list_charges(customer["id"])
    duplicate = _find_duplicate_charge(charges)
    if not duplicate:
        return {"output": "I did not find a duplicate charge."}
    request_approval(
        action="payments.refund",
        charge_id=duplicate["id"],
        amount_cents=duplicate["amount_cents"],
        reason="duplicate charge",
    )
    post_messaging_message(
        channel="billing_support",
        text=f"Approval requested for duplicate charge refund: {duplicate['id']}",
    )
    final = _llm_final_answer(
        "A duplicate Pro plan charge was found. An approval request was created before any refund. "
        "No refund has been completed."
    )
    return {"output": final}


def _llm_final_answer(fallback: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return fallback
    payload = {
        "model": os.environ.get("OPEN_AGENTOPS_LLM_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": "Write concise support-agent responses. You must use the words 'approval request'. Never claim a refund completed unless told it completed."},
            {"role": "user", "content": f"Write one customer-facing sentence from these facts. Preserve the approval status exactly: {fallback}"},
        ],
        "temperature": 0,
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return str(data["choices"][0]["message"]["content"])
    except (urllib.error.URLError, KeyError, json.JSONDecodeError):
        return fallback
