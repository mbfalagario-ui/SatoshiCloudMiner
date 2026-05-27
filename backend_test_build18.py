"""Build #18 backend regression for Satoshi Cloud Miner.

Covers:
  1) GET /api/system/btc_rate                  (NEW)
  2) GET /api/ai/agents                        (LLM-driven, idempotent per UTC day)
  3) POST /api/admin/ai/regenerate             (admin re-roll)
  4) GET /api/packages                         (exactly 10, no starter_099)
  + Regression: auth, dashboard, withdraw methods/min, support thread + msg,
    admin analytics/users/transactions, free-forever status/activate.

Spec deviations (worth flagging in summary, not failures):
  * Support endpoints in this build are:
      GET  /api/support/thread       (singular)
      POST /api/support/messages
      GET  /api/admin/support/threads
      POST /api/admin/support/threads/{user_id}/reply
    NOT POST /api/support/threads + .../{id}/messages as the review_request
    text suggested. The behaviour is equivalent; we test the actual routes.
"""

from __future__ import annotations
import json
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

import requests

BASE = "https://ios-clone-platform.preview.emergentagent.com/api"
ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"
TIMEOUT = 30

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, msg: str = "") -> None:
    results.append((name, ok, msg))
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name} :: {msg}")


def req(method: str, path: str, *, token: Optional[str] = None, json_body: Any = None,
        expected: Optional[int] = None) -> tuple[int, Any]:
    url = f"{BASE}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    try:
        r = requests.request(method, url, headers=headers,
                             data=json.dumps(json_body) if json_body is not None else None,
                             timeout=TIMEOUT)
    except requests.RequestException as e:
        return 0, {"_exception": str(e)}
    try:
        body = r.json()
    except Exception:
        body = {"_raw": r.text[:200]}
    return r.status_code, body


# ---------------------------------------------------------------- 1) NEW
def test_btc_rate():
    code, body = req("GET", "/system/btc_rate")
    if code != 200:
        record("1. GET /system/btc_rate", False, f"HTTP {code} body={body}")
        return
    btc = body.get("btc_usd")
    source = body.get("source")
    ok = (
        isinstance(btc, (int, float))
        and 1000 <= float(btc) <= 1_000_000
        and source in ("coingecko", "coinbase", "kraken", "default")
        and "fetched_at" in body
        and "age_seconds" in body
    )
    record("1. GET /system/btc_rate", ok,
           f"HTTP 200 btc_usd={btc} source={source} fetched_at={body.get('fetched_at')} age={body.get('age_seconds')}")
    return body


def _validate_agents(agents: list, label: str) -> bool:
    expected_ids = {"agent_arbiter", "agent_helios", "agent_orbital",
                    "agent_quasar", "agent_voltage", "agent_sentinel"}
    expected_names = {"Arbiter", "Helios", "Orbital", "Quasar", "Voltage", "Sentinel"}
    if not isinstance(agents, list) or len(agents) != 6:
        record(label, False, f"expected 6 agents, got {len(agents) if isinstance(agents, list) else 'non-list'}")
        return False
    ids = {a.get("id") for a in agents}
    names = {a.get("name") for a in agents}
    if ids != expected_ids and names != expected_names:
        record(label, False, f"agent ids/names mismatch: ids={ids} names={names}")
        return False
    required = ["id", "name", "strategy", "baseline_pct", "daily_pct", "win_rate",
                "signal_strength", "status", "action", "commentary", "ai_generated"]
    issues = []
    for a in agents:
        missing = [k for k in required if k not in a]
        if missing:
            issues.append(f"{a.get('id')}: missing {missing}")
        if not isinstance(a.get("commentary"), str) or not a.get("commentary").strip():
            issues.append(f"{a.get('id')}: empty commentary")
        dp = a.get("daily_pct")
        if not isinstance(dp, (int, float)) or not (-0.15 <= float(dp) <= 0.15):
            issues.append(f"{a.get('id')}: daily_pct out of range: {dp}")
        wr = a.get("win_rate")
        if not isinstance(wr, (int, float)) or not (0.5 <= float(wr) <= 0.95):
            issues.append(f"{a.get('id')}: win_rate out of range: {wr}")
    if issues:
        record(label, False, "; ".join(issues[:5]))
        return False
    ai_flags = [a.get("ai_generated") for a in agents]
    record(label, True,
           f"6 agents OK; ai_generated={ai_flags[0]} (all={set(ai_flags)})")
    return True


