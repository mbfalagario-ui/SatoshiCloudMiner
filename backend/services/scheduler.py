"""Lightweight in-process scheduler for the AI/automation features.

Runs inside the FastAPI worker (single replica). On every tick we sweep the
user collection and:
  * accrue mining earnings (so balance keeps moving even if the user is
    offline)
  * auto-claim daily check-ins for users that opted in
  * auto-reinvest balance into the next-tier package when the threshold is hit
  * refresh the AI Trading Agents snapshot once a day

All jobs are best-effort and exceptions are logged but never raise.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


def _safe(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[None]]:
    async def wrapper(*a, **kw):
        try:
            await fn(*a, **kw)
        except Exception:
            logger.exception("Scheduled job %s failed", fn.__name__)
    return wrapper


def start_jobs(
    accrue_all_users: Callable[..., Awaitable[Any]],
    auto_checkin: Callable[..., Awaitable[Any]],
    auto_reinvest: Callable[..., Awaitable[Any]],
    refresh_agents: Callable[..., Awaitable[Any]],
    auto_ship: Optional[Callable[..., Awaitable[Any]]] = None,
    uptime_check: Optional[Callable[..., Awaitable[Any]]] = None,
) -> None:
    s = get_scheduler()
    if s.running:
        return
    s.add_job(_safe(accrue_all_users), IntervalTrigger(minutes=5), id="accrue_all", replace_existing=True)
    s.add_job(_safe(auto_checkin), IntervalTrigger(hours=1), id="auto_checkin", replace_existing=True)
    s.add_job(_safe(auto_reinvest), IntervalTrigger(hours=2), id="auto_reinvest", replace_existing=True)
    s.add_job(_safe(refresh_agents), CronTrigger(hour=0, minute=5), id="refresh_agents", replace_existing=True)
    if auto_ship is not None:
        # Poll App Store Connect every 30 minutes. The tick is idempotent —
        # it no-ops until the main 1.0 version is approved.
        s.add_job(_safe(auto_ship), IntervalTrigger(minutes=30), id="auto_ship",
                  replace_existing=True, next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30))
    if uptime_check is not None:
        # Hit the public-facing prod URLs every 5 min. Alerts via ntfy.sh
        # on 2 consecutive failures.
        s.add_job(_safe(uptime_check), IntervalTrigger(minutes=5), id="uptime_check",
                  replace_existing=True, next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60))
    s.start()
    logger.info("Background scheduler started.")


def stop_jobs() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
