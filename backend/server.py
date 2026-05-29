from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
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

# Withdrawal limits are denominated in SATS (Lightning-only flow).
# Updated June-2025: minimum 0.00150000 BTC, no maximum, flat 10% fee.
MIN_WITHDRAW_SATS = 150_000     # 0.00150000 BTC
MAX_WITHDRAW_SATS = 10_000_000  # 0.10000000 BTC (safety ceiling — UI shows "no max")
WITHDRAW_FEE_PCT = 0.10         # flat 10% routing/processing fee
WITHDRAW_FEE_FLAT_SATS = 0      # no baseline; the 10% covers network costs
MAX_DAILY_WITHDRAW_SATS = 10_000_000  # effectively no daily cap

# Predefined shop packages. Names, taglines, and pricing are original to this
# app; the tier ladder is a common cloud-mining structure (small starter, BOGO
# welcome promo, mid-tier flagship, high-tier farms).
#
# IMPORTANT: every id in this list MUST exist as an inAppPurchaseV2 product
# in App Store Connect (verified via the WFQJ6L9KXS API key in
# /app/store/asc_metadata_upload.py). The legacy "starter_099" tier was
# removed in Build #18 because Apple had no record of it and StoreKit was
# returning E_PRODUCT_NOT_AVAILABLE on every tap. The Welcome Miner BOGO
# at $1.99 is now the lowest-priced entry point.
SHOP_PACKAGES = [
    {
        "id": "welcome_199",
        "name": "Welcome Miner",
        "tagline": "Buy One Get One Free",
        "price_usd": 1.99,
        "hash_rate": 12.0,
        "duration_days": 14,
        "daily_yield_usd": 0.32,
        "badge": "BOGO",
        "bogo": True,
        "ai_optimized": False,
        "profitability_score": 4.1,
    },
    {
        "id": "rookie_299",
        "name": "Rookie Rig",
        "tagline": "Steady passive yield",
        "price_usd": 2.99,
        "hash_rate": 18.0,
        "duration_days": 30,
        "daily_yield_usd": 0.18,
        "badge": None,
        "bogo": False,
        "ai_optimized": False,
        "profitability_score": 3.2,
    },
    {
        "id": "pro_499",
        "name": "Pro Rig",
        "tagline": "Most popular",
        "price_usd": 4.99,
        "hash_rate": 30.0,
        "duration_days": 30,
        "daily_yield_usd": 0.30,
        "badge": "POPULAR",
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.4,
    },
    {
        "id": "elite_999",
        "name": "Elite Cluster",
        "tagline": "Higher hashpower",
        "price_usd": 9.99,
        "hash_rate": 65.0,
        "duration_days": 30,
        "daily_yield_usd": 0.60,
        "badge": None,
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.2,
    },
    {
        "id": "ultra_1999",
        "name": "Ultra Cluster",
        "tagline": "Power user",
        "price_usd": 19.99,
        "hash_rate": 140.0,
        "duration_days": 60,
        "daily_yield_usd": 1.20,
        "badge": None,
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.5,
    },
    {
        "id": "mega_4999",
        "name": "Mega Farm",
        "tagline": "Pro tier farm",
        "price_usd": 49.99,
        "hash_rate": 380.0,
        "duration_days": 90,
        "daily_yield_usd": 2.80,
        "badge": "PRO",
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.7,
    },
    {
        "id": "giga_9999",
        "name": "Giga Farm",
        "tagline": "Industrial scale",
        "price_usd": 99.99,
        "hash_rate": 800.0,
        "duration_days": 120,
        "daily_yield_usd": 5.50,
        "badge": None,
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.6,
    },
    {
        "id": "titan_14999",
        "name": "Titan Farm",
        "tagline": "Premium yield",
        "price_usd": 149.99,
        "hash_rate": 1300.0,
        "duration_days": 180,
        "daily_yield_usd": 8.00,
        "badge": None,
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.8,
    },
    {
        "id": "colossus_19999",
        "name": "Colossus Farm",
        "tagline": "Maximum hashpower",
        "price_usd": 199.99,
        "hash_rate": 1900.0,
        "duration_days": 365,
        "daily_yield_usd": 6.50,
        "badge": "FLAGSHIP",
        "bogo": False,
        "ai_optimized": True,
        "profitability_score": 4.9,
    },
    # ------------------------------------------------------------------
    # One-time entitlement: removes interstitial ads + unlocks priority
    # support. Tracked on the User document as `ad_free=True` instead of
    # creating a machine.
    # ------------------------------------------------------------------
    {
        "id": "adfree_399",
        "name": "Ad-Free + Priority Support",
        "tagline": "One-time unlock · no ads, faster support",
        "price_usd": 3.99,
        "hash_rate": 0.0,
        "duration_days": 0,
        "daily_yield_usd": 0.0,
        "badge": "UPGRADE",
        "bogo": False,
        "ai_optimized": False,
        "profitability_score": 0.0,
        "entitlement": "ad_free",   # marker — backend handles this specially
    },
]


