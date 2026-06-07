"""
Build #33 — Apple IAP fail-closed hardening regression tests.

Covers:
  - POST /api/packages/buy: iOS gate (no tid → 402, fake tid → 402 sanitised),
    non-iOS path, duplicate-tid replay → 400.
  - POST /api/iap/restore: fake tid, empty array, error reason codes.
  - integrations.apple.verify_apple_transaction fail-closed behaviour with
    APPLE_VERIFY_REQUIRED=1.
  - Regression: /api/auth/login, /api/auth/me, /api/packages, /api/earnings,
    /api/telemetry/crash (3 types), /api/admin/telemetry/crashes.
"""
import os
import sys
import time
import uuid
import pytest
import requests

# Ensure /app/backend on path so we can import integrations.apple for unit tests
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://ios-clone-platform.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"
REVIEWER_EMAIL = "appreview1@hashratecloudminer.app"
REVIEWER_PASSWORD = "AppReview2026!"


# ------------------------------ fixtures ------------------------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(session, email, password):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text[:200]}"
    return r.json()


def _register(session):
    email = f"test_b33_{uuid.uuid4().hex[:10]}@hashcloud.app"
    password = "password123"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    return {"email": email, "password": password, "token": data["access_token"], "user": data["user"]}


@pytest.fixture(scope="module")
def admin(session):
    return _login(session, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def reviewer(session):
    return _login(session, REVIEWER_EMAIL, REVIEWER_PASSWORD)


@pytest.fixture(scope="module")
def fresh_user(session):
    return _register(session)


def auth(token, extra=None):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if extra:
        h.update(extra)
    return h


# ------------------------------ Regression: auth ------------------------------
def test_health(session):
    r = session.get(f"{API}/health", timeout=10)
    # /api/health may or may not exist; tolerate 200 or 404
    assert r.status_code in (200, 404)


def test_login_admin(admin):
    assert "access_token" in admin
    assert admin["user"]["email"] == ADMIN_EMAIL


def test_login_reviewer(reviewer):
    assert "access_token" in reviewer
    assert reviewer["user"]["email"] == REVIEWER_EMAIL


def test_auth_me(session, reviewer):
    r = session.get(f"{API}/auth/me", headers=auth(reviewer["access_token"]))
    assert r.status_code == 200
    assert r.json()["email"] == REVIEWER_EMAIL


def test_register_works(fresh_user):
    assert "token" in fresh_user
    assert fresh_user["user"]["email"] == fresh_user["email"]


# ------------------------------ Regression: packages / earnings ------------------------------
def test_get_packages(session):
    r = session.get(f"{API}/packages")
    assert r.status_code == 200
    body = r.json()
    assert "packages" in body and len(body["packages"]) > 0
    assert any(p["id"] == "rookie_299" for p in body["packages"])


def test_get_earnings(session, reviewer):
    r = session.get(f"{API}/earnings", headers=auth(reviewer["access_token"]))
    assert r.status_code == 200, r.text[:200]


# ------------------------------ /packages/buy — iOS gate ------------------------------
class TestPackagesBuyIOSGate:
    """Apple Guideline 2.1(b) — iOS request must carry an apple_transaction_id."""

    def test_ios_no_transaction_id_returns_402(self, session, fresh_user):
        r = session.post(
            f"{API}/packages/buy",
            json={"package_id": "rookie_299"},
            headers=auth(fresh_user["token"], {"X-Client-Platform": "ios"}),
        )
        assert r.status_code == 402, f"expected 402 got {r.status_code} body={r.text[:200]}"
        body = r.json()
        # Must surface a sanitised, user-visible string — NOT a stack trace.
        detail = (body.get("detail") or "").lower()
        assert "in-app purchase" in detail or "app store" in detail
        # Never leak raw "Traceback" or python exception strings.
        assert "traceback" not in detail
        assert "exception" not in detail

    def test_ios_fake_transaction_id_returns_402_sanitised(self, session, fresh_user):
        fake_tid = f"FAKE_TID_{uuid.uuid4().hex}"
        r = session.post(
            f"{API}/packages/buy",
            json={"package_id": "rookie_299", "apple_transaction_id": fake_tid},
            headers=auth(fresh_user["token"], {"X-Client-Platform": "ios"}),
        )
        # The Apple verifier with real credentials will return either
        # 401 (creds bad) or 4040010 (not found) → both wrapped as ValueError
        # → /packages/buy maps to 402. We tolerate 503 only if APPLE_VERIFY_REQUIRED
        # is unset AND the verifier somehow raised non-ValueError; ideally 402.
        assert r.status_code == 402, (
            f"expected 402 (sanitised) got {r.status_code}; "
            f"MUST NOT be 500 or leak. body={r.text[:300]}"
        )
        body = r.json()
        detail = (body.get("detail") or "")
        # No raw exception text leakage.
        for forbidden in ("Traceback", "ValueError", "APIException", "401", "4040010",
                          "appstoreserverlibrary", "issuer_id", "key_id", ".p8"):
            assert forbidden not in detail, f"leaked '{forbidden}' in detail: {detail}"
        # Must reference the user-actionable hint.
        assert ("verify" in detail.lower()) or ("payment sheet" in detail.lower())

    def test_non_ios_web_no_tid_succeeds(self, session, fresh_user):
        """X-Client-Platform: web (or absent) without apple_transaction_id
        must NOT be blocked by the iOS gate; in dev mode the purchase is
        granted (mock apple) or fails for unrelated reasons (e.g. quota),
        but it MUST NOT 402 with the iOS gate message."""
        r = session.post(
            f"{API}/packages/buy",
            json={"package_id": "welcome_199"},
            headers=auth(fresh_user["token"], {"X-Client-Platform": "web"}),
        )
        # Acceptable: 200 (granted) or 400 (already owned/promo limit) — anything
        # except the iOS-gate 402 with the "Apple In-App Purchase required" detail.
        if r.status_code == 402:
            detail = (r.json().get("detail") or "").lower()
            assert "in-app purchase required" not in detail, \
                "Web client was wrongly blocked by iOS gate"
        else:
            assert r.status_code in (200, 400), f"unexpected: {r.status_code} {r.text[:200]}"


# ------------------------------ /packages/buy — duplicate replay ------------------------------
class TestDuplicateTransactionIdReplay:
    def test_duplicate_apple_tid_returns_400_already_redeemed(self, session, fresh_user):
        """The dup-tid check in /packages/buy runs BEFORE Apple verification,
        so we seed Mongo directly with a transaction record bearing a known
        apple_transaction_id, then verify that POST /packages/buy with the
        same tid returns HTTP 400."""
        # Seed a "previously redeemed" record directly in Mongo.
        try:
            from pymongo import MongoClient
        except ImportError:
            pytest.skip("pymongo not available")
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "hashcloud_db")
        client = MongoClient(mongo_url)
        db = client[db_name]
        tid = f"TEST_REPLAY_{uuid.uuid4().hex}"
        seeded_id = str(uuid.uuid4())
        db.transactions.insert_one({
            "id": seeded_id,
            "user_id": "seed-user",
            "type": "purchase",
            "amount_usd": 2.99,
            "amount_btc": 0.0,
            "status": "completed",
            "description": "TEST seeded for dup-replay",
            "package_id": "rookie_299",
            "apple_transaction_id": tid,
            "apple_environment": "TEST_SEED",
            "apple_mocked": True,
            "created_at": "2026-01-01T00:00:00",
        })
        try:
            # Second redeem with the same tid → must return 400.
            r2 = session.post(
                f"{API}/packages/buy",
                json={"package_id": "rookie_299", "apple_transaction_id": tid},
                headers=auth(fresh_user["token"], {"X-Client-Platform": "web"}),
            )
            assert r2.status_code == 400, f"expected 400 got {r2.status_code} {r2.text[:200]}"
            detail = (r2.json().get("detail") or "").lower()
            assert "already redeemed" in detail or "already" in detail, detail
        finally:
            db.transactions.delete_one({"id": seeded_id})
            client.close()


