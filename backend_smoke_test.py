#!/usr/bin/env python3
"""
Smoke regression — Satoshi Cloud Miner Build #11 prep
Quick sanity sweep of 6 buckets after frontend-only changes.
"""
import os
import sys
import json
import requests

BASE = "https://ios-clone-platform.preview.emergentagent.com"
API = f"{BASE}/api"
ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASS = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"

results = {"pass": [], "fail": []}


def check(label, cond, detail=""):
    if cond:
        results["pass"].append(label)
        print(f"PASS  {label}  {detail}")
    else:
        results["fail"].append(f"{label}  {detail}")
        print(f"FAIL  {label}  {detail}")


def bucket(name):
    print(f"\n===== {name} =====")


# 1. AUTH
bucket("1. Auth")
admin_token = None
try:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=20,
    )
    check("auth.login.status_200", r.status_code == 200, f"http={r.status_code}")
    data = r.json() if r.status_code == 200 else {}
    admin_token = data.get("access_token")
    check("auth.login.access_token_present", bool(admin_token))
    user = data.get("user", {}) or {}
    check(
        "auth.login.user.is_admin_true",
        user.get("is_admin") is True,
        f"is_admin={user.get('is_admin')}",
    )
except Exception as e:
    check("auth.login", False, str(e))

if admin_token:
    try:
        r = requests.get(
            f"{API}/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=20,
        )
        check("auth.me.status_200", r.status_code == 200, f"http={r.status_code}")
        me = r.json() if r.status_code == 200 else {}
        check(
            "auth.me.is_admin_true",
            me.get("is_admin") is True,
            f"is_admin={me.get('is_admin')}",
        )
    except Exception as e:
        check("auth.me", False, str(e))


# 2. PACKAGES
bucket("2. Packages")
try:
    r = requests.get(f"{API}/packages", timeout=20)
    check("packages.status_200", r.status_code == 200, f"http={r.status_code}")
    pkgs = r.json() if r.status_code == 200 else []
    # accept either {packages: [...]} or [...]
    if isinstance(pkgs, dict) and "packages" in pkgs:
        pkgs = pkgs["packages"]
    check(
        "packages.count_11",
        isinstance(pkgs, list) and len(pkgs) == 11,
        f"count={len(pkgs) if isinstance(pkgs, list) else 'n/a'}",
    )
    adfree = None
    if isinstance(pkgs, list):
        for p in pkgs:
            pid = p.get("id") or p.get("package_id") or p.get("sku")
            if pid == "adfree_399":
                adfree = p
                break
    check("packages.adfree_399_present", adfree is not None)
    if adfree is not None:
        ent = adfree.get("entitlement")
        check(
            "packages.adfree_399.entitlement=='ad_free'",
            ent == "ad_free",
            f"entitlement={ent}",
        )
except Exception as e:
    check("packages", False, str(e))


# 3. WITHDRAW METHODS
bucket("3. Withdraw")
try:
    r = requests.get(f"{API}/withdraw/methods", timeout=20)
    check("withdraw.methods.status_200", r.status_code == 200, f"http={r.status_code}")
    payload = r.json() if r.status_code == 200 else {}
    # accept either dict with keys or { "methods": [...] } shape with lightning
    candidate = payload
    if isinstance(payload, dict) and "methods" in payload:
        # may also expose top-level params
        ln = None
        for m in payload.get("methods", []):
            if m.get("id") == "lightning":
                ln = m
                break
        candidate = {**payload, **(ln or {})}
    def gv(k):
        return candidate.get(k) if isinstance(candidate, dict) else None
    check("withdraw.min_sats==20", gv("min_sats") == 20, f"min_sats={gv('min_sats')}")
    check(
        "withdraw.max_sats==2500",
        gv("max_sats") == 2500,
        f"max_sats={gv('max_sats')}",
    )
    check(
        "withdraw.fee_pct==0.05",
        gv("fee_pct") == 0.05,
        f"fee_pct={gv('fee_pct')}",
    )
    check(
        "withdraw.fee_flat_sats==1",
        gv("fee_flat_sats") == 1,
        f"fee_flat_sats={gv('fee_flat_sats')}",
    )
except Exception as e:
    check("withdraw.methods", False, str(e))


# 4. ADMIN ENDPOINTS
bucket("4. Admin endpoints")
if admin_token:
    h = {"Authorization": f"Bearer {admin_token}"}
    try:
        r = requests.get(f"{API}/admin/analytics", headers=h, timeout=20)
        check(
            "admin.analytics.status_200",
            r.status_code == 200,
            f"http={r.status_code}",
        )
    except Exception as e:
        check("admin.analytics", False, str(e))

    try:
        r = requests.get(f"{API}/admin/users?search=", headers=h, timeout=20)
        check(
            "admin.users.status_200",
            r.status_code == 200,
            f"http={r.status_code}",
        )
        body = r.json() if r.status_code == 200 else None
        users_arr = body if isinstance(body, list) else (
            body.get("users") if isinstance(body, dict) else None
        )
        check(
            "admin.users.is_array",
            isinstance(users_arr, list),
            f"len={len(users_arr) if isinstance(users_arr, list) else 'n/a'}",
        )
    except Exception as e:
        check("admin.users", False, str(e))

    try:
        r = requests.get(f"{API}/admin/transactions", headers=h, timeout=20)
        check(
            "admin.transactions.status_200",
            r.status_code == 200,
            f"http={r.status_code}",
        )
    except Exception as e:
        check("admin.transactions", False, str(e))
else:
    check("admin.endpoints", False, "no admin token from auth.login")


# 5. AI TICKER
bucket("5. AI ticker")
try:
    r = requests.get(f"{API}/ai/ticker", timeout=30)
    check("ai.ticker.status_200", r.status_code == 200, f"http={r.status_code}")
    body = r.json() if r.status_code == 200 else {}
    check("ai.ticker.text_present", bool(body.get("text")), f"text_len={len(body.get('text') or '')}")
    check(
        "ai.ticker.generated_at_present",
        bool(body.get("generated_at")),
        f"generated_at={body.get('generated_at')}",
    )
except Exception as e:
    check("ai.ticker", False, str(e))


# 6. AUTO SETTINGS
bucket("6. Auto settings")
if admin_token:
    h = {"Authorization": f"Bearer {admin_token}"}
    try:
        r = requests.get(f"{API}/auto/settings", headers=h, timeout=20)
        check(
            "auto.settings.status_200",
            r.status_code == 200,
            f"http={r.status_code}",
        )
        body = r.json() if r.status_code == 200 else {}
        # Defaults per test_result.md history:
        #   auto_checkin=true, auto_reinvest=false,
        #   auto_reinvest_min_balance_usd=4.99
        # admin may have toggled auto_reinvest earlier, so only sanity check keys.
        check(
            "auto.settings.has_auto_checkin_key",
            "auto_checkin" in body,
            f"keys={list(body.keys())}",
        )
        check(
            "auto.settings.has_auto_reinvest_key",
            "auto_reinvest" in body,
            "",
        )
    except Exception as e:
        check("auto.settings", False, str(e))
else:
    check("auto.settings", False, "no admin token from auth.login")


print("\n===== SUMMARY =====")
print(f"PASS: {len(results['pass'])}")
print(f"FAIL: {len(results['fail'])}")
if results["fail"]:
    print("\nFailed checks:")
    for f in results["fail"]:
        print(f"  - {f}")
sys.exit(0 if not results["fail"] else 1)
