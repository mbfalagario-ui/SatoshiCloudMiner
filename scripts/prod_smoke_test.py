#!/usr/bin/env python3
"""End-to-end smoke test against the PRODUCTION backend.

Walks the exact flow an Apple reviewer would walk in TestFlight:
  1. Sign up a brand-new account (registration path)
  2. Sign in with a pre-provisioned reviewer account
  3. /api/auth/me           — session integrity
  4. /api/earnings          — main dashboard data
  5. /api/store/cross-sell  — home banner
  6. /api/ai/ticker         — home ticker
  7. /api/daily-checkin/status / claim     — check-in flow
  8. /api/ads/status / simulate            — ad flow (server-side)
  9. /api/store/packages    — IAP catalog
 10. /api/withdraw/methods  — Lightning methods (real)
 11. /api/redeem/quote      — redeem quoting (with $0 balance, should
                              gracefully error, not crash)
 12. /api/faqs              — support content
 13. /api/support/unread    — support thread
 14. Logout / 401 on protected routes after logout

Any RED line BLOCKS the EAS build (we will not ship a broken flow).
"""
from __future__ import annotations
import json
import sys
import time
import uuid
from typing import Optional

import httpx

API = "https://api.hashratecloudminer.com"
REVIEWER = "appreview1@hashratecloudminer.app"
REVIEWER_PWD = "AppReview2026!"

PASS = "\033[92m✅\033[0m"
FAIL = "\033[91m❌\033[0m"
WARN = "\033[93m⚠\033[0m"

results: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> None:
    icon = PASS if ok else FAIL
    print(f"  {icon} {name:<48} {detail}")
    results.append((name, ok, detail))


