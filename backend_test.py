"""Build #22 — AdMob / Virtual Hashrate Pivot — Full Backend Regression.

Runs against the live preview backend. Saves JSON results to
/app/test_results_build22.json. Prints PASS/FAIL counts at the end.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, Optional, List

import requests

BASE = "https://ios-clone-platform.preview.emergentagent.com/api"
ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"

results: List[Dict[str, Any]] = []


def log(name: str, ok: bool, detail: str = "") -> None:
    results.append({"name": name, "ok": ok, "detail": detail})
    icon = "PASS" if ok else "FAIL"
    print(f"[{icon}] {name} :: {detail[:300]}")


def post(path: str, body: Any = None, token: Optional[str] = None, timeout: int = 30):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.post(BASE + path, headers=h,
                         data=json.dumps(body) if body is not None else None,
                         timeout=timeout)


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
                          data=json.dumps(body) if body is not None else None,
                          timeout=timeout)


# ----------------------------- A. AUTH -----------------------------
def section_auth() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    # 1. admin login
    r = post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code == 200 and r.json().get("access_token") and r.json().get("user", {}).get("is_admin"):
        log("A1 admin login", True, f"is_admin={r.json()['user'].get('is_admin')}")
        out["admin_token"] = r.json()["access_token"]
    else:
        log("A1 admin login", False, f"status={r.status_code} body={r.text[:400]}")
        return out

    # 2. register new user
    new_email = f"test_b22_{uuid.uuid4().hex[:8]}@gmail.com"
    rr = post("/auth/register", {"email": new_email, "password": "Password123!"})
    if rr.status_code == 200:
        body = rr.json()
        u = body.get("user", {})
        cond = (
            body.get("access_token")
            and float(u.get("balance_btc", -1)) == 0.0
            and int(u.get("checkin_streak", -1)) == 0
        )
        log("A2 register fresh user", cond,
            f"email={new_email} balance_btc={u.get('balance_btc')} streak={u.get('checkin_streak')}")
        out["user_token"] = body.get("access_token")
        out["user_email"] = new_email
    else:
        log("A2 register fresh user", False, f"status={rr.status_code} body={rr.text[:400]}")
        return out

    # 3. /auth/me with new user
    rm = get("/auth/me", token=out["user_token"])
    if rm.status_code == 200:
        bal = rm.json().get("balance_btc", -1)
        log("A3 /auth/me fresh user", float(bal) == 0.0, f"balance_btc={bal}")
    else:
        log("A3 /auth/me fresh user", False, f"status={rm.status_code} body={rm.text[:400]}")

    return out


# ----------------------------- B. PACKAGES -----------------------------
EXPECTED_BONUS = {
    "welcome_199": 15, "rookie_299": 19, "pro_499": 24, "elite_999": 28,
    "ultra_1999": 33, "mega_4999": 37, "giga_9999": 42, "titan_14999": 46,
    "colossus_19999": 50, "adfree_399": 0,
}


def section_packages(user_token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    r = get("/packages")
    if r.status_code != 200:
        log("B4 GET /packages", False, f"status={r.status_code}")
        return out
    pkgs = r.json().get("packages", [])
    out["packages"] = pkgs

    # validate
    if len(pkgs) != 10:
        log("B4 packages count==10", False, f"got {len(pkgs)}")
    else:
        log("B4 packages count==10", True, "")

    bad_bonus = []
    bad_price = []
    bad_display = []
    for p in pkgs:
        pid = p.get("id")
        if pid in EXPECTED_BONUS and int(p.get("first_purchase_bonus_pct", -1)) != EXPECTED_BONUS[pid]:
            bad_bonus.append(f"{pid}={p.get('first_purchase_bonus_pct')} (expected {EXPECTED_BONUS[pid]})")
        if pid != "adfree_399":
            if not (float(p.get("original_price_usd", 0)) > float(p.get("price_usd", 0))):
                bad_price.append(f"{pid} orig={p.get('original_price_usd')} price={p.get('price_usd')}")
        if not p.get("hashrate_display"):
            bad_display.append(pid)

    log("B4 bonus_pct ladder", not bad_bonus, "; ".join(bad_bonus) if bad_bonus else "all match")
    log("B4 original_price_usd > price_usd", not bad_price,
        "; ".join(bad_price) if bad_price else "ok for all mining SKUs")
    log("B4 hashrate_display present", not bad_display,
        ", ".join(bad_display) if bad_display else "all present")

    # 5. buy welcome_199 first time
    r5 = post("/packages/buy", {"package_id": "welcome_199"}, token=user_token)
    if r5.status_code == 200:
        b = r5.json()
        ok = (
            b.get("first_purchase_bonus_applied") is True
            and int(b.get("bonus_pct", 0)) == 15
            and abs(float(b.get("bonus_ghs", 0)) - 7.5) < 0.01
        )
        log("B5 first buy welcome_199 bonus 15% (7.5 GH/s)", ok,
            f"applied={b.get('first_purchase_bonus_applied')} pct={b.get('bonus_pct')} ghs={b.get('bonus_ghs')}")
    else:
        log("B5 first buy welcome_199", False, f"status={r5.status_code} body={r5.text[:300]}")

    # 6. buy again — no bonus
    r6 = post("/packages/buy", {"package_id": "welcome_199"}, token=user_token)
    if r6.status_code == 200:
        b = r6.json()
        ok = (
            b.get("first_purchase_bonus_applied") is False
            and float(b.get("bonus_ghs", 99)) == 0.0
        )
        log("B6 second buy welcome_199 no bonus", ok,
            f"applied={b.get('first_purchase_bonus_applied')} bonus_ghs={b.get('bonus_ghs')}")
    else:
        log("B6 second buy welcome_199", False, f"status={r6.status_code} body={r6.text[:300]}")

    # 7. nonexistent
    r7 = post("/packages/buy", {"package_id": "non_existent"}, token=user_token)
    log("B7 buy non_existent -> 404", r7.status_code == 404, f"status={r7.status_code}")

    return out


# ----------------------------- C. DAILY CHECK-IN -----------------------------
def section_checkin(user_token: str) -> None:
    # We need a brand-new user that hasn't bought packages so it's "fresh".
    # Actually use the one from section A. Buys don't affect checkin state.
    r = get("/daily-checkin/status", token=user_token)
    if r.status_code == 200:
        s = r.json()
        ok = (
            s.get("available") is True
            and int(s.get("next_step")) == 1
            and abs(float(s.get("next_reward_ghs", 0)) - 1.2) < 0.001
            and s.get("ladder_ghs") == [1.2, 1.6, 2.2, 3.1, 5.0, 6.4, 8.0]
            and int(s.get("boost_duration_hours")) == 24
        )
        log("C8 checkin/status fresh user", ok,
            f"avail={s.get('available')} step={s.get('next_step')} reward={s.get('next_reward_ghs')}"
            f" ladder={s.get('ladder_ghs')} boost_h={s.get('boost_duration_hours')}")
    else:
        log("C8 checkin/status fresh user", False, f"status={r.status_code}")

    # 9. POST claim
    r9 = post("/daily-checkin", token=user_token)
    if r9.status_code == 200:
        b = r9.json()
        ok = int(b.get("streak", 0)) == 1 and float(b.get("awarded_usd", -1)) == 0.0
        log("C9 POST /daily-checkin", ok, f"streak={b.get('streak')} awarded_usd={b.get('awarded_usd')}")
    else:
        log("C9 POST /daily-checkin", False, f"status={r9.status_code} body={r9.text[:300]}")

    # 10. POST again -> 400
    r10 = post("/daily-checkin", token=user_token)
    body_txt = r10.text
    cond = r10.status_code == 400 and "Check in again at" in body_txt
    log("C10 POST again -> 400 with cooldown msg", cond,
        f"status={r10.status_code} body={body_txt[:200]}")

    # 11. status after claim
    r11 = get("/daily-checkin/status", token=user_token)
    if r11.status_code == 200:
        s = r11.json()
        ok = (
            s.get("available") is False
            and int(s.get("next_step")) == 2
            and abs(float(s.get("next_reward_ghs", 0)) - 1.6) < 0.001
        )
        log("C11 status after claim", ok,
            f"avail={s.get('available')} step={s.get('next_step')} reward={s.get('next_reward_ghs')}")
    else:
        log("C11 status after claim", False, f"status={r11.status_code}")


# ----------------------------- D. REWARDED ADS -----------------------------
def section_ads(user_token: str) -> None:
    r = get("/ads/status", token=user_token)
    if r.status_code == 200:
        s = r.json()
        ok = (
            int(s.get("ads_today", -1)) == 0
            and int(s.get("daily_cap", 0)) == 30
            and int(s.get("remaining_today", 0)) == 30
            and abs(float(s.get("next_reward_ghs", 0)) - 1.5) < 0.001
            and float(s.get("active_ad_hashrate_ghs", -1)) == 0.0
        )
        log("D12 ads/status fresh", ok,
            f"ads_today={s.get('ads_today')} cap={s.get('daily_cap')} rem={s.get('remaining_today')}"
            f" next={s.get('next_reward_ghs')} active={s.get('active_ad_hashrate_ghs')}")
    else:
        log("D12 ads/status fresh", False, f"status={r.status_code}")

    # 13. first claim
    r13 = post("/ads/claim_dev", token=user_token)
    if r13.status_code == 200:
        b = r13.json()
        ok = abs(float(b.get("reward_ghs", 0)) - 1.5) < 0.001 and int(b.get("position")) == 1
        log("D13 ads/claim_dev first ad", ok,
            f"reward={b.get('reward_ghs')} pos={b.get('position')}")
    else:
        log("D13 ads/claim_dev first ad", False, f"status={r13.status_code} body={r13.text[:300]}")

    # 14. claim 5 more times -> positions 2..6, 6th should be 3.0
    positions = [1]
    rewards = [1.5]
    for i in range(5):
        rr = post("/ads/claim_dev", token=user_token)
        if rr.status_code == 200:
            positions.append(int(rr.json().get("position")))
            rewards.append(float(rr.json().get("reward_ghs")))
        else:
            log(f"D14 ads/claim_dev #{i+2}", False, f"status={rr.status_code} body={rr.text[:200]}")
            return
    ok = positions == [1, 2, 3, 4, 5, 6] and abs(rewards[-1] - 3.0) < 0.001
    log("D14 ads positions 1-6 with 6th=3.0 GH/s", ok,
        f"positions={positions} rewards={rewards}")

    # 15. ads/status now
    rs = get("/ads/status", token=user_token)
    if rs.status_code == 200:
        s = rs.json()
        expected_active = 1.5 * 5 + 3.0  # 10.5
        ok = (
            int(s.get("ads_today")) == 6
            and int(s.get("remaining_today")) == 24
            and abs(float(s.get("active_ad_hashrate_ghs", 0)) - expected_active) < 0.1
        )
        log("D15 ads/status after 6 ads (active=10.5)", ok,
            f"ads_today={s.get('ads_today')} rem={s.get('remaining_today')} active={s.get('active_ad_hashrate_ghs')}")
    else:
        log("D15 ads/status after 6 ads", False, f"status={rs.status_code}")


# ----------------------------- E. EARNINGS + CROSS-SELL -----------------------------
def section_earnings_crosssell(user_token: str) -> None:
    r = get("/earnings", token=user_token)
    if r.status_code == 200:
        b = r.json()
        hr = b.get("hashrate", {})
        ok = (
            float(b.get("indicative_balance_btc", -1)) >= 0
            and "total_ghs" in hr and "pack_ghs" in hr and "checkin_ghs" in hr and "ad_ghs" in hr
            and bool(b.get("disclaimer"))
            and int(b.get("min_redeem_sats", 0)) == 25000
        )
        log("E16 GET /earnings", ok,
            f"bal_btc={b.get('indicative_balance_btc')} hr={hr} "
            f"min_redeem_sats={b.get('min_redeem_sats')} disclaimer_len={len(str(b.get('disclaimer')))}")
    else:
        log("E16 GET /earnings", False, f"status={r.status_code}")

    # 17. cross-sell
    r17 = get("/store/cross-sell", token=user_token)
    if r17.status_code == 200:
        b = r17.json()
        ok = (
            b.get("available") is True
            and b.get("package") is not None
            and b.get("headline") == "+100%!! More Computing Power"
            and int(b.get("discount_pct")) == 25
            and str(b.get("price_label", "")).startswith("$")
            and str(b.get("price_label", "")).endswith("!")
            and str(b.get("original_price_label", "")).startswith("$")
        )
        log("E17 store/cross-sell", ok,
            f"avail={b.get('available')} headline={b.get('headline')!r} "
            f"price_label={b.get('price_label')!r} orig={b.get('original_price_label')!r} disc={b.get('discount_pct')}")
    else:
        log("E17 store/cross-sell", False, f"status={r17.status_code} body={r17.text[:300]}")


# ----------------------------- F. REDEEM -----------------------------
def section_redeem(user_token: str, admin_token: str) -> None:
    # Use a FRESH user (no balance, no purchases) for the redeem tests so
    # "Insufficient balance" can be returned cleanly. The current user_token
    # has 2x welcome_199 purchases but balance still 0.
    fresh_email = f"test_b22r_{uuid.uuid4().hex[:8]}@gmail.com"
    rr = post("/auth/register", {"email": fresh_email, "password": "Password123!"})
    if rr.status_code != 200:
        log("F-setup fresh user for redeem", False, f"status={rr.status_code}")
        return
    fresh_token = rr.json()["access_token"]

    # 18. withdraw/methods fresh user
    r18 = get("/withdraw/methods", token=fresh_token)
    if r18.status_code == 200:
        b = r18.json()
        ok = (
            int(b.get("min_sats")) == 25000
            and int(b.get("max_sats")) == 50000
            and int(b.get("fee_flat_sats")) == 150
            and int(b.get("cooldown_hours")) == 24
            and float(b.get("fee_pct")) == 0.0
            and b.get("admin_unlimited") is False
        )
        log("F18 withdraw/methods fresh", ok,
            f"min={b.get('min_sats')} max={b.get('max_sats')} fee_flat={b.get('fee_flat_sats')} "
            f"cooldown_h={b.get('cooldown_hours')} fee_pct={b.get('fee_pct')} admin_unl={b.get('admin_unlimited')}")
    else:
        log("F18 withdraw/methods fresh", False, f"status={r18.status_code}")

    # 19. as admin
    r19 = get("/withdraw/methods", token=admin_token)
    if r19.status_code == 200:
        b = r19.json()
        ok = (
            int(b.get("min_sats")) == 1
            and int(b.get("fee_flat_sats")) == 0
            and int(b.get("cooldown_hours")) == 0
            and b.get("admin_unlimited") is True
        )
        log("F19 withdraw/methods admin", ok,
            f"min={b.get('min_sats')} fee_flat={b.get('fee_flat_sats')} "
            f"cooldown_h={b.get('cooldown_hours')} admin_unl={b.get('admin_unlimited')}")
    else:
        log("F19 withdraw/methods admin", False, f"status={r19.status_code}")

    # 20. redeem/quote 25000 -> insufficient balance
    r20 = post("/redeem/quote", {"amount_sats": 25000}, token=fresh_token)
    if r20.status_code == 200:
        b = r20.json()
        errs = " | ".join(b.get("errors", []))
        ok = (b.get("ok") is False) and ("Insufficient balance" in errs)
        log("F20 quote 25000 insufficient balance", ok, f"ok={b.get('ok')} errors={errs}")
    else:
        log("F20 quote 25000", False, f"status={r20.status_code} body={r20.text[:300]}")

    # 21. quote 10000 -> below min
    r21 = post("/redeem/quote", {"amount_sats": 10000}, token=fresh_token)
    if r21.status_code == 200:
        b = r21.json()
        errs = " | ".join(b.get("errors", []))
        ok = (b.get("ok") is False) and ("Minimum redeem is 25,000" in errs)
        log("F21 quote 10000 below min", ok, f"ok={b.get('ok')} errors={errs}")
    else:
        log("F21 quote 10000", False, f"status={r21.status_code} body={r21.text[:300]}")

    # 22. quote 60000 -> above max
    r22 = post("/redeem/quote", {"amount_sats": 60000}, token=fresh_token)
    if r22.status_code == 200:
        b = r22.json()
        errs = " | ".join(b.get("errors", []))
        ok = (b.get("ok") is False) and ("Maximum redeem is 50,000" in errs)
        log("F22 quote 60000 above max", ok, f"ok={b.get('ok')} errors={errs}")
    else:
        log("F22 quote 60000", False, f"status={r22.status_code} body={r22.text[:300]}")

    # 23. POST /withdraw amount=10000 -> 400 min-sats
    r23 = post("/withdraw",
               {"method_id": "lightning", "address": "test@speed.app", "amount_sats": 10000},
               token=fresh_token)
    cond = r23.status_code == 400 and "Minimum redeem is 25,000" in r23.text
    log("F23 withdraw amount=10000 -> 400 min-sats", cond,
        f"status={r23.status_code} body={r23.text[:200]}")

    # 24. POST /withdraw 25000 fresh user (no balance) -> 400 insufficient
    r24 = post("/withdraw",
               {"method_id": "lightning", "address": "test@speed.app", "amount_sats": 25000},
               token=fresh_token)
    cond = r24.status_code == 400 and "Insufficient balance" in r24.text
    log("F24 withdraw 25000 no balance -> 400 insufficient", cond,
        f"status={r24.status_code} body={r24.text[:200]}")


# ----------------------------- G. FAQs -----------------------------
def section_faqs() -> None:
    r = get("/faqs")
    if r.status_code != 200:
        log("G25 GET /faqs", False, f"status={r.status_code}")
        return
    faqs = r.json().get("faqs", [])
    required = {
        "faq_what_is_hashrate", "faq_daily_checkin", "faq_rewarded_ads",
        "faq_indicative_earnings", "faq_how_to_redeem", "faq_redeem_minimum",
        "faq_redeem_fees",
    }
    ids_present = {f.get("id") for f in faqs}
    missing = required - ids_present
    structured = all("id" in f and "q" in f and "a" in f for f in faqs)
    ok = len(faqs) == 18 and not missing and structured
    log("G25 GET /faqs (18, required ids)", ok,
        f"count={len(faqs)} missing={missing or 'none'} structured={structured}")


# ----------------------------- H. SUPPORT AI REPLY -----------------------------
def section_support_ai(user_token: str) -> None:
    r = post("/support/ai-reply",
             {"body": "How does the daily check-in work?"},
             token=user_token,
             timeout=60)
    if r.status_code != 200:
        log("H26 POST /support/ai-reply", False, f"status={r.status_code} body={r.text[:300]}")
        return
    b = r.json()
    ai_reply = b.get("ai_reply") or ""
    sf = b.get("suggested_faqs") or []
    ok = (
        b.get("ok") is True
        and b.get("is_premium") is False
        and isinstance(ai_reply, str) and len(ai_reply) > 0
        and len(sf) > 0
    )
    first_faq_id = sf[0].get("id") if sf else None
    first_match = first_faq_id == "faq_daily_checkin"
    log("H26 /support/ai-reply non-premium", ok,
        f"premium={b.get('is_premium')} reply_len={len(ai_reply)} "
        f"suggested_faqs[0]={first_faq_id} (should be faq_daily_checkin: {first_match})")

    # 27. thread should contain both messages
    rt = get("/support/thread", token=user_token)
    if rt.status_code != 200:
        log("H27 /support/thread", False, f"status={rt.status_code}")
        return
    msgs = rt.json().get("messages", [])
    has_user = any(m.get("sender") == "user" for m in msgs)
    has_admin_ai = any(m.get("sender") == "admin" and m.get("ai_generated") for m in msgs)
    log("H27 /support/thread has user + AI admin msg", has_user and has_admin_ai,
        f"msgs={len(msgs)} has_user={has_user} has_admin_ai={has_admin_ai}")


# ----------------------------- I. ADMIN CONFIG -----------------------------
def section_admin_config(admin_token: str, user_token: str) -> None:
    r = get("/admin/config", token=admin_token)
    if r.status_code != 200:
        log("I28 GET /admin/config", False, f"status={r.status_code}")
        return
    c = r.json()
    expected = {
        "payout_multiplier": 0.85,
        "redeem_fee_sats": 150,
        "redeem_min_sats": 25000,
        "redeem_max_sats": 50000,
        "redeem_cooldown_hours": 24,
        "ad_daily_cap": 30,
        "cross_sell_discount_pct": 25,
        "support_email": "support@hashratecloudminer.com",
    }
    mismatches = []
    for k, v in expected.items():
        if c.get(k) != v and not (isinstance(v, float) and abs(float(c.get(k, 0)) - v) < 0.001):
            mismatches.append(f"{k}={c.get(k)} (expected {v})")
    if c.get("checkin_ladder_ghs") != [1.2, 1.6, 2.2, 3.1, 5.0, 6.4, 8.0]:
        mismatches.append(f"checkin_ladder_ghs={c.get('checkin_ladder_ghs')}")
    log("I28 GET /admin/config initial values", not mismatches,
        ", ".join(mismatches) if mismatches else "all match")

    # 29. patch payout multiplier
    r29 = patch("/admin/config", {"payout_multiplier": 1.0}, token=admin_token)
    if r29.status_code == 200:
        ok = abs(float(r29.json().get("payout_multiplier", 0)) - 1.0) < 0.001
        log("I29 PATCH payout=1.0", ok, f"new={r29.json().get('payout_multiplier')}")
    else:
        log("I29 PATCH payout=1.0", False, f"status={r29.status_code}")

    # 30. patch back to 0.85
    r30 = patch("/admin/config", {"payout_multiplier": 0.85}, token=admin_token)
    if r30.status_code == 200:
        ok = abs(float(r30.json().get("payout_multiplier", 0)) - 0.85) < 0.001
        log("I30 PATCH payout=0.85", ok, f"new={r30.json().get('payout_multiplier')}")
    else:
        log("I30 PATCH payout=0.85", False, f"status={r30.status_code}")

    # 31. non-admin -> 403
    r31 = get("/admin/config", token=user_token)
    log("I31 non-admin /admin/config -> 403", r31.status_code == 403, f"status={r31.status_code}")


# ----------------------------- J. REGRESSION -----------------------------
def section_regression(admin_token: str) -> None:
    r = get("/system/btc_rate")
    if r.status_code == 200:
        b = r.json()
        btc = float(b.get("btc_usd", 0))
        ok = 10000 < btc < 500000
        log("J32 /system/btc_rate", ok, f"btc_usd={btc}")
    else:
        log("J32 /system/btc_rate", False, f"status={r.status_code}")

    r = get("/system/network")
    if r.status_code == 200:
        b = r.json()
        nh = float(b.get("network_hashrate_ghs", 0))
        log("J33 /system/network hashrate>1e18", nh > 1e18, f"network_hashrate_ghs={nh}")
    else:
        log("J33 /system/network", False, f"status={r.status_code}")

    r = get("/ai/ticker", timeout=60)
    if r.status_code == 200:
        txt = r.json().get("text") or ""
        log("J34 /ai/ticker", bool(txt), f"text_len={len(txt)}")
    else:
        log("J34 /ai/ticker", False, f"status={r.status_code}")

    r = get("/ai/agents", timeout=60)
    if r.status_code == 200:
        agents = r.json().get("agents", [])
        log("J35 /ai/agents 6 agents", len(agents) == 6, f"count={len(agents)}")
    else:
        log("J35 /ai/agents", False, f"status={r.status_code}")

    r = get("/admin/analytics", token=admin_token)
    log("J36 /admin/analytics admin", r.status_code == 200, f"status={r.status_code}")

    # 37. Migration sanity — schema_meta doc via MongoDB (direct query)
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        mc = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        doc = mc[db_name]["schema_meta"].find_one({"id": "schema"})
        ok = doc is not None and doc.get("version") == "v22_admob_pivot"
        log("J37 schema_meta v22_admob_pivot", ok,
            f"doc={ {k: doc.get(k) for k in ('id', 'version')} if doc else None }")
    except Exception as e:
        log("J37 schema_meta v22_admob_pivot", False, f"mongo exc={e}")


def main():
    print(f"=== Build #22 Regression vs {BASE} ===\n")
    auth = section_auth()
    admin_token = auth.get("admin_token")
    user_token = auth.get("user_token")
    if not admin_token or not user_token:
        print("FATAL: auth failed — cannot continue.")
        save_and_summarize()
        return

    section_packages(user_token)
    section_checkin(user_token)
    section_ads(user_token)
    section_earnings_crosssell(user_token)
    section_redeem(user_token, admin_token)
    section_faqs()
    # H — support AI must run on a fresh NON-premium user (no paid plans).
    nonprem_email = f"test_b22_np_{uuid.uuid4().hex[:8]}@gmail.com"
    rr = post("/auth/register", {"email": nonprem_email, "password": "Password123!"})
    if rr.status_code == 200:
        section_support_ai(rr.json()["access_token"])
    else:
        log("H26 setup non-premium user", False, f"status={rr.status_code}")
    section_admin_config(admin_token, user_token)
    section_regression(admin_token)
    save_and_summarize()


def save_and_summarize():
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    summary = {
        "base": BASE,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "failures": [r for r in results if not r["ok"]],
        "all": results,
    }
    with open("/app/test_results_build22.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n=== RESULTS: {passed}/{len(results)} PASS, {failed} FAIL ===")
    if failed:
        print("\nFailures:")
        for r in summary["failures"]:
            print(f"  - {r['name']} :: {r['detail'][:300]}")


if __name__ == "__main__":
    main()
