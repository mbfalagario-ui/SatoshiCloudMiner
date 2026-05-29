from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
import uuid
import logging
import secrets
import string

import bcrypt
import jwt as pyjwt

from integrations.apple import verify_apple_transaction
from integrations.blink import create_payout as blink_create_payout, get_payout as blink_get_payout
from integrations import ai as ai_mod
from integrations import btc_rate as btc_rate_mod
from services.scheduler import start_jobs, stop_jobs
from services.auto_ship import auto_ship_tick


def get_btc_usd_rate() -> float:
    """Live BTC/USD rate (refreshed every 5 min from CoinGecko/Coinbase/Kraken)."""
    return btc_rate_mod.get_btc_usd_rate()


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRES_MINUTES", "10080"))

ADMIN_EMAIL = (os.environ.get("ADMIN_EMAIL") or "").lower().strip() or None
ADMIN_INITIAL_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD") or None

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="Hashrate Cloud Miner API")
api = APIRouter(prefix="/api")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------- Constants ----------------------------
# BTC/USD rate is now LIVE — pulled from CoinGecko (with Coinbase + Kraken
# fallbacks) every 5 minutes. Use `get_btc_usd_rate()` to read the current
# cached value. The legacy hardcoded 65000.0 was removed in Build #18.
SATS_PER_BTC = 100_000_000
DAILY_CHECKIN_REWARD_USD = 0.05  # $0.05 awarded as BTC equivalent
REFERRAL_BONUS_USD = 0.50

# Withdrawal/redeem limits — Build #22+ (AdMob / Virtual Hashrate model).
# All monetary settings exposed as ENV knobs so the operator can tune
# profitability without redeploys.
MIN_WITHDRAW_SATS = int(os.environ.get("MIN_REDEEM_SATS", "25000"))
MAX_WITHDRAW_SATS = int(os.environ.get("MAX_REDEEM_SATS", "50000"))
WITHDRAW_FEE_FLAT_SATS = int(os.environ.get("REDEEM_FEE_SATS", "150"))
WITHDRAW_FEE_PCT = 0.0  # fee is flat now; previous 10% pct kept for backward-compat in tests
MAX_DAILY_WITHDRAW_SATS = MAX_WITHDRAW_SATS  # one redeem per 24h, max is the per-tx max
REDEEM_COOLDOWN_HOURS = int(os.environ.get("REDEEM_COOLDOWN_HOURS", "24"))
AD_DAILY_CAP = int(os.environ.get("AD_DAILY_CAP", "30"))
CROSS_SELL_DISCOUNT_PCT = int(os.environ.get("CROSS_SELL_DISCOUNT_PCT", "25"))
PAYOUT_MULTIPLIER = float(os.environ.get("PAYOUT_MULTIPLIER", "0.85"))
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@hashratecloudminer.com")

# ----------------------------------------------------------------------
# Daily Check-In ladder — 7-day progressive reward (GH/s, 24h boost each).
# Ladder resets at 1:00 AM UTC. Streak resets on missed day.
# ----------------------------------------------------------------------
DAILY_CHECKIN_LADDER_GHS = [1.2, 1.6, 2.2, 3.1, 5.0, 6.4, 8.0]
CHECKIN_BOOST_DURATION_HOURS = 24

# ----------------------------------------------------------------------
# Rewarded Ad ladder — GH/s reward per ad position in today's stack.
# Each ad's boost lasts 24h. Counter resets at 1:00 AM UTC.
# ----------------------------------------------------------------------
AD_REWARD_LADDER_GHS = [
    1.5, 1.5, 1.5, 1.5, 1.5,        # ads 1-5
    3.0, 3.0, 3.0, 3.0, 3.0,        # ads 6-10
    5.0, 5.0, 5.0, 5.0, 5.0,        # ads 11-15
    7.0, 7.0, 7.0, 7.0, 7.0,        # ads 16-20
    9.5, 9.5, 9.5, 9.5, 9.5,        # ads 21-25
    12.0, 12.0, 12.0, 12.0, 12.0,   # ads 26-30
]
AD_BOOST_DURATION_HOURS = 24

# Predefined shop packages — Build #22+ Apple-safe virtual hashrate model.
#
# IMPORTANT: every id in this list MUST exist as an inAppPurchaseV2 product
# in App Store Connect (verified via the WFQJ6L9KXS API key). Do NOT change
# the ids — these are locked into Apple. Names, taglines, bonuses, and
# durations may be edited freely (and synced to ASC via asc_metadata_upload).
#
# `first_purchase_bonus_pct` — one-time extra GH/s on the FIRST purchase of
# this SKU per user. Linear 15→50% ladder across the 9 mining plans.
# `original_price_usd` — marketing strike-through price for visual "25% off"
# (does not actually charge a different amount; Apple still bills `price_usd`).
SHOP_PACKAGES = [
    {
        "id": "welcome_199",
        "name": "Newcomer Boost",
        "tagline": "First-time-only mega boost",
        "offer_text": "Buy 1, Get 1 free",
        "price_usd": 1.99,
        "original_price_usd": 2.65,
        "hashrate_boost_ghs": 50,
        "duration_hours": 720,
        "badge": "NEW",
        "first_purchase_bonus_pct": 15,
        "ai_optimized": False,
    },
    {
        "id": "rookie_299",
        "name": "Daily Booster",
        "tagline": "30-day power-up",
        "offer_text": None,
        "price_usd": 2.99,
        "original_price_usd": 3.99,
        "hashrate_boost_ghs": 100,
        "duration_hours": 720,
        "badge": None,
        "first_purchase_bonus_pct": 19,
        "ai_optimized": False,
    },
    {
        "id": "pro_499",
        "name": "Pro Rig",
        "tagline": "Most popular",
        "offer_text": None,
        "price_usd": 4.99,
        "original_price_usd": 6.65,
        "hashrate_boost_ghs": 230,
        "duration_hours": 720,
        "badge": "POPULAR",
        "first_purchase_bonus_pct": 24,
        "ai_optimized": True,
    },
    {
        "id": "elite_999",
        "name": "Elite Rig",
        "tagline": "Save 25%",
        "offer_text": None,
        "price_usd": 9.99,
        "original_price_usd": 13.32,
        "hashrate_boost_ghs": 500,
        "duration_hours": 720,
        "badge": None,
        "first_purchase_bonus_pct": 28,
        "ai_optimized": True,
    },
    {
        "id": "ultra_1999",
        "name": "Ultra Rig",
        "tagline": "Best value",
        "offer_text": None,
        "price_usd": 19.99,
        "original_price_usd": 26.65,
        "hashrate_boost_ghs": 1100,
        "duration_hours": 720,
        "badge": "VALUE",
        "first_purchase_bonus_pct": 33,
        "ai_optimized": True,
    },
    {
        "id": "mega_4999",
        "name": "Mega Rig",
        "tagline": "Tera-class boost",
        "offer_text": None,
        "price_usd": 49.99,
        "original_price_usd": 66.65,
        "hashrate_boost_ghs": 2300,
        "duration_hours": 720,
        "badge": "PRO",
        "first_purchase_bonus_pct": 37,
        "ai_optimized": True,
    },
    {
        "id": "giga_9999",
        "name": "Giga Rig",
        "tagline": "Industrial scale",
        "offer_text": None,
        "price_usd": 99.99,
        "original_price_usd": 133.32,
        "hashrate_boost_ghs": 3500,
        "duration_hours": 720,
        "badge": None,
        "first_purchase_bonus_pct": 42,
        "ai_optimized": True,
    },
    {
        "id": "titan_14999",
        "name": "Titan Rig",
        "tagline": "Premium scale",
        "offer_text": "Buy 1, Get 1 free",
        "price_usd": 149.99,
        "original_price_usd": 199.99,
        "hashrate_boost_ghs": 4700,
        "duration_hours": 720,
        "badge": "BOGO",
        "first_purchase_bonus_pct": 46,
        "ai_optimized": True,
    },
    {
        "id": "colossus_19999",
        "name": "Colossus Rig",
        "tagline": "Maximum hashpower",
        "offer_text": "Buy 1, Get 1 free",
        "price_usd": 199.99,
        "original_price_usd": 266.65,
        "hashrate_boost_ghs": 7500,
        "duration_hours": 720,
        "badge": "FLAGSHIP",
        "first_purchase_bonus_pct": 50,
        "ai_optimized": True,
    },
    # ------------------------------------------------------------------
    # One-time entitlement: removes interstitial ads + unlocks priority
    # support. Tracked on the User document as `ad_free=True` instead of
    # creating a machine. No bonus % applies.
    # ------------------------------------------------------------------
    {
        "id": "adfree_399",
        "name": "Ad-Free + Priority Support",
        "tagline": "Remove ads · Priority queue",
        "offer_text": None,
        "price_usd": 3.99,
        "original_price_usd": 3.99,
        "hashrate_boost_ghs": 0,
        "duration_hours": 0,
        "badge": "UPGRADE",
        "first_purchase_bonus_pct": 0,
        "ai_optimized": False,
        "entitlement": "ad_free",
    },
]


def _enrich_package(p: Dict[str, Any]) -> Dict[str, Any]:
    """Hashrate-based package projection — Apple-safe (no ROI promises).

    Returns the boost pack's hashrate gain + duration + indicative GH/s-hours
    + UI helpers (display string, original price strike-through, bonus%).
    """
    boost_ghs = p.get("hashrate_boost_ghs", 0)
    duration_hours = p.get("duration_hours", 0)
    return {
        **p,
        "duration_label": (
            f"{duration_hours // 24}d" if duration_hours >= 24
            else f"{duration_hours}h"
        ) if duration_hours > 0 else "permanent",
        "gh_s_hours": boost_ghs * duration_hours,
        "hashrate_display": (
            f"{boost_ghs / 1000.0:.2f} TH/s" if boost_ghs >= 1000
            else f"{boost_ghs:.0f} GH/s"
        ),
    }


def _current_utc_day_bucket() -> str:
    """Day bucket keyed by 1:00 AM UTC reset boundary.
    Returns 'YYYY-MM-DD' for the most recent 1AM-UTC tick.
    """
    now = now_utc()
    # If current hour < 1, we belong to the previous day's bucket.
    if now.hour < 1:
        now = now - timedelta(days=1)
    return now.strftime("%Y-%m-%d")


def _next_1am_utc(now: Optional[datetime] = None) -> datetime:
    """Next 1:00 AM UTC boundary from `now`."""
    now = now or now_utc()
    today_1am = now.replace(hour=1, minute=0, second=0, microsecond=0)
    if now < today_1am:
        return today_1am
    return today_1am + timedelta(days=1)


def _ad_reward_for_position(position_1based: int) -> float:
    """GH/s reward for the Nth ad watched today (1-indexed)."""
    idx = max(0, min(len(AD_REWARD_LADDER_GHS) - 1, position_1based - 1))
    return float(AD_REWARD_LADDER_GHS[idx])


WITHDRAW_METHODS = [
    {
        "id": "lightning",
        "name": "Lightning Network",
        "subtitle": "Lightning invoice (BOLT11) or Lightning address",
        "icon": "flash",
    },
]


# ---------------------------- Models ----------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    referral_code: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class WithdrawRequest(BaseModel):
    method_id: str = "lightning"
    address: str = Field(min_length=2, max_length=2048)  # BOLT11 invoice can be long
    amount_sats: int = Field(gt=0, le=10_000_000)


class BuyPackageRequest(BaseModel):
    package_id: str
    apple_transaction_id: Optional[str] = None  # iOS App Store transaction id from StoreKit


class CheckinResponse(BaseModel):
    awarded_usd: float
    streak: int
    next_available_at: datetime


class AdminUserPatch(BaseModel):
    is_admin: Optional[bool] = None
    is_banned: Optional[bool] = None
    balance_btc_delta: Optional[float] = None    # positive credits, negative debits
    note: Optional[str] = None


class AdminTxnPatch(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None


class AutoSettingsUpdate(BaseModel):
    auto_checkin: Optional[bool] = None
    auto_reinvest: Optional[bool] = None
    auto_reinvest_min_balance_usd: Optional[float] = Field(default=None, ge=0)


# Free Forever — the once-per-24h complimentary mining plan added in
# Build #13. Hashpower expressed as a tiny TH/s fraction so the dashboard
# math (which is in TH/s everywhere else) keeps working without changes.
FREE_FOREVER_HASH_RATE_TH = 0.5            # = 500 GH/s
FREE_FOREVER_DAILY_YIELD_USD = 0.02        # tiny "thank you" yield
FREE_FOREVER_DURATION_HOURS = 24
FREE_FOREVER_COOLDOWN_HOURS = 24


class AdminAIAgentPatch(BaseModel):
    """Allow an operator to nudge a single AI Trading Agent for the current
    day's snapshot. Build #13 admin console enhancement."""
    daily_pct: Optional[float] = None
    win_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    signal_strength: Optional[str] = None   # 'high' | 'medium' | 'low'
    strategy: Optional[str] = None
    enabled: Optional[bool] = None


class AdminFeesReinvestRequest(BaseModel):
    """Reinvest the unredeemed withdrawal-commission fees collected to-date
    by attributing them to a target user's balance (default: the operator
    themselves). Build #13 admin console enhancement."""
    target_user_id: Optional[str] = None    # default = current admin
    note: Optional[str] = None


class SupportSendRequest(BaseModel):
    """User → admin support message. Build #15."""
    body: str = Field(min_length=1, max_length=2000)


class AdminSupportReplyRequest(BaseModel):
    """Admin → user support reply. Build #15."""
    body: str = Field(min_length=1, max_length=2000)
    user_id: Optional[str] = None      # not used; path param takes priority
    close_thread: Optional[bool] = False


# ---------------------------- Helpers ----------------------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str) -> str:
    now = now_utc()
    payload = {
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES),
    }
    return pyjwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def gen_referral_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(7))


