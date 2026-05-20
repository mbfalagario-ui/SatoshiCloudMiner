"""BTCPay Server pull-payment / payout client.

Behaviour:
  * If BTCPAY_BASE_URL, BTCPAY_API_KEY and BTCPAY_STORE_ID are all configured,
    calls BTCPay's Greenfield API to create a one-shot pull-payment and a
    payout under it for the requested amount/destination.
  * Otherwise returns a deterministic mocked payout in `pending` state so the
    frontend keeps working.

Greenfield docs: https://docs.btcpayserver.org/API/Greenfield/v1/
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class BTCPayConfig:
    base_url: Optional[str]
    api_key: Optional[str]
    store_id: Optional[str]

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.store_id)


def _load_config() -> BTCPayConfig:
    return BTCPayConfig(
        base_url=(os.environ.get("BTCPAY_BASE_URL") or "").rstrip("/") or None,
        api_key=os.environ.get("BTCPAY_API_KEY") or None,
        store_id=os.environ.get("BTCPAY_STORE_ID") or None,
    )


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"token {api_key}",
    }


def _detect_payment_method(destination: str) -> str:
    """Return BTCPay payment method name based on the destination shape."""
    d = destination.strip()
    if d.lower().startswith("lnbc") or d.lower().startswith("lntb"):
        return "BTC-LightningNetwork"
    if "@" in d and "." in d.split("@", 1)[1]:
        return "BTC-LightningNetwork"  # Lightning address
    if d.lower().startswith("lnurl"):
        return "BTC-LightningNetwork"
    return "BTC"  # on-chain Bitcoin address


def _normalize_status(state: Optional[str]) -> str:
    s = (state or "").lower()
    if not s:
        return "pending"
    if "await" in s or s == "new":
        return "pending"
    if "progress" in s or "processing" in s or "awaitingpayment" in s:
        return "in_progress"
    if "completed" in s or "paid" in s or s == "issued":
        return "completed"
    if "cancel" in s or s == "expired":
        return "failed"
    return "pending"


def create_payout(
    amount_usd: float,
    destination: str,
    description: str = "HashCloud withdrawal",
    timeout: float = 12.0,
) -> Dict[str, Any]:
    """Create a one-shot pull payment + payout on BTCPay.

    Returns a dict with:
        provider:           "btcpay" | "mock"
        pull_payment_id:    str
        payout_id:          str
        status:             "pending" | "in_progress" | "completed" | "failed"
        btcpay_state:       raw state string from BTCPay (or "MOCK")
        destination:        echoed back
        amount_usd:         echoed back
        payment_method:     "BTC" | "BTC-LightningNetwork"
        view_url:           https URL where the user can view payout (or None)
    """
    cfg = _load_config()
    method = _detect_payment_method(destination)

    if not cfg.enabled:
        logger.info("BTCPay: credentials not configured — returning MOCK payout.")
        return {
            "provider": "mock",
            "pull_payment_id": f"mock-pp-{uuid.uuid4().hex[:10]}",
            "payout_id": f"mock-po-{uuid.uuid4().hex[:10]}",
            "status": "pending",
            "btcpay_state": "MOCK",
            "destination": destination,
            "amount_usd": amount_usd,
            "payment_method": method,
            "view_url": None,
        }

    base = cfg.base_url
    headers = _headers(cfg.api_key)
    store_id = cfg.store_id

    # 1) Create a pull payment scoped to this single payout
    pp_url = f"{base}/api/v1/stores/{store_id}/pull-payments"
    pp_body = {
        "name": description,
        "amount": f"{amount_usd:.2f}",
        "currency": "USD",
        "payoutMethods": [method],
        "autoApproveClaims": True,
    }
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(pp_url, json=pp_body, headers=headers)
            r.raise_for_status()
            pp = r.json()
    except httpx.HTTPError as e:
        body = getattr(e, "response", None)
        detail = body.text if body is not None else str(e)
        raise RuntimeError(f"BTCPay create pull-payment failed: {detail}")

    pp_id = pp.get("id")
    if not pp_id:
        raise RuntimeError(f"BTCPay create pull-payment returned no id: {pp}")

    # 2) Create the payout under that pull payment
    po_url = f"{base}/api/v1/pull-payments/{pp_id}/payouts"
    po_body = {
        "destination": destination,
        "amount": f"{amount_usd:.2f}",
        "payoutMethodId": method,
    }
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(po_url, json=po_body, headers=headers)
            r.raise_for_status()
            po = r.json()
    except httpx.HTTPError as e:
        body = getattr(e, "response", None)
        detail = body.text if body is not None else str(e)
        raise RuntimeError(f"BTCPay create payout failed: {detail}")

    state = po.get("state") or po.get("status")
    return {
        "provider": "btcpay",
        "pull_payment_id": pp_id,
        "payout_id": po.get("id"),
        "status": _normalize_status(state),
        "btcpay_state": state,
        "destination": destination,
        "amount_usd": amount_usd,
        "payment_method": method,
        "view_url": pp.get("viewLink") or f"{base}/pull-payments/{pp_id}",
    }


def get_payout(payout_id: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Fetch the latest status of a payout, mapping BTCPay state to ours."""
    cfg = _load_config()
    if not cfg.enabled or payout_id.startswith("mock-po-"):
        return {"payout_id": payout_id, "status": "pending", "btcpay_state": "MOCK"}

    url = f"{cfg.base_url}/api/v1/stores/{cfg.store_id}/payouts/{payout_id}"
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, headers=_headers(cfg.api_key))
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        body = getattr(e, "response", None)
        detail = body.text if body is not None else str(e)
        raise RuntimeError(f"BTCPay get payout failed: {detail}")

    state = data.get("state") or data.get("status")
    return {
        "payout_id": data.get("id", payout_id),
        "status": _normalize_status(state),
        "btcpay_state": state,
        "destination": data.get("destination"),
    }
