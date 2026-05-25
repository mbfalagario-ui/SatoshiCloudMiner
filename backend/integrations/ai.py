"""AI text-generation helpers powered by the Emergent universal LLM key.

We keep one shared function per use case so the rest of the app can ignore the
underlying model details. All calls are best-effort: if the LLM is unavailable
or the response can't be parsed we return a sensible deterministic fallback so
the app stays fully functional offline.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PROVIDER = "openai"
DEFAULT_MODEL_NAME = "gpt-4o-mini"


def _key() -> Optional[str]:
    return os.environ.get("EMERGENT_LLM_KEY") or None


def enabled() -> bool:
    return bool(_key())


async def _chat(prompt: str, system: str, session_id: str,
                provider: str = DEFAULT_MODEL_PROVIDER,
                model: str = DEFAULT_MODEL_NAME,
                timeout_s: float = 12.0) -> Optional[str]:
    key = _key()
    if not key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
    except Exception as e:
        logger.warning("AI: emergentintegrations import failed (%s)", e)
        return None
    try:
        chat = LlmChat(
            api_key=key,
            session_id=session_id,
            system_message=system,
        ).with_model(provider, model)
        msg = UserMessage(text=prompt)
        text = await chat.send_message(msg)
        return str(text)
    except Exception as e:
        logger.warning("AI: chat call failed (%s)", e)
        return None


# ---------------- Market commentary ticker ----------------
FALLBACK_TICKERS = [
    "Mempool depth easing; transaction fees back below 8 sat/vB.",
    "Cluster utilisation steady at 94%. Hashrate trending up week-over-week.",
    "Lightning liquidity rebalanced; payout latency under 1.5s on average.",
    "Power-cost index dipped 2%. Margin envelope expanded for elite tiers.",
    "Difficulty adjustment forecast: small downward retarget expected.",
    "AI agents flagged a short-term yield optimisation across mid-tier rigs.",
    "Network propagation healthy. No reorgs in the last 24 hours.",
    "Sentiment scan: positive on miner profitability, neutral on price action.",
]


async def market_commentary() -> Dict[str, Any]:
    text = await _chat(
        prompt=(
            "Write ONE short, neutral sentence (max 18 words) summarising today's "
            "Bitcoin mining + Lightning network conditions. No financial advice, "
            "no price predictions. Return ONLY the sentence."
        ),
        system=(
            "You write tiny news-ticker style updates for a cloud-mining app. "
            "Concise, factual, no hype, no recommendation to buy/sell."
        ),
        session_id=f"ticker-{time.strftime('%Y%m%d')}",
    )
    if not text:
        text = random.choice(FALLBACK_TICKERS)
    text = text.strip().strip('"').strip("'").splitlines()[0][:220]
    return {"text": text, "generated_at": int(time.time())}


# ---------------- AI Trading Agents ----------------
# Each "agent" is a fictional simulated bot. Its daily P&L is a small random
# delta around a baseline. Visible to users and admins on the dashboard.
DEFAULT_AGENTS: List[Dict[str, Any]] = [
    {"id": "agent_arbiter",     "name": "Arbiter",     "strategy": "Latency arbitrage",        "baseline_pct": 0.018},
    {"id": "agent_helios",      "name": "Helios",      "strategy": "Hashrate momentum",        "baseline_pct": 0.022},
    {"id": "agent_orbital",     "name": "Orbital",     "strategy": "Difficulty hedging",        "baseline_pct": 0.015},
    {"id": "agent_quasar",      "name": "Quasar",      "strategy": "Lightning flow router",     "baseline_pct": 0.020},
    {"id": "agent_voltage",     "name": "Voltage",     "strategy": "Energy-cost rebalance",     "baseline_pct": 0.012},
    {"id": "agent_sentinel",    "name": "Sentinel",    "strategy": "Mempool front-running guard","baseline_pct": 0.014},
]


def snapshot_agents(seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """Deterministic daily snapshot keyed by today's date so all clients see
    the same numbers within a 24h window."""
    if seed is None:
        seed = int(time.strftime("%Y%m%d"))
    rng = random.Random(seed)
    out: List[Dict[str, Any]] = []
    for a in DEFAULT_AGENTS:
        wobble = (rng.random() - 0.45) * 0.012  # -0.0054 .. +0.0066
        pct = round(a["baseline_pct"] + wobble, 5)
        win_rate = round(rng.uniform(0.58, 0.84), 3)
        out.append({
            **a,
            "daily_pct": pct,
            "win_rate": win_rate,
            "signal_strength": rng.choice(["low", "medium", "high", "high"]),
            "status": "running",
        })
    return out