def usd_to_btc(usd: float) -> float:
    return usd / get_btc_usd_rate()


def btc_to_usd(btc: float) -> float:
    return btc * get_btc_usd_rate()


def sats_to_btc(sats: int) -> float:
    return sats / SATS_PER_BTC


def btc_to_sats(btc: float) -> int:
    return int(round(btc * SATS_PER_BTC))


def withdrawal_fee_sats(amount_sats: int) -> int:
    # Flat 10% fee — no baseline (covers Lightning routing + processing).
    return max(0, int(round(amount_sats * WITHDRAW_FEE_PCT)))


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Dict[str, Any]:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = pyjwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Account suspended")
    return user


async def get_current_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return current_user


async def accrue_earnings(user_id: str) -> Dict[str, float]:
    """Hashrate-based indicative earnings (Build #22+).

    Replaces the old fixed daily_yield_usd math. Sums the user's hashrate
    from active boost packs PLUS virtual hashrate granted by the daily
    check-in and rewarded ads (24h boost per ad, summed from active rows
    in `ad_views`). Multiplies by today's share of the live Bitcoin block
    reward, scaled by PAYOUT_MULTIPLIER (operator knob, default 0.85x).

    The result is **indicative** — earnings depend on real network
    hashrate and BTC price at accrual time.
    """
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        return {"accrued_btc": 0.0, "accrued_usd": 0.0}

    last = user.get("last_accrual_at")
    if isinstance(last, str):
        last = datetime.fromisoformat(last)
    if not last:
        last = now_utc()
    now = now_utc()
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)

    # --- Sum active hashrate (GH/s) from boost packs + virtual sources ---
    machines = await db.machines.find(
        {"user_id": user_id, "status": "active"}, {"_id": 0}
    ).to_list(500)
    user_hashrate_ghs = 0.0
    for m in machines:
        expires_at = m.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at and expires_at < now:
            await db.machines.update_one(
                {"id": m["id"]}, {"$set": {"status": "expired"}}
            )
            continue
        # New machines store hashrate_boost_ghs; legacy machines may have
        # hash_rate (interpret as GH/s for backward compat).
        ghs = m.get("hashrate_boost_ghs") or m.get("hash_rate") or 0
        user_hashrate_ghs += float(ghs)

    # Virtual hashrate from daily check-in (variable GH/s by ladder day, 24h boost)
    checkin_exp = user.get("checkin_hashrate_expires_at")
    if isinstance(checkin_exp, str):
        checkin_exp = datetime.fromisoformat(checkin_exp)
    if checkin_exp and checkin_exp.tzinfo is None:
        checkin_exp = checkin_exp.replace(tzinfo=timezone.utc)
    if checkin_exp and checkin_exp > now:
        user_hashrate_ghs += float(user.get("checkin_hashrate_ghs", 0.0))

    # Virtual hashrate from rewarded ads — sum each non-expired ad view's
    # individual reward (each ad's boost lasts 24h from earn time).
    ad_cursor = db.ad_views.find(
        {"user_id": user_id, "expires_at": {"$gt": now.isoformat()}},
        {"_id": 0, "reward_ghs": 1},
    )
    async for av in ad_cursor:
        user_hashrate_ghs += float(av.get("reward_ghs", 0.0))

    # --- Apply network math (real live values, no simulated data) ---
    try:
        from integrations import network as network_mod
        stats = network_mod.get_network_stats()
        net_ghs = max(1.0, stats["network_hashrate_ghs"])
        daily_btc = max(0.01, stats["daily_block_rewards_btc"])
    except Exception:
        net_ghs = 600_000_000_000.0
        daily_btc = 450.0

    multiplier = float(os.environ.get("PAYOUT_MULTIPLIER", "0.85"))
    elapsed_seconds = max(0.0, (now - last).total_seconds())
    if elapsed_seconds == 0 or user_hashrate_ghs == 0:
        accrued_btc = 0.0
        accrued_usd = 0.0
    else:
        fair_per_sec = (user_hashrate_ghs / net_ghs) * (daily_btc / 86400.0)
        accrued_btc = fair_per_sec * multiplier * elapsed_seconds
        accrued_usd = btc_to_usd(accrued_btc)

    await db.users.update_one(
        {"id": user_id},
        {
            "$inc": {
                "balance_btc": accrued_btc,
                "lifetime_earnings_btc": accrued_btc,
            },
            "$set": {"last_accrual_at": now.isoformat()},
        },
    )

    if accrued_usd > 0.00001:
        await db.transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": "mining",
                "amount_usd": accrued_usd,
                "amount_btc": accrued_btc,
                "status": "completed",
                "description": "Indicative earnings",
                "created_at": now.isoformat(),
            }
        )

    return {"accrued_btc": accrued_btc, "accrued_usd": accrued_usd}


async def total_hash_rate(user_id: str) -> float:
    cursor = db.machines.find({"user_id": user_id, "status": "active"}, {"_id": 0, "hash_rate": 1})
    total = 0.0
    async for m in cursor:
        total += float(m.get("hash_rate", 0.0))
    return total


async def todays_mining_usd(user_id: str) -> float:
    start_of_day = now_utc().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    cursor = db.transactions.find(
        {
            "user_id": user_id,
            "type": "mining",
            "created_at": {"$gte": start_of_day},
        },
        {"_id": 0, "amount_usd": 1},
    )
    total = 0.0
    async for t in cursor:
        total += float(t.get("amount_usd", 0.0))
    return total


def serialize_user_public(u: Dict[str, Any]) -> Dict[str, Any]:
    balance_btc = float(u.get("balance_btc", 0.0))
    lifetime_btc = float(u.get("lifetime_earnings_btc", 0.0))
    return {
        "id": u["id"],
        "email": u["email"],
        "referral_code": u.get("referral_code"),
        "created_at": u.get("created_at"),
        "balance_btc": round(balance_btc, 8),
        "balance_sats": btc_to_sats(balance_btc),
        "balance_usd": round(btc_to_usd(balance_btc), 2),
        "lifetime_btc": round(lifetime_btc, 8),
        "lifetime_sats": btc_to_sats(lifetime_btc),
        "lifetime_usd": round(btc_to_usd(lifetime_btc), 2),
        "is_admin": bool(u.get("is_admin", False)),
        "is_banned": bool(u.get("is_banned", False)),
        "ad_free": bool(u.get("ad_free", False)),
        "auto_checkin": bool(u.get("auto_checkin", True)),
        "auto_reinvest": bool(u.get("auto_reinvest", False)),
        "auto_reinvest_min_balance_usd": float(u.get("auto_reinvest_min_balance_usd", 4.99)),
        "checkin_streak": int(u.get("checkin_streak", 0)),
        "checkin_hashrate_ghs": float(u.get("checkin_hashrate_ghs", 0.0)),
        "purchased_sku_bonuses": list(u.get("purchased_sku_bonuses") or []),
    }


# ---------------------------- Routes: Auth ----------------------------
@api.post("/auth/register", response_model=TokenOut)
async def register(payload: UserCreate):
    email = payload.email.lower().strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    now = now_utc()
    ref_code = gen_referral_code()

    # Build #22+ — new users start with ZERO machines. They earn hashrate
    # via daily check-ins (free) and rewarded video ads (free) before
    # purchasing any mining plans. Streak starts at 0.

    # Optional referral
    referred_by = None
    if payload.referral_code:
        referrer = await db.users.find_one({"referral_code": payload.referral_code.upper()})
        if referrer:
            referred_by = referrer["id"]
            # Bonus to referrer
            await db.users.update_one(
                {"id": referrer["id"]},
                {"$inc": {"balance_btc": usd_to_btc(REFERRAL_BONUS_USD)}},
            )
            await db.transactions.insert_one(
                {
                    "id": str(uuid.uuid4()),
                    "user_id": referrer["id"],
                    "type": "referral",
                    "amount_usd": REFERRAL_BONUS_USD,
                    "amount_btc": usd_to_btc(REFERRAL_BONUS_USD),
                    "status": "completed",
                    "description": f"Referral bonus from new user",
                    "created_at": now.isoformat(),
                }
            )

    user_doc = {
        "id": user_id,
        "email": email,
        "password_hash": hash_password(payload.password),
        "referral_code": ref_code,
        "referred_by": referred_by,
        "balance_btc": 0.0,
        "lifetime_earnings_btc": 0.0,
        "last_accrual_at": now.isoformat(),
        "last_checkin_at": None,
        "last_checkin_day_bucket": None,
        "checkin_streak": 0,
        "checkin_hashrate_ghs": 0.0,
        "checkin_hashrate_expires_at": None,
        "purchased_sku_bonuses": [],
        "cross_sell_consumed_skus": [],
        "auto_checkin": False,  # Build #22+: ladder is manual to preserve UX
        "auto_reinvest": False,
        "created_at": now.isoformat(),
    }

    await db.users.insert_one(user_doc)

    user_public = serialize_user_public(user_doc)
    token = create_access_token(user_id, email)
    return TokenOut(access_token=token, user=user_public)


@api.post("/auth/login", response_model=TokenOut)
async def login(payload: UserLogin):
    email = payload.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Account suspended")
    token = create_access_token(user["id"], user["email"])
    return TokenOut(access_token=token, user=serialize_user_public(user))


@api.get("/auth/me")
async def me(current_user: Dict[str, Any] = Depends(get_current_user)):
    await accrue_earnings(current_user["id"])
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    return serialize_user_public(user)


# ---------------------------- Routes: Dashboard ----------------------------
@api.get("/dashboard")
async def dashboard(current_user: Dict[str, Any] = Depends(get_current_user)):
    await accrue_earnings(current_user["id"])
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0, "password_hash": 0})
    hash_rate = await total_hash_rate(current_user["id"])
    today_usd = await todays_mining_usd(current_user["id"])

    active_machines = await db.machines.find(
        {"user_id": current_user["id"], "status": "active"}, {"_id": 0}
    ).to_list(50)

    # Daily projected
    daily_projected_usd = sum(float(m.get("daily_yield_usd", 0.0)) for m in active_machines)

    return {
        "user": serialize_user_public(user),
        "hash_rate": round(hash_rate, 2),
        "active_machines_count": len(active_machines),
        "today_earnings_usd": round(today_usd, 4),
        "today_earnings_btc": round(usd_to_btc(today_usd), 8),
        "daily_projected_usd": round(daily_projected_usd, 4),
        "btc_usd_rate": get_btc_usd_rate(),
        "active_machines": active_machines[:5],
    }


# ---------------------------- Routes: Machines ----------------------------
@api.get("/machines")
async def list_machines(current_user: Dict[str, Any] = Depends(get_current_user)):
    await accrue_earnings(current_user["id"])
    machines = await db.machines.find(
        {"user_id": current_user["id"]}, {"_id": 0}
    ).sort("purchased_at", -1).to_list(200)
    return {"machines": machines}


# ---------------------------- Routes: Shop ----------------------------
@api.get("/packages")
async def get_packages():
    return {"packages": [_enrich_package(p) for p in SHOP_PACKAGES]}