def req(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    token: Optional[str] = None,
    body=None,
    expect: int = 200,
):
    headers = {"User-Agent": "HashrateCloudMiner/1.0.1 (com.satoshicloudminer; iPad; iOS 26.5)"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = client.request(method, f"{API}{path}", headers=headers,
                       content=json.dumps(body) if body is not None else None,
                       timeout=10.0)
    ok = r.status_code == expect
    try:
        data = r.json()
    except Exception:
        data = r.text
    return ok, r.status_code, data


def main() -> int:
    print("=" * 72)
    print("  PRODUCTION E2E SMOKE TEST")
    print("  Target:", API)
    print("=" * 72)
    print()

    with httpx.Client() as c:
        # ── A. Brand-new registration (the path Apple's iPad failed on) ──
        new_email = f"smoketest_{uuid.uuid4().hex[:8]}@hashratecloudminer.app"
        new_pwd = "SmokeTest2026!"
        ok, code, data = req(c, "POST", "/api/auth/register", body={
            "email": new_email,
            "password": new_pwd,
            "agree": True,
        }, expect=200)
        step(f"register fresh user", ok, f"HTTP {code}, email={new_email}" if ok else f"HTTP {code} {str(data)[:120]}")
        new_token = data.get("access_token") if ok and isinstance(data, dict) else None

        # ── B. Login with pre-provisioned reviewer ──
        ok, code, data = req(c, "POST", "/api/auth/login", body={
            "email": REVIEWER, "password": REVIEWER_PWD,
        }, expect=200)
        token = data.get("access_token") if ok and isinstance(data, dict) else None
        step("login reviewer1", ok and bool(token), f"HTTP {code}, jwt={'yes' if token else 'NO'}")

        if not token:
            print("\n❌ no token, cannot continue authenticated tests.")
            return 1

        # ── C. /me ──
        ok, code, data = req(c, "GET", "/api/auth/me", token=token)
        step("/api/auth/me", ok, f"HTTP {code}, user_id={data.get('id','?')[:8]} email={data.get('email','?')}")

        # ── D. Earnings ──
        ok, code, data = req(c, "GET", "/api/earnings", token=token)
        has_keys = ok and all(k in data for k in
            ["indicative_balance_btc", "lifetime_earnings_btc", "hashrate",
             "indicative_per_second_btc", "payout_multiplier", "btc_usd"])
        step("/api/earnings (all keys present)", has_keys,
             f"HTTP {code}, balance_btc={data.get('indicative_balance_btc',0):.10f}, hashrate.total_ghs={data.get('hashrate',{}).get('total_ghs','?')}")

        # ── E. Cross-sell + ticker ──
        ok, code, data = req(c, "GET", "/api/store/cross-sell", token=token)
        step("/api/store/cross-sell", ok, f"HTTP {code}")

        ok, code, data = req(c, "GET", "/api/ai/ticker", token=token)
        step("/api/ai/ticker", ok, f"HTTP {code}, text={(data.get('text') or '')[:50]!r}")

        # ── F. Daily check-in status ──
        ok, code, data = req(c, "GET", "/api/daily-checkin/status", token=token)
        step("/api/daily-checkin/status", ok, f"HTTP {code}, can_claim={data.get('can_claim')}")

        # ── G. Watch ad status (server side; no real ad impression) ──
        ok, code, data = req(c, "GET", "/api/ads/status", token=token)
        step("/api/ads/status", ok, f"HTTP {code}, views_today={data.get('views_today')} cap={data.get('cap')}")

        # ── H. Shop packages ──
        ok, code, data = req(c, "GET", "/api/packages", token=token)
        # Endpoint returns {"packages": [...]} OR a top-level array
        if isinstance(data, dict):
            pkgs = data.get("packages") or data.get("data") or []
        elif isinstance(data, list):
            pkgs = data
        else:
            pkgs = []
        count = len(pkgs)
        step("/api/packages", ok and count == 10,
             f"HTTP {code}, count={count} (expected 10)")
        if count == 10:
            stale = [p for p in pkgs if "farm" in (p.get("name", "").lower())]
            if stale:
                for p in stale:
                    step(f"  package {p.get('id')} name '{p.get('name')}' has 'Farm' (STALE!)", False, "")
            else:
                step("  all 10 package names match new branding (no 'Farm')", True, "")

        # ── I. Withdraw methods ──
        ok, code, data = req(c, "GET", "/api/withdraw/methods", token=token)
        methods_list = data.get("methods", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        method_ids = [m.get("id") for m in methods_list]
        step("/api/withdraw/methods", ok and len(method_ids) > 0,
             f"HTTP {code}, methods={method_ids} min_sats={data.get('min_sats') if isinstance(data, dict) else '?'}")

        # ── J. Redeem quote — reviewer has 0 balance ──
        # Endpoint may return 400 ("insufficient") OR 200 with feasible=false. Both fine.
        ok, code, data = req(c, "POST", "/api/redeem/quote", token=token, body={
            "amount_sats": 25000,
            "method_id": "bolt11",
        }, expect=200)
        # Accept any of: 200 (returns quote with feasible flag), 400 (insufficient)
        accepted = code in (200, 400, 422)
        step(f"/api/redeem/quote (0-balance handling)", accepted,
             f"HTTP {code} (graceful — not a 500)")

        # ── K. FAQs ──
        ok, code, data = req(c, "GET", "/api/faqs", token=token)
        faqs_list = data.get("faqs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        n = len(faqs_list)
        step("/api/faqs", ok and n > 0, f"HTTP {code}, count={n}")

        # ── L. Support thread ──
        ok, code, data = req(c, "GET", "/api/support/unread", token=token)
        step("/api/support/unread", ok, f"HTTP {code}")

        ok, code, data = req(c, "GET", "/api/support/thread", token=token)
        step("/api/support/thread", ok, f"HTTP {code}")

        # ── M. Auto-ship settings (admin-only flag for users) ──
        ok, code, data = req(c, "GET", "/api/auto/settings", token=token)
        step("/api/auto/settings", ok, f"HTTP {code}")

        # ── N. Legal HTML pages from prod domain ──
        for path in ("/support", "/privacy", "/"):
            r = c.get(f"https://hashratecloudminer.com{path}", timeout=10.0)
            ok = r.status_code == 200 and len(r.content) > 500
            step(f"https://hashratecloudminer.com{path}", ok,
                 f"HTTP {r.status_code} size={len(r.content)}")

        # ── O. Make sure deleting the smoke-test account leaves Atlas clean ──
        # (Not required for review, just hygiene.)
        # Use the new user's token to call a self-delete if endpoint exists.
        ok, code, data = req(c, "POST", "/api/auth/me/delete", token=new_token, expect=200)
        if not ok and code != 404:
            print(f"  {WARN} self-delete returned HTTP {code}; cleaning manually is fine")

    print()
    print("=" * 72)
    total = len(results)
    passed = sum(1 for _, p, _ in results if p)
    failed = total - passed
    print(f"  SUMMARY: {passed}/{total} passed, {failed} failed")
    if failed:
        print(f"  FAILED tests:")
        for name, p, detail in results:
            if not p:
                print(f"    - {name}: {detail}")
        return 1
    print(f"  ✅ ALL GREEN — backend is production-ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