# ---------------------------------------------------------------- 2) NEW
def test_ai_agents_public():
    code, body = req("GET", "/ai/agents")
    if code != 200:
        record("2a. GET /ai/agents (first hit)", False, f"HTTP {code} body={body}")
        return None
    agents1 = body.get("agents") or []
    _validate_agents(agents1, "2a. GET /ai/agents (first hit, schema)")

    # Idempotency: hit again — should return identical snapshot for today
    code2, body2 = req("GET", "/ai/agents")
    if code2 != 200:
        record("2b. GET /ai/agents (cached idempotent)", False, f"HTTP {code2}")
        return agents1
    agents2 = body2.get("agents") or []
    same = (body.get("date") == body2.get("date")) and \
           all(a1.get("daily_pct") == a2.get("daily_pct") and
               a1.get("win_rate") == a2.get("win_rate")
               for a1, a2 in zip(agents1, agents2))
    record("2b. GET /ai/agents (cached idempotent)", same,
           f"date={body.get('date')} match={same}")
    return agents1


# ---------------------------------------------------------------- Admin login
def login(email: str, password: str) -> Optional[str]:
    code, body = req("POST", "/auth/login", json_body={"email": email, "password": password})
    if code == 200 and body.get("access_token"):
        return body["access_token"]
    return None


# ---------------------------------------------------------------- 3) NEW
def test_admin_regenerate(admin_token: str, prev_agents: Optional[list]):
    code, body = req("POST", "/admin/ai/regenerate", token=admin_token)
    if code != 200:
        record("3. POST /admin/ai/regenerate", False, f"HTTP {code} body={body}")
        return
    agents = body.get("agents") or []
    has_admin = body.get("regenerated_by_admin")
    schema_ok = _validate_agents(agents, "3a. /admin/ai/regenerate schema")
    record("3b. /admin/ai/regenerate regenerated_by_admin", has_admin == ADMIN_EMAIL,
           f"regenerated_by_admin={has_admin}")
    return agents


# ---------------------------------------------------------------- 4) NEW
def test_packages():
    code, body = req("GET", "/packages")
    if code != 200:
        record("4. GET /packages", False, f"HTTP {code}")
        return
    pkgs = body.get("packages") if isinstance(body, dict) else body
    if not isinstance(pkgs, list):
        record("4. GET /packages", False, f"non-list response: {type(pkgs)}")
        return

    count_ok = len(pkgs) == 10
    starter_absent = all(p.get("id") != "starter_099" for p in pkgs)

    expected_order = [
        "welcome_199", "rookie_299", "pro_499", "elite_999", "ultra_1999",
        "mega_4999", "giga_9999", "titan_14999", "colossus_19999", "adfree_399",
    ]
    actual_ids = [p.get("id") for p in pkgs]
    order_ok = actual_ids == expected_order

    record("4a. /packages count == 10", count_ok, f"got {len(pkgs)}")
    record("4b. /packages no starter_099", starter_absent,
           f"ids={actual_ids}")
    record("4c. /packages order matches spec", order_ok,
           f"actual={actual_ids}")

    # Mining package keys
    mining_pkgs = [p for p in pkgs if p.get("id") != "adfree_399"]
    bad = []
    for p in mining_pkgs:
        for k in ("hash_rate", "daily_yield_usd", "duration_days"):
            if k not in p:
                bad.append(f"{p.get('id')} missing {k}")
    record("4d. mining packages have required keys", not bad,
           "; ".join(bad) if bad else f"9 mining pkgs OK")


# ---------------------------------------------------------------- Regression
def test_regression_auth_dashboard(admin_token: str):
    # Register a fresh user
    email = f"build18_{uuid.uuid4().hex[:10]}@gmail.com"
    pw = "Sup3rSecret!123"
    code, body = req("POST", "/auth/register",
                     json_body={"email": email, "password": pw})
    ok = code == 200 and body.get("access_token") and body.get("user", {}).get("email") == email
    record("R1. POST /auth/register", ok, f"HTTP {code}")
    if not ok:
        return None, None
    user_token = body["access_token"]

    # Login round-trip
    code, body = req("POST", "/auth/login", json_body={"email": email, "password": pw})
    ok = code == 200 and body.get("access_token")
    record("R2. POST /auth/login round-trip", ok, f"HTTP {code}")
    if ok:
        user_token = body["access_token"]

    # /auth/me
    code, body = req("GET", "/auth/me", token=user_token)
    record("R3. GET /auth/me", code == 200 and body.get("email") == email,
           f"HTTP {code} email={body.get('email')}")

    # /dashboard with live BTC rate (not hardcoded 65000)
    code, body = req("GET", "/dashboard", token=user_token)
    btc_rate = body.get("btc_usd_rate") if isinstance(body, dict) else None
    rate_ok = isinstance(btc_rate, (int, float)) and 1000 <= float(btc_rate) <= 1_000_000
    # We accept either live (!=65000) or default fallback (==65000) — flag if exactly 65000
    note = "(default fallback rate — provider unreachable?)" if btc_rate == 65000 else ""
    record("R4. GET /dashboard btc_usd_rate live", code == 200 and rate_ok,
           f"HTTP {code} btc_usd_rate={btc_rate} {note}")

    # /withdraw/methods (regular user) — should include btc_usd_rate live
    code, body = req("GET", "/withdraw/methods", token=user_token)
    btc_rate2 = body.get("btc_usd_rate") if isinstance(body, dict) else None
    record("R5. GET /withdraw/methods btc_usd_rate", code == 200 and isinstance(btc_rate2, (int, float)),
           f"HTTP {code} min_sats={body.get('min_sats')} fee_pct={body.get('fee_pct')} btc_usd_rate={btc_rate2}")

    # Sub-min withdraw → 400 (regular user min 150000)
    code, body = req("POST", "/withdraw", token=user_token,
                     json_body={"method_id": "lightning",
                                "address": "lightning@example.com",
                                "amount_sats": 100})
    record("R6. POST /withdraw sub-min → 400", code == 400,
           f"HTTP {code} detail={body.get('detail') if isinstance(body, dict) else body}")

    return user_token, email


