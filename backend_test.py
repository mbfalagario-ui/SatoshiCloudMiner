"""
Satoshi Cloud Miner — backend test suite.

Tests against the public REACT_APP_BACKEND_URL / EXPO_PUBLIC_BACKEND_URL,
which routes via Kubernetes ingress to the FastAPI app.
"""
import os
import sys
import time
import uuid
import json
import asyncio
from typing import Any, Dict, Optional, Tuple

import requests

BASE_URL = "https://ios-clone-platform.preview.emergentagent.com/api"

ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"


# --------------------- result tracking ---------------------
results: Dict[str, Dict[str, Any]] = {}


def record(test: str, passed: bool, detail: str = "") -> None:
    results[test] = {"passed": passed, "detail": detail}
    flag = "PASS" if passed else "FAIL"
    print(f"[{flag}] {test} -- {detail}")


def req(method: str, path: str, token: Optional[str] = None, **kw) -> requests.Response:
    headers = kw.pop("headers", {}) or {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    timeout = kw.pop("timeout", 30)
    return requests.request(method, BASE_URL + path, headers=headers, timeout=timeout, **kw)


# --------------------- credentials helper ---------------------
def register_user(email_prefix: str = "tester") -> Tuple[str, str, Dict[str, Any]]:
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@satoshitest.io"
    password = "MinerPass!2026"
    r = req("POST", "/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return email, data["access_token"], data["user"]


def login(email: str, password: str) -> Tuple[int, Dict[str, Any]]:
    r = req("POST", "/auth/login", json={"email": email, "password": password})
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    return r.status_code, body


# --------------------- 1. Auth tests ---------------------
def test_auth() -> Optional[str]:
    email = f"trader_{uuid.uuid4().hex[:8]}@satoshitest.io"
    password = "GoodMiner!42"

    # register
    r = req("POST", "/auth/register", json={"email": email, "password": password})
    if r.status_code != 200:
        record("auth.register", False, f"{r.status_code} {r.text[:200]}")
        return None
    data = r.json()
    if "access_token" not in data or "user" not in data:
        record("auth.register", False, f"missing fields: {list(data.keys())}")
        return None
    record("auth.register", True, f"user_id={data['user']['id']}")
    token_reg = data["access_token"]

    # duplicate register should 400
    r = req("POST", "/auth/register", json={"email": email, "password": password})
    record("auth.duplicate_register_rejected", r.status_code == 400, f"status={r.status_code}")

    # login
    code, body = login(email, password)
    if code != 200 or "access_token" not in body:
        record("auth.login", False, f"{code} {str(body)[:200]}")
        return None
    record("auth.login", True, "token returned")
    token = body["access_token"]

    # wrong password
    code2, _ = login(email, "wrongpassword")
    record("auth.wrong_password_rejected", code2 == 401, f"status={code2}")

    # GET /auth/me
    r = req("GET", "/auth/me", token=token)
    if r.status_code != 200:
        record("auth.me", False, f"{r.status_code} {r.text[:200]}")
        return token
    me = r.json()
    ok_fields = all(k in me for k in ("id", "email", "balance_btc", "balance_sats", "is_admin"))
    record("auth.me", ok_fields and me["email"] == email,
           f"email={me.get('email')} balance_sats={me.get('balance_sats')}")

    # /auth/me without token
    r = req("GET", "/auth/me")
    record("auth.me_requires_token", r.status_code == 401, f"status={r.status_code}")

    return token


# --------------------- 2. Packages ---------------------
REQUIRED_PKG_FIELDS = (
    "roi_pct", "break_even_days", "total_return_usd",
    "profitable", "profitability_score", "ai_optimized",
)


def test_packages(user_token: str) -> None:
    r = req("GET", "/packages")
    if r.status_code != 200:
        record("packages.list", False, f"{r.status_code} {r.text[:200]}")
        return
    pkgs = r.json().get("packages", [])
    if len(pkgs) != 10:
        record("packages.count", False, f"expected 10 got {len(pkgs)}")
    else:
        record("packages.count", True, "10 packages")

    missing = []
    for p in pkgs:
        for f in REQUIRED_PKG_FIELDS:
            if f not in p:
                missing.append(f"{p.get('id')}::{f}")
    record("packages.enrichment_fields", not missing, f"missing={missing[:5]}")

    # Buy first package WITH a fake apple transaction id
    starter = next((p for p in pkgs if p["id"] == "starter_099"), pkgs[0])
    fake_apple_tx = f"200000{int(time.time())}"  # unique per run
    body = {"package_id": starter["id"], "apple_transaction_id": fake_apple_tx}
    r = req("POST", "/packages/buy", token=user_token, json=body)
    if r.status_code != 200:
        record("packages.buy_with_apple_tx", False, f"{r.status_code} {r.text[:300]}")
    else:
        bj = r.json()
        env = bj.get("apple", {}).get("environment")
        # AUTH_FAILED_FALLBACK expected (since Apple JWT fails 401)
        ok = (
            bj.get("success") is True
            and bj.get("machines_added") == 1
            and env == "AUTH_FAILED_FALLBACK"
        )
        record("packages.buy_with_apple_tx", ok,
               f"success={bj.get('success')} machines={bj.get('machines_added')} env={env}")

    # Buy BOGO welcome_199 without apple transaction id (dev fallback)
    body2 = {"package_id": "welcome_199"}
    r = req("POST", "/packages/buy", token=user_token, json=body2)
    if r.status_code != 200:
        record("packages.buy_bogo_no_apple", False, f"{r.status_code} {r.text[:300]}")
    else:
        bj = r.json()
        ok = bj.get("success") is True and bj.get("machines_added") == 2
        record("packages.buy_bogo_no_apple", ok,
               f"machines_added={bj.get('machines_added')} (expected 2)")

    # Idempotency: replay same apple_transaction_id -> 400
    body3 = {"package_id": starter["id"], "apple_transaction_id": fake_apple_tx}
    r = req("POST", "/packages/buy", token=user_token, json=body3)
    record("packages.buy_idempotent_replay", r.status_code == 400, f"status={r.status_code}")

    # 404 on bogus package
    r = req("POST", "/packages/buy", token=user_token, json={"package_id": "nope_999"})
    record("packages.buy_unknown_pkg", r.status_code == 404, f"status={r.status_code}")


# --------------------- 3. Withdraw ---------------------
def credit_user_sats(user_id: str, sats: int) -> bool:
    """Credit balance_btc directly in Mongo (the user starts at 0)."""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
    except ImportError:
        print("motor not installed in test env, falling back to admin patch")
        return False
    # We'll do this via the synchronous pymongo since asyncio is messy here
    try:
        from pymongo import MongoClient
    except ImportError:
        return False
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "hashcloud_db")
    client = MongoClient(mongo_url)
    db = client[db_name]
    btc = sats / 100_000_000
    res = db.users.update_one({"id": user_id}, {"$inc": {"balance_btc": btc}})
    client.close()
    return res.modified_count == 1


def credit_user_via_admin(admin_token: str, user_id: str, sats: int) -> bool:
    """Use admin PATCH /admin/users/{id} with balance_btc_delta."""
    btc = sats / 100_000_000
    r = req(
        "PATCH",
        f"/admin/users/{user_id}",
        token=admin_token,
        json={"balance_btc_delta": btc, "note": f"test credit {sats} sats"},
    )
    return r.status_code == 200


def get_balance_sats(token: str) -> int:
    r = req("GET", "/auth/me", token=token)
    if r.status_code != 200:
        return -1
    return int(r.json().get("balance_sats", 0))


def test_withdraw_methods() -> None:
    r = req("GET", "/withdraw/methods")
    if r.status_code != 200:
        record("withdraw.methods", False, f"{r.status_code} {r.text[:200]}")
        return
    body = r.json()
    methods = body.get("methods", [])
    only_lightning = len(methods) == 1 and methods[0].get("id") == "lightning"
    ok = (
        only_lightning
        and body.get("min_sats") == 20
        and body.get("max_sats") == 2500
        and abs(float(body.get("fee_pct", 0)) - 0.05) < 1e-9
        and body.get("fee_flat_sats") == 1
        and "btc_usd_rate" in body
    )
    record(
        "withdraw.methods",
        ok,
        f"methods_count={len(methods)} min={body.get('min_sats')} max={body.get('max_sats')} fee_pct={body.get('fee_pct')} fee_flat={body.get('fee_flat_sats')}",
    )


def test_withdraw_flow(admin_token: str) -> None:
    # Fresh user
    email, token, user = register_user("withdraw")
    user_id = user["id"]

    # 1) Below min -> 400
    r = req("POST", "/withdraw", token=token,
            json={"method_id": "lightning", "address": "test@blink.sv", "amount_sats": 10})
    record("withdraw.below_min_rejected", r.status_code == 400, f"status={r.status_code} body={r.text[:120]}")

    # 2) Above max -> 400
    r = req("POST", "/withdraw", token=token,
            json={"method_id": "lightning", "address": "test@blink.sv", "amount_sats": 3000})
    record("withdraw.above_max_rejected", r.status_code == 400, f"status={r.status_code} body={r.text[:120]}")

    # 3) Insufficient balance (user starts with 0 sats balance) - try minimum
    r = req("POST", "/withdraw", token=token,
            json={"method_id": "lightning", "address": "test@blink.sv", "amount_sats": 100})
    if r.status_code == 400 and "insufficient" in r.text.lower():
        record("withdraw.insufficient_balance", True, "got 400 insufficient")
    else:
        record("withdraw.insufficient_balance", False, f"status={r.status_code} body={r.text[:200]}")

    # Credit 3000 sats via admin so we can test refund + cap
    if not credit_user_via_admin(admin_token, user_id, 3000):
        record("withdraw.credit_user_for_tests", False, "admin patch failed")
        return
    record("withdraw.credit_user_for_tests", True, "credited 3000 sats via admin")

    bal_before = get_balance_sats(token)
    # 4) Valid but invalid LN address -> 502 and refund
    # Use a clearly invalid LN address string
    bad_addr = "definitely-not-a-valid-lightning-address-xyzzy"
    r = req("POST", "/withdraw", token=token,
            json={"method_id": "lightning", "address": bad_addr, "amount_sats": 100},
            timeout=45)
    is_502 = r.status_code == 502
    record("withdraw.invalid_ln_returns_502", is_502, f"status={r.status_code} body={r.text[:200]}")

    # Allow a moment for refund to settle
    time.sleep(1)
    bal_after = get_balance_sats(token)
    # Refund should restore amount + fee
    record(
        "withdraw.refund_on_failure",
        bal_after == bal_before,
        f"before={bal_before} after={bal_after} (must be equal)",
    )

    # 5) 24h cap. We need to fake a "successful or pending" withdrawal totalling 2500 sats.
    # Easiest: insert via Mongo directly OR have admin create. Since we can't easily mock Blink success,
    # use Mongo directly.
    inserted_via_mongo = False
    try:
        from pymongo import MongoClient
        from datetime import datetime, timezone
        client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbn = os.environ.get("DB_NAME", "hashcloud_db")
        db = client[dbn]
        now_iso = datetime.now(timezone.utc).isoformat()
        db.transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "withdrawal",
            "status": "pending",
            "amount_sats": 2500,
            "fee_sats": 126,
            "amount_btc": 2500 / 100_000_000,
            "created_at": now_iso,
        })
        client.close()
        inserted_via_mongo = True
    except Exception as e:
        record("withdraw.24h_cap_setup", False, f"mongo insert failed: {e}")

    if inserted_via_mongo:
        record("withdraw.24h_cap_setup", True, "inserted 2500 sats pending tx")
        r = req("POST", "/withdraw", token=token,
                json={"method_id": "lightning", "address": "test@blink.sv", "amount_sats": 50})
        cap_hit = r.status_code == 400 and "cap" in r.text.lower()
        record("withdraw.24h_cap_enforced", cap_hit, f"status={r.status_code} body={r.text[:200]}")


