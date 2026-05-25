"""Blink Wallet (api.blink.sv) — Lightning + on-chain BTC payouts.

Blink exposes a GraphQL API. We support:
  * BOLT11 Lightning invoices         → lnInvoicePaymentSend / lnNoAmountInvoicePaymentSend
  * Lightning addresses (user@host)   → resolve LNURL-pay → BOLT11 → lnInvoicePaymentSend
  * On-chain BTC addresses            → onChainPaymentSend

If BLINK_API_KEY / BLINK_BTC_WALLET_ID are not configured the module returns a
deterministic MOCK payout so the rest of the stack keeps working in dev.

Docs: https://dev.blink.sv/
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

BLINK_GRAPHQL_URL = "https://api.blink.sv/graphql"

# USD per BTC for converting our internal USD payout amount → sats.
# Kept in sync with server.BTC_USD_RATE.
DEFAULT_BTC_USD = 65000.0

LIGHTNING_ADDRESS_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
BOLT11_PREFIXES = ("lnbc", "lntb", "lnbcrt", "lnsb")
LNURL_PREFIX = "lnurl"


@dataclass
class BlinkConfig:
    api_key: Optional[str]
    btc_wallet_id: Optional[str]
    usd_wallet_id: Optional[str]
    btc_usd_rate: float

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.btc_wallet_id)


def _load_config() -> BlinkConfig:
    return BlinkConfig(
        api_key=os.environ.get("BLINK_API_KEY") or None,
        btc_wallet_id=os.environ.get("BLINK_BTC_WALLET_ID") or None,
        usd_wallet_id=os.environ.get("BLINK_USD_WALLET_ID") or None,
        btc_usd_rate=float(os.environ.get("BLINK_BTC_USD_RATE", DEFAULT_BTC_USD)),
    )


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
    }


def _gql(api_key: str, query: str, variables: Optional[Dict[str, Any]] = None,
         timeout: float = 15.0) -> Dict[str, Any]:
    with httpx.Client(timeout=timeout) as c:
        r = c.post(BLINK_GRAPHQL_URL, headers=_headers(api_key),
                   json={"query": query, "variables": variables or {}})
        r.raise_for_status()
        data = r.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"Blink GraphQL errors: {data['errors']}")
    return data.get("data", {})


def usd_to_sats(amount_usd: float, btc_usd: float) -> int:
    btc = amount_usd / btc_usd
    return max(1, int(round(btc * 100_000_000)))


def detect_destination_kind(destination: str) -> str:
    d = destination.strip()
    dl = d.lower()
    if any(dl.startswith(p) for p in BOLT11_PREFIXES):
        return "bolt11"
    if dl.startswith(LNURL_PREFIX):
        return "lnurl"
    if LIGHTNING_ADDRESS_RE.match(d):
        return "lightning_address"
    # BTC on-chain — accept bech32 (bc1…) or legacy (1.. / 3..).
    if re.match(r"^(bc1[ac-hj-np-z02-9]{6,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$", d):
        return "onchain"
    return "unknown"


def _resolve_lnurl_pay(lnurl_or_address: str, amount_sats: int,
                       timeout: float = 12.0) -> str:
    """Resolve a Lightning address or LNURL-pay → fetch a BOLT11 invoice."""
    if LIGHTNING_ADDRESS_RE.match(lnurl_or_address):
        user, host = lnurl_or_address.split("@", 1)
        well_known = f"https://{host}/.well-known/lnurlp/{user}"
    else:
        # LNURL bech32 string. To keep deps small we let the caller pre-decode
        # if needed; we just refuse here.
        raise RuntimeError("Raw LNURL strings are not yet supported — use a Lightning address or BOLT11 invoice.")

    with httpx.Client(timeout=timeout) as c:
        meta = c.get(well_known)
        meta.raise_for_status()
        info = meta.json()
        if info.get("tag") != "payRequest":
            raise RuntimeError(f"LNURL-pay endpoint returned wrong tag: {info.get('tag')!r}")
        callback = info["callback"]
        min_sendable = int(info.get("minSendable", 0))
        max_sendable = int(info.get("maxSendable", 0))
        msats = amount_sats * 1000
        if min_sendable and msats < min_sendable:
            raise RuntimeError(f"Amount {msats} msats below minSendable {min_sendable}")
        if max_sendable and msats > max_sendable:
            raise RuntimeError(f"Amount {msats} msats above maxSendable {max_sendable}")

        sep = "&" if "?" in callback else "?"
        cb_url = f"{callback}{sep}amount={msats}"
        cb = c.get(cb_url)
        cb.raise_for_status()
        cb_info = cb.json()
        if "pr" not in cb_info:
            raise RuntimeError(f"LNURL callback did not return invoice: {cb_info}")
        return cb_info["pr"]


# ---------- GraphQL mutations ----------
_MUTATION_LN_INVOICE_SEND = """
mutation LnInvoicePaymentSend($input: LnInvoicePaymentInput!) {
  lnInvoicePaymentSend(input: $input) {
    status
    errors { message code path }
  }
}
"""

_MUTATION_LN_NOAMOUNT_INVOICE_SEND = """
mutation LnNoAmountInvoicePaymentSend($input: LnNoAmountInvoicePaymentInput!) {
  lnNoAmountInvoicePaymentSend(input: $input) {
    status
    errors { message code path }
  }
}
"""

_MUTATION_ONCHAIN_SEND = """
mutation OnChainPaymentSend($input: OnChainPaymentSendInput!) {
  onChainPaymentSend(input: $input) {
    status
    errors { message code path }
  }
}
"""


def _normalize_status(s: Optional[str]) -> str:
    s = (s or "").upper()
    if s in ("SUCCESS", "PAID"):
        return "completed"
    if s in ("PENDING",):
        return "in_progress"
    if s in ("FAILED", "ALREADY_PAID"):
        return "failed"
    if not s:
        return "pending"
    return s.lower()


def _mock_payout(amount_usd: float, destination: str, kind: str) -> Dict[str, Any]:
    return {
        "provider": "mock",
        "status": "pending",
        "blink_state": "MOCK",
        "payout_id": f"mock-blink-{uuid.uuid4().hex[:10]}",
        "destination": destination,
        "amount_usd": amount_usd,
        "amount_sats": usd_to_sats(amount_usd, DEFAULT_BTC_USD),
        "kind": kind,
        "view_url": None,
    }


def create_payout(
    amount_usd: float,
    destination: str,
    description: str = "HashCloud withdrawal",
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Send a real Lightning / on-chain payout via Blink Wallet."""
    cfg = _load_config()
    kind = detect_destination_kind(destination)
    if kind == "unknown":
        raise RuntimeError(f"Unsupported destination format: {destination!r}")

    if not cfg.enabled:
        logger.info("Blink: credentials not configured — returning MOCK payout.")
        return _mock_payout(amount_usd, destination, kind)

    amount_sats = usd_to_sats(amount_usd, cfg.btc_usd_rate)
    bolt11: Optional[str] = None

    try:
        if kind == "bolt11":
            bolt11 = destination
        elif kind == "lightning_address":
            bolt11 = _resolve_lnurl_pay(destination, amount_sats, timeout=timeout)
        elif kind == "lnurl":
            raise RuntimeError("Raw LNURL strings not supported yet — use Lightning address or BOLT11.")

        if bolt11:
            # Try amount-included BOLT11 first; if Blink complains about amount
            # being part of the invoice it will return an error → fall back to
            # noAmount variant.
            input_ = {
                "walletId": cfg.btc_wallet_id,
                "paymentRequest": bolt11,
                "memo": description[:512],
            }
            data = _gql(
                cfg.api_key, _MUTATION_LN_INVOICE_SEND,
                {"input": input_}, timeout=timeout,
            )
            send = data.get("lnInvoicePaymentSend") or {}
            errors = send.get("errors") or []
            status = send.get("status")

            # Amountless invoice path
            if errors and any("amount" in (e.get("message") or "").lower() for e in errors):
                input_amt = {
                    "walletId": cfg.btc_wallet_id,
                    "paymentRequest": bolt11,
                    "amount": amount_sats,
                    "memo": description[:512],
                }
                data = _gql(
                    cfg.api_key, _MUTATION_LN_NOAMOUNT_INVOICE_SEND,
                    {"input": input_amt}, timeout=timeout,
                )
                send = data.get("lnNoAmountInvoicePaymentSend") or {}
                errors = send.get("errors") or []
                status = send.get("status")

            return _build_result(send, amount_usd, amount_sats, destination, kind, status, errors)

        if kind == "onchain":
            input_ = {
                "walletId": cfg.btc_wallet_id,
                "address": destination,
                "amount": amount_sats,
                "memo": description[:512],
            }
            data = _gql(
                cfg.api_key, _MUTATION_ONCHAIN_SEND,
                {"input": input_}, timeout=timeout,
            )
            send = data.get("onChainPaymentSend") or {}
            errors = send.get("errors") or []
            status = send.get("status")
            return _build_result(send, amount_usd, amount_sats, destination, kind, status, errors)

    except httpx.HTTPError as e:
        body = getattr(e, "response", None)
        detail = body.text if body is not None else str(e)
        raise RuntimeError(f"Blink HTTP error: {detail}")

    raise RuntimeError(f"Blink: payout path not handled for kind={kind!r}")


def _build_result(send: Dict[str, Any], amount_usd: float, amount_sats: int,
                  destination: str, kind: str, status: Optional[str],
                  errors: Any) -> Dict[str, Any]:
    if errors:
        # Bubble up Blink's error in a readable form so the caller can refund
        # the user's balance and show a meaningful message.
        msgs = []
        for e in errors:
            if isinstance(e, dict):
                m = e.get("message") or e.get("code") or "unknown"
                msgs.append(str(m))
            else:
                msgs.append(str(e))
        raise RuntimeError("Blink payment failed: " + "; ".join(msgs))
    return {
        "provider": "blink",
        "status": _normalize_status(status),
        "blink_state": status,
        "payout_id": f"blink-{uuid.uuid4().hex[:12]}",
        "destination": destination,
        "amount_usd": amount_usd,
        "amount_sats": amount_sats,
        "kind": kind,
        "view_url": "https://wallet.blink.sv/transactions",
    }


def get_payout(payout_id: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Blink payments are synchronous (status returned at submission) so we
    just echo the stored status back. Kept for API parity with btcpay."""
    return {"payout_id": payout_id, "status": "completed" if payout_id.startswith("blink-") else "pending"}