def _enrich_package(p: Dict[str, Any]) -> Dict[str, Any]:
    """Add AI-style projection fields used by the Mine tab UI."""
    total_return = p["daily_yield_usd"] * p["duration_days"]
    roi_pct = ((total_return - p["price_usd"]) / p["price_usd"]) * 100.0
    break_even_days = (
        p["price_usd"] / p["daily_yield_usd"] if p["daily_yield_usd"] > 0 else 9999.0
    )
    return {
        **p,
        "total_return_usd": round(total_return, 2),
        "roi_pct": round(roi_pct, 1),
        "break_even_days": round(break_even_days, 1),
        "profitable": total_return > p["price_usd"],
    }


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
    """Compute mining earnings since last accrual and credit balance."""
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

    # Get active machines
    machines = await db.machines.find(
        {"user_id": user_id, "status": "active"}, {"_id": 0}
    ).to_list(500)

    accrued_usd = 0.0
    active_machines = []
    for m in machines:
        expires_at = m.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        # If expired, mark expired
        if expires_at and expires_at < now:
            await db.machines.update_one(
                {"id": m["id"]}, {"$set": {"status": "expired"}}
            )
            # Earn only until expiration
            machine_end = expires_at
        else:
            machine_end = now
            active_machines.append(m)

        machine_elapsed = max(0.0, (machine_end - last).total_seconds())
        if machine_elapsed <= 0:
            continue
        per_second = m["daily_yield_usd"] / 86400.0
        accrued_usd += per_second * machine_elapsed

    accrued_btc = usd_to_btc(accrued_usd)

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

    if accrued_usd > 0.0001:
        # Aggregate daily mining payout transaction (one per accrual call)
        await db.transactions.insert_one(
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "type": "mining",
                "amount_usd": accrued_usd,
                "amount_btc": accrued_btc,
                "status": "completed",
                "description": "Cloud mining earnings",
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

    # Welcome miner — gives free trial mining for 24h
    welcome_machine = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "package_id": "welcome_gift",
        "name": "Welcome Miner (Free Trial)",
        "hash_rate": 3.0,
        "daily_yield_usd": 0.10,
        "duration_days": 1,
        "purchased_at": now.isoformat(),
        "expires_at": (now + timedelta(days=1)).isoformat(),
        "status": "active",
    }

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
        "checkin_streak": 0,
        "created_at": now.isoformat(),
    }

    await db.users.insert_one(user_doc)
    await db.machines.insert_one(welcome_machine)

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

    def _make_machine(suffix: str = "") -> Dict[str, Any]:
        return {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "package_id": pkg["id"],
            "name": pkg["name"] + suffix,
            "hash_rate": pkg["hash_rate"],
            "daily_yield_usd": pkg["daily_yield_usd"],
            "duration_days": pkg["duration_days"],
            "purchased_at": now.isoformat(),
            "expires_at": (now + timedelta(days=pkg["duration_days"])).isoformat(),
            "status": "active",
        }

    machines_added = [_make_machine()]
    if pkg.get("bogo"):
        machines_added.append(_make_machine(" (Bonus)"))

    await db.machines.insert_many(machines_added)

    await db.transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "type": "purchase",
            "amount_usd": pkg["price_usd"],
            "amount_btc": 0.0,
            "status": "completed",
            "description": f"Purchased {pkg['name']}" + (" (BOGO)" if pkg.get("bogo") else ""),
            "apple_transaction_id": payload.apple_transaction_id,
            "apple_environment": apple_info.get("environment"),
            "apple_mocked": bool(apple_info.get("_mocked")),
            "created_at": now.isoformat(),
        }
    )

    return {
        "success": True,
        "machines_added": len(machines_added),
        "package": pkg,
        "apple": {
            "verified": not apple_info.get("_mocked", True),
            "environment": apple_info.get("environment"),
        },
    }