# --------------------- 4. Admin endpoints ---------------------
def admin_login() -> Optional[str]:
    code, body = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if code != 200:
        record("admin.login", False, f"{code} {str(body)[:200]}")
        return None
    if not body.get("user", {}).get("is_admin"):
        record("admin.login", False, "user is_admin=false")
        return None
    record("admin.login", True, "got admin token")
    return body["access_token"]


def test_admin_endpoints(admin_token: str, non_admin_token: str) -> None:
    # Analytics
    r = req("GET", "/admin/analytics", token=admin_token)
    if r.status_code != 200:
        record("admin.analytics", False, f"{r.status_code} {r.text[:200]}")
    else:
        a = r.json()
        required = ("users", "machines", "revenue_usd", "paid_out_usd",
                    "profit_margin_pct", "payouts_by_status",
                    "latest_withdrawals", "ai_agents_today", "btc_usd_rate")
        missing = [k for k in required if k not in a]
        record("admin.analytics", not missing, f"missing={missing}")

    # Users list
    r = req("GET", "/admin/users", token=admin_token)
    if r.status_code != 200:
        record("admin.users_list", False, f"{r.status_code} {r.text[:200]}")
        target_user_id = None
    else:
        users = r.json().get("users", [])
        sample = users[0] if users else {}
        ok = bool(users) and "is_admin" in sample and "is_banned" in sample
        record("admin.users_list", ok, f"count={len(users)} sample_keys_ok={ok}")
        target_user_id = None

    # Create a fresh user to ban-test
    target_email, target_token, target_user = register_user("ban_target")
    target_user_id = target_user["id"]

    # search
    r = req("GET", f"/admin/users?search={target_email[:6]}", token=admin_token)
    record("admin.users_search", r.status_code == 200, f"status={r.status_code}")

    # Ban the user
    r = req("PATCH", f"/admin/users/{target_user_id}",
            token=admin_token, json={"is_banned": True, "note": "test ban"})
    if r.status_code != 200:
        record("admin.ban_user", False, f"{r.status_code} {r.text[:200]}")
    else:
        body = r.json()
        record("admin.ban_user", body.get("is_banned") is True, f"is_banned={body.get('is_banned')}")

    # Banned user cannot login -> 403
    code, body = login(target_email, "MinerPass!2026")
    record("admin.banned_user_blocked", code == 403, f"status={code} body={str(body)[:120]}")
    # Note: existing token should also get 403 when calling /auth/me
    r = req("GET", "/auth/me", token=target_token)
    record("admin.banned_user_token_blocked", r.status_code == 403, f"status={r.status_code}")

    # Unban (cleanup, also tests admin PATCH again)
    r = req("PATCH", f"/admin/users/{target_user_id}",
            token=admin_token, json={"is_banned": False})
    record("admin.unban_user", r.status_code == 200 and r.json().get("is_banned") is False,
           f"status={r.status_code}")

    # Transactions list
    r = req("GET", "/admin/transactions", token=admin_token)
    if r.status_code != 200:
        record("admin.transactions_list", False, f"{r.status_code} {r.text[:200]}")
        first_tx_id = None
    else:
        txs = r.json().get("transactions", [])
        record("admin.transactions_list", True, f"count={len(txs)}")
        first_tx_id = txs[0]["id"] if txs else None

    # Filter
    r = req("GET", "/admin/transactions?type=purchase", token=admin_token)
    record("admin.transactions_filter", r.status_code == 200, f"status={r.status_code}")

    # Patch a transaction
    if first_tx_id:
        r = req("PATCH", f"/admin/transactions/{first_tx_id}",
                token=admin_token, json={"status": "completed", "note": "test patch"})
        if r.status_code != 200:
            record("admin.transactions_patch", False, f"{r.status_code} {r.text[:200]}")
        else:
            t = r.json().get("transaction", {})
            record("admin.transactions_patch", t.get("status") == "completed",
                   f"status={t.get('status')}")

    # Audit
    r = req("GET", "/admin/audit", token=admin_token)
    if r.status_code != 200:
        record("admin.audit", False, f"{r.status_code} {r.text[:200]}")
    else:
        items = r.json().get("audit", [])
        record("admin.audit", isinstance(items, list), f"entries={len(items)}")

    # 403 for non-admin
    for path in ("/admin/analytics", "/admin/users", "/admin/transactions", "/admin/audit"):
        r = req("GET", path, token=non_admin_token)
        record(f"admin.403_for_non_admin {path}", r.status_code == 403, f"status={r.status_code}")


