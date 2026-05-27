"""Live BTC/USD rate provider.

Replaces the previous hardcoded `BTC_USD_RATE = 65000.0` constant. Fetches
the spot rate from CoinGecko (free, no API key) and caches it in-process
with a 5-minute TTL. Falls back to the last good value (or a safe
default) on any network/HTTP failure so the rest of the app never
crashes due to an upstream outage.

Public surface:
    get_btc_usd_rate()             -> float (synchronous, returns cached value)
    refresh_btc_usd_rate()         -> coroutine, performs one fetch
    start_periodic_refresh(loop)   -> kicks off a 5-min background refresh
                                       loop; safe to call multiple times.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Last-known-good rate. Seeded with a sane default so the app boots even
# before the first network round-trip completes.
_CACHE = {
    "rate": float(os.environ.get("BTC_USD_RATE_DEFAULT") or 65000.0),
    "fetched_at": 0.0,
    "source": "default",
}
_REFRESH_TASK: Optional[asyncio.Task] = None

# Multiple free public endpoints so a single provider outage doesn't break us.
_SOURCES = [
    {
        "name": "coingecko",
        "url": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
        "parse": lambda j: float(j["bitcoin"]["usd"]),
    },
    {
        "name": "coinbase",
        "url": "https://api.coinbase.com/v2/prices/BTC-USD/spot",
        "parse": lambda j: float(j["data"]["amount"]),
    },
    {
        "name": "kraken",
        "url": "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
        "parse": lambda j: float(next(iter(j["result"].values()))["c"][0]),
    },
]


def get_btc_usd_rate() -> float:
    """Synchronous accessor — returns last cached rate."""
    return float(_CACHE["rate"])


def rate_info() -> dict:
    """Detailed metadata for /api/system/btc_rate-style endpoints."""
    age = max(0.0, time.time() - float(_CACHE["fetched_at"])) if _CACHE["fetched_at"] else None
    return {
        "btc_usd": float(_CACHE["rate"]),
        "source": _CACHE["source"],
        "fetched_at": _CACHE["fetched_at"] or None,
        "age_seconds": age,
    }


async def refresh_btc_usd_rate(timeout: float = 6.0) -> float:
    """Fetch from each provider in order until one succeeds. Updates cache."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        for src in _SOURCES:
            try:
                resp = await client.get(src["url"], headers={
                    "User-Agent": "SatoshiCloudMiner/1.0 (+https://satoshicloudminer.app)",
                    "Accept": "application/json",
                })
                resp.raise_for_status()
                rate = src["parse"](resp.json())
                if 1_000.0 < rate < 1_000_000.0:  # sanity
                    _CACHE["rate"] = float(rate)
                    _CACHE["fetched_at"] = time.time()
                    _CACHE["source"] = src["name"]
                    logger.info("BTC/USD refreshed from %s → $%.2f", src["name"], rate)
                    return rate
                logger.warning("BTC rate from %s out of range: %s", src["name"], rate)
            except Exception as e:
                logger.warning("BTC rate fetch %s failed: %s", src["name"], e)
    logger.warning("All BTC rate sources failed; keeping last value $%.2f (%s)",
                   _CACHE["rate"], _CACHE["source"])
    return float(_CACHE["rate"])


async def _refresh_loop(interval_s: float):
    while True:
        try:
            await refresh_btc_usd_rate()
        except Exception:
            logger.exception("btc_rate refresh loop tick failed (swallowed)")
        await asyncio.sleep(interval_s)


def start_periodic_refresh(interval_s: float = 300.0) -> None:
    """Idempotent: kicks off the refresh loop once per process."""
    global _REFRESH_TASK
    if _REFRESH_TASK and not _REFRESH_TASK.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("btc_rate: no running event loop; skipping periodic refresh")
        return
    _REFRESH_TASK = loop.create_task(_refresh_loop(interval_s))
    logger.info("btc_rate: started periodic refresh every %.0fs", interval_s)


def stop_periodic_refresh() -> None:
    global _REFRESH_TASK
    if _REFRESH_TASK and not _REFRESH_TASK.done():
        _REFRESH_TASK.cancel()
    _REFRESH_TASK = None