# ---------------------------- Routes: Withdraw ----------------------------
@api.get("/withdraw/methods")
async def withdraw_methods(current_user: Dict[str, Any] = Depends(get_current_user)):
    # Operator privilege — admins withdraw any amount at any time at 0% fee.
    # Build #14 ask: keep regular users on the 150k sats / 10% rules but
    # allow the operator account to drain commission balances freely.
    if current_user.get("is_admin"):
        return {
            "methods": WITHDRAW_METHODS,
            "min_sats": 1,                 # 1 sat — effectively unrestricted
            "max_sats": MAX_WITHDRAW_SATS,
            "max_daily_sats": MAX_DAILY_WITHDRAW_SATS,
            "fee_pct": 0.0,
            "fee_flat_sats": 0,
            "btc_usd_rate": get_btc_usd_rate(),
            "admin_unlimited": True,
        }
    return {
        "methods": WITHDRAW_METHODS,
        "min_sats": MIN_WITHDRAW_SATS,
        "max_sats": MAX_WITHDRAW_SATS,
        "max_daily_sats": MAX_DAILY_WITHDRAW_SATS,
        "fee_pct": WITHDRAW_FEE_PCT,
        "fee_flat_sats": WITHDRAW_FEE_FLAT_SATS,
        "btc_usd_rate": get_btc_usd_rate(),
        "admin_unlimited": False,
    }