# --------------------- 5. AI endpoints ---------------------
def test_ai_endpoints(token: str) -> None:
    # ticker (slow up to 12s)
    r = req("GET", "/ai/ticker", token=token, timeout=25)
    if r.status_code != 200:
        record("ai.ticker", False, f"{r.status_code} {r.text[:200]}")
    else:
        body = r.json()
        text = body.get("text", "")
        ok = bool(text) and len(text) <= 220 and "generated_at" in body
        record("ai.ticker", ok, f"len={len(text)} has_generated_at={'generated_at' in body}")

    # agents
    r = req("GET", "/ai/agents", token=token, timeout=20)
    if r.status_code != 200:
        record("ai.agents", False, f"{r.status_code} {r.text[:200]}")
        return
    body = r.json()
    agents = body.get("agents", [])
    if len(agents) != 6:
        record("ai.agents", False, f"expected 6 got {len(agents)}: {agents}")
        return
    missing = []
    for a in agents:
        for f in ("daily_pct", "win_rate", "signal_strength", "status"):
            if f not in a:
                missing.append(f"{a.get('name')}::{f}")
    record("ai.agents", not missing and "date" in body,
           f"agents=6 missing_fields={missing[:3]}")


# --------------------- 6. Auto settings ---------------------
def test_auto_settings(token: str) -> None:
    r = req("GET", "/auto/settings", token=token)
    if r.status_code != 200:
        record("auto.get_defaults", False, f"{r.status_code} {r.text[:200]}")
        return
    body = r.json()
    ok = (
        body.get("auto_checkin") is True
        and body.get("auto_reinvest") is False
        and abs(float(body.get("auto_reinvest_min_balance_usd", 0)) - 4.99) < 1e-9
    )
    record("auto.get_defaults", ok,
           f"checkin={body.get('auto_checkin')} reinvest={body.get('auto_reinvest')} min={body.get('auto_reinvest_min_balance_usd')}")

    # toggle reinvest
    r = req("POST", "/auto/settings", token=token, json={"auto_reinvest": True})
    if r.status_code != 200:
        record("auto.post_toggle", False, f"{r.status_code} {r.text[:200]}")
        return
    body = r.json()
    record("auto.post_toggle", body.get("auto_reinvest") is True,
           f"auto_reinvest={body.get('auto_reinvest')}")

    # confirm via GET
    r = req("GET", "/auto/settings", token=token)
    record("auto.get_reflects_toggle",
           r.status_code == 200 and r.json().get("auto_reinvest") is True,
           f"status={r.status_code} body={r.text[:120]}")


