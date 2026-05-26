"""Build #16 — FULL BACKEND AUDIT.

Covers all 50 review_request checks against the live preview backend.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Optional

import requests

BASE = "https://ios-clone-platform.preview.emergentagent.com/api"
ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"

results: list[tuple[str, bool, str]] = []


def log(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name} :: {detail}")


def post(path: str, body: Any = None, token: Optional[str] = None, timeout: int = 30,
         extra_headers: Optional[Dict[str, str]] = None, raw: bool = False):
    h = {} if raw else {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if extra_headers:
        h.update(extra_headers)
    data = None
    if body is not None:
        data = body if raw else json.dumps(body)
    return requests.post(BASE + path, headers=h, data=data, timeout=timeout)


def get(path: str, token: Optional[str] = None, timeout: int = 30):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.get(BASE + path, headers=h, timeout=timeout)


def patch(path: str, body: Any = None, token: Optional[str] = None, timeout: int = 30):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.patch(BASE + path, headers=h,
                          data=json.dumps(body) if body is not None else None, timeout=timeout)


def admin_login() -> str:
    r = post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def register_fresh_user() -> Dict[str, Any]:
    email = f"build16_{uuid.uuid4().hex[:10]}@example.com"
    pw = "Sup3rTest!2026"
    r = post("/auth/register", {"email": email, "password": pw})
    assert r.status_code == 200, r.text
    j = r.json()
    return {"token": j["access_token"], "id": j["user"]["id"], "email": email, "password": pw}


# --------------------------------------------------------------------
# 1-6. Auth + Account
# --------------------------------------------------------------------
def section_auth():
    print("\n=== 1-6. Auth + Account ===")
    email = f"build16_{uuid.uuid4().hex[:10]}@example.com"
    pw = "Sup3rTest!2026"

    # 1
    r = post("/auth/register", {"email": email, "password": pw})
    ok = r.status_code == 200
    j = r.json() if ok else {}
    log("01 POST /auth/register new",
        ok and "access_token" in j and "user" in j,
        f"status={r.status_code} has_token={'access_token' in j} has_user={'user' in j}")
    user_token = j.get("access_token", "")
    user_id = j.get("user", {}).get("id")

    # 2
    r = post("/auth/register", {"email": email, "password": pw})
    log("02 POST /auth/register dup → 400", r.status_code == 400, f"status={r.status_code} body={r.text[:160]}")

    # 3
    r = post("/auth/login", {"email": email, "password": pw})
    log("03 POST /auth/login correct → 200",
        r.status_code == 200 and "access_token" in r.json(),
        f"status={r.status_code}")

    # 4
    r = post("/auth/login", {"email": email, "password": "wrongpw_xxxxxxxx"})
    log("04 POST /auth/login wrong → 401", r.status_code == 401, f"status={r.status_code}")

    # 5
    r = get("/auth/me", user_token)
    j = r.json() if r.status_code == 200 else {}
    log("05 GET /auth/me → 200",
        r.status_code == 200 and j.get("email") == email,
        f"status={r.status_code} email={j.get('email')}")

    # 6
    r = get("/auth/me")
    log("06 GET /auth/me no token → 401", r.status_code == 401, f"status={r.status_code}")

    return user_token, user_id, email


# --------------------------------------------------------------------
# 7-8. Packages + IAP
# --------------------------------------------------------------------
def section_packages(user_token: str):
    print("\n=== 7-8. Packages ===")

    # 7
    r = get("/packages", user_token)
    ok = r.status_code == 200
    body = r.json() if ok else {}
    pkgs = body.get("packages") if isinstance(body, dict) else body
    ids = {p.get("id") for p in pkgs} if isinstance(pkgs, list) else set()
    log("07 GET /packages → 11 incl adfree_399",
        ok and isinstance(pkgs, list) and len(pkgs) == 11 and "adfree_399" in ids,
        f"status={r.status_code} n_pkgs={len(pkgs) if isinstance(pkgs, list) else 'n/a'} adfree={'adfree_399' in ids}")

    # 8
    r = post("/packages/buy", {"garbage": "ohno"}, user_token)
    log("08 POST /packages/buy malformed → 422", r.status_code == 422, f"status={r.status_code}")


# --------------------------------------------------------------------
# 9-10. Mining + Dashboard
# --------------------------------------------------------------------
def section_dashboard(user_token: str):
    print("\n=== 9-10. Mining + Dashboard ===")

    r = get("/dashboard", user_token)
    j = r.json() if r.status_code == 200 else {}
    needed = {"hash_rate_total", "machines", "balance_btc"}
    has_all = needed.issubset(j.keys()) if isinstance(j, dict) else False
    log("09 GET /dashboard → 200 hash+machines+balance",
        r.status_code == 200 and has_all,
        f"status={r.status_code} keys={sorted(list(j.keys()))[:14] if isinstance(j, dict) else 'n/a'}")

    r = get("/machines", user_token)
    j = r.json() if r.status_code == 200 else None
    machines = j.get("machines") if isinstance(j, dict) and "machines" in j else j
    log("10 GET /machines → 200 array",
        r.status_code == 200 and isinstance(machines, list),
        f"status={r.status_code} n_machines={len(machines) if isinstance(machines, list) else 'n/a'}")


# --------------------------------------------------------------------
# 11-12. Daily check-in
# --------------------------------------------------------------------
def section_checkin(user_token: str):
    print("\n=== 11-12. Daily check-in ===")
    # review_request says POST /api/checkin/daily but actual route is /daily-checkin
    # Try both paths so we report accurately.
    r = post("/checkin/daily", None, user_token)
    if r.status_code == 404:
        log("11 POST /checkin/daily 1st → 200 (NOTE: actual route is /daily-checkin)",
            False, f"status=404 — route /checkin/daily NOT FOUND in backend; trying /daily-checkin")
        r = post("/daily-checkin", None, user_token)
        log("11b POST /daily-checkin 1st → 200",
            r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
        r2 = post("/daily-checkin", None, user_token)
        log("12 POST /daily-checkin 2nd → 400 already",
            r2.status_code == 400, f"status={r2.status_code} body={r2.text[:160]}")
    else:
        log("11 POST /checkin/daily 1st → 200", r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
        r2 = post("/checkin/daily", None, user_token)
        log("12 POST /checkin/daily 2nd → 400 already",
            r2.status_code == 400, f"status={r2.status_code} body={r2.text[:160]}")


# --------------------------------------------------------------------
# 13. Referrals
# --------------------------------------------------------------------
def section_referrals(user_token: str):
    print("\n=== 13. Referrals ===")
    r = get("/referrals/summary", user_token)
    if r.status_code == 404:
        log("13 GET /referrals/summary → 200 (NOTE: actual route is /referral)",
            False, f"status=404 — /referrals/summary NOT FOUND; trying /referral")
        r = get("/referral", user_token)
        log("13b GET /referral → 200",
            r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")
    else:
        log("13 GET /referrals/summary → 200", r.status_code == 200, f"status={r.status_code}")


# --------------------------------------------------------------------
# 14-16. Free Forever
# --------------------------------------------------------------------
def section_free_forever(user_token: str):
    print("\n=== 14-16. Free Forever ===")
    # 14
    r = get("/free-forever/status", user_token)
    j = r.json() if r.status_code == 200 else {}
    log("14 GET /free-forever/status",
        r.status_code == 200 and j.get("hash_rate_display") == "500 GH/s" and j.get("duration_hours") == 24,
        f"status={r.status_code} hash_rate_display={j.get('hash_rate_display')} duration_hours={j.get('duration_hours')}")

    # 15
    r = post("/free-forever/activate", None, user_token)
    log("15 POST /free-forever/activate fresh → 200",
        r.status_code == 200, f"status={r.status_code} body={r.text[:160]}")

    # 16
    r = post("/free-forever/activate", None, user_token)
    body_text = r.text
    log("16 POST /free-forever/activate 2nd → 400 cooldown msg",
        r.status_code == 400 and ("already active" in body_text.lower() or "wait" in body_text.lower()),
        f"status={r.status_code} body={body_text[:200]}")


# --------------------------------------------------------------------
# 17-21. Withdraw
# --------------------------------------------------------------------
def section_withdraw(admin_token: str, user_token: str):
    print("\n=== 17-21. Withdraw ===")
    # 17
    r = get("/withdraw/methods", admin_token)
    j = r.json() if r.status_code == 200 else {}
    log("17 admin /withdraw/methods (min=1 fee=0 admin_unlimited=true)",
        r.status_code == 200 and j.get("min_sats") == 1 and j.get("fee_pct") == 0 and j.get("admin_unlimited") is True,
        f"min={j.get('min_sats')} fee_pct={j.get('fee_pct')} admin_unlimited={j.get('admin_unlimited')}")

    # 18 — spec says fee_pct=0.10 for user (Build #14)
    r = get("/withdraw/methods", user_token)
    j = r.json() if r.status_code == 200 else {}
    log("18 user /withdraw/methods (min=150000 fee=0.10 admin_unlimited=false)",
        r.status_code == 200 and j.get("min_sats") == 150000 and abs(j.get("fee_pct", 0) - 0.10) < 1e-9 and j.get("admin_unlimited") is False,
        f"min={j.get('min_sats')} fee_pct={j.get('fee_pct')} admin_unlimited={j.get('admin_unlimited')}")

    # 19
    r = post("/withdraw", {"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 10}, user_token)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    log("19 user withdraw amount=10 → 400 'Minimum 150,000'",
        r.status_code == 400 and "150,000" in detail,
        f"status={r.status_code} detail={detail[:160]}")

    # 20
    r = post("/withdraw", {"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 0}, user_token)
    log("20 user withdraw amount=0 → 400/422",
        r.status_code in (400, 422), f"status={r.status_code} body={r.text[:160]}")

    # 21
    r = post("/withdraw", {"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 200_000_000}, user_token)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    log("21 user withdraw 200M sats → 400 max/insufficient",
        r.status_code == 400 and ("maximum" in detail.lower() or "insufficient" in detail.lower() or "exceeds" in detail.lower() or "cap" in detail.lower()),
        f"status={r.status_code} detail={detail[:200]}")


# --------------------------------------------------------------------
# 22-23. Auto settings
# --------------------------------------------------------------------
def section_auto(user_token: str):
    print("\n=== 22-23. Auto settings ===")
    r = get("/auto/settings", user_token)
    j = r.json() if r.status_code == 200 else {}
    log("22 GET /auto/settings → 200",
        r.status_code == 200 and "auto_checkin" in j and "auto_reinvest" in j,
        f"status={r.status_code} keys={list(j.keys())}")

    current = bool(j.get("auto_reinvest", False))
    r = post("/auto/settings", {"auto_reinvest": not current}, user_token)
    j2 = r.json() if r.status_code == 200 else {}
    log("23 POST /auto/settings toggle → 200",
        r.status_code == 200 and bool(j2.get("auto_reinvest")) == (not current),
        f"status={r.status_code} new_auto_reinvest={j2.get('auto_reinvest')}")


# --------------------------------------------------------------------
# 24. Transactions
# --------------------------------------------------------------------
def section_transactions(user_token: str):
    print("\n=== 24. Transactions ===")
    r = get("/transactions", user_token)
    j = r.json() if r.status_code == 200 else None
    arr = j.get("transactions") if isinstance(j, dict) and "transactions" in j else j
    log("24 GET /transactions → 200 array",
        r.status_code == 200 and isinstance(arr, list),
        f"status={r.status_code} n={len(arr) if isinstance(arr, list) else 'n/a'}")


# --------------------------------------------------------------------
# 25-26. AI ticker + agents
# --------------------------------------------------------------------
def section_ai(user_token: str):
    print("\n=== 25-26. AI ticker + agents ===")
    r = get("/ai/ticker", user_token)
    j = r.json() if r.status_code == 200 else {}
    log("25 GET /ai/ticker → 200",
        r.status_code == 200 and ("text" in j or "ticker" in j),
        f"status={r.status_code} keys={list(j.keys()) if isinstance(j, dict) else 'n/a'}")

    r = get("/ai/agents", user_token)
    j = r.json() if r.status_code == 200 else {}
    agents = j.get("agents") if isinstance(j, dict) and "agents" in j else j
    log("26 GET /ai/agents → 200",
        r.status_code == 200 and isinstance(agents, list) and len(agents) == 6,
        f"status={r.status_code} n_agents={len(agents) if isinstance(agents, list) else 'n/a'}")


# --------------------------------------------------------------------
# 27-36. Admin endpoints
# --------------------------------------------------------------------
def section_admin(admin_token: str, user_token: str, user_id: str):
    print("\n=== 27-36. Admin endpoints ===")
    # 27
    r = get("/admin/analytics", admin_token)
    log("27 /admin/analytics admin → 200", r.status_code == 200, f"status={r.status_code}")
    # 28
    r = get("/admin/analytics", user_token)
    log("28 /admin/analytics non-admin → 403", r.status_code == 403, f"status={r.status_code}")
    # 29
    r = get("/admin/users", admin_token)
    log("29 /admin/users admin → 200", r.status_code == 200, f"status={r.status_code}")
    # 30
    r = get("/admin/transactions", admin_token)
    log("30 /admin/transactions admin → 200", r.status_code == 200, f"status={r.status_code}")
    # 31
    r = get("/admin/audit", admin_token)
    log("31 /admin/audit admin → 200", r.status_code == 200, f"status={r.status_code}")
    # 32
    r = get("/admin/ai/agents", admin_token)
    j = r.json() if r.status_code == 200 else {}
    agents = j.get("agents") if isinstance(j, dict) and "agents" in j else j
    log("32 /admin/ai/agents admin → 200",
        r.status_code == 200 and isinstance(agents, list) and len(agents) >= 1,
        f"status={r.status_code} n={len(agents) if isinstance(agents, list) else 'n/a'}")
    # 33
    agent_id = None
    if isinstance(agents, list) and agents:
        agent_id = agents[0].get("id") or agents[0].get("agent_id") or agents[0].get("key")
    if agent_id:
        r = patch(f"/admin/ai/agents/{agent_id}",
                  {"daily_pct": 0.04, "win_rate": 0.8, "signal_strength": "high"},
                  admin_token)
        log("33 PATCH /admin/ai/agents/{id} admin → 200",
            r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    else:
        log("33 PATCH /admin/ai/agents/{id} admin → 200", False, "no agent_id found")

    # 34
    r = post("/admin/ai/regenerate", None, admin_token)
    log("34 POST /admin/ai/regenerate admin → 200", r.status_code == 200, f"status={r.status_code}")
    # 35
    r = get("/admin/fees/summary", admin_token)
    j = r.json() if r.status_code == 200 else {}
    needed = {"fees_collected_sats", "available_sats", "fees_reinvested_sats"}
    log("35 GET /admin/fees/summary admin → 200",
        r.status_code == 200 and needed.issubset(j.keys()),
        f"status={r.status_code} keys={sorted(list(j.keys()))[:10]}")
    # 36
    available_sats = int(j.get("available_sats", 0)) if isinstance(j, dict) else 0
    r = post("/admin/fees/reinvest", {"target_user_id": None, "note": "test reinvest"}, admin_token)
    if available_sats == 0:
        log("36 POST /admin/fees/reinvest fees=0 → 400",
            r.status_code == 400, f"status={r.status_code} body={r.text[:200]}")
    else:
        # Pool is not empty — call again, second should be 400 if drained, else just note status.
        log(f"36 POST /admin/fees/reinvest (available={available_sats}) → status",
            r.status_code in (200, 400), f"status={r.status_code} body={r.text[:200]} note=pool was not 0")


# --------------------------------------------------------------------
# 37-47. Premium Support (Build #15)
# --------------------------------------------------------------------
def section_support(admin_token: str, user_token: str, user_id: str):
    print("\n=== 37-47. Premium Support ===")
    r = get("/support/thread", user_token)
    j = r.json() if r.status_code == 200 else {}
    log("37 GET /support/thread user → 200 thread+messages",
        r.status_code == 200 and "thread" in j and "messages" in j,
        f"status={r.status_code} keys={list(j.keys())}")

    r = post("/support/messages", {"body": "Hello, I need help with my account."}, user_token)
    log("38 POST /support/messages user → 200",
        r.status_code == 200 and r.json().get("ok") is True,
        f"status={r.status_code} body={r.text[:200]}")

    r = get("/support/unread", user_token)
    log("39 GET /support/unread user → 200",
        r.status_code == 200 and "unread_user_count" in r.json(),
        f"status={r.status_code} body={r.text[:200]}")

    r = get("/admin/support/threads", admin_token)
    j = r.json() if r.status_code == 200 else {}
    threads = j.get("threads") if isinstance(j, dict) else None
    log("40 GET /admin/support/threads admin → 200",
        r.status_code == 200 and isinstance(threads, list),
        f"status={r.status_code} n_threads={len(threads) if isinstance(threads, list) else 'n/a'}")

    r = get("/admin/support/unread", admin_token)
    log("41 GET /admin/support/unread admin → 200",
        r.status_code == 200 and "unread_admin_count" in r.json(),
        f"status={r.status_code} body={r.text[:200]}")

    r = get(f"/admin/support/threads/{user_id}", admin_token)
    log("42 GET /admin/support/threads/{user_id} admin → 200",
        r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

    r = post(f"/admin/support/threads/{user_id}/reply", {"body": "We're on it!"}, admin_token)
    log("43 POST /admin/support/threads/{user_id}/reply admin → 200",
        r.status_code == 200 and r.json().get("message", {}).get("sender") == "admin",
        f"status={r.status_code} body={r.text[:200]}")

    r = post(f"/admin/support/threads/{user_id}/close", None, admin_token)
    log("44 POST /admin/support/threads/{user_id}/close admin → 200",
        r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")

    r = post("/support/messages", {"body": ""}, user_token)
    log("45 POST /support/messages empty → 400/422", r.status_code in (400, 422), f"status={r.status_code}")

    r = post("/support/messages", {"body": "x" * 2001}, user_token)
    log("46 POST /support/messages 2001-char → 422", r.status_code == 422, f"status={r.status_code}")

    r = get("/admin/support/threads", user_token)
    log("47 cross-account: /admin/support/threads as non-admin → 403",
        r.status_code == 403, f"status={r.status_code}")


# --------------------------------------------------------------------
# 48. Performance smoke
# --------------------------------------------------------------------
def section_performance(admin_token: str, user_token: str):
    print("\n=== 48. Performance smoke (<500ms) ===")
    targets = [
        ("/support/thread", user_token),
        ("/admin/support/threads", admin_token),
        ("/support/unread", user_token),
        ("/admin/support/unread", admin_token),
        ("/admin/ai/agents", admin_token),
        ("/admin/fees/summary", admin_token),
        ("/free-forever/status", user_token),
        ("/withdraw/methods", user_token),
    ]
    for path, tok in targets:
        t0 = time.time()
        r = get(path, tok)
        dt_ms = (time.time() - t0) * 1000
        log(f"48 {path} <500ms",
            r.status_code == 200 and dt_ms < 500,
            f"{dt_ms:.0f}ms status={r.status_code}")


# --------------------------------------------------------------------
# 49-50. Edge cases
# --------------------------------------------------------------------
def section_edge_cases(user_token: str):
    print("\n=== 49-50. Edge cases ===")
    garbage_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.garbage.signature"
    # 49
    protected_paths = ["/auth/me", "/dashboard", "/machines", "/transactions",
                       "/free-forever/status", "/support/thread"]
    all_401 = True
    statuses = {}
    for p in protected_paths:
        r = get(p, garbage_token)
        statuses[p] = r.status_code
        if r.status_code != 401:
            all_401 = False
    log("49 garbage JWT → 401 on all protected", all_401,
        f"statuses={statuses}")

    # 50 — POST without Content-Type but with valid body
    r = post("/auto/settings", {"auto_reinvest": True}, user_token, raw=True)
    # If sent raw with dict it's str(dict) — let's force a json-body without Content-Type header
    r = requests.post(BASE + "/auto/settings",
                      headers={"Authorization": f"Bearer {user_token}"},
                      data=json.dumps({"auto_reinvest": True}),
                      timeout=20)
    log("50 POST without Content-Type header → 200/422 (graceful)",
        r.status_code in (200, 422, 415, 400),
        f"status={r.status_code} body={r.text[:200]}")


# --------------------------------------------------------------------
# Run
# --------------------------------------------------------------------
def main():
    admin_token = admin_login()
    user_token, user_id, user_email = section_auth()
    print(f"\nFresh user: {user_email} id={user_id}")

    section_packages(user_token)
    section_dashboard(user_token)
    section_checkin(user_token)
    section_referrals(user_token)
    section_free_forever(user_token)
    section_withdraw(admin_token, user_token)
    section_auto(user_token)
    section_transactions(user_token)
    section_ai(user_token)
    section_admin(admin_token, user_token, user_id)
    section_support(admin_token, user_token, user_id)
    section_performance(admin_token, user_token)
    section_edge_cases(user_token)

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"{passed}/{total} passed")
    fails = [(n, d) for n, ok, d in results if not ok]
    if fails:
        print("\nFAILURES:")
        for n, d in fails:
            print(f"  - {n} :: {d}")


if __name__ == "__main__":
    main()