@api.post("/withdraw")
async def withdraw(
    payload: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    method = next((m for m in WITHDRAW_METHODS if m["id"] == payload.method_id), None)
    if not method:
        raise HTTPException(status_code=400, detail="Lightning is the only supported withdrawal method")

    # Build #14 — admins bypass the 150k sats minimum AND the 10% fee.
    # Regular users still hit MIN_WITHDRAW_SATS + 10% fee unchanged.
    is_admin_caller = bool(current_user.get("is_admin"))

    amount_sats = int(payload.amount_sats)
    if amount_sats < 1:
        raise HTTPException(status_code=400, detail="Amount must be at least 1 sat.")
    if not is_admin_caller and amount_sats < MIN_WITHDRAW_SATS:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum withdrawal is {MIN_WITHDRAW_SATS:,} sats ({MIN_WITHDRAW_SATS / SATS_PER_BTC:.8f} BTC)",
        )
    if amount_sats > MAX_WITHDRAW_SATS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum withdrawal is {MAX_WITHDRAW_SATS:,} sats ({MAX_WITHDRAW_SATS / SATS_PER_BTC:.8f} BTC)",
        )

    fee_sats = 0 if is_admin_caller else withdrawal_fee_sats(amount_sats)
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
                f"Insufficient balance. Need {total_debit_sats} sats "
                f"({amount_sats} sats + {fee_sats} sats fee), have "
                f"{btc_to_sats(balance_btc)} sats."
            ),
        )

    # 24h withdraw cap (counts paid amount, fees excluded so a user can always pay fees).
    yesterday = (now_utc() - timedelta(hours=24)).isoformat()
    cursor = db.transactions.find(
        {
            "user_id": current_user["id"],
            "type": "withdrawal",
            "status": {"$in": ["completed", "pending", "in_progress"]},
            "created_at": {"$gte": yesterday},
        },
        {"_id": 0, "amount_sats": 1},
    )
    spent_sats = 0
    async for t in cursor:
        spent_sats += int(t.get("amount_sats") or 0)
    if spent_sats + amount_sats > MAX_DAILY_WITHDRAW_SATS:
        remaining = max(0, MAX_DAILY_WITHDRAW_SATS - spent_sats)
        raise HTTPException(
            status_code=400,
            detail=(
                f"24h withdrawal cap is {MAX_DAILY_WITHDRAW_SATS} sats. "
                f"Remaining: {remaining} sats."
            ),
        )

    # Reserve the balance (amount + fee) up-front so concurrent withdrawals can't double-spend.
    await db.users.update_one(
        {"id": current_user["id"]}, {"$inc": {"balance_btc": -total_debit_btc}}
    )

    # ------------------------------------------------------------------
    # Blink Wallet payout (real Lightning).
    # If the call fails, we refund the full reserved amount (incl. fee).
    # ------------------------------------------------------------------
    try:
        payout = blink_create_payout(
            amount_usd=round(btc_to_usd(amount_btc), 6),  # informational
            destination=payload.address,
            description="Hashrate Cloud Miner withdrawal",
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
        "description": "Lightning withdrawal",
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


# ---------------------------- Routes: Daily check-in ----------------------------
@api.get("/daily-checkin/status")
async def checkin_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    last = user.get("last_checkin_at")
    last_dt = None
    if last:
        last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    now = now_utc()
    available = (last_dt is None) or ((now - last_dt) >= timedelta(hours=20))
    next_at = last_dt + timedelta(hours=20) if last_dt else now
    return {
        "available": available,
        "streak": int(user.get("checkin_streak", 0)),
        "reward_usd": DAILY_CHECKIN_REWARD_USD,
        "next_available_at": next_at.isoformat() if next_at else None,
    }


@api.post("/daily-checkin", response_model=CheckinResponse)
async def daily_checkin(current_user: Dict[str, Any] = Depends(get_current_user)):
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    last = user.get("last_checkin_at")
    now = now_utc()
    last_dt = None
    if last:
        last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)

    if last_dt and (now - last_dt) < timedelta(hours=20):
        next_at = last_dt + timedelta(hours=20)
        raise HTTPException(
            status_code=400,
            detail=f"Check in again at {next_at.isoformat()}",
        )

    new_streak = int(user.get("checkin_streak", 0)) + 1
    if last_dt and (now - last_dt) > timedelta(hours=48):
        new_streak = 1  # streak broken

    reward_usd = DAILY_CHECKIN_REWARD_USD * (1 + min(new_streak - 1, 6) * 0.2)
    reward_btc = usd_to_btc(reward_usd)

    await db.users.update_one(
        {"id": current_user["id"]},
        {
            "$set": {"last_checkin_at": now.isoformat(), "checkin_streak": new_streak},
            "$inc": {"balance_btc": reward_btc, "lifetime_earnings_btc": reward_btc},
        },
    )

    await db.transactions.insert_one(
        {
            "id": str(uuid.uuid4()),
            "user_id": current_user["id"],
            "type": "bonus",
            "amount_usd": reward_usd,
            "amount_btc": reward_btc,
            "status": "completed",
            "description": f"Daily check-in (streak {new_streak})",
            "created_at": now.isoformat(),
        }
    )

    return CheckinResponse(
        awarded_usd=round(reward_usd, 4),
        streak=new_streak,
        next_available_at=now + timedelta(hours=20),
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
    except Exception as e:
        logger.warning("Index creation issue: %s", e)

    # Seed the admin account (idempotent).
    await _ensure_admin_user()

    # Kick off the live BTC/USD rate refresher (every 5 min, with fallback).
    try:
        await btc_rate_mod.refresh_btc_usd_rate()
        btc_rate_mod.start_periodic_refresh(interval_s=300.0)
    except Exception:
        logger.exception("btc_rate startup failed (using cached default)")

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
    cursor = db.users.find({"auto_checkin": True}, {"_id": 0, "id": 1, "last_checkin_at": 1, "checkin_streak": 1})
    now = now_utc()
    async for u in cursor:
        last = u.get("last_checkin_at")
        last_dt = None
        if last:
            last_dt = datetime.fromisoformat(last) if isinstance(last, str) else last
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
        if last_dt and (now - last_dt) < timedelta(hours=20):
            continue
        try:
            streak = int(u.get("checkin_streak", 0)) + 1
            if last_dt and (now - last_dt) > timedelta(hours=48):
                streak = 1
            reward = DAILY_CHECKIN_REWARD_USD * min(streak, 7)
            await db.users.update_one(
                {"id": u["id"]},
                {
                    "$set": {"last_checkin_at": now.isoformat(), "checkin_streak": streak},
                    "$inc": {"balance_btc": usd_to_btc(reward)},
                },
            )
            await db.transactions.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": u["id"],
                "type": "checkin",
                "amount_usd": reward,
                "amount_btc": usd_to_btc(reward),
                "status": "completed",
                "description": f"Auto daily check-in (streak {streak})",
                "created_at": now.isoformat(),
            })
        except Exception:
            logger.exception("auto checkin failed for %s", u.get("id"))


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
            # Pick the most expensive package that the user can afford.
            target = None
            for p in sorted(SHOP_PACKAGES, key=lambda x: -x["price_usd"]):
                if p["price_usd"] <= balance_usd and p["id"] != "starter_099":
                    target = p
                    break
            if not target:
                continue
            cost_btc = usd_to_btc(target["price_usd"])
            now = now_utc()
            machine = {
                "id": str(uuid.uuid4()),
                "user_id": u["id"],
                "package_id": target["id"],
                "name": target["name"],
                "hash_rate": target["hash_rate"],
                "daily_yield_usd": target["daily_yield_usd"],
                "duration_days": target["duration_days"],
                "purchased_at": now.isoformat(),
                "expires_at": (now + timedelta(days=target["duration_days"])).isoformat(),
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
