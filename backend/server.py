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


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRES_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRES_MINUTES", "10080"))

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

app = FastAPI(title="HashCloud API")
api = APIRouter(prefix="/api")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ---------------------------- Constants ----------------------------
BTC_USD_RATE = 65000.0  # simulated rate (USD per BTC)
DAILY_CHECKIN_REWARD_USD = 0.05  # $0.05 awarded as BTC equivalent
REFERRAL_BONUS_USD = 0.50
MIN_WITHDRAWAL_USD = 1.00
MAX_DAILY_WITHDRAWAL_USD = 2.00

# Predefined shop packages (mirroring MeMiner-style tiers; original content)
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
    },
]

WITHDRAW_METHODS = [
    {"id": "lightning", "name": "Lightning Network", "subtitle": "Instant BTC", "icon": "flash"},
    {"id": "coinbase", "name": "Coinbase", "subtitle": "BTC address", "icon": "wallet"},
    {"id": "zbd", "name": "ZBD", "subtitle": "Lightning gaming wallet", "icon": "game-controller"},
    {"id": "speed", "name": "Speed Wallet", "subtitle": "Lightning invoice", "icon": "speedometer"},
    {"id": "cashapp", "name": "Cash App", "subtitle": "$Cashtag", "icon": "logo-usd"},
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
    method_id: str
    address: str = Field(min_length=2, max_length=256)
    amount_usd: float = Field(gt=0)


class BuyPackageRequest(BaseModel):
    package_id: str
    apple_transaction_id: Optional[str] = None  # iOS App Store transaction id from StoreKit


class CheckinResponse(BaseModel):
    awarded_usd: float
    streak: int
    next_available_at: datetime


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
    return user


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
        "balance_usd": round(btc_to_usd(balance_btc), 2),
        "lifetime_btc": round(lifetime_btc, 8),
        "lifetime_usd": round(btc_to_usd(lifetime_btc), 2),
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
    return {"packages": SHOP_PACKAGES}


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
        "min_usd": MIN_WITHDRAWAL_USD,
        "max_daily_usd": MAX_DAILY_WITHDRAWAL_USD,
    }


@api.post("/withdraw")
async def withdraw(
    payload: WithdrawRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    method = next((m for m in WITHDRAW_METHODS if m["id"] == payload.method_id), None)
    if not method:
        raise HTTPException(status_code=400, detail="Invalid withdrawal method")
    if payload.amount_usd < MIN_WITHDRAWAL_USD:
        raise HTTPException(
            status_code=400, detail=f"Minimum withdrawal is ${MIN_WITHDRAWAL_USD:.2f}"
        )

    await accrue_earnings(current_user["id"])
    user = await db.users.find_one({"id": current_user["id"]}, {"_id": 0})
    balance_usd = btc_to_usd(float(user.get("balance_btc", 0.0)))
    if payload.amount_usd > balance_usd:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 24h withdraw cap
    yesterday = (now_utc() - timedelta(hours=24)).isoformat()
    cursor = db.transactions.find(
        {
            "user_id": current_user["id"],
            "type": "withdrawal",
            "status": {"$in": ["completed", "pending"]},
            "created_at": {"$gte": yesterday},
        },
        {"_id": 0, "amount_usd": 1},
    )
    spent = 0.0
    async for t in cursor:
        spent += float(t.get("amount_usd", 0.0))
    if spent + payload.amount_usd > MAX_DAILY_WITHDRAWAL_USD:
        remaining = max(0.0, MAX_DAILY_WITHDRAWAL_USD - spent)
        raise HTTPException(
            status_code=400,
            detail=f"24h withdrawal limit ${MAX_DAILY_WITHDRAWAL_USD:.2f} reached. Remaining: ${remaining:.2f}",
        )

    amount_btc = usd_to_btc(payload.amount_usd)
    # Reserve the balance first
    await db.users.update_one(
        {"id": current_user["id"]}, {"$inc": {"balance_btc": -amount_btc}}
    )

    # ------------------------------------------------------------------
    # Blink Wallet payout (real Lightning / on-chain BTC).
    # Falls back to a mock `pending` payout if Blink isn't configured.
    # If the live call fails, we refund the user's balance immediately.
    # ------------------------------------------------------------------
    try:
        payout = blink_create_payout(
            amount_usd=payload.amount_usd,
            destination=payload.address,
            description=f"HashCloud withdrawal via {method['name']}",
        )
    except Exception as e:
        # Refund the reserved balance and bubble up an error
        await db.users.update_one(
            {"id": current_user["id"]}, {"$inc": {"balance_btc": amount_btc}}
        )
        logger.exception("Blink payout failed")
        raise HTTPException(status_code=502, detail=f"Payout provider error: {e}")

    tx = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "type": "withdrawal",
        "amount_usd": payload.amount_usd,
        "amount_btc": amount_btc,
        "status": payout.get("status", "pending"),
        "method": method["name"],
        "address": payload.address,
        "description": f"Withdrawal via {method['name']}",
        "blink_provider": payout.get("provider"),
        "blink_payout_id": payout.get("payout_id"),
        "blink_state": payout.get("blink_state"),
        "blink_view_url": payout.get("view_url"),
        "amount_sats": payout.get("amount_sats"),
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
        "share_text": f"Join HashCloud and start cloud mining! Use my code {user.get('referral_code')} for a bonus.",
    }


# ---------------------------- Health ----------------------------
@api.get("/")
async def root():
    return {"app": "HashCloud", "status": "ok"}


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


@app.on_event("shutdown")
async def shutdown():
    client.close()
