"""HashCloud backend API tests"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://ios-clone-platform.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def new_user(session):
    """Register a fresh test user for the test session"""
    email = f"test_{uuid.uuid4().hex[:10]}@hashcloud.app"
    password = "password123"
    r = session.post(f"{API}/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": email,
        "password": password,
        "token": data["access_token"],
        "user": data["user"],
    }


def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------------------------- Health ----------------------------
def test_health(session):
    r = session.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


# ---------------------------- Auth ----------------------------
class TestAuth:
    def test_register_returns_token_and_user(self, new_user):
        assert "token" in new_user and len(new_user["token"]) > 20
        u = new_user["user"]
        assert u["email"] == new_user["email"]
        assert u.get("referral_code") and len(u["referral_code"]) == 7
        assert u["balance_btc"] == 0.0

    def test_login_same_credentials(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["email"], "password": new_user["password"]
        })
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()

    def test_login_wrong_password(self, session, new_user):
        r = session.post(f"{API}/auth/login", json={
            "email": new_user["email"], "password": "wrongpass"
        })
        assert r.status_code == 401

    def test_register_duplicate_email(self, session, new_user):
        r = session.post(f"{API}/auth/register", json={
            "email": new_user["email"], "password": "password123"
        })
        assert r.status_code == 400

    def test_auth_me(self, session, new_user):
        r = session.get(f"{API}/auth/me", headers=auth_headers(new_user["token"]))
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["email"] == new_user["email"]
        assert "balance_btc" in body and "balance_usd" in body

    def test_auth_me_no_token(self, session):
        r = session.get(f"{API}/auth/me")
        assert r.status_code == 401


# ---------------------------- Dashboard / Machines ----------------------------
class TestDashboard:
    def test_dashboard_has_welcome_miner(self, session, new_user):
        r = session.get(f"{API}/dashboard", headers=auth_headers(new_user["token"]))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["hash_rate"] == 3.0, f"expected 3.0 hashrate from welcome miner, got {d['hash_rate']}"
        assert d["active_machines_count"] == 1
        assert "today_earnings_usd" in d
        assert "user" in d
        assert d["btc_usd_rate"] > 0

    def test_machines_lists_welcome(self, session, new_user):
        r = session.get(f"{API}/machines", headers=auth_headers(new_user["token"]))
        assert r.status_code == 200
        machines = r.json()["machines"]
        assert len(machines) >= 1
        assert any(m["package_id"] == "welcome_gift" for m in machines)


# ---------------------------- Packages / Shop ----------------------------
class TestPackages:
    def test_get_packages(self, session):
        r = session.get(f"{API}/packages")
        assert r.status_code == 200
        pkgs = r.json()["packages"]
        assert len(pkgs) == 10, f"expected 10 packages, got {len(pkgs)}"
        ids = [p["id"] for p in pkgs]
        assert "welcome_199" in ids
        assert "colossus_19999" in ids
        # BOGO check
        bogo = next(p for p in pkgs if p["id"] == "welcome_199")
        assert bogo["bogo"] is True
        # FLAGSHIP badge check
        flagship = next(p for p in pkgs if p["id"] == "colossus_19999")
        assert flagship["badge"] == "FLAGSHIP"

    def test_buy_starter(self, session, new_user):
        r = session.post(f"{API}/packages/buy",
                         headers=auth_headers(new_user["token"]),
                         json={"package_id": "starter_099"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["success"] is True
        assert d["machines_added"] == 1

    def test_buy_bogo_adds_two_miners(self, session):
        # Use a brand-new user so we can assert exact count
        email = f"TEST_bogo_{uuid.uuid4().hex[:8]}@hashcloud.app"
        rr = session.post(f"{API}/auth/register", json={"email": email, "password": "password123"})
        assert rr.status_code == 200
        token = rr.json()["access_token"]

        r = session.post(f"{API}/packages/buy",
                         headers=auth_headers(token),
                         json={"package_id": "welcome_199"})
        assert r.status_code == 200, r.text
        assert r.json()["machines_added"] == 2

        # Verify machines list reflects 1 welcome + 2 BOGO = 3
        m = session.get(f"{API}/machines", headers=auth_headers(token))
        assert m.status_code == 200
        ms = m.json()["machines"]
        bogo_count = sum(1 for x in ms if x["package_id"] == "welcome_199")
        assert bogo_count == 2

    def test_buy_invalid_package(self, session, new_user):
        r = session.post(f"{API}/packages/buy",
                         headers=auth_headers(new_user["token"]),
                         json={"package_id": "does_not_exist"})
        assert r.status_code == 404


# ---------------------------- Transactions ----------------------------
class TestTransactions:
    def test_transactions_after_purchase(self, session, new_user):
        r = session.get(f"{API}/transactions", headers=auth_headers(new_user["token"]))
        assert r.status_code == 200
        txs = r.json()["transactions"]
        # Should have at least a purchase tx from buy_starter test
        types = {t["type"] for t in txs}
        assert "purchase" in types


# ---------------------------- Daily check-in ----------------------------
class TestDailyCheckin:
    def test_status_available_then_post_then_rejected(self, session):
        email = f"TEST_dc_{uuid.uuid4().hex[:8]}@hashcloud.app"
        rr = session.post(f"{API}/auth/register", json={"email": email, "password": "password123"})
        token = rr.json()["access_token"]

        s = session.get(f"{API}/daily-checkin/status", headers=auth_headers(token))
        assert s.status_code == 200
        assert s.json()["available"] is True

        c1 = session.post(f"{API}/daily-checkin", headers=auth_headers(token))
        assert c1.status_code == 200, c1.text
        assert c1.json()["streak"] == 1
        assert c1.json()["awarded_usd"] > 0

        # second call within 20h should be rejected
        c2 = session.post(f"{API}/daily-checkin", headers=auth_headers(token))
        assert c2.status_code == 400

        s2 = session.get(f"{API}/daily-checkin/status", headers=auth_headers(token))
        assert s2.json()["available"] is False


# ---------------------------- Referral ----------------------------
class TestReferral:
    def test_referral_returns_code(self, session, new_user):
        r = session.get(f"{API}/referral", headers=auth_headers(new_user["token"]))
        assert r.status_code == 200
        d = r.json()
        assert d["code"] == new_user["user"]["referral_code"]
        assert d["invited_count"] == 0
        assert d["bonus_per_invite_usd"] == 0.50


# ---------------------------- Withdraw ----------------------------
class TestWithdraw:
    def test_withdraw_methods(self, session, new_user):
        r = session.get(f"{API}/withdraw/methods", headers=auth_headers(new_user["token"]))
        assert r.status_code == 200
        d = r.json()
        assert d["min_usd"] == 1.0
        assert d["max_daily_usd"] == 2.0
        assert len(d["methods"]) >= 3

    def test_withdraw_below_min_rejected(self, session, new_user):
        r = session.post(f"{API}/withdraw",
                         headers=auth_headers(new_user["token"]),
                         json={"method_id": "lightning", "address": "addr@test", "amount_usd": 0.5})
        assert r.status_code == 400
        assert "Minimum" in r.json().get("detail", "")

    def test_withdraw_above_balance_rejected(self, session, new_user):
        r = session.post(f"{API}/withdraw",
                         headers=auth_headers(new_user["token"]),
                         json={"method_id": "lightning", "address": "addr@test", "amount_usd": 9999.0})
        assert r.status_code == 400
        assert "Insufficient" in r.json().get("detail", "")

    def test_withdraw_invalid_method(self, session, new_user):
        r = session.post(f"{API}/withdraw",
                         headers=auth_headers(new_user["token"]),
                         json={"method_id": "bogus", "address": "addr@test", "amount_usd": 1.0})
        assert r.status_code == 400

    def test_withdraw_success_when_balance_allows(self, session):
        """Build up balance via mining accrual, then withdraw."""
        email = f"TEST_wd_{uuid.uuid4().hex[:8]}@hashcloud.app"
        rr = session.post(f"{API}/auth/register", json={"email": email, "password": "password123"})
        token = rr.json()["access_token"]

        # Boost balance by doing a daily-checkin a few times is not possible (20h gate).
        # Instead, buy a small package then wait briefly for accrual.
        # Simpler: directly accrue a few seconds of mining from welcome miner is tiny.
        # Trigger accrual & also do daily checkin which gives $0.05.
        session.post(f"{API}/daily-checkin", headers=auth_headers(token))

        # Sleep ~2s for mining accrual on welcome miner (~$0.10/day = ~0.0000023/sec).
        # That's still way below $1. So just attempt $1 withdrawal — should fail with insufficient.
        # The "success when balance allows" can be validated with a small amount that matches balance.
        time.sleep(1)
        me = session.get(f"{API}/auth/me", headers=auth_headers(token))
        bal_usd = float(me.json()["balance_usd"])

        if bal_usd >= 1.0:
            r = session.post(f"{API}/withdraw",
                             headers=auth_headers(token),
                             json={"method_id": "lightning", "address": "lnaddr@test", "amount_usd": 1.0})
            assert r.status_code == 200, r.text
            assert r.json()["transaction"]["status"] == "pending"
        else:
            # Balance too small from accrual alone; confirm the rejection path works
            # and skip the success assertion (documented limitation since no admin top-up endpoint).
            r = session.post(f"{API}/withdraw",
                             headers=auth_headers(token),
                             json={"method_id": "lightning", "address": "lnaddr@test", "amount_usd": 1.0})
            assert r.status_code == 400
            pytest.skip(f"Balance ${bal_usd:.4f} too small to test withdraw success path without admin seed")
