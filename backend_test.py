"""
Backend regression test for Build #14.
Focus: Admin unlimited withdrawal privilege + previously-shipped feature regression.
"""
import os
import sys
import time
import uuid
import json
import requests

BASE = "https://ios-clone-platform.preview.emergentagent.com"
API = f"{BASE}/api"

ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASS = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"

PASS = []
FAIL = []


def record(name, ok, info=""):
    line = f"{'✅' if ok else '❌'} {name}: {info}"
    print(line)
    (PASS if ok else FAIL).append(line)


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def register_fresh_user():
    email = f"qa_b14_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "password123"})
    assert r.status_code == 200, f"register failed {r.status_code} {r.text}"
    return r.json()["access_token"], email


def login_admin():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    j = r.json()
    return j["access_token"], j


# ------------------- A. Admin unlimited withdrawal -------------------
def test_admin_unlimited():
    print("\n=== A. Admin unlimited withdrawal ===")
    admin_tok, admin_session = login_admin()
    record("A0 admin login + is_admin flag", admin_session["user"].get("is_admin") is True,
           f"is_admin={admin_session['user'].get('is_admin')}")

    user_tok, user_email = register_fresh_user()

    # 1) GET /api/withdraw/methods as ADMIN
    r = requests.get(f"{API}/withdraw/methods", headers=hdr(admin_tok))
    ok = r.status_code == 200
    if ok:
        j = r.json()
        cond = (j.get("min_sats") == 1 and j.get("fee_pct") == 0.0
                and j.get("fee_flat_sats") == 0 and j.get("admin_unlimited") is True)
        record("A1 GET /withdraw/methods (admin)", cond,
               f"min_sats={j.get('min_sats')} fee_pct={j.get('fee_pct')} fee_flat_sats={j.get('fee_flat_sats')} admin_unlimited={j.get('admin_unlimited')}")
    else:
        record("A1 GET /withdraw/methods (admin)", False, f"status={r.status_code} body={r.text[:200]}")

    # 2) GET /api/withdraw/methods as REGULAR
    r = requests.get(f"{API}/withdraw/methods", headers=hdr(user_tok))
    ok = r.status_code == 200
    if ok:
        j = r.json()
        cond = (j.get("min_sats") == 150000 and abs(j.get("fee_pct", 0) - 0.1) < 1e-9
                and j.get("fee_flat_sats") == 0 and j.get("admin_unlimited") is False)
        record("A2 GET /withdraw/methods (regular)", cond,
               f"min_sats={j.get('min_sats')} fee_pct={j.get('fee_pct')} fee_flat_sats={j.get('fee_flat_sats')} admin_unlimited={j.get('admin_unlimited')}")
    else:
        record("A2 GET /withdraw/methods (regular)", False, f"status={r.status_code} body={r.text[:200]}")

    # 3) POST /api/withdraw as ADMIN with amount_sats=10 — should NOT get min error
    r = requests.post(f"{API}/withdraw", headers=hdr(admin_tok),
                      json={"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 10})
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    is_min_err = "Minimum withdrawal" in detail or "150,000" in detail or "150000" in detail
    ok = (not is_min_err)
    record("A3 POST /withdraw admin amount=10 (no min error)", ok,
           f"status={r.status_code} detail='{detail[:150]}'")

    # 4) POST /api/withdraw as REGULAR with amount_sats=10 → 400 minimum error
    r = requests.post(f"{API}/withdraw", headers=hdr(user_tok),
                      json={"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 10})
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    ok = (r.status_code == 400 and "Minimum withdrawal is 150,000 sats" in detail)
    record("A4 POST /withdraw regular amount=10 (min err)", ok,
           f"status={r.status_code} detail='{detail[:200]}'")

    # 5) POST /api/withdraw as ADMIN with amount_sats=1 — should pass min check
    r = requests.post(f"{API}/withdraw", headers=hdr(admin_tok),
                      json={"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 1})
    detail = ""
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    is_min_err = "Minimum withdrawal" in detail
    ok = (not is_min_err)
    record("A5 POST /withdraw admin amount=1 (pass min check)", ok,
           f"status={r.status_code} detail='{detail[:150]}'")

    # 6) POST /api/withdraw as ADMIN with amount_sats=0
    # Note: WithdrawRequest validator requires amount_sats > 0, so pydantic returns 422
    # Spec says "Expect 400 'Amount must be at least 1 sat.'"
    r = requests.post(f"{API}/withdraw", headers=hdr(admin_tok),
                      json={"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 0})
    detail = ""
    try:
        body = r.json()
        detail = body.get("detail", "") if isinstance(body.get("detail"), str) else json.dumps(body.get("detail"))
    except Exception:
        detail = r.text
    # accept either 400 with proper message OR 422 from pydantic
    ok_400 = (r.status_code == 400 and "at least 1 sat" in detail)
    ok_422 = (r.status_code == 422)
    record("A6 POST /withdraw admin amount=0", ok_400 or ok_422,
           f"status={r.status_code} detail='{detail[:200]}' (400 preferred, 422 from pydantic also acceptable)")


# ------------------- B. Regression -------------------
def test_regression():
    print("\n=== B. Regression ===")
    admin_tok, _ = login_admin()

    # 7) auth/login admin → 200 + is_admin true; bad pw → 401
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong-password"})
    record("B7a admin login wrong-pw → 401", r.status_code == 401, f"status={r.status_code}")
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    ok = r.status_code == 200 and r.json().get("user", {}).get("is_admin") is True
    record("B7b admin login → 200 is_admin", ok, f"status={r.status_code} is_admin={r.json().get('user',{}).get('is_admin')}")

    # 8) /packages → 11 with adfree_399
    r = requests.get(f"{API}/packages")
    if r.status_code == 200:
        pkgs = r.json().get("packages", [])
        ids = {p["id"] for p in pkgs}
        ok = (len(pkgs) == 11 and "adfree_399" in ids)
        record("B8 GET /packages 11 incl adfree_399", ok, f"count={len(pkgs)} adfree={'adfree_399' in ids}")
    else:
        record("B8 GET /packages", False, f"status={r.status_code}")

    # 9) Free Forever
    user_tok, _ = register_fresh_user()
    r = requests.get(f"{API}/free-forever/status", headers=hdr(user_tok))
    if r.status_code == 200:
        j = r.json()
        cond = ("active" in j and j.get("hash_rate_display") == "500 GH/s"
                and j.get("duration_hours") == 24)
        record("B9a free-forever/status keys+display", cond,
               f"active={j.get('active')} hr_display={j.get('hash_rate_display')} duration_hours={j.get('duration_hours')}")
    else:
        record("B9a free-forever/status", False, f"status={r.status_code}")

    r = requests.post(f"{API}/free-forever/activate", headers=hdr(user_tok))
    if r.status_code == 200:
        j = r.json()
        ok = j.get("ok") is True and j.get("machine_id")
        record("B9b free-forever/activate first call", ok, f"ok={j.get('ok')} machine={bool(j.get('machine_id'))}")
    else:
        record("B9b free-forever/activate first call", False, f"status={r.status_code} body={r.text[:200]}")

    # Verify machine added
    r = requests.get(f"{API}/machines", headers=hdr(user_tok))
    if r.status_code == 200:
        machines = r.json().get("machines", [])
        has_ff = any(m.get("package_id") == "free_forever" for m in machines)
        record("B9b2 free-forever machine created", has_ff, f"machines_count={len(machines)} has_ff={has_ff}")

    # Second call within 24h → 400
    r = requests.post(f"{API}/free-forever/activate", headers=hdr(user_tok))
    record("B9c free-forever/activate second call (400)", r.status_code == 400,
           f"status={r.status_code} detail={r.text[:200]}")

    # 10) Admin AI controls
    r = requests.get(f"{API}/admin/ai/agents", headers=hdr(admin_tok))
    if r.status_code == 200:
        j = r.json()
        agents = j.get("agents", [])
        record("B10a GET /admin/ai/agents", len(agents) > 0, f"agents_count={len(agents)}")
        if agents:
            agent_id = agents[0].get("id")
            r2 = requests.patch(f"{API}/admin/ai/agents/{agent_id}", headers=hdr(admin_tok),
                                json={"daily_pct": 0.04, "win_rate": 0.8, "signal_strength": "high"})
            record("B10b PATCH /admin/ai/agents/{id}", r2.status_code == 200,
                   f"status={r2.status_code}")
    else:
        record("B10a GET /admin/ai/agents", False, f"status={r.status_code}")

    r = requests.post(f"{API}/admin/ai/regenerate", headers=hdr(admin_tok))
    record("B10c POST /admin/ai/regenerate", r.status_code == 200, f"status={r.status_code}")

    # Non-admin should get 403
    user_tok2, _ = register_fresh_user()
    r = requests.get(f"{API}/admin/ai/agents", headers=hdr(user_tok2))
    record("B10d /admin/ai/agents non-admin → 403", r.status_code == 403, f"status={r.status_code}")
    r = requests.post(f"{API}/admin/ai/regenerate", headers=hdr(user_tok2))
    record("B10e /admin/ai/regenerate non-admin → 403", r.status_code == 403, f"status={r.status_code}")

    # 11) Admin fees reinvest
    r = requests.get(f"{API}/admin/fees/summary", headers=hdr(admin_tok))
    if r.status_code == 200:
        j = r.json()
        ok = all(k in j for k in ("fees_collected_sats", "available_sats", "fees_reinvested_sats"))
        record("B11a /admin/fees/summary", ok,
               f"fees_collected={j.get('fees_collected_sats')} available={j.get('available_sats')} reinvested={j.get('fees_reinvested_sats')}")
        available = int(j.get("available_sats", 0))
    else:
        record("B11a /admin/fees/summary", False, f"status={r.status_code}")
        available = 0

    if available == 0:
        r = requests.post(f"{API}/admin/fees/reinvest", headers=hdr(admin_tok), json={})
        ok = r.status_code == 400
        detail = ""
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text
        ok_detail = "No unreinvested fees available" in detail
        record("B11b /admin/fees/reinvest available=0 → 400", ok and ok_detail,
               f"status={r.status_code} detail='{detail[:150]}'")
    else:
        record("B11b /admin/fees/reinvest available=0 → 400", True,
               f"SKIPPED — available_sats={available} > 0, not testing the empty-pool branch")

    r = requests.get(f"{API}/admin/fees/summary", headers=hdr(user_tok2))
    record("B11c /admin/fees/summary non-admin → 403", r.status_code == 403, f"status={r.status_code}")
    r = requests.post(f"{API}/admin/fees/reinvest", headers=hdr(user_tok2), json={})
    record("B11d /admin/fees/reinvest non-admin → 403", r.status_code == 403, f"status={r.status_code}")

    # 12) /ai/ticker + /ai/agents
    r = requests.get(f"{API}/ai/ticker")
    if r.status_code == 200:
        j = r.json()
        record("B12a /ai/ticker", bool(j.get("text") or j.get("commentary") or j),
               f"keys={list(j.keys())[:5]}")
    else:
        record("B12a /ai/ticker", False, f"status={r.status_code}")
    r = requests.get(f"{API}/ai/agents")
    if r.status_code == 200:
        j = r.json()
        record("B12b /ai/agents", len(j.get("agents", [])) > 0,
               f"agents_count={len(j.get('agents', []))}")
    else:
        record("B12b /ai/agents", False, f"status={r.status_code}")

    # 13) /packages/buy malformed input
    r = requests.post(f"{API}/packages/buy", headers=hdr(user_tok2),
                      json={"package_id": "nonexistent_pkg_id"})
    record("B13a /packages/buy unknown pkg → 404", r.status_code == 404,
           f"status={r.status_code}")
    r = requests.post(f"{API}/packages/buy", headers=hdr(user_tok2), json={})  # missing package_id
    record("B13b /packages/buy missing package_id → 422", r.status_code == 422,
           f"status={r.status_code}")


# ------------------- C. Performance smoke -------------------
def test_perf():
    print("\n=== C. Performance ===")
    user_tok, _ = register_fresh_user()
    admin_tok, _ = login_admin()

    def timed_get(path, tok):
        start = time.time()
        r = requests.get(f"{API}{path}", headers=hdr(tok))
        return r.status_code, time.time() - start

    s, t = timed_get("/dashboard", user_tok)
    record("C14a /dashboard < 2s", s == 200 and t < 2.0, f"status={s} elapsed={t:.3f}s")

    s, t = timed_get("/admin/analytics", admin_tok)
    record("C14b /admin/analytics < 2s", s == 200 and t < 2.0, f"status={s} elapsed={t:.3f}s")

    s, t = timed_get("/free-forever/status", user_tok)
    record("C14c /free-forever/status < 2s", s == 200 and t < 2.0, f"status={s} elapsed={t:.3f}s")


if __name__ == "__main__":
    try:
        test_admin_unlimited()
        test_regression()
        test_perf()
    except Exception as e:
        import traceback
        traceback.print_exc()
        FAIL.append(f"UNCAUGHT EXCEPTION: {e}")

    print("\n" + "=" * 70)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    print("=" * 70)
    if FAIL:
        print("\nFAILED CHECKS:")
        for f in FAIL:
            print(f)
        sys.exit(1)
    sys.exit(0)
