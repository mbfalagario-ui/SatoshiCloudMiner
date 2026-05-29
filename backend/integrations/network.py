"""Live Bitcoin network stats — feeds the indicative-earnings engine.

Pulls real network hashrate (EH/s -> GH/s) and 24h network block reward total
from mempool.space (primary) with a blockchain.info fallback. Cached in-process
for 10 minutes so we don't hammer the upstream API.

Public surface:
    get_network_stats() -> dict  (synchronous, returns cached)
    refresh()           -> coroutine
    start_periodic_refresh(interval_s=600.0)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Conservative defaults (current-era Bitcoin), used until first live fetch.
_CACHE = {
    "network_hashrate_ghs": 600_000_000_000.0,   # 600 EH/s -> in GH/s
    "daily_block_rewards_btc": 450.0,
    "fetched_at": 0.0,
    "source": "default",
}
_REFRESH_TASK: Optional[asyncio.Task] = None


def get_network_stats() -> dict:
    return {
        "network_hashrate_ghs": float(_CACHE["network_hashrate_ghs"]),
        "daily_block_rewards_btc": float(_CACHE["daily_block_rewards_btc"]),
        "source": _CACHE["source"],
        "fetched_at": _CACHE["fetched_at"] or None,
        "age_seconds": max(0.0, time.time() - float(_CACHE["fetched_at"])) if _CACHE["fetched_at"] else None,
    }


async def refresh(timeout: float = 8.0) -> dict:
    headers = {
        "User-Agent": "HashrateCloudMiner/1.0 (+https://hashratecloudminer.app)",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        # mempool.space primary
        try:
            r = await client.get("https://mempool.space/api/v1/mining/hashrate/1d")
            r.raise_for_status()
            j = r.json()
            # mempool returns hashrate in H/s (raw number, very large)
            hps = float(j.get("currentHashrate", 0))
            if hps > 1e18:  # sanity: > 1 EH/s
                _CACHE["network_hashrate_ghs"] = hps / 1e9
                _CACHE["source"] = "mempool.space"
                _CACHE["fetched_at"] = time.time()
            # mempool block reward
            try:
                r2 = await client.get("https://mempool.space/api/v1/mining/reward-stats/144")
                if r2.status_code == 200:
                    rj = r2.json()
                    total_reward_sats = float(rj.get("totalReward", 0))
                    if total_reward_sats > 0:
                        _CACHE["daily_block_rewards_btc"] = total_reward_sats / 100_000_000.0
            except Exception:
                pass
            logger.info(
                "network: refreshed hashrate=%.0f EH/s rewards=%.1f BTC/day from %s",
                _CACHE["network_hashrate_ghs"] / 1e9,
                _CACHE["daily_block_rewards_btc"],
                _CACHE["source"],
            )
            return get_network_stats()
        except Exception as e:
            logger.warning("network: mempool.space fetch failed: %s", e)

        # blockchain.info fallback
        try:
            r = await client.get("https://blockchain.info/q/hashrate")  # in GH/s
            if r.status_code == 200:
                ghs = float(r.text.strip())
                if ghs > 1e9:  # sanity > 1 EH/s
                    _CACHE["network_hashrate_ghs"] = ghs
                    _CACHE["source"] = "blockchain.info"
                    _CACHE["fetched_at"] = time.time()
                    logger.info("network: refreshed from blockchain.info (no rewards data, keeping prior)")
        except Exception as e:
            logger.warning("network: blockchain.info fallback failed: %s", e)
    return get_network_stats()


async def _refresh_loop(interval_s: float):
    while True:
        try:
            await refresh()
        except Exception:
            logger.exception("network: refresh tick failed (swallowed)")
        await asyncio.sleep(interval_s)


def start_periodic_refresh(interval_s: float = 600.0) -> None:
    global _REFRESH_TASK
    if _REFRESH_TASK and not _REFRESH_TASK.done():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("network: no running event loop; skipping periodic refresh")
        return
    _REFRESH_TASK = loop.create_task(_refresh_loop(interval_s))
    logger.info("network: started periodic refresh every %.0fs", interval_s)


def stop_periodic_refresh() -> None:
    global _REFRESH_TASK
    if _REFRESH_TASK and not _REFRESH_TASK.done():
        _REFRESH_TASK.cancel()
    _REFRESH_TASK = None
