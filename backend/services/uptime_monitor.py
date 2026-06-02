"""Self-hosted uptime monitoring.

Every 5 minutes we hit the public-facing prod URLs and the auth endpoint
that Apple's reviewer uses. If anything 4xx/5xx (or times out) twice in
a row, we push a notification to a private ntfy.sh topic — the admin's
phone gets a push alert.

Why ntfy.sh:
  • No signup, no API key.
  • Anyone who knows the topic name can send/receive — we use a long
    random secret so only the admin's phone (subscribed to the topic)
    receives notifications.
  • Free forever, push notifications on iOS + Android.

Recovery notifications:
  • After a fail-fail sequence, when checks pass again we send a
    "RESOLVED" message so the admin knows the issue cleared.

Everything is logged to the `uptime_events` Mongo collection so we
have a 7-day rolling history (auto-pruned).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

# ── Endpoints we monitor ───────────────────────────────────────────────
# Each tuple is (label, method, url, kw_kwarg)
#   kw_kwarg is body json for POSTs, or None for GETs.
_PROD_BASE_HTML = "https://hashratecloudminer.com"
_PROD_BASE_API = "https://api.hashratecloudminer.com"

CHECKS: List[Dict[str, Any]] = [
    {
        "label": "support",
        "method": "GET",
        "url": f"{_PROD_BASE_HTML}/support",
        "expect_status": 200,
        "expect_substring": "Support",
    },
    {
        "label": "privacy",
        "method": "GET",
        "url": f"{_PROD_BASE_HTML}/privacy",
        "expect_status": 200,
        "expect_substring": "Privacy",
    },
    {
        "label": "marketing",
        "method": "GET",
        "url": f"{_PROD_BASE_HTML}/",
        "expect_status": 200,
        "expect_substring": "Hashrate Cloud Miner",
    },
    {
        "label": "api_health",
        "method": "GET",
        "url": f"{_PROD_BASE_API}/api/system/btc_rate",
        "expect_status": 200,
        "expect_substring": None,
    },
    {
        "label": "api_auth",
        "method": "POST",
        "url": f"{_PROD_BASE_API}/api/auth/login",
        "body": {
            "email": "appreview1@hashratecloudminer.app",
            "password": "AppReview2026!",
        },
        "expect_status": 200,
        "expect_substring": "access_token",
    },
]


# In-memory consecutive-fail counter per endpoint, reset on success.
_consecutive_fails: Dict[str, int] = {c["label"]: 0 for c in CHECKS}

# Threshold: only fire alert after N consecutive failures (avoids
# transient blips creating noise).
ALERT_AFTER_N_FAILS = 2


async def _check_one(c: httpx.AsyncClient, check: Dict[str, Any]) -> Dict[str, Any]:
    started = datetime.now(timezone.utc)
    label = check["label"]
    url = check["url"]
    method = check["method"]
    body = check.get("body")
    expect_status = check["expect_status"]
    expect_substring = check.get("expect_substring")

    result: Dict[str, Any] = {
        "label": label,
        "url": url,
        "ts": started.isoformat(),
    }
    try:
        if method == "GET":
            r = await c.get(url, timeout=8.0)
        else:
            r = await c.post(url, json=body, timeout=8.0)
        text = r.text or ""
        passed = r.status_code == expect_status and (
            expect_substring is None or expect_substring in text
        )
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        result.update({
            "ok": passed,
            "status": r.status_code,
            "ms": elapsed_ms,
            "reason": (
                "" if passed
                else f"status={r.status_code}"
                + ("" if expect_substring is None
                   else (f",missing '{expect_substring}'" if expect_substring not in text
                         else ""))
            ),
        })
    except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
        result.update({
            "ok": False, "status": -1, "ms": -1,
            "reason": f"{type(e).__name__}: {str(e)[:80]}",
        })
    except Exception as e:  # noqa: BLE001
        result.update({
            "ok": False, "status": -2, "ms": -1,
            "reason": f"{type(e).__name__}: {str(e)[:80]}",
        })
    return result


async def _ntfy_push(topic: str, message: str, *, title: str = "Hashrate Cloud Miner",
                      priority: str = "high", tags: str = "warning") -> None:
    """Send a push notification to ntfy.sh."""
    if not topic:
        logger.warning("uptime: no NTFY_TOPIC set — alert dropped")
        return
    try:
        async with httpx.AsyncClient() as c:
            await c.post(
                f"https://ntfy.sh/{topic}",
                content=message.encode("utf-8"),
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": tags,
                },
                timeout=5.0,
            )
    except Exception:  # noqa: BLE001
        logger.exception("uptime: ntfy push failed")


async def run_uptime_check(db) -> None:
    """Single tick. Called by the APScheduler every 5 minutes."""
    topic = os.environ.get("NTFY_TOPIC", "")

    async with httpx.AsyncClient(follow_redirects=True) as c:
        results = await asyncio.gather(*[_check_one(c, ck) for ck in CHECKS])

    # Log to mongo (best effort)
    try:
        await db.uptime_events.insert_many([
            {
                **r,
                "ts": datetime.fromisoformat(r["ts"].replace("Z", "+00:00")),
            }
            for r in results
        ])
    except Exception:  # noqa: BLE001
        logger.exception("uptime: insert into mongo failed")

    # Process state transitions + alerts
    for r in results:
        label = r["label"]
        was_failing = _consecutive_fails[label] >= ALERT_AFTER_N_FAILS
        if r["ok"]:
            # Recovery if we had been failing
            if was_failing:
                await _ntfy_push(
                    topic,
                    message=(
                        f"✅ RESOLVED: {label} is back up.\n"
                        f"URL: {r['url']}\n"
                        f"Latency: {r['ms']}ms"
                    ),
                    title=f"Uptime OK — {label}",
                    priority="default",
                    tags="white_check_mark,hashrate",
                )
            _consecutive_fails[label] = 0
        else:
            _consecutive_fails[label] += 1
            if _consecutive_fails[label] == ALERT_AFTER_N_FAILS:
                await _ntfy_push(
                    topic,
                    message=(
                        f"❌ {label} has failed {ALERT_AFTER_N_FAILS}x in a row.\n"
                        f"URL: {r['url']}\n"
                        f"Reason: {r['reason']}\n"
                        f"At: {r['ts']}\n\n"
                        "If Apple is reviewing right now, this could trigger "
                        "another rejection. Investigate immediately."
                    ),
                    title=f"🚨 ALERT — {label} DOWN",
                    priority="urgent",
                    tags="rotating_light,hashrate",
                )

    # Prune logs >7 days old
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    try:
        await db.uptime_events.delete_many({"ts": {"$lt": cutoff}})
    except Exception:  # noqa: BLE001
        pass

    fail_count = sum(1 for r in results if not r["ok"])
    if fail_count:
        logger.warning("uptime: %d/%d failed",
                       fail_count, len(results))
    else:
        logger.info("uptime: all %d checks OK", len(results))


async def send_test_notification(topic: str) -> bool:
    """Used by /api/admin/uptime/test to fire a one-off notification so
    the admin can confirm they're subscribed correctly."""
    if not topic:
        return False
    await _ntfy_push(
        topic,
        message=(
            "👋 If you're reading this in the ntfy app, monitoring is "
            "wired up correctly. You'll only hear from this topic when "
            "an alert (or recovery) fires.\n\n"
            f"Topic: {topic}\n"
            f"Time: {datetime.now(timezone.utc).isoformat()}"
        ),
        title="Hashrate Cloud Miner — monitoring online",
        priority="default",
        tags="bell,hashrate",
    )
    return True