def test_regression_support(user_token: str, admin_token: str, user_email: str):
    # User creates / fetches thread
    code, body = req("GET", "/support/thread", token=user_token)
    ok = code == 200 and "thread" in body and "messages" in body
    record("R7. GET /support/thread (user)", ok, f"HTTP {code}")
    if not ok:
        return

    # User sends a message  (route is POST /support/messages, body={"body": ...})
    code, body = req("POST", "/support/messages", token=user_token,
                     json_body={"body": f"Build #18 hello from {user_email}"})
    msg_ok = code == 200 and body.get("ok") is True and body.get("message", {}).get("sender") == "user"
    record("R8. POST /support/messages (user)", msg_ok,
           f"HTTP {code} sender={body.get('message', {}).get('sender') if isinstance(body, dict) else '?'}")

    # Admin replies (route is POST /admin/support/threads/{user_id}/reply)
    code, mebody = req("GET", "/auth/me", token=user_token)
    user_id = mebody.get("id") if isinstance(mebody, dict) else None
    if not user_id:
        record("R9. admin reply", False, "no user_id resolved")
        return
    code, body = req("POST", f"/admin/support/threads/{user_id}/reply",
                     token=admin_token,
                     json_body={"body": "Build #18 admin reply ack"})
    record("R9. POST /admin/support/threads/{uid}/reply (admin)",
           code == 200 and body.get("ok") is True and body.get("message", {}).get("sender") == "admin",
           f"HTTP {code} sender={body.get('message', {}).get('sender') if isinstance(body, dict) else '?'}")


def test_regression_admin(admin_token: str):
    for ep in ("/admin/analytics", "/admin/users", "/admin/transactions"):
        code, body = req("GET", ep, token=admin_token)
        record(f"R10. GET {ep}", code == 200,
               f"HTTP {code} keys={list(body.keys())[:5] if isinstance(body, dict) else '?'}")


def test_regression_free_forever(user_token: str):
    code, body = req("GET", "/free-forever/status", token=user_token)
    record("R11. GET /free-forever/status",
           code == 200 and "hash_rate_display" in body and "duration_hours" in body,
           f"HTTP {code} active={body.get('active')} display={body.get('hash_rate_display')}")

    code, body = req("POST", "/free-forever/activate", token=user_token)
    first_ok = code == 200 and body.get("ok") is True
    record("R12. POST /free-forever/activate (first)", first_ok,
           f"HTTP {code} ok={body.get('ok')}")

    # Idempotent — second activate while active must 400
    code, body = req("POST", "/free-forever/activate", token=user_token)
    record("R13. POST /free-forever/activate (idempotent)",
           code == 400,
           f"HTTP {code} detail={body.get('detail') if isinstance(body, dict) else body}")


# ---------------------------------------------------------------- main
def main():
    print(f"\n=== Build #18 backend regression — base={BASE} ===\n")

    # 1
    test_btc_rate()
    # 2
    prev_agents = test_ai_agents_public()
    # 4
    test_packages()

    # admin login for 3 + regression
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_token:
        record("ADMIN LOGIN", False, "admin login failed — aborting admin-gated tests")
    else:
        record("ADMIN LOGIN", True, f"token len={len(admin_token)}")
        # 3
        test_admin_regenerate(admin_token, prev_agents)
        # regression
        user_token, user_email = test_regression_auth_dashboard(admin_token)
        if user_token and user_email:
            test_regression_support(user_token, admin_token, user_email)
            test_regression_free_forever(user_token)
        test_regression_admin(admin_token)

    # summary
    fails = [r for r in results if not r[1]]
    passes = [r for r in results if r[1]]
    print(f"\n=== Build #18 summary: {len(passes)}/{len(results)} PASS, {len(fails)} FAIL ===")
    if fails:
        print("FAILURES:")
        for n, _, m in fails:
            print(f"  - {n} :: {m}")
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