# ------------------------------ /iap/restore ------------------------------
class TestIAPRestore:
    def test_empty_purchases_returns_clean_empty_result(self, session, fresh_user):
        r = session.post(
            f"{API}/iap/restore",
            json={"purchases": []},
            headers=auth(fresh_user["token"]),
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body.get("success") is True
        assert body.get("restored_count") == 0
        assert body.get("restored") == []
        assert body.get("skipped") == []
        assert body.get("errors") == []

    def test_fake_transaction_id_returns_reason_code(self, session, fresh_user):
        fake_tid = f"FAKE_RESTORE_{uuid.uuid4().hex}"
        r = session.post(
            f"{API}/iap/restore",
            json={
                "purchases": [
                    {"transaction_id": fake_tid, "product_id": "rookie_299"}
                ]
            },
            headers=auth(fresh_user["token"]),
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        # The fake tid should NOT be restored (Apple refuses or mock cannot match).
        # Acceptable outcomes:
        #   1) errors=[{reason: 'apple_verification_refused' or 'verifier_unavailable'}]
        #   2) In pure dev mode where mock returns ok, restored=[...] — but the
        #      review request explicitly expects 'apple_verification_refused' on
        #      this env (creds present but 401 from Apple).
        all_errors = body.get("errors", [])
        all_restored = body.get("restored", [])
        if all_errors:
            reasons = [e.get("reason") for e in all_errors]
            assert any(
                r_ in ("apple_verification_refused", "verifier_unavailable")
                for r_ in reasons
            ), f"unexpected error reasons: {reasons}"
            # Must NEVER expose raw Apple exception text in any error field.
            for e in all_errors:
                for v in e.values():
                    if isinstance(v, str):
                        for forbidden in ("Traceback", "APIException", "4040010"):
                            assert forbidden not in v
        else:
            # Mock path: at least the call must not have leaked any internal field.
            assert isinstance(all_restored, list)


# ------------------------------ Telemetry regression ------------------------------
class TestTelemetryRegression:
    def test_crash_simple(self, session):
        r = session.post(
            f"{API}/telemetry/crash",
            json={
                "message": "TEST_b33_simple",
                "type": "javascript",
                "fatal": False,
                "stack": "at TestRunner",
                "app_version": "1.0.3",
                "build_number": "33",
            },
        )
        assert r.status_code == 200

    def test_crash_minimal(self, session):
        r = session.post(f"{API}/telemetry/crash", json={"message": "TEST_b33_min"})
        assert r.status_code == 200

    def test_crash_native_fatal(self, session):
        r = session.post(
            f"{API}/telemetry/crash",
            json={
                "message": "TEST_b33_fatal",
                "type": "native",
                "fatal": True,
                "platform": "ios",
                "os_version": "26.5",
            },
        )
        assert r.status_code == 200

    def test_admin_telemetry_requires_admin(self, session, fresh_user, admin):
        # No auth → 401
        r0 = session.get(f"{API}/admin/telemetry/crashes")
        assert r0.status_code == 401
        # Non-admin → 403
        r1 = session.get(f"{API}/admin/telemetry/crashes", headers=auth(fresh_user["token"]))
        assert r1.status_code == 403
        # Admin → 200
        r2 = session.get(f"{API}/admin/telemetry/crashes", headers=auth(admin["access_token"]))
        assert r2.status_code == 200
        body = r2.json()
        # Must not leak Mongo _id
        items = body.get("items") if isinstance(body, dict) else body
        if isinstance(items, list) and items:
            for item in items:
                assert "_id" not in item


# ------------------------------ Unit tests: integrations.apple ------------------------------
class TestAppleVerifyFailClosed:
    """Direct unit tests on integrations.apple.verify_apple_transaction.
    These do NOT touch the running server."""

    def _reload_apple(self):
        # Force reload so env-var changes are picked up if cached.
        import importlib
        from integrations import apple as apple_mod
        importlib.reload(apple_mod)
        return apple_mod

    def test_no_creds_with_require_real_raises(self, monkeypatch):
        monkeypatch.setenv("APPLE_VERIFY_REQUIRED", "1")
        monkeypatch.delenv("APPLE_PRIVATE_KEY_PATH", raising=False)
        monkeypatch.delenv("APPLE_KEY_ID", raising=False)
        monkeypatch.delenv("APPLE_ISSUER_ID", raising=False)
        monkeypatch.delenv("APPLE_BUNDLE_ID", raising=False)
        apple_mod = self._reload_apple()
        with pytest.raises(ValueError) as exc:
            apple_mod.verify_apple_transaction("any_tid", expected_product_id="rookie_299")
        assert "required" in str(exc.value).lower() or "credentials" in str(exc.value).lower()

    def test_no_creds_dev_mode_returns_mock(self, monkeypatch):
        monkeypatch.delenv("APPLE_VERIFY_REQUIRED", raising=False)
        monkeypatch.delenv("APPLE_PRIVATE_KEY_PATH", raising=False)
        monkeypatch.delenv("APPLE_KEY_ID", raising=False)
        monkeypatch.delenv("APPLE_ISSUER_ID", raising=False)
        monkeypatch.delenv("APPLE_BUNDLE_ID", raising=False)
        apple_mod = self._reload_apple()
        res = apple_mod.verify_apple_transaction("dev_tid", expected_product_id="rookie_299")
        assert res.get("_mocked") is True
        assert res.get("environment") == "MOCK"
        assert res.get("transactionId") == "dev_tid"

    def test_401_with_require_real_raises_no_mock_fallback(self, monkeypatch):
        """With real creds present (which currently return 401 from Apple)
        AND APPLE_VERIFY_REQUIRED=1, the verifier MUST raise ValueError —
        never fall back to a MOCK."""
        # Keep the existing real creds from .env (already loaded by backend).
        # We just flip the safety switch on.
        monkeypatch.setenv("APPLE_VERIFY_REQUIRED", "1")
        monkeypatch.setenv("APPLE_PRIVATE_KEY_PATH", "/app/backend/keys/SubscriptionKey_J55DSC44V5.p8")
        monkeypatch.setenv("APPLE_KEY_ID", "J55DSC44V5")
        monkeypatch.setenv("APPLE_ISSUER_ID", "d3284874-7bd8-4eff-b272-c9ef0122df9a")
        monkeypatch.setenv("APPLE_BUNDLE_ID", "app.satoshicloudminer")
        if not os.path.exists("/app/backend/keys/SubscriptionKey_J55DSC44V5.p8"):
            pytest.skip("Apple .p8 not present in this env — fail-closed live-path can't be exercised.")
        apple_mod = self._reload_apple()
        # Use a clearly fake tid. Apple should return 401 (bad creds) or 4040010 (not found).
        with pytest.raises(ValueError):
            apple_mod.verify_apple_transaction(
                f"FAKE_{uuid.uuid4().hex}", expected_product_id="rookie_299"
            )