@api.post("/packages/buy")
async def buy_package(
    payload: BuyPackageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    pkg = next((p for p in SHOP_PACKAGES if p["id"] == payload.package_id), None)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")

    await accrue_earnings(current_user["id"])
    now = now_utc()

    # ------------------------------------------------------------------
    # Apple IAP receipt validation
    # If the client supplied an `apple_transaction_id` (it will when the
    # purchase originated from StoreKit on iOS), we validate it against the
    # App Store Server API and refuse the request if it doesn't match this
    # package's product id. When Apple credentials aren't configured the
    # verifier returns a MOCK response so the endpoint still works in dev.
    # Each transactionId can only be redeemed ONCE.
    # ------------------------------------------------------------------
    apple_info: Dict[str, Any] = {"_mocked": True, "skipped": True}
    if payload.apple_transaction_id:
        # Idempotency: refuse a transactionId that's already been redeemed.
        existing = await db.transactions.find_one(
            {"apple_transaction_id": payload.apple_transaction_id}
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="This Apple transaction was already redeemed."
            )
        try:
            apple_info = verify_apple_transaction(
                payload.apple_transaction_id,
                expected_product_id=pkg["id"],
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Apple IAP validation failed: {e}")
        except Exception as e:
            logger.exception("Apple IAP verification crashed")
            raise HTTPException(status_code=500, detail=f"Apple IAP verification error: {e}")

    # ------------------------------------------------------------------
    # Entitlement products (no machine — just flip a user flag, e.g. ad_free)
    # ------------------------------------------------------------------
    entitlement = pkg.get("entitlement")
    if entitlement == "ad_free":
        already = bool(current_user.get("ad_free"))
        if already:
            raise HTTPException(status_code=400, detail="You already own the Ad-Free upgrade.")
        await db.users.update_one(
            {"id": current_user["id"]},
            {"$set": {"ad_free": True, "ad_free_purchased_at": now.isoformat()}},
        )
        await db.transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": current_user["id"],
                "type": "purchase",
                "amount_usd": pkg["price_usd"],
                "amount_btc": 0.0,
                "status": "completed",
                "description": f"Purchased {pkg['name']}",
                "package_id": pkg["id"],
                "entitlement": "ad_free",
                "apple_transaction_id": payload.apple_transaction_id,
                "apple_environment": apple_info.get("environment"),
                "apple_mocked": bool(apple_info.get("_mocked")),
                "created_at": now.isoformat(),
            }
        )
        return {
            "success": True,
            "machines_added": 0,
            "entitlement_granted": "ad_free",
            "package": pkg,
            "apple": {
                "verified": not apple_info.get("_mocked", True),
                "environment": apple_info.get("environment"),
            },
        }

    def _make_machine(suffix: str = "", bonus_ghs: float = 0.0) -> Dict[str, Any]:
        boost_ghs = pkg.get("hashrate_boost_ghs", 0) + bonus_ghs
        duration_h = pkg.get("duration_hours", 720)
        return {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "package_id": pkg["id"],
            "name": pkg["name"] + suffix,
            "hashrate_boost_ghs": boost_ghs,
            "hash_rate": boost_ghs,  # backward-compat
            "duration_hours": duration_h,
            "purchased_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=duration_h)).isoformat(),
            "status": "active",
        }

    # ------------------------------------------------------------------
    # One-time first-purchase bonus (15→50% linear ladder).
    # Applied ONLY on the first time this user buys this SKU. The user's
    # `purchased_sku_bonuses` array tracks consumed bonuses.
    # ------------------------------------------------------------------
    user_doc = await db.users.find_one({"id": current_user["id"]}, {"_id": 0}) or {}
    consumed_bonuses = list(user_doc.get("purchased_sku_bonuses") or [])
    bonus_pct = float(pkg.get("first_purchase_bonus_pct") or 0)
    apply_bonus = bonus_pct > 0 and (pkg["id"] not in consumed_bonuses)
    bonus_ghs = (pkg.get("hashrate_boost_ghs", 0) * bonus_pct / 100.0) if apply_bonus else 0.0

    machines_added = [_make_machine(bonus_ghs=bonus_ghs)]

    await db.machines.insert_many(machines_added)

    if apply_bonus:
        await db.users.update_one(
            {"id": current_user["id"]},
            {"$addToSet": {"purchased_sku_bonuses": pkg["id"]}},
        )

    await db.transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "type": "purchase",
            "amount_usd": pkg["price_usd"],
            "amount_btc": 0.0,
            "status": "completed",
            "description": (
                f"Purchased {pkg['name']}"
                + (f" + first-time bonus +{bonus_pct:.0f}% (+{bonus_ghs:.1f} GH/s)" if apply_bonus else "")
            ),
            "package_id": pkg["id"],
            "bonus_pct_applied": bonus_pct if apply_bonus else 0.0,
            "bonus_ghs_applied": bonus_ghs,
            "apple_transaction_id": payload.apple_transaction_id,
            "apple_environment": apple_info.get("environment"),
            "apple_mocked": bool(apple_info.get("_mocked")),
            "created_at": now.isoformat(),
        }
    )

    return {
        "success": True,
        "machines_added": len(machines_added),
        "first_purchase_bonus_applied": apply_bonus,
        "bonus_pct": bonus_pct if apply_bonus else 0.0,
        "bonus_ghs": round(bonus_ghs, 2),
        "package": pkg,
        "apple": {
            "verified": not apple_info.get("_mocked", True),
            "environment": apple_info.get("environment"),
        },
    }


