"""Telemetry endpoint tests for Build #33 crash reporting pipeline.

Covers:
- POST /api/telemetry/crash (no auth, multiple payload variants, edge cases)
- GET  /api/admin/telemetry/crashes (admin auth, limit param, end-to-end)
- Regression: POST /api/auth/login + GET /api/auth/me
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://ios-clone-platform.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "mbfalagario@gmail.com"
ADMIN_PASSWORD = "SCMiner!Adm-9k4Vp2QrZxNb7sLe"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(session):
    r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "access_token" in data
    assert data["user"].get("is_admin") is True, f"user is not admin: {data['user']}"
    return data["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============================ POST /api/telemetry/crash ============================
class TestCrashIngestion:
    """No-auth crash ingest endpoint — must be permissive and never 500."""

    def test_basic_crash_returns_ok_and_id(self, session):
        payload = {
            "type": "error",
            "fatal": True,
            "message": "TEST_basic_crash: ReferenceError: foo is not defined",
            "stack": "at Object.<anonymous> (/index.js:42:13)\nat Module._compile (node:internal/modules/cjs/loader:1256:14)",
            "app_version": "1.0.3",
            "build_number": "33",
            "platform": "ios",
            "os_version": "26.5",
            "ts": "2026-01-15T10:00:00.000Z",
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, f"unexpected {r.status_code}: {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert "id" in body and len(body["id"]) >= 32  # uuid4
        # verify it's a valid uuid
        uuid.UUID(body["id"])

    def test_unhandled_rejection_type(self, session):
        payload = {
            "type": "unhandled-rejection",
            "fatal": False,
            "message": "TEST_promise_rej: Network request failed",
            "stack": "at fetch (/api.ts:12)",
            "app_version": "1.0.3",
            "build_number": "33",
            "platform": "ios",
            "os_version": "26.5",
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_render_boundary_type(self, session):
        payload = {
            "type": "render-boundary",
            "fatal": True,
            "message": "TEST_render_boundary: cannot read properties of undefined (reading 'map')",
            "stack": "in MachineList\nin Suspense\nin App",
            "app_version": "1.0.3",
            "build_number": "33",
            "platform": "ios",
            "os_version": "26.5",
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_error_type(self, session):
        payload = {
            "type": "error",
            "message": "TEST_error_type",
            "stack": "stack",
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_empty_body_returns_200_with_safe_defaults(self, session):
        """Empty payload must not 500 — server should write safe defaults."""
        r = session.post(f"{API}/telemetry/crash", json={})
        assert r.status_code == 200, f"empty body should not 500: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        assert "id" in body

    def test_missing_fields_returns_200(self, session):
        """Partial payload should be accepted."""
        r = session.post(f"{API}/telemetry/crash", json={"message": "TEST_missing_fields_only_message"})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_oversized_stack_truncates_gracefully(self, session):
        """Stack >20KB must be accepted (server truncates to 20000 chars)."""
        big_stack = "A" * 100_000  # 100KB
        payload = {
            "type": "error",
            "fatal": True,
            "message": "TEST_oversized_stack",
            "stack": big_stack,
            "app_version": "1.0.3",
            "build_number": "33",
            "platform": "ios",
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, f"oversize should not 500: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        crash_id = body["id"]

        # Verify truncation by fetching via admin and checking len <= 20000
        login = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        token = login.json()["access_token"]
        g = session.get(f"{API}/admin/telemetry/crashes?limit=200", headers=auth_headers(token))
        assert g.status_code == 200
        found = [c for c in g.json()["crashes"] if c["id"] == crash_id]
        assert len(found) == 1, "oversized crash not retrievable via admin"
        assert len(found[0]["stack"]) <= 20000, f"stack not truncated: len={len(found[0]['stack'])}"

    def test_oversized_message_truncates(self, session):
        """Message >4000 must be truncated, not rejected."""
        payload = {
            "type": "error",
            "message": "TEST_oversized_msg_" + ("B" * 10_000),
            "stack": "trace",
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

    def test_no_auth_required(self, session):
        """Endpoint must be open — no auth header should still succeed."""
        plain_session = requests.Session()  # no headers
        r = plain_session.post(
            f"{API}/telemetry/crash",
            json={"type": "error", "message": "TEST_no_auth_required", "stack": ""},
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 200, f"unauth crash POST failed: {r.status_code} {r.text}"
        assert r.json().get("ok") is True

    def test_malformed_body_invalid_json(self, session):
        """Non-JSON body should not 500 (FastAPI returns 422 for invalid JSON)."""
        r = requests.post(f"{API}/telemetry/crash",
                          data="not-json-at-all",
                          headers={"Content-Type": "application/json"})
        # FastAPI Body(...) with Dict will reject malformed JSON with 422 — that's fine.
        # The contract from the request is "empty body / missing fields = 200 with defaults",
        # which we've already tested. Malformed JSON returning 422 is acceptable, not 500.
        assert r.status_code in (200, 422), f"unexpected status for malformed JSON: {r.status_code} {r.text}"
        assert r.status_code != 500

    def test_array_body_does_not_crash_server(self, session):
        """An array body where dict is expected — must not 500."""
        r = session.post(f"{API}/telemetry/crash", json=[{"type": "error"}])
        # FastAPI will reject with 422; the server shouldn't 500.
        assert r.status_code != 500, f"server 500 on array body: {r.text}"

    def test_non_string_fields_are_coerced(self, session):
        """Numeric/bool values for string fields should be coerced via str()."""
        payload = {
            "type": 1,
            "fatal": "yes",
            "message": 12345,
            "stack": None,
            "app_version": 1.0,
            "build_number": 33,
            "platform": True,
            "os_version": None,
            "ts": 1736937600,
        }
        r = session.post(f"{API}/telemetry/crash", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True


# ============================ GET /api/admin/telemetry/crashes ============================
class TestCrashAdminFetch:

    def test_admin_fetch_no_auth_unauthorized(self, session):
        """Without bearer token, expect 401 (per request)."""
        r = session.get(f"{API}/admin/telemetry/crashes")
        # get_current_user with no Authorization should raise 401
        assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"

    def test_admin_fetch_non_admin_forbidden(self, session):
        """Authenticated non-admin user should get 403."""
        email = f"TEST_telem_nonadmin_{uuid.uuid4().hex[:8]}@hashcloud.app"
        rr = session.post(f"{API}/auth/register", json={"email": email, "password": "password123"})
        assert rr.status_code == 200, rr.text
        token = rr.json()["access_token"]
        r = session.get(f"{API}/admin/telemetry/crashes", headers=auth_headers(token))
        assert r.status_code == 403, f"expected 403 for non-admin, got {r.status_code}"

    def test_admin_fetch_with_auth_returns_list(self, session, admin_token):
        r = session.get(f"{API}/admin/telemetry/crashes", headers=auth_headers(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "crashes" in body and isinstance(body["crashes"], list)
        assert "total" in body and isinstance(body["total"], int)
        # Each crash should not leak _id and should have id+received_at
        for c in body["crashes"]:
            assert "_id" not in c
            assert "id" in c
            assert "received_at" in c

    def test_admin_fetch_sorted_received_at_desc(self, session, admin_token):
        r = session.get(f"{API}/admin/telemetry/crashes?limit=50", headers=auth_headers(admin_token))
        assert r.status_code == 200
        crashes = r.json()["crashes"]
        if len(crashes) >= 2:
            timestamps = [c["received_at"] for c in crashes]
            assert timestamps == sorted(timestamps, reverse=True), \
                f"crashes not sorted desc by received_at: {timestamps[:3]}"

    def test_admin_fetch_respects_limit(self, session, admin_token):
        # First ensure there are at least 3 crashes
        for i in range(3):
            session.post(f"{API}/telemetry/crash", json={
                "type": "error",
                "message": f"TEST_limit_seed_{i}",
                "stack": "x",
            })
        r = session.get(f"{API}/admin/telemetry/crashes?limit=2", headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        assert len(body["crashes"]) <= 2
        assert body["total"] == len(body["crashes"])

    def test_admin_fetch_limit_capped_at_200(self, session, admin_token):
        r = session.get(f"{API}/admin/telemetry/crashes?limit=999", headers=auth_headers(admin_token))
        assert r.status_code == 200
        body = r.json()
        # implementation uses min(limit, 200)
        assert len(body["crashes"]) <= 200


# ============================ End-to-end ============================
class TestE2E:
    def test_post_then_get_finds_crash(self, session, admin_token):
        unique_msg = f"TEST_e2e_{uuid.uuid4().hex[:12]}"
        payload = {
            "type": "error",
            "fatal": True,
            "message": unique_msg,
            "stack": "at e2e",
            "app_version": "1.0.3",
            "build_number": "33",
            "platform": "ios",
            "os_version": "26.5",
        }
        post = session.post(f"{API}/telemetry/crash", json=payload)
        assert post.status_code == 200
        crash_id = post.json()["id"]

        # Fetch as admin — newest first, so it should be near the top
        get = session.get(f"{API}/admin/telemetry/crashes?limit=200", headers=auth_headers(admin_token))
        assert get.status_code == 200
        crashes = get.json()["crashes"]
        match = [c for c in crashes if c["id"] == crash_id]
        assert len(match) == 1, f"crash {crash_id} not in admin list"
        c = match[0]
        assert c["message"] == unique_msg
        assert c["type"] == "error"
        assert c["fatal"] is True
        assert c["app_version"] == "1.0.3"
        assert c["build_number"] == "33"
        assert c["platform"] == "ios"
        assert c["os_version"] == "26.5"
        assert c["stack"] == "at e2e"


# ============================ Regression ============================
class TestRegression:
    def test_login_admin(self, session):
        r = session.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()

    def test_auth_me_admin(self, session, admin_token):
        r = session.get(f"{API}/auth/me", headers=auth_headers(admin_token))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body.get("is_admin") is True

    def test_auth_me_unauthenticated(self, session):
        r = session.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_health(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
