#!/usr/bin/env python3
"""
Build #17 Backend Smoke Regression Test
8 checks, ~2 min total
"""
import requests
import uuid
import json
import sys

BASE_URL = "https://ios-clone-platform.preview.emergentagent.com"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"

results = []

def record(num, name, passed, detail=""):
    icon = "PASS" if passed else "FAIL"
    print(f"[{icon}] #{num} {name}")
    if detail:
        print(f"        {detail}")
    results.append({"num": num, "name": name, "passed": passed, "detail": detail})

def main():
    # 1. Admin login
    try:
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                          timeout=15)
        ok = r.status_code == 200
        admin_token = None
        is_admin = False
        if ok:
            data = r.json()
            admin_token = data.get("access_token") or data.get("token")
            user = data.get("user") or {}
            is_admin = user.get("is_admin", False)
            ok = bool(admin_token) and is_admin
        record(1, "POST /api/auth/login admin -> 200 with is_admin=true",
               ok, f"status={r.status_code}, is_admin={is_admin}")
    except Exception as e:
        record(1, "POST /api/auth/login admin", False, str(e))
        admin_token = None

    if not admin_token:
        print("\nAdmin login failed; aborting subsequent admin checks.")
        return

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. /withdraw/methods admin
    try:
        r = requests.get(f"{API}/withdraw/methods", headers=admin_headers, timeout=15)
        data = r.json() if r.status_code == 200 else {}
        # locate fields - may be at root or in array
        min_sats = data.get("min_sats")
        fee_pct = data.get("fee_pct")
        admin_unlimited = data.get("admin_unlimited")
        if min_sats is None and "methods" in data and data["methods"]:
            m = data["methods"][0]
            min_sats = m.get("min_sats", min_sats)
            fee_pct = m.get("fee_pct", fee_pct)
            admin_unlimited = m.get("admin_unlimited", admin_unlimited)
        ok = (r.status_code == 200 and min_sats == 1 and fee_pct == 0
              and admin_unlimited is True)
        record(2, "GET /api/withdraw/methods admin -> min=1, fee=0, admin_unlimited=true",
               ok, f"status={r.status_code}, min_sats={min_sats}, fee_pct={fee_pct}, admin_unlimited={admin_unlimited}")
    except Exception as e:
        record(2, "GET /api/withdraw/methods admin", False, str(e))

    # 3. /withdraw/methods regular user (new)
    user_token = None
    try:
        unique = uuid.uuid4().hex[:12]
        email = f"smoke_b17_{unique}@gmail.com"
        rr = requests.post(f"{API}/auth/register",
                           json={"email": email, "password": "Password!23"},
                           timeout=15)
        if rr.status_code in (200, 201):
            d = rr.json()
            user_token = d.get("access_token") or d.get("token")
        else:
            # fallback: try login
            rr = requests.post(f"{API}/auth/login",
                               json={"email": email, "password": "Password!23"},
                               timeout=15)
            if rr.status_code == 200:
                user_token = rr.json().get("access_token")
        if not user_token:
            record(3, "GET /api/withdraw/methods user", False,
                   f"could not obtain user token; register={rr.status_code}, body={rr.text[:200]}")
        else:
            r = requests.get(f"{API}/withdraw/methods",
                             headers={"Authorization": f"Bearer {user_token}"},
                             timeout=15)
            data = r.json() if r.status_code == 200 else {}
            min_sats = data.get("min_sats")
            fee_pct = data.get("fee_pct")
            if min_sats is None and "methods" in data and data["methods"]:
                m = data["methods"][0]
                min_sats = m.get("min_sats", min_sats)
                fee_pct = m.get("fee_pct", fee_pct)
            ok = (r.status_code == 200 and min_sats == 150000 and fee_pct == 0.10)
            record(3, "GET /api/withdraw/methods user -> min=150000, fee=0.10",
                   ok, f"status={r.status_code}, min_sats={min_sats}, fee_pct={fee_pct}")
    except Exception as e:
        record(3, "GET /api/withdraw/methods user", False, str(e))

    # 4. /packages -> 11
    try:
        r = requests.get(f"{API}/packages", timeout=15)
        data = r.json() if r.status_code == 200 else {}
        pkgs = data.get("packages") if isinstance(data, dict) else data
        count = len(pkgs) if isinstance(pkgs, list) else 0
        ok = r.status_code == 200 and count == 11
        record(4, "GET /api/packages -> 11 packages", ok,
               f"status={r.status_code}, count={count}")
    except Exception as e:
        record(4, "GET /api/packages", False, str(e))

    # 5. /free-forever/status (need auth - use user)
    try:
        headers = {"Authorization": f"Bearer {user_token}"} if user_token else admin_headers
        r = requests.get(f"{API}/free-forever/status", headers=headers, timeout=15)
        ok = r.status_code == 200
        record(5, "GET /api/free-forever/status -> 200",
               ok, f"status={r.status_code}, body={r.text[:120]}")
    except Exception as e:
        record(5, "GET /api/free-forever/status", False, str(e))

    # 6. /support/thread user
    try:
        headers = {"Authorization": f"Bearer {user_token}"} if user_token else admin_headers
        r = requests.get(f"{API}/support/thread", headers=headers, timeout=15)
        ok = r.status_code == 200
        record(6, "GET /api/support/thread user -> 200",
               ok, f"status={r.status_code}")
    except Exception as e:
        record(6, "GET /api/support/thread", False, str(e))

    # 7. /admin/support/threads admin
    try:
        r = requests.get(f"{API}/admin/support/threads", headers=admin_headers, timeout=15)
        ok = r.status_code == 200
        record(7, "GET /api/admin/support/threads admin -> 200",
               ok, f"status={r.status_code}")
    except Exception as e:
        record(7, "GET /api/admin/support/threads", False, str(e))

    # 8. /admin/fees/summary admin
    try:
        r = requests.get(f"{API}/admin/fees/summary", headers=admin_headers, timeout=15)
        ok = r.status_code == 200
        record(8, "GET /api/admin/fees/summary admin -> 200",
               ok, f"status={r.status_code}")
    except Exception as e:
        record(8, "GET /api/admin/fees/summary", False, str(e))

    # Summary
    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n=== Build #17 Smoke Result: {passed}/{total} PASS ===")
    for r in results:
        icon = "PASS" if r["passed"] else "FAIL"
        print(f"  [{icon}] #{r['num']} {r['name']}")
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