# ---------------------------- Routes: Withdraw ----------------------------
@api.get("/withdraw/methods")
async def withdraw_methods(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Returns redeem limits + fee + cooldown for the Earnings → Redeem flow.

    Admins bypass all limits (1 sat min, 0 fee, no cooldown) so they can
    drain commission balances freely.
    """
    if current_user.get("is_admin"):
        return {
            "methods": WITHDRAW_METHODS,
            "min_sats": 1,
            "max_sats": 10_000_000,
            "max_daily_sats": 10_000_000,
            "fee_pct": 0.0,
            "fee_flat_sats": 0,
            "cooldown_hours": 0,
            "btc_usd_rate": get_btc_usd_rate(),
            "admin_unlimited": True,
        }
    return {
        "methods": WITHDRAW_METHODS,
        "min_sats": MIN_WITHDRAW_SATS,
        "max_sats": MAX_WITHDRAW_SATS,
        "max_daily_sats": MAX_DAILY_WITHDRAW_SATS,
        "fee_pct": 0.0,
        "fee_flat_sats": WITHDRAW_FEE_FLAT_SATS,
        "cooldown_hours": REDEEM_COOLDOWN_HOURS,
        "btc_usd_rate": get_btc_usd_rate(),
        "admin_unlimited": False,
    }


class RedeemQuoteRequest(BaseModel):
    amount_sats: int = Field(gt=0, le=10_000_000)


@api.post("/redeem/quote")
async def redeem_quote(
    payload: RedeemQuoteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Pre-flight fee/balance preview for the Redeem confirmation modal.

    Returns the fee, total debit, remaining balance, and warnings without
    actually triggering a payout. Apple-safe: no fee is hidden from the user.
    """
    is_admin_caller = bool(current_user.get("is_admin"))
    amount_sats = int(payload.amount_sats)

    min_s = 1 if is_admin_caller else MIN_WITHDRAW_SATS
    max_s = 10_000_000 if is_admin_caller else MAX_WITHDRAW_SATS
    fee_sats = 0 if is_admin_caller else WITHDRAW_FEE_FLAT_SATS

    errors: List[str] = []
    if amount_sats < min_s:
        errors.append(f"Minimum redeem is {min_s:,} sats.")
    if amount_sats > max_s:
        errors.append(f"Maximum redeem is {max_s:,} sats.")

    await accrue_earnings(current_user["id"])
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    balance_sats = btc_to_sats(float(user.get("balance_btc", 0.0)))
    total_debit = amount_sats + fee_sats

    if total_debit > balance_sats:
        errors.append(
            f"Insufficient balance. You need {total_debit:,} sats ({amount_sats:,} + {fee_sats} fee) "
            f"but have {balance_sats:,} sats."
        )

    # 24h cooldown check
    cooldown_remaining_seconds = 0
    if not is_admin_caller and REDEEM_COOLDOWN_HOURS > 0:
        last = await db.transactions.find_one(
            {
                "user_id": current_user["id"],
                "type": "withdrawal",
                "status": {"$in": ["completed", "pending", "in_progress"]},
            },
            sort=[("created_at", -1)],
        )
        if last:
            try:
                last_at = datetime.fromisoformat(last["created_at"])
                if last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                next_at = last_at + timedelta(hours=REDEEM_COOLDOWN_HOURS)
                if now_utc() < next_at:
                    cooldown_remaining_seconds = int((next_at - now_utc()).total_seconds())
                    errors.append(
                        f"Only one redeem per {REDEEM_COOLDOWN_HOURS} hours. "
                        f"Try again in {cooldown_remaining_seconds // 3600}h {(cooldown_remaining_seconds % 3600) // 60}m."
                    )
            except Exception:
                pass

    return {
        "ok": len(errors) == 0,
        "amount_sats": amount_sats,
        "fee_sats": fee_sats,
        "total_debit_sats": total_debit,
        "balance_sats": balance_sats,
        "remaining_balance_sats": max(0, balance_sats - total_debit),
        "amount_btc": sats_to_btc(amount_sats),
        "fee_btc": sats_to_btc(fee_sats),
        "amount_usd": round(btc_to_usd(sats_to_btc(amount_sats)), 4),
        "fee_usd": round(btc_to_usd(sats_to_btc(fee_sats)), 4),
        "cooldown_hours": REDEEM_COOLDOWN_HOURS,
        "cooldown_remaining_seconds": cooldown_remaining_seconds,
        "min_sats": min_s,
        "max_sats": max_s,
        "errors": errors,
    }


@api.post("/withdraw")
async def withdraw(
    payload: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Lightning redeem — instant payout via Blink. Fee deducted from balance.
    Once per REDEEM_COOLDOWN_HOURS for non-admin users.
    """
    method = next((m for m in WITHDRAW_METHODS if m["id"] == payload.method_id), None)
    if not method:
        raise HTTPException(status_code=400, detail="Lightning is the only supported redeem method")

    is_admin_caller = bool(current_user.get("is_admin"))
    amount_sats = int(payload.amount_sats)
    if amount_sats < 1:
        raise HTTPException(status_code=400, detail="Amount must be at least 1 sat.")
    if not is_admin_caller:
        if amount_sats < MIN_WITHDRAW_SATS:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum redeem is {MIN_WITHDRAW_SATS:,} sats ({MIN_WITHDRAW_SATS / SATS_PER_BTC:.8f} BTC).",
            )
        if amount_sats > MAX_WITHDRAW_SATS:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum redeem is {MAX_WITHDRAW_SATS:,} sats ({MAX_WITHDRAW_SATS / SATS_PER_BTC:.8f} BTC).",
            )

    fee_sats = 0 if is_admin_caller else WITHDRAW_FEE_FLAT_SATS
    total_debit_sats = amount_sats + fee_sats
    amount_btc = sats_to_btc(amount_sats)
    fee_btc = sats_to_btc(fee_sats)
    total_debit_btc = sats_to_btc(total_debit_sats)

    await accrue_earnings(current_user["id"])
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    balance_btc = float(user.get("balance_btc", 0.0))
    if total_debit_btc > balance_btc + 1e-12:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient balance. Need {total_debit_sats:,} sats "
                f"({amount_sats:,} sats + {fee_sats} sats fee), have "
                f"{btc_to_sats(balance_btc):,} sats."
            ),
        )

    # 24h cooldown — once per cooldown window. Skip for admin.
    if not is_admin_caller and REDEEM_COOLDOWN_HOURS > 0:
        last = await db.transactions.find_one(
            {
                "user_id": current_user["id"],
                "type": "withdrawal",
                "status": {"$in": ["completed", "pending", "in_progress"]},
            },
            sort=[("created_at", -1)],
        )
        if last:
            try:
                last_at = datetime.fromisoformat(last["created_at"])
                if last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                next_at = last_at + timedelta(hours=REDEEM_COOLDOWN_HOURS)
                if now_utc() < next_at:
                    remaining = int((next_at - now_utc()).total_seconds())
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Only one redeem per {REDEEM_COOLDOWN_HOURS} hours. "
                            f"Try again in {remaining // 3600}h {(remaining % 3600) // 60}m."
                        ),
                    )
            except HTTPException:
                raise
            except Exception:
                pass

    # Reserve balance up-front so concurrent calls can't double-spend.
    await db.users.update_one(
        {"id": current_user["id"]}, {"$inc": {"balance_btc": -total_debit_btc}}
    )

    # Real Lightning payout via Blink (instant). Refund full debit on failure.
    try:
        payout = blink_create_payout(
            amount_usd=round(btc_to_usd(amount_btc), 6),
            destination=payload.address,
            description="Hashrate Cloud Miner redeem",
        )
    except Exception as e:
        await db.users.update_one(
            {"id": current_user["id"]}, {"$inc": {"balance_btc": total_debit_btc}}
        )
        logger.exception("Blink payout failed")
        raise HTTPException(status_code=502, detail=f"Payout provider error: {e}")

    tx = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "user_email": user.get("email"),
        "type": "withdrawal",
        "amount_sats": amount_sats,
        "fee_sats": fee_sats,
        "total_debit_sats": total_debit_sats,
        "amount_btc": amount_btc,
        "fee_btc": fee_btc,
        "amount_usd": round(btc_to_usd(amount_btc), 6),
        "status": payout.get("status", "pending"),
        "method": method["name"],
        "address": payload.address,
        "description": "Lightning redeem",
        "blink_provider": payout.get("provider"),
        "blink_payout_id": payout.get("payout_id"),
        "blink_state": payout.get("blink_state"),
        "blink_view_url": payout.get("view_url"),
        "destination_kind": payout.get("kind"),
        "created_at": now_utc().isoformat(),
    }
    await db.transactions.insert_one({**tx})
    tx.pop("_id", None)
    return {"success": True, "transaction": tx, "payout": payout}


# ---------------------------- Routes: Transactions ----------------------------
@api.get("/withdraw/{tx_id}/status")
async def withdraw_status(tx_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    tx = await db.transactions.find_one(
        {"id": tx_id, "user_id": current_user["id"], "type": "withdrawal"}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Withdrawal not found")
    payout_id = tx.get("blink_payout_id")
    if not payout_id:
        return {"transaction": tx, "live_status": None}
    try:
        live = blink_get_payout(payout_id)
    except Exception as e:
        return {"transaction": tx, "live_status": None, "error": str(e)}
    # Update stored status if it changed
    if live.get("status") and live["status"] != tx.get("status"):
        await db.transactions.update_one(
            {"id": tx_id},
            {"$set": {"status": live["status"], "blink_state": live.get("blink_state")}},
        )
        tx["status"] = live["status"]
    return {"transaction": tx, "live_status": live}


@api.get("/transactions")
async def transactions(
    current_user: Dict[str, Any] = Depends(get_current_user),
    limit: int = 100,
):
    items = (
        await db.transactions.find({"user_id": current_user["id"]}, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    return {"transactions": items}


# ---------------------------- Routes: Daily check-in (Build #22+) ----------------------------
# 7-day progressive ladder, GH/s reward for 24h boost. Resets at 1:00 AM UTC.
# Streak resets to Day 1 on missed day.
def _checkin_state(user: Dict[str, Any]) -> Dict[str, Any]:
    """Compute the user's current check-in availability + next step in ladder."""
    now = now_utc()
    last = user.get("last_checkin_at")
    last_dt = None
    if last:
        last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

    streak = int(user.get("checkin_streak", 0))
    today_bucket = _current_utc_day_bucket()
    last_bucket = (user.get("last_checkin_day_bucket") or "")

    # Available if user has NOT checked in today's bucket.
    available = (last_bucket != today_bucket)

    # If user missed a day → reset to Day 1 next claim.
    next_step = 1
    if available:
        if not last_dt:
            next_step = 1
        else:
            # Compute number of bucket-days since last check-in.
            try:
                last_bucket_dt = datetime.strptime(last_bucket, "%Y-%m-%d").replace(tzinfo=timezone.utc) if last_bucket else None
            except Exception:
                last_bucket_dt = None
            today_bucket_dt = datetime.strptime(today_bucket, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_gap = (today_bucket_dt - last_bucket_dt).days if last_bucket_dt else 999
            if days_gap == 1 and streak < 7:
                next_step = streak + 1
            elif days_gap == 1 and streak >= 7:
                next_step = 1  # cycle restart after Day 7
            else:
                next_step = 1  # streak broken
    else:
        # User already claimed today → preview the next claim's step.
        # If streak < 7, next claim is streak+1; if streak == 7 it resets to 1.
        next_step = streak + 1 if (streak >= 1 and streak < 7) else 1

    next_reward_ghs = DAILY_CHECKIN_LADDER_GHS[next_step - 1]
    next_at = _next_1am_utc(now)

    return {
        "available": available,
        "streak": streak,
        "next_step": next_step,
        "ladder_ghs": DAILY_CHECKIN_LADDER_GHS,
        "next_reward_ghs": next_reward_ghs,
        "boost_duration_hours": CHECKIN_BOOST_DURATION_HOURS,
        "next_available_at": next_at.isoformat(),
    }


@api.get("/daily-checkin/status")
async def checkin_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return _checkin_state(user)


@api.post("/daily-checkin", response_model=CheckinResponse)
async def daily_checkin(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    state = _checkin_state(user)

    if not state["available"]:
        raise HTTPException(
            status_code=400,
            detail=f"Check in again at {state['next_available_at']}",
        )

    now = now_utc()
    new_step = int(state["next_step"])
    reward_ghs = float(state["next_reward_ghs"])
    today_bucket = _current_utc_day_bucket()
    boost_expires = now + timedelta(hours=CHECKIN_BOOST_DURATION_HOURS)

    await db.users.update_one(
        {"id": current_user["id"]},
        {
            "$set": {
                "last_checkin_at": now.isoformat(),
                "last_checkin_day_bucket": today_bucket,
                "checkin_streak": new_step,
                "checkin_hashrate_ghs": reward_ghs,
                "checkin_hashrate_expires_at": boost_expires.isoformat(),
            },
        },
    )

    await db.transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "type": "checkin",
            "amount_usd": 0.0,
            "amount_btc": 0.0,
            "status": "completed",
            "description": f"Daily check-in Day {new_step}: +{reward_ghs} GH/s for 24h",
            "reward_ghs": reward_ghs,
            "step": new_step,
            "created_at": now.isoformat(),
        }
    )

    return CheckinResponse(
        awarded_usd=0.0,
        streak=new_step,
        next_available_at=_next_1am_utc(now),
    )


# ---------------------------- Routes: Referral ----------------------------
@api.get("/referral")
async def referral(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    count = await db.users.count_documents({"referred_by": current_user["id"]})
    return {
        "code": user.get("referral_code"),
        "invited_count": count,
        "bonus_per_invite_usd": REFERRAL_BONUS_USD,
        "share_text": f"Mine Bitcoin in the cloud — join Hashrate Cloud Miner with my code {user.get('referral_code')} for a bonus.",
    }


# ---------------------------- Routes: AI / Automation ----------------------------
@api.get("/ai/ticker")
async def ai_ticker():
    return await ai_mod.market_commentary(btc_usd=get_btc_usd_rate())


# Public diagnostic — also useful for the Wallet UI to display the live rate.
@api.get("/system/btc_rate")
async def system_btc_rate():
    return btc_rate_mod.rate_info()


# Live Bitcoin network stats (hashrate + daily block rewards). Drives the
# indicative-earnings engine.
@api.get("/system/network")
async def system_network():
    from integrations import network as network_mod
    return network_mod.get_network_stats()


# ---------------------------- Rewarded ads (AdMob) ----------------------------
@api.get("/ads/ssv_callback")
async def admob_ssv_callback(request: Request):
    """Google AdMob server-side verification callback.

    Apple-safe pattern: ad revenue funds the user's hashrate boost, NOT
    the user's IAP. Each verified callback grants a progressive GH/s reward
    based on the user's ad count today (1-5: 1.5 GH/s, 6-10: 3.0, 11-15: 5.0,
    16-20: 7.0, 21-25: 9.5, 26-30: 12.0 GH/s). Max 30 ads/day, resets at
    1:00 AM UTC. Each ad's boost lasts 24h independently.

    Idempotent on `transaction_id` (ad_view_id). Returns 200 on success
    so AdMob doesn't retry, including for duplicates.
    """
    from integrations import admob as admob_mod
    qs = str(request.url.query)
    ok, params = admob_mod.verify_ssv_query(qs)
    if not ok or not params:
        logger.warning("admob SSV: bad signature or params; qs=%s", qs[:300])
        return {"status": "rejected", "reason": "signature_invalid"}

    tx_id = params.get("transaction_id")
    if not tx_id:
        return {"status": "rejected", "reason": "missing_transaction_id"}

    ts = params.get("timestamp", "0")
    try:
        if not admob_mod.is_fresh(int(ts)):
            logger.warning("admob SSV: stale timestamp %s", ts)
            return {"status": "rejected", "reason": "stale"}
    except Exception:
        pass

    user_id = params.get("custom_data") or params.get("user_id")
    if not user_id:
        logger.warning("admob SSV: no user_id/custom_data")
        return {"status": "rejected", "reason": "no_user"}

    existing = await db.ad_views.find_one({"transaction_id": tx_id}, {"_id": 0})
    if existing:
        return {"status": "ok", "reason": "duplicate"}

    now = now_utc()
    bucket = _current_utc_day_bucket()
    daily_count = await db.ad_views.count_documents({
        "user_id": user_id, "day_bucket": bucket,
    })
    if daily_count >= AD_DAILY_CAP:
        return {"status": "rejected", "reason": "daily_cap"}

    position = daily_count + 1
    reward_ghs = _ad_reward_for_position(position)
    expires_at = now + timedelta(hours=AD_BOOST_DURATION_HOURS)

    await db.ad_views.insert_one({
        "transaction_id": tx_id,
        "user_id": user_id,
        "day_bucket": bucket,
        "date": now.strftime("%Y-%m-%d"),
        "position": position,
        "reward_ghs": reward_ghs,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    })
    return {
        "status": "ok",
        "reward_ghs": reward_ghs,
        "position": position,
        "daily_cap": AD_DAILY_CAP,
        "boost_duration_hours": AD_BOOST_DURATION_HOURS,
    }


@api.post("/ads/claim_dev")
async def ads_claim_dev(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Dev/Test endpoint — manually credit a rewarded-ad reward.

    On production iOS builds the real AdMob SDK fires `/api/ads/ssv_callback`
    automatically. This endpoint exists so the in-app "Watch ad" button can
    locally grant the reward when SSV isn't yet wired (e.g. simulator, web).
    Subject to the same 30/day cap and 1AM UTC reset.
    """
    user_id = current_user["id"]
    now = now_utc()
    bucket = _current_utc_day_bucket()
    daily_count = await db.ad_views.count_documents({
        "user_id": user_id, "day_bucket": bucket,
    })
    if daily_count >= AD_DAILY_CAP:
        raise HTTPException(
            status_code=400,
            detail=f"You've watched all {AD_DAILY_CAP} rewarded ads available today.",
        )
    position = daily_count + 1
    reward_ghs = _ad_reward_for_position(position)
    expires_at = now + timedelta(hours=AD_BOOST_DURATION_HOURS)
    await db.ad_views.insert_one({
        "transaction_id": f"dev-{uuid.uuid4().hex}",
        "user_id": user_id,
        "day_bucket": bucket,
        "date": now.strftime("%Y-%m-%d"),
        "position": position,
        "reward_ghs": reward_ghs,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "source": "dev",
    })
    return {
        "ok": True,
        "reward_ghs": reward_ghs,
        "position": position,
        "remaining_today": AD_DAILY_CAP - position,
    }


@api.get("/ads/status")
async def ads_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """How many ads the user has watched in the current day-bucket + total
    active ad-boosted hashrate."""
    now = now_utc()
    bucket = _current_utc_day_bucket()
    n = await db.ad_views.count_documents({
        "user_id": current_user["id"], "day_bucket": bucket,
    })
    # Sum active ad rewards
    active_ghs = 0.0
    cur = db.ad_views.find(
        {"user_id": current_user["id"], "expires_at": {"$gt": now.isoformat()}},
        {"_id": 0, "reward_ghs": 1},
    )
    async for v in cur:
        active_ghs += float(v.get("reward_ghs", 0.0))

    next_pos = min(n + 1, AD_DAILY_CAP)
    next_reward = _ad_reward_for_position(next_pos) if n < AD_DAILY_CAP else 0.0

    return {
        "ads_today": n,
        "daily_cap": AD_DAILY_CAP,
        "remaining_today": max(0, AD_DAILY_CAP - n),
        "active_ad_hashrate_ghs": round(active_ghs, 2),
        "next_reward_ghs": next_reward,
        "boost_duration_hours": AD_BOOST_DURATION_HOURS,
    }


# ---------------------------- Indicative earnings ----------------------------
@api.get("/earnings")
async def earnings_view(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Indicative earnings snapshot — used by the Earnings tab.

    Computes total user hashrate (boost packs + check-in + ads), pulls
    live network stats, returns an estimate. Earnings are illustrative;
    the operator's payout_multiplier governs final amounts.
    """
    from integrations import network as network_mod
    # Settle any pending accrual first
    await accrue_earnings(current_user["id"])
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    now = now_utc()

    # Sum hashrate components
    machines = await db.machines.find(
        {"user_id": current_user["id"], "status": "active"}, {"_id": 0}
    ).to_list(500)
    pack_ghs = 0.0
    for m in machines:
        exp = m.get("expires_at")
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and exp < now:
            continue
        pack_ghs += float(m.get("hashrate_boost_ghs") or m.get("hash_rate") or 0)

    checkin_exp = user.get("checkin_hashrate_expires_at")
    if isinstance(checkin_exp, str):
        checkin_exp = datetime.fromisoformat(checkin_exp)
    if checkin_exp and checkin_exp.tzinfo is None:
        checkin_exp = checkin_exp.replace(tzinfo=timezone.utc)
    checkin_ghs = float(user.get("checkin_hashrate_ghs", 0.0)) if (checkin_exp and checkin_exp > now) else 0.0

    # Sum still-active per-ad-view rewards (Build #22+ schema)
    ad_ghs = 0.0
    cur = db.ad_views.find(
        {"user_id": current_user["id"], "expires_at": {"$gt": now.isoformat()}},
        {"_id": 0, "reward_ghs": 1},
    )
    async for av in cur:
        ad_ghs += float(av.get("reward_ghs", 0.0))

    total_ghs = pack_ghs + checkin_ghs + ad_ghs

    stats = network_mod.get_network_stats()
    net_ghs = max(1.0, stats["network_hashrate_ghs"])
    daily_btc = max(0.01, stats["daily_block_rewards_btc"])
    multiplier = float(os.environ.get("PAYOUT_MULTIPLIER", "0.85"))
    fair_per_day = (total_ghs / net_ghs) * daily_btc
    indicative_daily_btc = fair_per_day * multiplier
    indicative_per_second_btc = indicative_daily_btc / 86400.0

    return {
        "indicative_balance_btc": float(user.get("balance_btc", 0.0)),
        "lifetime_earnings_btc": float(user.get("lifetime_earnings_btc", 0.0)),
        "hashrate": {
            "total_ghs": total_ghs,
            "pack_ghs": pack_ghs,
            "checkin_ghs": checkin_ghs,
            "ad_ghs": ad_ghs,
        },
        "indicative_daily_btc": indicative_daily_btc,
        "indicative_daily_usd": btc_to_usd(indicative_daily_btc),
        "indicative_per_second_btc": indicative_per_second_btc,
        "payout_multiplier": multiplier,
        "network": {
            "hashrate_ehs": net_ghs / 1e9,
            "daily_block_rewards_btc": daily_btc,
            "source": stats.get("source"),
        },
        "btc_usd": get_btc_usd_rate(),
        "min_redeem_sats": int(os.environ.get("MIN_REDEEM_SATS", "25000")),
        "disclaimer": (
            "Earnings shown are indicative estimates only. Hashrate Cloud Miner "
            "does not hold or manage on-chain assets; it is not a wallet, "
            "trading platform, or fund manager. Final amounts depend on live "
            "network conditions and server records."
        ),
    }


# Redemption — non-custodial framing. User pastes their own BTC/Lightning
# address at redemption time. Backend issues the payout via Blink.
@api.post("/redeem")
async def redeem(
    payload: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Alias for the existing /api/withdraw flow with redemption framing."""
    return await withdraw(payload, current_user)


# Static download — Foolproof iOS Clone Prompts Playbook PDF.
@api.get("/downloads/playbook.pdf")
async def download_playbook_pdf():
    p = "/app/store/playbook/Foolproof_iOS_Clone_Prompts_Playbook.pdf"
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Playbook not generated yet")
    return FileResponse(
        p,
        media_type="application/pdf",
        filename="Foolproof_iOS_Clone_Prompts_Playbook.pdf",
    )


# Individual PRODUCT_SPEC files (so the user can attach them directly).
@api.get("/downloads/spec_btc.md")
async def download_spec_btc():
    p = "/app/store/playbook/specs/PRODUCT_SPEC_Satoshi_Cloud_Miner.md"
    if not os.path.exists(p):
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="text/markdown",
                        filename="PRODUCT_SPEC_Satoshi_Cloud_Miner.md")


@api.get("/downloads/spec_ltc_doge.md")
async def download_spec_ltc_doge():
    p = "/app/store/playbook/specs/PRODUCT_SPEC_LTC_DOGE_Cloud_Miner.md"
    if not os.path.exists(p):
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="text/markdown",
                        filename="PRODUCT_SPEC_LTC_DOGE_Cloud_Miner.md")


# Single bundle ZIP — playbook PDF + both specs + README in one click.
@api.get("/downloads/bundle.zip")
async def download_bundle_zip():
    p = "/app/store/playbook/Ship_A_Clone_Bundle.zip"
    if not os.path.exists(p):
        raise HTTPException(status_code=404)
    return FileResponse(p, media_type="application/zip",
                        filename="Ship_A_Clone_Bundle.zip")


@api.get("/ai/agents")
async def ai_agents():
    """Today's LLM-driven AI Trading Agents snapshot (cached per UTC day)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cached = await db.ai_snapshots.find_one({"date": today}, {"_id": 0})
    if cached and cached.get("agents"):
        return cached
    agents = await ai_mod.snapshot_agents(btc_usd=get_btc_usd_rate())
    snap = {"date": today, "agents": agents, "created_at": now_utc().isoformat()}
    try:
        await db.ai_snapshots.update_one({"date": today}, {"$set": snap}, upsert=True)
    except Exception:
        pass
    return snap


@api.get("/auto/settings")
async def get_auto_settings(current_user: Dict[str, Any] = Depends(get_current_user)):
    return {
        "auto_checkin": bool(current_user.get("auto_checkin", True)),
        "auto_reinvest": bool(current_user.get("auto_reinvest", False)),
        "auto_reinvest_min_balance_usd": float(current_user.get("auto_reinvest_min_balance_usd", 4.99)),
    }


@api.post("/auto/settings")
async def set_auto_settings(
    payload: AutoSettingsUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    upd: Dict[str, Any] = {}
    if payload.auto_checkin is not None:
        upd["auto_checkin"] = bool(payload.auto_checkin)
    if payload.auto_reinvest is not None:
        upd["auto_reinvest"] = bool(payload.auto_reinvest)
    if payload.auto_reinvest_min_balance_usd is not None:
        upd["auto_reinvest_min_balance_usd"] = float(payload.auto_reinvest_min_balance_usd)
    if upd:
        await db.users.update_one({"id": current_user["id"]}, {"$set": upd})
    return await get_auto_settings(current_user={**current_user, **upd})


# ---------------------------- Routes: Free Forever ----------------------------
# Build #13 — a complimentary 24h mining plan for every user. They can
# re-activate it every 24 hours; in between activations the "next available"
# countdown is what the Home screen renders.
def _free_forever_state(user: Dict[str, Any]) -> Dict[str, Any]:
    last_iso = user.get("free_forever_last_activated_at")
    now = now_utc()
    if not last_iso:
        return {
            "active": False,
            "expires_at": None,
            "next_available_at": now.isoformat(),
            "hash_rate_th": FREE_FOREVER_HASH_RATE_TH,
            "hash_rate_display": "500 GH/s",
            "duration_hours": FREE_FOREVER_DURATION_HOURS,
            "daily_yield_usd": FREE_FOREVER_DAILY_YIELD_USD,
        }
    try:
        last = datetime.fromisoformat(last_iso)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
    except Exception:
        last = now - timedelta(days=2)  # treat malformed as expired
    expires = last + timedelta(hours=FREE_FOREVER_DURATION_HOURS)
    next_available = last + timedelta(hours=FREE_FOREVER_COOLDOWN_HOURS)
    return {
        "active": now < expires,
        "expires_at": expires.isoformat() if now < expires else None,
        "next_available_at": (now if now >= next_available else next_available).isoformat(),
        "hash_rate_th": FREE_FOREVER_HASH_RATE_TH,
        "hash_rate_display": "500 GH/s",
        "duration_hours": FREE_FOREVER_DURATION_HOURS,
        "daily_yield_usd": FREE_FOREVER_DAILY_YIELD_USD,
    }


@api.get("/free-forever/status")
async def free_forever_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return _free_forever_state(user or current_user)


@api.post("/free-forever/activate")
async def free_forever_activate(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    state = _free_forever_state(user or current_user)

    if state["active"]:
        raise HTTPException(
            status_code=400,
            detail="Free Forever is already active. Wait for the current 24h cycle to finish before activating again.",
        )

    now = now_utc()
    # Cooldown check — should always pass when active==False with our equal
    # 24h duration + cooldown, but kept for safety in case durations diverge.
    next_avail_iso = state.get("next_available_at")
    if next_avail_iso:
        try:
            next_avail = datetime.fromisoformat(next_avail_iso)
            if next_avail.tzinfo is None:
                next_avail = next_avail.replace(tzinfo=timezone.utc)
            if now < next_avail:
                wait_seconds = int((next_avail - now).total_seconds())
                raise HTTPException(
                    status_code=400,
                    detail=f"Free Forever will be available again in {wait_seconds // 3600}h {(wait_seconds % 3600) // 60}m.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    # Mint the 24h miner and bump the user's activation timestamp.
    machine = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "package_id": "free_forever",
        "name": "Free Forever",
        "hash_rate": FREE_FOREVER_HASH_RATE_TH,
        "daily_yield_usd": FREE_FOREVER_DAILY_YIELD_USD,
        "duration_days": FREE_FOREVER_DURATION_HOURS / 24.0,
        "purchased_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=FREE_FOREVER_DURATION_HOURS)).isoformat(),
        "status": "active",
    }
    await db.machines.insert_one(machine)
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"free_forever_last_activated_at": now.isoformat()}},
    )

    # Refresh user snapshot for the response.
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    return {
        "ok": True,
        "machine_id": machine["id"],
        "status": _free_forever_state(user or current_user),
    }


# ---------------------------- Routes: Premium Support Chat (Build #15) ----------------------------
# A simple two-party chat: every regular user has at most ONE support thread
# with the operator. Messages go into `db.support_messages`; per-thread
# metadata (last activity, status, unread counts) lives in `db.support_threads`.
SUPPORT_REPLY_SLA_HOURS = 48


async def _support_get_or_create_thread(user_id: str, user_email: str) -> Dict[str, Any]:
    existing = await db.support_threads.find_one({"user_id": user_id}, {"_id": 0})
    if existing:
        return existing
    now = now_utc().isoformat()
    thread = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_email": user_email,
        "status": "open",                          # open | closed
        "created_at": now,
        "last_message_at": None,
        "last_message_preview": None,
        "last_message_from": None,                 # 'user' | 'admin'
        "unread_user_count": 0,                    # admin → user not yet read by user
        "unread_admin_count": 0,                   # user → admin not yet read by admin
    }
    await db.support_threads.insert_one(thread.copy())
    return thread


async def _support_serialize_messages(thread_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    cursor = db.support_messages.find({"thread_id": thread_id}, {"_id": 0}).sort("created_at", 1)
    return await cursor.to_list(limit)


@api.get("/support/thread")
async def support_get_thread(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Fetch the signed-in user's thread + all messages. Auto-marks any
    unread admin → user messages as read."""
    thread = await _support_get_or_create_thread(current_user["id"], current_user["email"])
    msgs = await _support_serialize_messages(thread["id"])
    # mark admin→user messages as read (the user just opened the chat)
    if thread.get("unread_user_count", 0) > 0:
        await db.support_threads.update_one(
            {"id": thread["id"]},
            {"$set": {"unread_user_count": 0}},
        )
        await db.support_messages.update_many(
            {"thread_id": thread["id"], "sender": "admin", "read_at": None},
            {"$set": {"read_at": now_utc().isoformat()}},
        )
        thread["unread_user_count"] = 0
    return {
        "thread": thread,
        "messages": msgs,
        "sla_hours": SUPPORT_REPLY_SLA_HOURS,
    }


@api.get("/support/unread")
async def support_unread(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Cheap polling endpoint used to badge the Profile menu entry."""
    thread = await db.support_threads.find_one({"user_id": current_user["id"]}, {"_id": 0})
    return {"unread_user_count": int((thread or {}).get("unread_user_count", 0))}


@api.post("/support/messages")
async def support_send_message(
    payload: SupportSendRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    thread = await _support_get_or_create_thread(current_user["id"], current_user["email"])
    now = now_utc().isoformat()
    msg = {
        "id": str(uuid.uuid4()),
        "thread_id": thread["id"],
        "user_id": current_user["id"],            # who the thread belongs to
        "sender": "user",                         # 'user' | 'admin'
        "sender_email": current_user["email"],
        "body": body[:2000],
        "created_at": now,
        "read_at": None,
    }
    await db.support_messages.insert_one(msg.copy())

    # Bump thread metadata. Admin's unread count grows; if thread was closed,
    # reopen it so the operator console picks it up again.
    await db.support_threads.update_one(
        {"id": thread["id"]},
        {
            "$set": {
                "last_message_at": now,
                "last_message_preview": body[:140],
                "last_message_from": "user",
                "status": "open",
            },
            "$inc": {"unread_admin_count": 1},
        },
    )
    return {"ok": True, "message": msg}


# ---------------------------- Routes: Admin (Support) ----------------------------
@api.get("/admin/support/threads")
async def admin_support_threads(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """Operator inbox — all support threads, newest activity first.

    `status_filter` query param: 'open' (default), 'closed', or 'all'."""
    cursor = db.support_threads.find({}, {"_id": 0}).sort("last_message_at", -1)
    threads = await cursor.to_list(500)
    # Soft-sort: threads with last_message_at=None go to the bottom.
    threads.sort(key=lambda t: t.get("last_message_at") or "", reverse=True)
    total_unread = sum(int(t.get("unread_admin_count", 0)) for t in threads)
    open_count = sum(1 for t in threads if t.get("status", "open") == "open")
    return {
        "threads": threads,
        "total_unread_admin": total_unread,
        "open_count": open_count,
        "sla_hours": SUPPORT_REPLY_SLA_HOURS,
    }


@api.get("/admin/support/unread")
async def admin_support_unread(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """Cheap polling endpoint used to badge the Operator Console."""
    pipeline = [{"$group": {"_id": None, "n": {"$sum": {"$ifNull": ["$unread_admin_count", 0]}}}}]
    agg = await db.support_threads.aggregate(pipeline).to_list(1)
    return {"unread_admin_count": int((agg[0] if agg else {}).get("n", 0))}


@api.get("/admin/support/threads/{user_id}")
async def admin_support_thread_detail(
    user_id: str,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "hashed_password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    thread = await db.support_threads.find_one({"user_id": user_id}, {"_id": 0})
    if not thread:
        # auto-create so the operator can open a brand-new conversation
        thread = await _support_get_or_create_thread(user_id, user.get("email") or user_id)
    msgs = await _support_serialize_messages(thread["id"])

    # Opening the thread in the operator console marks all user→admin
    # messages as read so the badge doesn't keep counting them.
    if thread.get("unread_admin_count", 0) > 0:
        await db.support_threads.update_one(
            {"id": thread["id"]},
            {"$set": {"unread_admin_count": 0}},
        )
        await db.support_messages.update_many(
            {"thread_id": thread["id"], "sender": "user", "read_at": None},
            {"$set": {"read_at": now_utc().isoformat()}},
        )
        thread["unread_admin_count"] = 0
    return {
        "thread": thread,
        "messages": msgs,
        "user": user,
        "sla_hours": SUPPORT_REPLY_SLA_HOURS,
    }


@api.post("/admin/support/threads/{user_id}/reply")
async def admin_support_reply(
    user_id: str,
    payload: AdminSupportReplyRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Reply cannot be empty.")
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    thread = await _support_get_or_create_thread(user_id, user.get("email") or user_id)

    now = now_utc().isoformat()
    msg = {
        "id": str(uuid.uuid4()),
        "thread_id": thread["id"],
        "user_id": user_id,
        "sender": "admin",
        "sender_email": current_admin["email"],
        "body": body[:2000],
        "created_at": now,
        "read_at": None,
    }
    await db.support_messages.insert_one(msg.copy())

    update_set: Dict[str, Any] = {
        "last_message_at": now,
        "last_message_preview": body[:140],
        "last_message_from": "admin",
    }
    if payload.close_thread:
        update_set["status"] = "closed"
    await db.support_threads.update_one(
        {"id": thread["id"]},
        {
            "$set": update_set,
            "$inc": {"unread_user_count": 1},
        },
    )

    # Write to the audit log so admin replies appear in /admin/audit.
    await db.admin_audit.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": "support_reply",
        "target_user_id": user_id,
        "thread_id": thread["id"],
        "message_id": msg["id"],
        "preview": body[:140],
        "closed_thread": bool(payload.close_thread),
        "created_at": now,
    })

    return {"ok": True, "message": msg}


@api.post("/admin/support/threads/{user_id}/close")
async def admin_support_close(
    user_id: str,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """Close a thread without sending a message (e.g. resolved internally)."""
    thread = await db.support_threads.find_one({"user_id": user_id}, {"_id": 0})
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found.")
    await db.support_threads.update_one(
        {"id": thread["id"]},
        {"$set": {"status": "closed", "closed_at": now_utc().isoformat()}},
    )
    return {"ok": True}


# ---------------------------- Routes: Admin ----------------------------
@api.get("/admin/analytics")
async def admin_analytics(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    total_users = await db.users.count_documents({})
    banned_users = await db.users.count_documents({"is_banned": True})
    total_machines = await db.machines.count_documents({})
    active_machines = await db.machines.count_documents({"status": "active"})
    expired_machines = await db.machines.count_documents({"status": "expired"})

    # Revenue & payouts (sum across collections)
    pipeline_purchases = [
        {"$match": {"type": "purchase"}},
        {"$group": {"_id": None, "total_usd": {"$sum": "$amount_usd"}, "count": {"$sum": 1}}},
    ]
    pipeline_payouts = [
        {"$match": {"type": "withdrawal"}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "total_sats": {"$sum": {"$ifNull": ["$amount_sats", 0]}},
            "total_fee_sats": {"$sum": {"$ifNull": ["$fee_sats", 0]}},
        }},
    ]
    pipeline_mining = [
        {"$match": {"type": "mining"}},
        {"$group": {"_id": None, "total_usd": {"$sum": "$amount_usd"}}},
    ]

    purchases = await db.transactions.aggregate(pipeline_purchases).to_list(1)
    payouts_by_status = await db.transactions.aggregate(pipeline_payouts).to_list(20)
    mining = await db.transactions.aggregate(pipeline_mining).to_list(1)

    revenue_usd = float((purchases[0] if purchases else {}).get("total_usd", 0.0))
    paid_out_sats = sum(int(p.get("total_sats", 0)) for p in payouts_by_status if p["_id"] in ("completed", "in_progress", "pending"))
    fees_collected_sats = sum(int(p.get("total_fee_sats", 0)) for p in payouts_by_status)
    mining_usd_paid = float((mining[0] if mining else {}).get("total_usd", 0.0))
    paid_out_usd = btc_to_usd(sats_to_btc(paid_out_sats))
    fees_usd = btc_to_usd(sats_to_btc(fees_collected_sats))
    gross_margin_usd = revenue_usd - paid_out_usd - mining_usd_paid + fees_usd
    profit_margin_pct = (gross_margin_usd / revenue_usd * 100.0) if revenue_usd > 0 else 0.0

    # Latest 5 withdrawals
    latest_wd = await db.transactions.find(
        {"type": "withdrawal"}, {"_id": 0}
    ).sort("created_at", -1).to_list(5)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snap = await db.ai_snapshots.find_one({"date": today}, {"_id": 0}) or {}

    return {
        "users": {"total": total_users, "banned": banned_users},
        "machines": {"total": total_machines, "active": active_machines, "expired": expired_machines},
        "revenue_usd": round(revenue_usd, 2),
        "paid_out_usd": round(paid_out_usd, 2),
        "paid_out_sats": paid_out_sats,
        "fees_collected_sats": fees_collected_sats,
        "fees_collected_usd": round(fees_usd, 2),
        "mining_usd_paid": round(mining_usd_paid, 4),
        "gross_margin_usd": round(gross_margin_usd, 2),
        "profit_margin_pct": round(profit_margin_pct, 1),
        "payouts_by_status": payouts_by_status,
        "latest_withdrawals": latest_wd,
        "ai_agents_today": snap.get("agents", []),
        "btc_usd_rate": get_btc_usd_rate(),
    }


@api.get("/admin/users")
async def admin_users(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    limit: int = 200,
    search: Optional[str] = None,
):
    q: Dict[str, Any] = {}
    if search:
        q["email"] = {"$regex": search.lower(), "$options": "i"}
    users = await db.users.find(q, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(limit)
    return {"users": [serialize_user_public(u) | {"is_banned": bool(u.get("is_banned", False))} for u in users]}


@api.patch("/admin/users/{user_id}")
async def admin_patch_user(
    user_id: str,
    payload: AdminUserPatch,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    upd: Dict[str, Any] = {}
    inc: Dict[str, Any] = {}
    if payload.is_admin is not None:
        upd["is_admin"] = bool(payload.is_admin)
    if payload.is_banned is not None:
        upd["is_banned"] = bool(payload.is_banned)
    if payload.balance_btc_delta is not None:
        inc["balance_btc"] = float(payload.balance_btc_delta)
    set_doc: Dict[str, Any] = {}
    if upd:
        set_doc["$set"] = upd
    if inc:
        set_doc["$inc"] = inc
    if set_doc:
        await db.users.update_one({"id": user_id}, set_doc)
    # Audit log
    await db.admin_audit.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "target_user_id": user_id,
        "patch": payload.model_dump(),
        "note": payload.note,
        "created_at": now_utc().isoformat(),
    })
    user2 = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return serialize_user_public(user2) | {"is_banned": bool(user2.get("is_banned", False))}


@api.get("/admin/transactions")
async def admin_transactions(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    limit: int = 200,
    type: Optional[str] = None,
    status_: Optional[str] = None,
):
    q: Dict[str, Any] = {}
    if type:
        q["type"] = type
    if status_:
        q["status"] = status_
    items = await db.transactions.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"transactions": items}


@api.patch("/admin/transactions/{tx_id}")
async def admin_patch_tx(
    tx_id: str,
    payload: AdminTxnPatch,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    upd: Dict[str, Any] = {}
    if payload.status is not None:
        upd["status"] = payload.status
    if payload.note is not None:
        upd["admin_note"] = payload.note
    if upd:
        r = await db.transactions.update_one({"id": tx_id}, {"$set": upd})
        if r.matched_count == 0:
            raise HTTPException(status_code=404, detail="Transaction not found")
    await db.admin_audit.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": current_admin["id"],
        "target_tx_id": tx_id,
        "patch": payload.model_dump(),
        "created_at": now_utc().isoformat(),
    })
    tx = await db.transactions.find_one({"id": tx_id}, {"_id": 0})
    return {"transaction": tx}


@api.get("/admin/audit")
async def admin_audit(
    current_admin: Dict[str, Any] = Depends(get_current_admin),
    limit: int = 100,
):
    items = await db.admin_audit.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return {"audit": items}


# ---------------------------- Routes: Admin — AI controls (Build #13) ----------------------------
@api.get("/admin/ai/agents")
async def admin_ai_agents(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """Return today's stored AI agent snapshot for operator editing."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snap = await db.ai_snapshots.find_one({"date": today}, {"_id": 0})
    if not snap:
        agents = await ai_mod.snapshot_agents(btc_usd=get_btc_usd_rate())
        snap = {"date": today, "agents": agents, "created_at": now_utc().isoformat()}
        try:
            await db.ai_snapshots.update_one({"date": today}, {"$set": snap}, upsert=True)
        except Exception:
            pass
    return snap


@api.patch("/admin/ai/agents/{agent_id}")
async def admin_patch_ai_agent(
    agent_id: str,
    payload: AdminAIAgentPatch,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """Patch a single agent inside today's snapshot. Used by the operator
    console to nudge daily_pct / win_rate / signal_strength on the fly."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snap = await db.ai_snapshots.find_one({"date": today})
    if not snap:
        raise HTTPException(status_code=404, detail="No AI snapshot for today yet — regenerate first.")

    agents = list(snap.get("agents", []))
    idx = next((i for i, a in enumerate(agents) if a.get("id") == agent_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found in today's snapshot.")

    agent = dict(agents[idx])
    if payload.daily_pct is not None:
        agent["daily_pct"] = float(payload.daily_pct)
    if payload.win_rate is not None:
        agent["win_rate"] = float(payload.win_rate)
    if payload.signal_strength is not None:
        if payload.signal_strength not in ("high", "medium", "low"):
            raise HTTPException(400, "signal_strength must be one of: high, medium, low")
        agent["signal_strength"] = payload.signal_strength
    if payload.strategy is not None:
        agent["strategy"] = payload.strategy.strip() or agent.get("strategy", "")
    if payload.enabled is not None:
        agent["enabled"] = bool(payload.enabled)
    agents[idx] = agent

    await db.ai_snapshots.update_one(
        {"date": today},
        {"$set": {"agents": agents, "last_admin_edit_at": now_utc().isoformat()}},
    )
    await db.admin_audit.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "target_ai_agent_id": agent_id,
        "patch": payload.model_dump(),
        "created_at": now_utc().isoformat(),
    })
    return {"agent": agent}


@api.post("/admin/ai/regenerate")
async def admin_regenerate_ai(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """Force regenerate today's AI agents snapshot (replaces whatever the
    daily cron produced or any admin edits). Useful when an operator wants
    fresh strategies before the next 24h cron tick."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    agents = await ai_mod.snapshot_agents(btc_usd=get_btc_usd_rate())
    snap = {
        "date": today,
        "agents": agents,
        "created_at": now_utc().isoformat(),
        "regenerated_by_admin": current_admin["email"],
    }
    await db.ai_snapshots.update_one({"date": today}, {"$set": snap}, upsert=True)
    await db.admin_audit.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": "ai_regenerate",
        "created_at": now_utc().isoformat(),
    })
    return snap


# ---------------------------- Routes: Admin — Fee reinvest (Build #13) ----------------------------
async def _fees_summary() -> Dict[str, Any]:
    """Aggregate all withdrawal-commission fees ever collected, minus any that
    have already been reinvested (we tag those with type='fee_reinvest')."""
    pipeline_fees = [
        {"$match": {"type": "withdrawal"}},
        {"$group": {"_id": None, "fee_sats": {"$sum": {"$ifNull": ["$fee_sats", 0]}}, "count": {"$sum": 1}}},
    ]
    pipeline_reinv = [
        {"$match": {"type": "fee_reinvest"}},
        {"$group": {"_id": None, "amount_sats": {"$sum": {"$ifNull": ["$amount_sats", 0]}}, "count": {"$sum": 1}}},
    ]
    fees = await db.transactions.aggregate(pipeline_fees).to_list(1)
    reinv = await db.transactions.aggregate(pipeline_reinv).to_list(1)
    fee_sats_total = int((fees[0] if fees else {}).get("fee_sats", 0))
    reinv_sats_total = int((reinv[0] if reinv else {}).get("amount_sats", 0))
    available_sats = max(0, fee_sats_total - reinv_sats_total)
    return {
        "fees_collected_sats": fee_sats_total,
        "fees_collected_btc": round(sats_to_btc(fee_sats_total), 8),
        "fees_collected_usd": round(btc_to_usd(sats_to_btc(fee_sats_total)), 2),
        "fees_reinvested_sats": reinv_sats_total,
        "fees_reinvested_btc": round(sats_to_btc(reinv_sats_total), 8),
        "fees_reinvested_usd": round(btc_to_usd(sats_to_btc(reinv_sats_total)), 2),
        "available_sats": available_sats,
        "available_btc": round(sats_to_btc(available_sats), 8),
        "available_usd": round(btc_to_usd(sats_to_btc(available_sats)), 2),
        "withdrawals_count": int((fees[0] if fees else {}).get("count", 0)),
        "reinvest_count": int((reinv[0] if reinv else {}).get("count", 0)),
    }


@api.get("/admin/fees/summary")
async def admin_fees_summary(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """Operator-only view of total withdrawal commission fees collected and
    how much of that pool has been reinvested vs. is still available."""
    return await _fees_summary()


@api.post("/admin/fees/reinvest")
async def admin_fees_reinvest(
    payload: AdminFeesReinvestRequest,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    """Reinvest the unreinvested commission pool by crediting a target user's
    balance with the available sats. Records a `fee_reinvest` transaction so
    the next call's `_fees_summary` knows the pool is now drained."""
    summary = await _fees_summary()
    available = int(summary["available_sats"])
    if available <= 0:
        raise HTTPException(
            status_code=400,
            detail="No unreinvested fees available. The commission pool is empty.",
        )

    target_id = payload.target_user_id or current_admin["id"]
    target = await db.users.find_one({"id": target_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail=f"Target user {target_id} not found.")

    amount_btc = sats_to_btc(available)
    amount_usd = btc_to_usd(amount_btc)

    # Credit the target's balance.
    await db.users.update_one(
        {"id": target_id},
        {"$inc": {"balance_btc": amount_btc, "lifetime_earnings_btc": amount_btc}},
    )

    # Record a transaction so the summary stays consistent across calls.
    tx_id = str(uuid.uuid4())
    await db.transactions.insert_one({
        "id": tx_id,
        "user_id": target_id,
        "type": "fee_reinvest",
        "amount_sats": available,
        "amount_btc": amount_btc,
        "amount_usd": round(amount_usd, 4),
        "status": "completed",
        "note": (payload.note or "Operator reinvested commission fees").strip()[:280],
        "created_at": now_utc().isoformat(),
        "performed_by_admin": current_admin["id"],
    })
    await db.admin_audit.insert_one({
        "id": str(uuid.uuid4()),
        "admin_id": current_admin["id"],
        "admin_email": current_admin["email"],
        "action": "fees_reinvest",
        "target_user_id": target_id,
        "amount_sats": available,
        "amount_usd": amount_usd,
        "tx_id": tx_id,
        "created_at": now_utc().isoformat(),
    })

    return {
        "ok": True,
        "tx_id": tx_id,
        "target_user_id": target_id,
        "target_user_email": target.get("email"),
        "credited_sats": available,
        "credited_btc": round(amount_btc, 8),
        "credited_usd": round(amount_usd, 2),
        "summary": await _fees_summary(),
    }


# ---------------------------- Store: cross-sell banner (Build #22+) ----------------------------
async def _user_total_hashrate_ghs(user_id: str, user: Optional[Dict[str, Any]] = None) -> float:
    """Sum the user's active hashrate from packs + check-in + ads (live)."""
    if user is None:
        user = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
    now = now_utc()
    total = 0.0
    cursor = db.machines.find({"user_id": user_id, "status": "active"}, {"_id": 0})
    async for m in cursor:
        exp = m.get("expires_at")
        if isinstance(exp, str):
            try:
                exp = datetime.fromisoformat(exp)
            except Exception:
                exp = None
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp and exp < now:
            continue
        total += float(m.get("hashrate_boost_ghs") or m.get("hash_rate") or 0.0)

    # Check-in boost (if still active)
    cexp = user.get("checkin_hashrate_expires_at")
    if isinstance(cexp, str):
        try:
            cexp = datetime.fromisoformat(cexp)
        except Exception:
            cexp = None
    if cexp and cexp.tzinfo is None:
        cexp = cexp.replace(tzinfo=timezone.utc)
    if cexp and cexp > now:
        total += float(user.get("checkin_hashrate_ghs", 0.0))

    # Ads — sum still-active ad views
    cur = db.ad_views.find(
        {"user_id": user_id, "expires_at": {"$gt": now.isoformat()}},
        {"_id": 0, "reward_ghs": 1},
    )
    async for av in cur:
        total += float(av.get("reward_ghs", 0.0))
    return total


@api.get("/store/cross-sell")
async def store_cross_sell(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Dynamic cross-sell banner — mirrors a +100% boost on the user's
    current hashrate, marketed at 25% off.

    Logic:
      1. Compute user's current total active hashrate H (in GH/s).
      2. Find the smallest mining SKU whose hashrate_boost_ghs >= max(H, 50).
         (Floor 50 GH/s so brand-new users get a real banner.)
      3. Skip SKUs the user has already purchased the one-time cross-sell
         escalation for (`cross_sell_consumed_skus`) so the banner steps up.
      4. Marketing display: actual SKU price, plus original_price_usd
         strike-through (~33% higher → 25% off illusion).
      5. If no SKU is bigger → return null (max tier reached).
    """
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0}) or {}
    consumed = set(user.get("cross_sell_consumed_skus") or [])
    H = await _user_total_hashrate_ghs(current_user["id"], user)
    target_ghs = max(H * 2.0, 50.0)

    candidates = [
        p for p in SHOP_PACKAGES
        if p.get("hashrate_boost_ghs", 0) > 0 and p["id"] not in consumed
    ]
    candidates.sort(key=lambda p: p["hashrate_boost_ghs"])
    pick = None
    for p in candidates:
        if p["hashrate_boost_ghs"] >= target_ghs:
            pick = p
            break
    if not pick:
        pick = candidates[-1] if candidates else None

    if not pick:
        return {
            "available": False,
            "reason": "max_tier_reached",
            "user_hashrate_ghs": H,
        }

    return {
        "available": True,
        "user_hashrate_ghs": round(H, 2),
        "package": _enrich_package(pick),
        "headline": "+100%!! More Computing Power",
        "price_label": f"${pick['price_usd']:.2f}!",
        "original_price_label": f"${pick['original_price_usd']:.2f}",
        "discount_pct": CROSS_SELL_DISCOUNT_PCT,
        "cta": "Boost Now",
    }


# ---------------------------- Admin: profitability knobs ----------------------------
@api.get("/admin/config")
async def admin_config_get(current_admin: Dict[str, Any] = Depends(get_current_admin)):
    """Read all profitability knobs. These come from env vars by default
    but can be overridden by writing to admin_config collection."""
    overrides = await db.admin_config.find_one({"id": "global"}, {"_id": 0}) or {}
    return {
        "payout_multiplier": float(overrides.get("payout_multiplier", PAYOUT_MULTIPLIER)),
        "redeem_fee_sats": int(overrides.get("redeem_fee_sats", WITHDRAW_FEE_FLAT_SATS)),
        "redeem_min_sats": int(overrides.get("redeem_min_sats", MIN_WITHDRAW_SATS)),
        "redeem_max_sats": int(overrides.get("redeem_max_sats", MAX_WITHDRAW_SATS)),
        "redeem_cooldown_hours": int(overrides.get("redeem_cooldown_hours", REDEEM_COOLDOWN_HOURS)),
        "ad_daily_cap": int(overrides.get("ad_daily_cap", AD_DAILY_CAP)),
        "cross_sell_discount_pct": int(overrides.get("cross_sell_discount_pct", CROSS_SELL_DISCOUNT_PCT)),
        "checkin_ladder_ghs": list(overrides.get("checkin_ladder_ghs", DAILY_CHECKIN_LADDER_GHS)),
        "ad_reward_ladder_ghs": list(overrides.get("ad_reward_ladder_ghs", AD_REWARD_LADDER_GHS)),
        "support_email": str(overrides.get("support_email", SUPPORT_EMAIL)),
        "_overridden_keys": list(overrides.keys()) if overrides else [],
    }


class AdminConfigPatch(BaseModel):
    payout_multiplier: Optional[float] = None
    redeem_fee_sats: Optional[int] = None
    redeem_min_sats: Optional[int] = None
    redeem_max_sats: Optional[int] = None
    redeem_cooldown_hours: Optional[int] = None
    ad_daily_cap: Optional[int] = None
    cross_sell_discount_pct: Optional[int] = None
    support_email: Optional[str] = None


@api.patch("/admin/config")
async def admin_config_patch(
    payload: AdminConfigPatch,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    upd: Dict[str, Any] = {k: v for k, v in payload.model_dump().items() if v is not None}
    if upd:
        await db.admin_config.update_one(
            {"id": "global"}, {"$set": {"id": "global", **upd}}, upsert=True
        )
        await db.admin_audit.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": current_admin["id"],
            "admin_email": current_admin["email"],
            "action": "config.patch",
            "patch": upd,
            "created_at": now_utc().isoformat(),
        })
        # Apply mutable env-style knobs in-process where safe
        for k, v in upd.items():
            if k == "payout_multiplier":
                os.environ["PAYOUT_MULTIPLIER"] = str(v)
    return await admin_config_get(current_admin=current_admin)


# ---------------------------- FAQs (Build #22+) ----------------------------
SEEDED_FAQS: List[Dict[str, Any]] = [
    {"id": "faq_what_is_hashrate", "q": "What is hashrate in this app?",
     "a": "Hashrate is virtual computing power expressed in GH/s (gigahash per second). Higher hashrate produces higher indicative earnings. You earn hashrate from daily check-ins, rewarded ads, and one-time hashrate boost purchases."},
    {"id": "faq_daily_checkin", "q": "How does the daily check-in work?",
     "a": "Tap Claim each day to receive a hashrate boost that grows across 7 days: Day 1 = 1.2 GH/s, all the way up to Day 7 = 8.0 GH/s. Each boost lasts 24 hours. Miss a day and your streak resets to Day 1."},
    {"id": "faq_rewarded_ads", "q": "How do rewarded ads work?",
     "a": "Watch short rewarded video ads to earn hashrate boosts. The reward scales as you watch more: 1.5 GH/s for the first few, up to 12.0 GH/s for later ones. You can watch up to 30 ads per day. Each ad's boost lasts 24 hours."},
    {"id": "faq_indicative_earnings", "q": "What are 'indicative earnings'?",
     "a": "Your indicative earnings are an estimate based on your virtual hashrate's share of the live Bitcoin network. Hashrate Cloud Miner does NOT hold or manage your assets and is not a wallet, trading platform, or fund manager. Earnings shown are illustrative and final amounts depend on server records."},
    {"id": "faq_how_to_redeem", "q": "How do I redeem my earnings?",
     "a": "Open the Earnings tab → tap Redeem → select Lightning → paste your Lightning invoice or address (e.g. user@speed.app, user@zbd.gg, or a BOLT11 invoice starting with 'lnbc') → enter amount → confirm. Payouts are processed instantly through the Lightning Network."},
    {"id": "faq_redeem_minimum", "q": "What is the minimum redeem amount?",
     "a": "The minimum redeem is 25,000 sats and the maximum is 50,000 sats per request. You can redeem once every 24 hours."},
    {"id": "faq_redeem_fees", "q": "Are there fees on redemption?",
     "a": "A small Lightning Network fee is deducted from your balance at redeem time to cover routing costs. You will see the exact fee, total deduction, and your remaining balance in the confirmation modal before you tap Redeem."},
    {"id": "faq_24h_cooldown", "q": "Why is there a 24-hour cooldown on redeeming?",
     "a": "To keep the Lightning Network healthy and prevent abuse, each user can submit one redeem request per 24 hours. The cooldown starts the moment your redeem is broadcast."},
    {"id": "faq_iap_bonus", "q": "What is the one-time hashrate boost bonus?",
     "a": "Every mining plan grants a one-time free hashrate bonus on your FIRST purchase of that plan: starting at +15% on the entry tier and going up to +50% on the flagship Colossus Rig. The bonus stacks with the plan's base hashrate."},
    {"id": "faq_cross_sell", "q": "What is the +100% More Computing Power banner?",
     "a": "It's a dynamic offer that mirrors your current hashrate at a 25% discount. Tap it to double your active hashrate. Each time you purchase the banner offer, the next-tier-up SKU appears at the same 25% discount."},
    {"id": "faq_safety", "q": "Is my account safe?",
     "a": "Yes. We don't hold your private keys, your seed phrase, or any on-chain assets. You provide your own Lightning wallet address at redeem time, so funds always flow directly to a wallet you control."},
    {"id": "faq_login_issues", "q": "I can't sign in. What do I do?",
     "a": "Double-check your email and password. If you're stuck, send a message to support from this chat and the team will help you. Premium users (any active mining plan) get priority response."},
    {"id": "faq_appstore_iap", "q": "How do in-app purchases work?",
     "a": "Mining plans are billed by Apple via standard In-App Purchase. You'll see the Apple confirmation sheet with Face ID / Touch ID. Apple handles refunds and disputes via reportaproblem.apple.com."},
    {"id": "faq_lightning_addresses", "q": "What Lightning addresses are supported?",
     "a": "We accept BOLT11 invoices (starting with 'lnbc') AND Lightning addresses (e.g. user@speed.app, user@zbd.gg, user@walletofsatoshi.com). For BOLT11 invoices, make sure the amount you encode is 0 sats so the redeem amount you enter is honored."},
    {"id": "faq_ad_free_upgrade", "q": "What does the Ad-Free upgrade do?",
     "a": "The Ad-Free + Priority Support upgrade removes interstitial banner ads and routes your support requests to a faster queue. Rewarded video ads (which give you hashrate) remain available — they're opt-in only."},
    {"id": "faq_payout_multiplier", "q": "What controls how much I earn per GH/s?",
     "a": "Earnings are computed live: your hashrate share of the Bitcoin network multiplied by the daily block reward (~450 BTC/day), then scaled by an operator-controlled multiplier. The multiplier is conservative by design so the app remains sustainable."},
    {"id": "faq_premium_support", "q": "How do I get priority support?",
     "a": "Premium users (anyone with an active paid mining plan) automatically get priority support — your messages are tagged for the admin's attention and SLA is 48 hours. Free users get instant AI-powered chat responses; admins also monitor that queue."},
    {"id": "faq_account_delete", "q": "How do I delete my account?",
     "a": "Email support@hashratecloudminer.com from the address you registered with and we'll permanently delete your account and any associated data within 14 days, in line with Apple's App Store Review guidelines and applicable data protection laws."},
]


@api.get("/faqs")
async def faqs_get():
    """Public FAQ list — used by the in-app Support chat for free users."""
    rows = await db.faqs.find({"enabled": {"$ne": False}}, {"_id": 0}).sort("order", 1).to_list(100)
    if not rows:
        # Lazy seed on first call
        for i, faq in enumerate(SEEDED_FAQS):
            await db.faqs.update_one(
                {"id": faq["id"]},
                {"$set": {**faq, "order": i, "enabled": True}},
                upsert=True,
            )
        rows = await db.faqs.find({"enabled": True}, {"_id": 0}).sort("order", 1).to_list(100)
    return {"faqs": rows}


class FAQPatch(BaseModel):
    q: Optional[str] = None
    a: Optional[str] = None
    order: Optional[int] = None
    enabled: Optional[bool] = None


@api.patch("/admin/faqs/{faq_id}")
async def admin_faq_patch(
    faq_id: str,
    payload: FAQPatch,
    current_admin: Dict[str, Any] = Depends(get_current_admin),
):
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if upd:
        await db.faqs.update_one({"id": faq_id}, {"$set": upd})
        await db.admin_audit.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": current_admin["id"],
            "admin_email": current_admin["email"],
            "action": f"faq.patch:{faq_id}",
            "patch": upd,
            "created_at": now_utc().isoformat(),
        })
    return await db.faqs.find_one({"id": faq_id}, {"_id": 0})


# ---------------------------- Support: AI helper for free users ----------------------------
@api.post("/support/ai-reply")
async def support_ai_reply(
    payload: SupportSendRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate an AI reply to the user's last message + return suggested
    FAQs. Premium users (active paid plan or ad_free) ALSO get their message
    routed to the admin support thread."""
    user_id = current_user["id"]
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Detect "premium" — active paid SKU machine OR ad_free entitlement
    is_premium = bool(current_user.get("ad_free"))
    if not is_premium:
        active = await db.machines.count_documents({
            "user_id": user_id,
            "status": "active",
            "package_id": {"$nin": ["welcome_gift", "free_forever"]},
        })
        is_premium = active > 0

    # Persist the user message into the thread (admin sees it)
    thread = await _support_get_or_create_thread(user_id, current_user["email"])
    now_iso = now_utc().isoformat()
    user_msg = {
        "id": str(uuid.uuid4()),
        "thread_id": thread["id"],
        "user_id": user_id,
        "sender": "user",
        "sender_email": current_user["email"],
        "body": body[:2000],
        "created_at": now_iso,
        "read_at": None,
        "is_premium": is_premium,
    }
    await db.support_messages.insert_one(user_msg.copy())
    await db.support_threads.update_one(
        {"id": thread["id"]},
        {
            "$set": {
                "last_message_at": now_iso,
                "last_message_preview": body[:140],
                "last_message_from": "user",
                "status": "open",
                "is_premium": is_premium,
            },
            "$inc": {"unread_admin_count": 1},
        },
    )

    # Pull FAQs for context
    faqs = await db.faqs.find({"enabled": {"$ne": False}}, {"_id": 0}).sort("order", 1).to_list(50)
    faq_corpus = "\n\n".join(f"Q: {f['q']}\nA: {f['a']}" for f in faqs)

    # AI reply
    ai_text = None
    try:
        from integrations import ai as ai_mod
        sys_msg = (
            "You are the support assistant for Hashrate Cloud Miner — a Bitcoin "
            "cloud-mining app with virtual hashrate, daily check-ins, rewarded "
            "ads, in-app purchases, and Lightning Network redeems. You ONLY "
            "answer questions using the Knowledge Base below. If a question is "
            "off-topic or you don't know, say: \"I'm not sure — I'll route this "
            "to our human support team.\" Keep replies under 90 words. "
            f"Knowledge Base:\n{faq_corpus[:3500]}"
        )
        ai_text = await ai_mod._chat(
            prompt=body,
            system=sys_msg,
            session_id=f"support-{user_id}",
            timeout_s=12.0,
        )
    except Exception as e:
        logger.warning("support ai-reply failed: %s", e)

    if not ai_text:
        ai_text = (
            "Thanks for your message! Our team will reply within 48 hours. "
            "In the meantime, check the FAQ list below — it covers the most "
            "common questions about hashrate, redemption, and bonuses."
        )

    # Save AI reply as an 'admin' sender message tagged ai=true so the
    # user's chat history reads cleanly even when admin hasn't replied yet.
    ai_msg = {
        "id": str(uuid.uuid4()),
        "thread_id": thread["id"],
        "user_id": user_id,
        "sender": "admin",
        "sender_email": "ai@hashratecloudminer.app",
        "body": ai_text[:2000],
        "created_at": now_utc().isoformat(),
        "read_at": now_utc().isoformat(),
        "ai_generated": True,
    }
    await db.support_messages.insert_one(ai_msg.copy())
    await db.support_threads.update_one(
        {"id": thread["id"]},
        {"$set": {
            "last_message_at": ai_msg["created_at"],
            "last_message_preview": ai_text[:140],
            "last_message_from": "ai",
        }},
    )

    # Top-3 matched FAQ suggestions (naive keyword match)
    tokens = [t for t in body.lower().split() if len(t) > 3][:8]
    scored = []
    for f in faqs:
        text = (f["q"] + " " + f["a"]).lower()
        score = sum(1 for t in tokens if t in text)
        if score > 0:
            scored.append((score, f))
    scored.sort(key=lambda x: -x[0])
    suggested = [f for (_, f) in scored[:3]]

    return {
        "ok": True,
        "is_premium": is_premium,
        "ai_reply": ai_text,
        "suggested_faqs": suggested,
        "message_id": ai_msg["id"],
    }


# ---------------------------- Health ----------------------------
@api.get("/")
async def root():
    return {"app": "Hashrate Cloud Miner", "status": "ok"}


# Include router
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    # Ensure indexes
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("referral_code", unique=True)
        await db.machines.create_index([("user_id", 1), ("status", 1)])
        await db.transactions.create_index([("user_id", 1), ("created_at", -1)])
        await db.ad_views.create_index([("user_id", 1), ("day_bucket", 1)])
        await db.ad_views.create_index("transaction_id", unique=True)
        await db.faqs.create_index("id", unique=True)
    except Exception as e:
        logger.warning("Index creation issue: %s", e)

    # ----------------------------------------------------------------
    # ONE-TIME DATA WIPE MIGRATION (Build #22 AdMob pivot)
    # Drop incompatible legacy data so the new hashrate/AdMob model can
    # operate on a clean slate. Preserves auth (users.email + password).
    # Idempotent via _meta.schema_version.
    # ----------------------------------------------------------------
    try:
        target_version = os.environ.get("SCHEMA_VERSION", "v22_admob_pivot")
        meta_col = db["schema_meta"]
        meta = await meta_col.find_one({"id": "schema"}, {"_id": 0}) or {}
        if meta.get("version") != target_version:
            logger.warning("schema migration: wiping legacy collections (target=%s, current=%s)",
                           target_version, meta.get("version"))
            # Wipe machines + transactions + ad_views (legacy "date" shape)
            await db.machines.delete_many({})
            await db.transactions.delete_many({})
            await db.ad_views.delete_many({})
            # Reset legacy fields on every user, keep auth + admin flag
            await db.users.update_many({}, {"$set": {
                "balance_btc": 0.0,
                "lifetime_earnings_btc": 0.0,
                "last_accrual_at": now_utc().isoformat(),
                "last_checkin_at": None,
                "last_checkin_day_bucket": None,
                "checkin_streak": 0,
                "checkin_hashrate_ghs": 0.0,
                "checkin_hashrate_expires_at": None,
                "ad_hashrate_ghs": 0.0,
                "ad_hashrate_expires_at": None,
                "purchased_sku_bonuses": [],
                "cross_sell_consumed_skus": [],
                "free_forever_last_activated_at": None,
            }})
            await meta_col.update_one(
                {"id": "schema"},
                {"$set": {"id": "schema", "version": target_version,
                          "migrated_at": now_utc().isoformat()}},
                upsert=True,
            )
            logger.warning("schema migration: complete (v22_admob_pivot)")
    except Exception:
        logger.exception("schema migration failed (continuing)")

    # Seed the admin account (idempotent).
    await _ensure_admin_user()

    # Seed FAQs
    try:
        for i, faq in enumerate(SEEDED_FAQS):
            await db.faqs.update_one(
                {"id": faq["id"]},
                {"$setOnInsert": {**faq, "order": i, "enabled": True}},
                upsert=True,
            )
    except Exception:
        logger.exception("FAQ seed failed")

    # Kick off the live BTC/USD rate refresher (every 5 min, with fallback).
    try:
        await btc_rate_mod.refresh_btc_usd_rate()
        btc_rate_mod.start_periodic_refresh(interval_s=300.0)
    except Exception:
        logger.exception("btc_rate startup failed (using cached default)")

    # Kick off the live Bitcoin network-stats refresher (every 10 min).
    try:
        from integrations import network as network_mod
        await network_mod.refresh()
        network_mod.start_periodic_refresh(interval_s=600.0)
    except Exception:
        logger.exception("network startup failed (using defaults)")

    # Kick off background AI / automation jobs.
    try:
        start_jobs(
            accrue_all_users=_job_accrue_all_users,
            auto_checkin=_job_auto_checkin,
            auto_reinvest=_job_auto_reinvest,
            refresh_agents=_job_refresh_agents,
            auto_ship=auto_ship_tick,
        )
    except Exception:
        logger.exception("Failed to start background scheduler")


@app.on_event("shutdown")
async def shutdown():
    try:
        btc_rate_mod.stop_periodic_refresh()
    except Exception:
        pass
    try:
        stop_jobs()
    except Exception:
        pass
    client.close()


# ---------------------------- Admin seed ----------------------------
async def _ensure_admin_user() -> None:
    if not ADMIN_EMAIL or not ADMIN_INITIAL_PASSWORD:
        return
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    now = now_utc()
    if existing:
        # Make sure flag is set and the seeded password works (idempotent reset
        # so the operator can always log in after redeploying).
        updates: Dict[str, Any] = {}
        if not existing.get("is_admin"):
            updates["is_admin"] = True
        if not verify_password(ADMIN_INITIAL_PASSWORD, existing.get("password_hash", "")):
            updates["password_hash"] = hash_password(ADMIN_INITIAL_PASSWORD)
        if updates:
            await db.users.update_one({"id": existing["id"]}, {"$set": updates})
            logger.info("Admin account synced for %s (%s)", ADMIN_EMAIL, list(updates.keys()))
        return

    user_id = str(uuid.uuid4())
    doc = {
        "id": user_id,
        "email": ADMIN_EMAIL,
        "password_hash": hash_password(ADMIN_INITIAL_PASSWORD),
        "referral_code": gen_referral_code(),
        "referred_by": None,
        "balance_btc": 0.0,
        "lifetime_earnings_btc": 0.0,
        "last_accrual_at": now.isoformat(),
        "last_checkin_at": None,
        "checkin_streak": 0,
        "is_admin": True,
        "is_banned": False,
        "auto_checkin": True,
        "auto_reinvest": False,
        "auto_reinvest_min_balance_usd": 4.99,
        "created_at": now.isoformat(),
    }
    try:
        await db.users.insert_one(doc)
        logger.info("Seeded admin user %s", ADMIN_EMAIL)
    except Exception as e:
        logger.warning("Admin seed failed: %s", e)


# ---------------------------- Scheduled jobs ----------------------------
async def _job_accrue_all_users():
    cursor = db.users.find({}, {"_id": 0, "id": 1})
    async for u in cursor:
        try:
            await accrue_earnings(u["id"])
        except Exception:
            logger.exception("accrue failed for %s", u.get("id"))


async def _job_auto_checkin():
    """Build #22+ no-op — the daily-checkin ladder is intentionally manual
    so users come back to tap. Auto-checkin would short-circuit the streak
    UX. Kept as a stub for the scheduler factory."""
    return


async def _job_auto_reinvest():
    cursor = db.users.find({"auto_reinvest": True}, {"_id": 0})
    async for u in cursor:
        try:
            await accrue_earnings(u["id"])
            user = await db.users.find_one({"id": u["id"]}, {"_id": 0})
            min_usd = float(user.get("auto_reinvest_min_balance_usd", 4.99))
            balance_usd = btc_to_usd(float(user.get("balance_btc", 0.0)))
            if balance_usd < min_usd:
                continue
            # Pick the most expensive mining package that the user can afford.
            target = None
            for p in sorted(SHOP_PACKAGES, key=lambda x: -x["price_usd"]):
                if p.get("entitlement"):
                    continue  # skip ad-free upgrade
                if p["price_usd"] <= balance_usd:
                    target = p
                    break
            if not target:
                continue
            cost_btc = usd_to_btc(target["price_usd"])
            now = now_utc()
            duration_h = target.get("duration_hours", 720)
            boost_ghs = target.get("hashrate_boost_ghs", 0)
            machine = {
                "id": str(uuid.uuid4()),
                "user_id": u["id"],
                "package_id": target["id"],
                "name": target["name"],
                "hashrate_boost_ghs": boost_ghs,
                "hash_rate": boost_ghs,
                "duration_hours": duration_h,
                "purchased_at": now.isoformat(),
                "expires_at": (now + timedelta(hours=duration_h)).isoformat(),
                "status": "active",
                "auto_purchased": True,
            }
            await db.machines.insert_one(machine)
            await db.users.update_one(
                {"id": u["id"]}, {"$inc": {"balance_btc": -cost_btc}}
            )
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": u["id"],
                "type": "reinvest",
                "package_id": target["id"],
                "amount_usd": target["price_usd"],
                "amount_btc": cost_btc,
                "status": "completed",
                "description": f"Auto-reinvest into {target['name']}",
                "created_at": now.isoformat(),
            })
        except Exception:
            logger.exception("auto reinvest failed for %s", u.get("id"))


async def _job_refresh_agents():
    # Persist today's snapshot so admin analytics can read it consistently.
    agents = await ai_mod.snapshot_agents(btc_usd=get_btc_usd_rate())
    snap = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "agents": agents,
        "created_at": now_utc().isoformat(),
    }
    try:
        await db.ai_snapshots.update_one(
            {"date": snap["date"]}, {"$set": snap}, upsert=True
        )
    except Exception:
        logger.exception("agent snapshot persist failed")
