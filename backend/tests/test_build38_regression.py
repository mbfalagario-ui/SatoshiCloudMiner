"""
Build 38 backend regression smoke (post cross-sell banner removal + Profile FAQ
duplicate fix).

Target: PRODUCTION backend https://api.hashratecloudminer.com
Reviewer accounts: appreview1/2/3@hashratecloudminer.app / AppReview2026!

Covers App-Review critical checks 1-10 from the review request.
"""
import re
import json
import pytest
import requests

PROD_URL = "https://api.hashratecloudminer.com"

REVIEWERS = [
    ("appreview1@hashratecloudminer.app", "AppReview2026!"),
    ("appreview2@hashratecloudminer.app", "AppReview2026!"),
    ("appreview3@hashratecloudminer.app", "AppReview2026!"),
]

RIG_RE = re.compile(r"\bRig\b")
BANNED_FAQ_PHRASES = ["View Booster Options", "+100%", "Colossus Rig", "Pro Rig", "Ultra Rig"]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def reviewer1_token(session):
    r = session.post(
        f"{PROD_URL}/api/auth/login",
        json={"email": REVIEWERS[0][0], "password": REVIEWERS[0][1]},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    assert "access_token" in body
    return body["access_token"]


def _authed_headers(token):
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


def _contains_rig(obj) -> bool:
    """Recursively check if any string value in `obj` matches the word \\bRig\\b."""
    if isinstance(obj, str):
        return bool(RIG_RE.search(obj))
    if isinstance(obj, dict):
        return any(_contains_rig(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_contains_rig(v) for v in obj)
    return False


# ---------------------------------------------------------------------------
# 1. FAQ purity
# ---------------------------------------------------------------------------
class TestFaqPurity:
    def test_faq_count_and_no_cross_sell(self, session):
        r = session.get(f"{PROD_URL}/api/faqs", timeout=30)
        assert r.status_code == 200
        body = r.json()
        faqs = body.get("faqs", body) if isinstance(body, dict) else body
        assert isinstance(faqs, list), f"expected list, got {type(faqs)}"
        assert len(faqs) == 17, f"expected 17 FAQs, got {len(faqs)}: ids={[f.get('id') for f in faqs]}"
        ids = [f.get("id") for f in faqs]
        assert "faq_cross_sell" not in ids, f"faq_cross_sell still present: {ids}"

    def test_faq_no_banned_phrases_or_rig(self, session):
        r = session.get(f"{PROD_URL}/api/faqs", timeout=30)
        assert r.status_code == 200
        body = r.json()
        faqs = body.get("faqs", body) if isinstance(body, dict) else body
        for faq in faqs:
            q = faq.get("q", "") or ""
            a = faq.get("a", "") or ""
            blob = f"{q}\n{a}"
            for phrase in BANNED_FAQ_PHRASES:
                assert phrase not in blob, (
                    f"banned phrase '{phrase}' found in FAQ id={faq.get('id')}: {blob[:200]}"
                )
            assert not RIG_RE.search(blob), (
                f"\\bRig\\b matched in FAQ id={faq.get('id')}: {blob[:200]}"
            )


# ---------------------------------------------------------------------------
# 2-4. Machine / Dashboard / Transactions purity
# ---------------------------------------------------------------------------
class TestRigPurity:
    def test_machines_no_rig(self, session, reviewer1_token):
        r = session.get(f"{PROD_URL}/api/machines", headers=_authed_headers(reviewer1_token), timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        machines = body.get("machines", body) if isinstance(body, dict) else body
        assert isinstance(machines, list)
        for m in machines:
            name = m.get("name", "") or ""
            assert not RIG_RE.search(name), f"\\bRig\\b in machine name: {name}"

    def test_dashboard_no_rig(self, session, reviewer1_token):
        r = session.get(f"{PROD_URL}/api/dashboard", headers=_authed_headers(reviewer1_token), timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert not _contains_rig(body), f"\\bRig\\b found in /api/dashboard: {json.dumps(body)[:400]}"

    def test_transactions_no_rig(self, session, reviewer1_token):
        r = session.get(f"{PROD_URL}/api/transactions", headers=_authed_headers(reviewer1_token), timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert not _contains_rig(body), f"\\bRig\\b found in /api/transactions: {json.dumps(body)[:400]}"


# ---------------------------------------------------------------------------
# 5. Critical health smoke — all must be 200
# ---------------------------------------------------------------------------
UNAUTHED_ENDPOINTS = [
    "/api/",
    "/api/packages",
    "/api/system/btc_rate",
    "/api/faqs",
]

AUTHED_ENDPOINTS = [
    "/api/auth/me",
    "/api/dashboard",
    "/api/machines",
    "/api/transactions",
    "/api/earnings",
    "/api/withdraw/methods",
    "/api/daily-checkin/status",
    "/api/ads/status",
    "/api/auto/settings",
    "/api/support/thread",
    "/api/support/unread",
    "/api/free-forever/status",
]


@pytest.mark.parametrize("path", UNAUTHED_ENDPOINTS)
def test_unauthed_health_200(session, path):
    r = session.get(f"{PROD_URL}{path}", timeout=30)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("path", AUTHED_ENDPOINTS)
def test_authed_health_200(session, reviewer1_token, path):
    r = session.get(f"{PROD_URL}{path}", headers=_authed_headers(reviewer1_token), timeout=30)
    assert r.status_code == 200, f"{path} → {r.status_code} {r.text[:200]}"


# ---------------------------------------------------------------------------
# 6. Packages catalog integrity
# ---------------------------------------------------------------------------
class TestPackagesCatalog:
    def test_packages_count_and_ids(self, session):
        r = session.get(f"{PROD_URL}/api/packages", timeout=30)
        assert r.status_code == 200
        body = r.json()
        packages = body.get("packages", body) if isinstance(body, dict) else body
        assert isinstance(packages, list)
        assert len(packages) == 10, f"expected 10 packages, got {len(packages)}: {[p.get('id') for p in packages]}"
        ids = [p.get("id") for p in packages]
        assert "adfree_399" in ids, f"adfree_399 missing: {ids}"
        assert "starter_099" not in ids, f"starter_099 must NOT be present: {ids}"

    def test_packages_mining_fields(self, session):
        r = session.get(f"{PROD_URL}/api/packages", timeout=30)
        assert r.status_code == 200
        body = r.json()
        packages = body.get("packages", body) if isinstance(body, dict) else body
        # 9 mining packages = all packages except adfree_399
        mining = [p for p in packages if p.get("id") != "adfree_399"]
        assert len(mining) == 9, f"expected 9 mining packages, got {len(mining)}"
        required = ["hashrate_boost_ghs", "price_usd", "original_price_usd",
                    "first_purchase_bonus_pct", "hashrate_display"]
        for p in mining:
            for field in required:
                assert field in p, f"package {p.get('id')} missing field {field}: keys={list(p.keys())}"


# ---------------------------------------------------------------------------
# 7. Withdraw bounds for regular users
# ---------------------------------------------------------------------------
class TestWithdrawBounds:
    def test_withdraw_methods_regular_user(self, session, reviewer1_token):
        r = session.get(f"{PROD_URL}/api/withdraw/methods", headers=_authed_headers(reviewer1_token), timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        # accept either { methods, min_sats,... } or list shape; ensure key bounds
        # The review spec says these top-level keys must be present:
        # min_sats=25000, max_sats=50000, fee_flat_sats=150, cooldown_hours=24, admin_unlimited=false
        bounds = body if isinstance(body, dict) else {}
        assert bounds.get("min_sats") == 25000, f"min_sats wrong: {bounds.get('min_sats')}"
        assert bounds.get("max_sats") == 50000, f"max_sats wrong: {bounds.get('max_sats')}"
        assert bounds.get("fee_flat_sats") == 150, f"fee_flat_sats wrong: {bounds.get('fee_flat_sats')}"
        assert bounds.get("cooldown_hours") == 24, f"cooldown_hours wrong: {bounds.get('cooldown_hours')}"
        assert bounds.get("admin_unlimited") is False, f"admin_unlimited wrong: {bounds.get('admin_unlimited')}"

    def test_withdraw_below_min_returns_400(self, session, reviewer1_token):
        payload = {"method_id": "lightning", "address": "test@speed.app", "amount_sats": 100}
        r = session.post(
            f"{PROD_URL}/api/withdraw",
            headers=_authed_headers(reviewer1_token),
            json=payload,
            timeout=30,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:300]}"
        body_text = r.text.lower()
        assert "min" in body_text or "25000" in body_text, f"expected min-sats error msg, got {r.text[:300]}"


# ---------------------------------------------------------------------------
# 8. Daily check-in idempotency
# ---------------------------------------------------------------------------
class TestDailyCheckin:
    def test_second_call_same_day_returns_400(self, session, reviewer1_token):
        # First call: may succeed or fail (already-checked-in)
        r1 = session.post(f"{PROD_URL}/api/daily-checkin", headers=_authed_headers(reviewer1_token), timeout=30)
        # Allow 200 or 400 here (idempotency guard might already have fired)
        assert r1.status_code in (200, 400), f"first call status {r1.status_code}: {r1.text[:200]}"
        # Second call must be 400 with "Check in again at"
        r2 = session.post(f"{PROD_URL}/api/daily-checkin", headers=_authed_headers(reviewer1_token), timeout=30)
        assert r2.status_code == 400, f"second call expected 400, got {r2.status_code}: {r2.text[:300]}"
        assert "check in again at" in r2.text.lower(), f"expected 'Check in again at' in body, got {r2.text[:300]}"


# ---------------------------------------------------------------------------
# 9. Reviewer accounts have is_admin=false
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("email,password", REVIEWERS)
def test_reviewer_is_not_admin(session, email, password):
    r = session.post(
        f"{PROD_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    token = r.json()["access_token"]
    me = session.get(f"{PROD_URL}/api/auth/me", headers=_authed_headers(token), timeout=30)
    assert me.status_code == 200, f"{email} /me {me.status_code} {me.text[:200]}"
    body = me.json()
    assert body.get("is_admin") is False, f"{email} is_admin={body.get('is_admin')}"


# ---------------------------------------------------------------------------
# 10. Cross-sell endpoint regression — must NOT return 500
# ---------------------------------------------------------------------------
def test_cross_sell_endpoint_no_500(session, reviewer1_token):
    r = session.get(f"{PROD_URL}/api/store/cross-sell", headers=_authed_headers(reviewer1_token), timeout=30)
    assert r.status_code != 500, f"/api/store/cross-sell returned 500: {r.text[:300]}"
    # Acceptable: 200 (still parses) or 404 (route removed) per review spec
    assert r.status_code in (200, 404), f"unexpected status {r.status_code}: {r.text[:200]}"
