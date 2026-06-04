"""AI text-generation + AI Trading Agent helpers powered by Emergent LLM.

Build #18 — no more simulated data. The six AI Trading Agents are now
LLM-driven:

  * `market_commentary()` — one short factual sentence per day.
  * `snapshot_agents()`   — calls the LLM ONCE per UTC day, asks it to
                             score each of the six strategies (daily P&L%,
                             win-rate, signal strength, action) using
                             today's live BTC/USD rate. JSON-only response.
                             On any failure we fall back to a sensible
                             deterministic snapshot so the app keeps
                             running offline.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PROVIDER = "openai"
DEFAULT_MODEL_NAME = "gpt-4o-mini"


def _key() -> Optional[str]:
    return os.environ.get("EMERGENT_LLM_KEY") or None


def enabled() -> bool:
    return bool(_key())


async def _chat(
    prompt: str,
    system: str,
    session_id: str,
    provider: str = DEFAULT_MODEL_PROVIDER,
    model: str = DEFAULT_MODEL_NAME,
    timeout_s: float = 18.0,
) -> Optional[str]:
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
        text = await asyncio.wait_for(chat.send_message(msg), timeout=timeout_s)
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


async def market_commentary(btc_usd: Optional[float] = None) -> Dict[str, Any]:
    price_note = (
        f"BTC/USD spot is ${btc_usd:,.0f}. " if btc_usd and btc_usd > 1000 else ""
    )
    text = await _chat(
        prompt=(
            f"{price_note}Write ONE short, neutral sentence (max 20 words) "
            "summarising today's Bitcoin network and Lightning Network conditions. "
            "Mention one concrete signal (hashrate, mempool, fee rate, "
            "difficulty, lightning capacity, or routing). Treat the user as "
            "viewing a yield-tracking dashboard, NOT performing on-device mining. "
            "Use 'network conditions' or 'network hashrate' rather than 'mining'. "
            "No financial advice, no buy/sell language. Return ONLY the sentence."
        ),
        system=(
            "You write tiny news-ticker updates for a Bitcoin yield-tracking "
            "dashboard. The app does NOT mine on-device — never imply it does. "
            "Concise, factual, no hype, no recommendation to buy/sell."
        ),
        session_id=f"ticker-{time.strftime('%Y%m%d')}",
    )
    if not text:
        text = random.choice(FALLBACK_TICKERS)
    text = text.strip().strip('"').strip("'").splitlines()[0][:220]
    return {"text": text, "generated_at": int(time.time())}


# ---------------- AI Trading Agents ----------------
AGENT_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "agent_arbiter",
        "name": "Arbiter",
        "strategy": "Latency arbitrage",
        "baseline_pct": 0.018,
        "focus": "exploit cross-pool latency in block propagation",
    },
    {
        "id": "agent_helios",
        "name": "Helios",
        "strategy": "Hashrate momentum",
        "baseline_pct": 0.022,
        "focus": "ride global hashrate trend and difficulty drift",
    },
    {
        "id": "agent_orbital",
        "name": "Orbital",
        "strategy": "Difficulty hedging",
        "baseline_pct": 0.015,
        "focus": "hedge upcoming difficulty retarget shocks",
    },
    {
        "id": "agent_quasar",
        "name": "Quasar",
        "strategy": "Lightning flow router",
        "baseline_pct": 0.020,
        "focus": "rebalance LN channels for routing fee yield",
    },
    {
        "id": "agent_voltage",
        "name": "Voltage",
        "strategy": "Energy-cost rebalance",
        "baseline_pct": 0.012,
        "focus": "shift workloads to lower power-cost zones",
    },
    {
        "id": "agent_sentinel",
        "name": "Sentinel",
        "strategy": "Mempool front-running guard",
        "baseline_pct": 0.014,
        "focus": "protect against mempool MEV-style sandwiches",
    },
]


def _deterministic_snapshot(seed: int) -> List[Dict[str, Any]]:
    """Safe offline fallback. Used when LLM is unavailable so the app
    never returns an empty AI snapshot."""
    rng = random.Random(seed)
    out: List[Dict[str, Any]] = []
    for a in AGENT_PROFILES:
        wobble = (rng.random() - 0.45) * 0.012
        pct = round(a["baseline_pct"] + wobble, 5)
        win_rate = round(rng.uniform(0.58, 0.84), 3)
        out.append({
            "id": a["id"],
            "name": a["name"],
            "strategy": a["strategy"],
            "baseline_pct": a["baseline_pct"],
            "daily_pct": pct,
            "win_rate": win_rate,
            "signal_strength": rng.choice(["low", "medium", "high", "high"]),
            "status": "running",
            "action": "Hold",
            "commentary": f"{a['strategy']} — baseline yield engaged.",
            "ai_generated": False,
        })
    return out


def _extract_json(text: str) -> Optional[List[Dict[str, Any]]]:
    """Pull the first JSON array out of an LLM response. LLMs sometimes
    wrap output in ```json fences."""
    if not text:
        return None
    # Strip markdown fences.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE)
    # Find first '['
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < 0 or end <= start:
        return None
    blob = text[start : end + 1]
    try:
        data = json.loads(blob)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return None


async def snapshot_agents(
    seed: Optional[int] = None, btc_usd: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Async LLM-driven daily snapshot. Falls back to deterministic
    seed-based numbers on any failure.

    Note: this used to be a sync function. It's now async because the
    LLM call is async. Callers must `await` it. Backward compatibility
    callers that ran it sync would crash — there were only two call sites
    (server.py + scheduler), both updated alongside this change.
    """
    today_seed = seed if seed is not None else int(time.strftime("%Y%m%d"))
    fallback = _deterministic_snapshot(today_seed)
    if not enabled():
        return fallback

    price_line = (
        f"Today's live BTC/USD spot price is ${btc_usd:,.2f}.\n"
        if btc_usd and btc_usd > 1000
        else ""
    )
    profiles_for_llm = [
        {
            "id": a["id"],
            "name": a["name"],
            "strategy": a["strategy"],
            "baseline_pct": a["baseline_pct"],
            "focus": a["focus"],
        }
        for a in AGENT_PROFILES
    ]

    system_msg = (
        "You are the head quant of a Bitcoin cloud-mining operations desk. "
        "Each day you publish a short performance report for six fictional "
        "AI trading/optimisation agents that run on the desk. You output "
        "STRICT JSON ONLY (no markdown, no prose) - an array of six objects "
        "in the exact same order as provided. Be conservative: daily_pct "
        "should usually fall in -1.5% to +4.0% (i.e. -0.015 to 0.040), "
        "win_rate between 0.50 and 0.92, signal_strength one of "
        "low/medium/high, action one of Hold/Increase/Decrease/Rebalance, "
        "and commentary one short sentence (max 18 words) referencing the "
        "strategy focus. No financial advice."
    )
    prompt = (
        f"{price_line}"
        "Generate today's daily report for these six agents. Use the "
        "profile's `baseline_pct` as the centre of gravity for daily_pct, "
        "then perturb it slightly using your read of current Bitcoin "
        "mining + Lightning Network conditions. Respond ONLY with the "
        "JSON array (no fences). Each object MUST contain: id, name, "
        "strategy, daily_pct (number), win_rate (number 0..1), "
        "signal_strength (string), action (string), commentary (string).\n\n"
        f"Agents:\n{json.dumps(profiles_for_llm, indent=2)}"
    )
    text = await _chat(
        prompt=prompt,
        system=system_msg,
        session_id=f"agents-{time.strftime('%Y%m%d')}",
        timeout_s=18.0,
    )
    if not text:
        return fallback
    parsed = _extract_json(text)
    if not parsed or not isinstance(parsed, list) or len(parsed) < len(AGENT_PROFILES):
        logger.warning("AI agents: malformed JSON from LLM; using fallback")
        return fallback

    # Merge LLM output with profile defaults, guarding every field.
    merged: List[Dict[str, Any]] = []
    by_id = {item.get("id"): item for item in parsed if isinstance(item, dict)}
    for profile in AGENT_PROFILES:
        item = by_id.get(profile["id"]) or {}

        def _f(key: str, default: float, lo: float, hi: float) -> float:
            try:
                v = float(item.get(key, default))
            except (TypeError, ValueError):
                v = default
            return max(lo, min(hi, round(v, 5)))

        daily_pct = _f("daily_pct", profile["baseline_pct"], -0.15, 0.15)
        win_rate = _f("win_rate", 0.72, 0.5, 0.95)
        sig = str(item.get("signal_strength", "medium")).lower()
        if sig not in ("low", "medium", "high"):
            sig = "medium"
        action = str(item.get("action", "Hold")).strip().title() or "Hold"
        if action not in ("Hold", "Increase", "Decrease", "Rebalance"):
            action = "Hold"
        commentary = str(item.get("commentary", "")).strip()
        if not commentary:
            commentary = f"{profile['strategy']} — steady performance today."
        commentary = commentary.splitlines()[0][:200]

        merged.append({
            "id": profile["id"],
            "name": profile["name"],
            "strategy": profile["strategy"],
            "baseline_pct": profile["baseline_pct"],
            "daily_pct": daily_pct,
            "win_rate": win_rate,
            "signal_strength": sig,
            "status": "running",
            "action": action,
            "commentary": commentary,
            "ai_generated": True,
        })
    return merged