# --------------------- Run ---------------------
def main() -> int:
    print(f"\n=== Satoshi Cloud Miner backend tests vs {BASE_URL} ===\n")

    # 1. Auth
    token = test_auth()
    if not token:
        print("Auth failed catastrophically; aborting.")
        print_summary()
        return 1

    # 4. Admin login (needed for some withdraw tests)
    admin_token = admin_login()

    # 2. Packages
    test_packages(token)

    # 3. Withdraw
    test_withdraw_methods()
    if admin_token:
        test_withdraw_flow(admin_token)
    else:
        record("withdraw.flow_skipped", False, "no admin token, cannot credit balance")

    # 4. Admin endpoints (need non-admin token)
    if admin_token:
        test_admin_endpoints(admin_token, token)

    # 5. AI
    test_ai_endpoints(token)

    # 6. Auto settings
    test_auto_settings(token)

    print_summary()
    return 0 if all(v["passed"] for v in results.values()) else 1


def print_summary() -> None:
    print("\n=== Summary ===")
    passed = [k for k, v in results.items() if v["passed"]]
    failed = [k for k, v in results.items() if not v["passed"]]
    print(f"PASSED: {len(passed)}")
    print(f"FAILED: {len(failed)}")
    if failed:
        print("\nFailed tests:")
        for k in failed:
            print(f"  - {k}: {results[k]['detail']}")


if __name__ == "__main__":
    sys.exit(main())
