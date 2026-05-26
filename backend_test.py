"""Build #15 backend regression — Premium Support Chat + previous features."""
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


def post(path: str, body: Any = None, token: Optional[str] = None, timeout: int = 30):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.post(BASE + path, headers=h, data=json.dumps(body) if body is not None else None, timeout=timeout)


def get(path: str, token: Optional[str] = None, timeout: int = 30):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return requests.get(BASE + path, headers=h, timeout=timeout)


def admin_login() -> str:
    r = post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def register_fresh_user() -> tuple[str, str, str]:
    email = f"build15_{uuid.uuid4().hex[:10]}@example.com"
    pw = "Sup3rTest!2026"
    r = post("/auth/register", {"email": email, "password": pw})
    assert r.status_code == 200, r.text
    j = r.json()
    return j["access_token"], j["user"]["id"], email


def test_premium_support():
    print("\n=== A. Premium Support Chat ===")
    admin_token = admin_login()
    user_token, user_id, user_email = register_fresh_user()
    print(f"Fresh user: {user_email} id={user_id}")

    # 1.
    r = get("/support/thread", user_token)
    ok = r.status_code == 200
    j = r.json() if ok else {}
    thread = j.get("thread", {}) if ok else {}
    msgs = j.get("messages", []) if ok else []
    sla = j.get("sla_hours") if ok else None
    log(
        "A1 GET /support/thread (fresh user)",
        ok and thread.get("status") == "open" and thread.get("unread_user_count", 0) == 0 and msgs == [] and sla == 48,
        f"status={r.status_code} thread.status={thread.get('status')} unread_user={thread.get('unread_user_count')} msgs={len(msgs)} sla={sla}",
    )

    # 2.
    body_text = "Hello, I need help with my Free Forever activation"
    r = post("/support/messages", {"body": body_text}, user_token)
    ok = r.status_code == 200
    j = r.json() if ok else {}
    msg = j.get("message", {}) if ok else {}
    log(
        "A2 POST /support/messages",
        ok and j.get("ok") is True and msg.get("sender") == "user" and msg.get("body") == body_text and msg.get("read_at") is None,
        f"status={r.status_code} ok={j.get('ok')} sender={msg.get('sender')} body_match={msg.get('body')==body_text} read_at={msg.get('read_at')}",
    )

    # 3.
    r = get("/support/unread", user_token)
    ok = r.status_code == 200 and r.json().get("unread_user_count") == 0
    log("A3 GET /support/unread (user, own msg)", ok, f"status={r.status_code} body={r.text[:200]}")

    # 4.
    r = get("/admin/support/threads", admin_token)
    ok = r.status_code == 200
    j = r.json() if ok else {}
    threads = j.get("threads", []) if ok else []
    our_thread = next((t for t in threads if t.get("user_id") == user_id), None)
    total_unread_admin = j.get("total_unread_admin", 0)
    open_count = j.get("open_count", 0)
    log(
        "A4 GET /admin/support/threads",
        ok and our_thread is not None and our_thread.get("unread_admin_count", 0) >= 1 and total_unread_admin >= 1 and open_count >= 1 and j.get("sla_hours") == 48,
        f"status={r.status_code} thread_found={our_thread is not None} unread_admin={our_thread.get('unread_admin_count') if our_thread else None} total_unread_admin={total_unread_admin} open_count={open_count} sla={j.get('sla_hours')}",
    )

    # 5.
    r = get("/admin/support/unread", admin_token)
    ok = r.status_code == 200
    pre_admin_unread = r.json().get("unread_admin_count", 0) if ok else 0
    log("A5 GET /admin/support/unread", ok and pre_admin_unread >= 1, f"unread_admin_count={pre_admin_unread}")

    # 6.
    r = get(f"/admin/support/threads/{user_id}", admin_token)
    ok = r.status_code == 200
    j = r.json() if ok else {}
    detail_msgs = j.get("messages", []) if ok else []
    log("A6a GET /admin/support/threads/{user_id}", ok and len(detail_msgs) >= 1, f"status={r.status_code} msgs={len(detail_msgs)}")
    r = get("/admin/support/unread", admin_token)
    post_admin_unread = r.json().get("unread_admin_count", 0)
    log(
        "A6b /admin/support/unread decremented after view",
        post_admin_unread == max(0, pre_admin_unread - 1),
        f"pre={pre_admin_unread} post={post_admin_unread}",
    )

    # 7.
    reply_text = "Hi! Try pulling-to-refresh on Home — your Free Forever should be there."
    r = post(f"/admin/support/threads/{user_id}/reply", {"body": reply_text}, admin_token)
    ok = r.status_code == 200
    j = r.json() if ok else {}
    msg = j.get("message", {}) if ok else {}
    log(
        "A7 POST /admin/support/threads/{user_id}/reply",
        ok and msg.get("sender") == "admin" and msg.get("body") == reply_text,
        f"status={r.status_code} sender={msg.get('sender')} body_match={msg.get('body')==reply_text}",
    )

    # 8.
    r = get("/support/unread", user_token)
    ok = r.status_code == 200 and r.json().get("unread_user_count") == 1
    log("A8 user /support/unread after admin reply", ok, f"body={r.text[:200]}")

    # 9.
    r = get("/support/thread", user_token)
    ok = r.status_code == 200
    j = r.json() if ok else {}
    msgs = j.get("messages", []) if ok else []
    senders = [m.get("sender") for m in msgs]
    chronological = len(senders) >= 2 and senders[0] == "user" and senders[1] == "admin"
    log(
        "A9a GET /support/thread (both messages, chronological)",
        ok and len(msgs) >= 2 and chronological,
        f"msgs={len(msgs)} senders={senders}",
    )
    r2 = get("/support/unread", user_token)
    ok2 = r2.status_code == 200 and r2.json().get("unread_user_count") == 0
    log("A9b user /support/unread auto-cleared", ok2, f"body={r2.text[:200]}")

    # 10.
    r = post(f"/admin/support/threads/{user_id}/close", None, admin_token)
    log("A10a POST /admin/support/threads/{user_id}/close", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
    r = get("/admin/support/threads", admin_token)
    threads = r.json().get("threads", []) if r.status_code == 200 else []
    our_thread = next((t for t in threads if t.get("user_id") == user_id), None)
    log(
        "A10b thread status=closed in /admin/support/threads",
        our_thread is not None and our_thread.get("status") == "closed",
        f"status={our_thread.get('status') if our_thread else None}",
    )

    # 11.
    r = get("/admin/support/threads", user_token)
    log("A11a non-admin → /admin/support/threads = 403", r.status_code == 403, f"status={r.status_code}")
    r = post("/support/messages", {"body": "hi"}, None)
    log("A11b no-token → /support/messages = 401", r.status_code == 401, f"status={r.status_code}")

    # 12.
    r = post("/support/messages", {"body": ""}, user_token)
    log("A12a empty body → 400/422", r.status_code in (400, 422), f"status={r.status_code}")
    big = "x" * 2001
    r = post("/support/messages", {"body": big}, user_token)
    log("A12b 2001-char body → 422", r.status_code == 422, f"status={r.status_code}")

    return admin_token, user_token


def test_regression(admin_token: str, user_token: str):
    print("\n=== B. Regression ===")
    r = get("/withdraw/methods", admin_token)
    j = r.json() if r.status_code == 200 else {}
    log(
        "B13a /withdraw/methods admin",
        r.status_code == 200 and j.get("min_sats") == 1 and j.get("fee_pct") == 0 and j.get("admin_unlimited") is True,
        f"min={j.get('min_sats')} fee_pct={j.get('fee_pct')} admin_unlimited={j.get('admin_unlimited')}",
    )
    r = get("/withdraw/methods", user_token)
    j = r.json() if r.status_code == 200 else {}
    log(
        "B13b /withdraw/methods regular",
        r.status_code == 200 and j.get("min_sats") == 150000 and abs(j.get("fee_pct", 0) - 0.10) < 1e-9 and j.get("admin_unlimited") is False,
        f"min={j.get('min_sats')} fee_pct={j.get('fee_pct')} admin_unlimited={j.get('admin_unlimited')}",
    )
    r = post("/withdraw", {"method_id": "lightning", "address": "lnbc1abcdef", "amount_sats": 10}, user_token)
    try:
        detail = r.json().get("detail", "")
    except Exception:
        detail = r.text
    log(
        "B13c POST /withdraw regular amount=10 → 400 + min msg",
        r.status_code == 400 and "Minimum withdrawal is 150,000 sats" in detail,
        f"status={r.status_code} detail={detail[:160]}",
    )

    r = get("/free-forever/status", user_token)
    j = r.json() if r.status_code == 200 else {}
    log(
        "B14a /free-forever/status",
        r.status_code == 200 and j.get("hash_rate_display") == "500 GH/s" and j.get("duration_hours") == 24,
        f"hash_rate_display={j.get('hash_rate_display')} duration_hours={j.get('duration_hours')}",
    )

    r = get("/admin/ai/agents", admin_token)
    j = r.json() if r.status_code == 200 else {}
    agents = j.get("agents") if isinstance(j, dict) else j
    log(
        "B14b /admin/ai/agents",
        r.status_code == 200 and isinstance(agents, list) and len(agents) >= 1,
        f"status={r.status_code} n_agents={len(agents) if isinstance(agents, list) else 'n/a'}",
    )

    r = post("/admin/ai/regenerate", None, admin_token)
    log("B14c POST /admin/ai/regenerate", r.status_code == 200, f"status={r.status_code}")

    r = get("/admin/fees/summary", admin_token)
    j = r.json() if r.status_code == 200 else {}
    required = {"fees_collected_sats", "available_sats", "fees_reinvested_sats"}
    log(
        "B14d /admin/fees/summary",
        r.status_code == 200 and required.issubset(j.keys()),
        f"keys={sorted(list(j.keys()))[:10]}",
    )

    r = post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    log("B15a admin login", r.status_code == 200, f"status={r.status_code}")
    r = get("/packages", admin_token)
    body = r.json() if r.status_code == 200 else []
    if isinstance(body, dict) and "packages" in body:
        pkgs = body["packages"]
    else:
        pkgs = body
    ids = {p.get("id") for p in pkgs} if isinstance(pkgs, list) else set()
    log(
        "B15b /packages 11 pkgs incl adfree_399",
        r.status_code == 200 and len(pkgs) == 11 and "adfree_399" in ids,
        f"n_pkgs={len(pkgs) if isinstance(pkgs, list) else 'n/a'} adfree={'adfree_399' in ids}",
    )
    r = get("/dashboard", admin_token)
    log("B15c /dashboard (admin)", r.status_code == 200, f"status={r.status_code}")
    r = get("/ai/ticker", admin_token)
    log("B15d /ai/ticker", r.status_code == 200, f"status={r.status_code}")


def test_performance(admin_token: str, user_token: str):
    print("\n=== C. Performance smoke ===")
    targets = [
        ("/support/thread", user_token),
        ("/admin/support/threads", admin_token),
        ("/support/unread", user_token),
        ("/admin/support/unread", admin_token),
    ]
    for path, tok in targets:
        t0 = time.time()
        r = get(path, tok)
        dt_ms = (time.time() - t0) * 1000
        log(f"C {path} <500ms", r.status_code == 200 and dt_ms < 500, f"{dt_ms:.0f}ms status={r.status_code}")


if __name__ == "__main__":
    admin_token, user_token = test_premium_support()
    test_regression(admin_token, user_token)
    test_performance(admin_token, user_token)

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"{passed}/{total} passed")
    fails = [(n, d) for n, ok, d in results if not ok]
    if fails:
        print("\nFAILURES:")
        for n, d in fails:
            print(f"  - {n} :: {d}")
