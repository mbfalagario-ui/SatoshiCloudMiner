from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
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
from services.scheduler import start_jobs, stop_jobs


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

app = FastAPI(title="Satoshi Cloud Miner API")
api = APIRouter(prefix="/api")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------- Constants ----------------------------
BTC_USD_RATE = 65000.0  # simulated rate (USD per BTC)
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
SHOP_PACKAGES = [
    {
        "id": "starter_099",
        "name": "Starter Boost",
        "tagline": "Try premium mining for less than $1",
        "price_usd": 0.99,
        "hash_rate": 5.0,
        "duration_days": 7,
        "daily_yield_usd": 0.20,
        "badge": "Best for beginners",
        "bogo": False,
        "ai_optimized": False,
        "profitability_score": 3.6,
    },
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
    return usd / BTC_USD_RATE


def btc_to_usd(btc: float) -> float:
    return btc * BTC_USD_RATE


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
        "btc_usd_rate": BTC_USD_RATE,
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
async def withdraw_methods():
    return {
        "methods": WITHDRAW_METHODS,
        "min_sats": MIN_WITHDRAW_SATS,
        "max_sats": MAX_WITHDRAW_SATS,
        "max_daily_sats": MAX_DAILY_WITHDRAW_SATS,
        "fee_pct": WITHDRAW_FEE_PCT,
        "fee_flat_sats": WITHDRAW_FEE_FLAT_SATS,
        "btc_usd_rate": BTC_USD_RATE,
    }


@api.post("/withdraw")
async def withdraw(
    payload: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    method = next((m for m in WITHDRAW_METHODS if m["id"] == payload.method_id), None)
    if not method:
        raise HTTPException(status_code=400, detail="Lightning is the only supported withdrawal method")

    amount_sats = int(payload.amount_sats)
    if amount_sats < MIN_WITHDRAW_SATS:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum withdrawal is {MIN_WITHDRAW_SATS:,} sats ({MIN_WITHDRAW_SATS / SATS_PER_BTC:.8f} BTC)",
        )
    if amount_sats > MAX_WITHDRAW_SATS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum withdrawal is {MAX_WITHDRAW_SATS:,} sats ({MAX_WITHDRAW_SATS / SATS_PER_BTC:.8f} BTC)",
        )

    fee_sats = withdrawal_fee_sats(amount_sats)
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
            description="Satoshi Cloud Miner withdrawal",
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
        "share_text": f"Mine Bitcoin in the cloud — join Satoshi Cloud Miner with my code {user.get('referral_code')} for a bonus.",
    }


# ---------------------------- Routes: AI / Automation ----------------------------
@api.get("/ai/ticker")
async def ai_ticker():
    return await ai_mod.market_commentary()


@api.get("/ai/agents")
async def ai_agents():
    """Today's deterministic AI Trading Agents snapshot."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cached = await db.ai_snapshots.find_one({"date": today}, {"_id": 0})
    if cached and cached.get("agents"):
        return cached
    agents = ai_mod.snapshot_agents()
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
        "btc_usd_rate": BTC_USD_RATE,
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


# ---------------------------- Health ----------------------------
@api.get("/")
async def root():
    return {"app": "Satoshi Cloud Miner", "status": "ok"}


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

    # Kick off background AI / automation jobs.
    try:
        start_jobs(
            accrue_all_users=_job_accrue_all_users,
            auto_checkin=_job_auto_checkin,
            auto_reinvest=_job_auto_reinvest,
            refresh_agents=_job_refresh_agents,
        )
    except Exception:
        logger.exception("Failed to start background scheduler")


@app.on_event("shutdown")
async def shutdown():
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
    snap = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "agents": ai_mod.snapshot_agents(),
        "created_at": now_utc().isoformat(),
    }
    try:
        await db.ai_snapshots.update_one(
            {"date": snap["date"]}, {"$set": snap}, upsert=True
        )
    except Exception:
        logger.exception("agent snapshot persist failed")
