# PRODUCT_SPEC.md — DogeLite Cloud Miner (LTC + DOGE)

> **HOW TO USE THIS FILE**
> Attach this file when you send **PROMPT L01** (Litecoin + Dogecoin variant) from the Foolproof iOS Clone Prompts Playbook. The agent will read every section and treat it as the canonical truth.
> Anywhere you see `<…>` placeholders, the agent will ask you to fill them in **once** at the start.
> If you prefer a different app name from "DogeLite Cloud Miner", change Section 1 only — the rest stays identical.

---

## 0 · TL;DR

A dark-themed, dual-accent iOS app that simulates **Litecoin + Dogecoin** cloud mining. One single app, both coins, with a coin-selector in the wallet UI. Users buy "mining rigs" via Apple In-App Purchase, accrue daily yields in their chosen coin, and withdraw on-chain via the NowPayments REST API. Six AI Trading Agents publish a daily LLM-driven performance report that adapts its commentary to the user's currently-selected coin. One admin console handles operations.

- **Platform**: iOS only (no iPad UI, no Android in v1).
- **Stack**: Expo Router + React Native (TypeScript) + FastAPI + MongoDB.
- **Coins**: Litecoin (LTC) + Dogecoin (DOGE). Single app. Coin selector on Wallet tab.
- **Monetisation**: same 10 IAPs as Satoshi Cloud Miner (USD pricing).
- **Withdrawals**: real on-chain LTC + DOGE payouts via NowPayments REST API.
- **AI**: real LLM (Emergent universal LLM key) — no simulated data anywhere.

---

## 1 · Identity & Branding

| Field | Value |
|---|---|
| App name (default) | DogeLite Cloud Miner |
| App name (override) | `<MY_APP_NAME>` |
| Bundle ID | `<BUNDLE_ID>` (suggested: `app.dogelitecloudminer`) |
| App Store name | DogeLite Cloud Miner |
| App tagline | AI-driven Litecoin + Dogecoin cloud mining with on-chain payouts |
| Primary background | `#0B0E14` (deep ink) |
| Litecoin accent | `#345D9D` (silver-blue) — used when LTC is the selected coin |
| Dogecoin accent | `#C2A633` (gold) — used when DOGE is the selected coin |
| Neutral accent | `#5AF4AC` (neon green, for buttons + status pills) |
| Text on dark | `#FFFFFF` |
| Muted text | `#5B6470` |
| Icon style | 1024×1024 RGB no-alpha, full-bleed dark `#0B0E14`, with both the LTC glyph (silver-blue) and DOGE glyph (gold) side by side, no white border |
| App theme | Dark only |

---

## 2 · Architecture (non-negotiable)

- **Frontend**: Expo SDK 51+, Expo Router (file-based, `app/` directory), TypeScript, Zustand for shared state (incl. the **coin selector**), AsyncStorage for persistence, react-native-iap **v15 Nitro specs**.
- **Backend**: FastAPI on Python 3.11, Motor (async MongoDB), APScheduler for cron, JWT auth.
- **Database**: MongoDB.
- **No iPad UI**: `ios.supportsTablet: false`.
- **No tracking permission**: do NOT declare `NSUserTrackingUsageDescription`.

### Coin-selector convention (used everywhere)
- Zustand store key: `selectedCoin: "LTC" | "DOGE"`. Default: `"LTC"`. Persisted in AsyncStorage.
- Every backend call that returns coin-specific data must accept `?coin=LTC|DOGE`. Backend defaults to `LTC` if absent.
- Header pill in every screen shows the current coin so the user is never confused which balance/yield is being shown.

---

## 3 · Screens

5 tabs via `app/(tabs)/_layout.tsx`.

### 3.1 Dashboard (`app/(tabs)/index.tsx`)
- **Purpose**: glanceable hero showing BOTH balances simultaneously.
- **UI**:
  - Two-up hero cards side by side: **LTC balance** (silver-blue accent) + **DOGE balance** (gold accent). Each shows native amount + USD equivalent.
  - Two live tickers below: `LTC/USD` and `DOGE/USD` (source + age).
  - "AI Market Update" line — one LLM-generated sentence, references the **currently-selected** coin from the Zustand store.
  - "AI Trading Agents" preview — top 3 agents with daily_pct + status pill.
  - Primary CTA: `Buy a rig →`.
- **Data**: `GET /api/dashboard`, `GET /api/system/rates`, `GET /api/ai/ticker?coin=...`, `GET /api/ai/agents?coin=...`.

### 3.2 Plans / Mine / Shop (`app/(tabs)/shop.tsx`)
- **Purpose**: present every IAP plan as a card; one tap to purchase via StoreKit.
- **UI**:
  - Scrollable list of 10 plan cards (see Section 5).
  - Each card: plan name, tagline, USD price, hashrate, daily yield in **USD** with a sub-line showing the **LTC** and **DOGE** equivalents computed from live rates, duration, profitability score, BUY button.
  - "Free Forever" 24h plan available once per user.
  - Friendly **"Coming soon"** message (not "Purchase failed") when StoreKit reports product unavailable.
- **Data**: `GET /api/packages`, `GET /api/system/rates`, `GET /api/free-forever/status`, `POST /api/free-forever/activate`, `POST /api/iap/validate`.

### 3.3 Wallet (`app/(tabs)/wallet.tsx`) — the most coin-aware screen
- **Purpose**: balance management + on-chain withdrawal.
- **UI**:
  - **Coin selector** at the top: a segmented control `LTC | DOGE`. Selection is the Zustand `selectedCoin` and persisted. Tinted with the active coin's accent color.
  - Balance card for the selected coin: native amount, USD equivalent, last-accrued timestamp.
  - Live rate card for the selected coin (`/api/system/rates`).
  - **"Withdraw" CTA** → modal:
    - "Pay to" field: a coin-typed address (LTC or DOGE, validated client-side with the right regex).
    - Amount field in native units OR USD (toggle).
    - Estimated fee + final amount preview from NowPayments.
    - Submit → `POST /api/withdraw {coin, address, amount_native}`.
  - Transaction history list filtered by selected coin.
- **Data**: `GET /api/wallet?coin=LTC|DOGE`, `GET /api/system/rates`, `GET /api/withdraw/methods?coin=...`, `POST /api/withdraw`, `GET /api/transactions?coin=...`.

### 3.4 AI Agents (`app/(tabs)/agents.tsx`)
- **Purpose**: daily LLM-generated agent reports.
- **UI**:
  - Six agent cards (same 6 as SCM — Arbiter, Helios, Orbital, Quasar, Voltage, Sentinel).
  - Each card: name, strategy, daily_pct, win_rate, signal pill, action chip, one-sentence commentary.
  - Commentary must reference the user's currently-selected coin. E.g. if LTC is selected, Quasar's commentary might say "Litecoin Lightning channels rebalanced; routing fee yield improved."
- **Data**: `GET /api/ai/agents?coin=LTC|DOGE`.

### 3.5 Profile (`app/(tabs)/profile.tsx`)
- Email, referral code, auto-reinvest toggle, Premium Support link, Free-Forever status, sign out.

### 3.6 Admin (`app/admin/*.tsx`, admin only)
- Analytics across both coins (separate columns LTC and DOGE).
- Users / Transactions / AI controls / Support inbox.

### 3.7 Premium Support Chat
- Same flow as SCM. Bi-directional thread between user and admin. iOS-safe header.

---

## 4 · Authentication

Identical to Satoshi Cloud Miner:
- `POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me`.
- bcrypt cost 12.
- JWT HS256, 7-day exp, `JWT_SECRET` env.
- Admin user seeded idempotently from `ADMIN_EMAIL` + `ADMIN_PASSWORD` env.

---

## 5 · IAP product ladder (USD prices, identical to Satoshi Cloud Miner)

> Apple still charges in USD. The plan's daily yield is stored as **USD** in the DB and the UI converts it to LTC and DOGE using live rates from `/api/system/rates`. The user's balance is stored in **two separate fields** (one per coin) and accrues based on the user's `preferred_coin` at purchase time. The Wallet screen's coin selector flips which balance is displayed.

| Product ID | Type | Price | Display name | Tagline | Machines | Hashrate ea. | Daily yield ea. (USD) | Duration | BOGO | AI optimized | Profitability score |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `welcome_199` | consumable | $1.99 | Welcome Miner | Buy One Get One Free | 2 | 12 H/s | $0.16 | 30 d | ✅ | — | 4.4 |
| `rookie_299` | consumable | $2.99 | Rookie Rig | First step into the network | 1 | 18 H/s | $0.30 | 14 d | — | — | 5.0 |
| `pro_499` | consumable | $4.99 | Pro Rig | Workhorse for steady yield | 1 | 32 H/s | $0.40 | 30 d | — | ✅ | 6.1 |
| `elite_999` | consumable | $9.99 | Elite Cluster | AI-tuned mid-tier | 1 | 65 H/s | $0.85 | 30 d | — | ✅ | 7.0 |
| `ultra_1999` | consumable | $19.99 | Ultra Cluster | Twin-rig setup | 2 | 75 H/s | $1.50 | 60 d | — | ✅ | 7.6 |
| `mega_4999` | consumable | $49.99 | Mega Farm | Quad-cluster output | 4 | 110 H/s | $3.50 | 60 d | — | ✅ | 8.3 |
| `giga_9999` | consumable | $99.99 | Giga Farm | Six-cluster output | 6 | 175 H/s | $7.00 | 90 d | — | ✅ | 8.8 |
| `titan_14999` | consumable | $149.99 | Titan Farm | Eight-cluster output | 8 | 240 H/s | $11.50 | 90 d | — | ✅ | 9.3 |
| `colossus_19999` | consumable | $199.99 | Colossus Farm | Top-tier deployment | 10 | 320 H/s | $16.00 | 120 d | — | ✅ | 9.8 |
| `adfree_399` | non-consumable | $3.99 | Ad-Free + Priority Support | Remove interstitial ads + priority support | — | — | — | — | — | — | — |

Apple receipt validation is identical to SCM (use the IAP Server `.p8` key, NOT the App Manager key).

**Free Forever**: 1× per-user 24-hour rig at 5 H/s / $0.05 day-yield. Activated by `POST /api/free-forever/activate`. Countdown timer in UI. User picks LTC or DOGE for the accrual at activation time.

---

## 6 · Mining mechanics

| Behaviour | Rule |
|---|---|
| Yield unit | USD per day per machine. Stored in USD. Accrued into the user's **preferred_coin** balance using the latest live rate. |
| Per-machine coin assignment | At purchase, user's currently-selected coin is recorded as `machine.coin`. Yield accrues into that coin's balance. |
| Coin switch behaviour | Switching the coin selector does NOT change existing machines' coin. New purchases use the new coin. |
| Accrual cron | Every 5 minutes: prorated yield ( `daily_yield_usd × 5/1440` ) → convert to native units using `/api/system/rates` → add to `user.balance_<coin>_native`. |
| Machine expiry | When `expires_at < now()`, status flips to `expired`. |
| Auto-checkin / auto-reinvest crons | Same as SCM. |
| Daily AI snapshot cron | 00:05 UTC: refresh both `/api/ai/agents?coin=LTC` and `/api/ai/agents?coin=DOGE` caches. |

---

## 7 · External integrations

| Integration | Purpose | Env var | Diag endpoint |
|---|---|---|---|
| Apple App Store Server API | Validate IAP receipts | `IAP_KEY_ID`, `IAP_ISSUER_ID`, `IAP_P8_PATH` | `/api/diag/apple` |
| NowPayments REST API | LTC + DOGE on-chain payouts | `NOWPAY_API_KEY`, `NOWPAY_IPN_SECRET`, `LTC_PAYOUT_ADDR`, `DOGE_PAYOUT_ADDR` | `/api/diag/nowpayments` |
| Emergent universal LLM | AI Trading Agents + ticker (coin-aware) | `EMERGENT_LLM_KEY` | `/api/diag/llm` |
| CoinGecko / Coinbase / Kraken | LTC/USD + DOGE/USD price cascade | _(no key)_ | `/api/system/rates` |

Every integration must have a `/api/diag/*` endpoint that proves the wire is live (real round-trip) before the agent moves on to the next.

### NowPayments specifics
- API base: `https://api.nowpayments.io/v1`
- Auth: `x-api-key: <NOWPAY_API_KEY>` header.
- Payout endpoint: `POST /payout` with `{currency: "ltc"|"doge", amount: <native>, address: <user_addr>, ipn_callback_url: ...}`.
- Sandbox: use NowPayments test mode for the diag round-trip.
- IPN verification: HMAC-SHA512 of the raw body using `NOWPAY_IPN_SECRET`. Reject any IPN with a mismatched signature.

---

## 8 · AI Trading Agents (real LLM, coin-aware)

Same six agents as SCM (Arbiter, Helios, Orbital, Quasar, Voltage, Sentinel) with the same baseline percentages and strategy names. The **only** difference: the LLM prompt passes the currently-selected coin so commentary references it explicitly.

System prompt template:
> You are the head quant of a **{coin}** cloud-mining operations desk. Each day you publish a short performance report for six fictional AI agents. Output strict JSON only. Daily_pct -0.015 to +0.040. Win_rate 0.50 to 0.92. Commentary one short sentence referencing **{coin}** mining or {coin_l2} routing conditions. No financial advice.

Where `{coin}` is `Litecoin` or `Dogecoin` and `{coin_l2}` is `Litecoin Lightning` (yes, LTC has its own LN) or `Dogecoin on-chain`.

Caching: separate `ai_snapshots` documents per `(date, coin)`. Re-roll endpoint: `POST /api/admin/ai/regenerate?coin=LTC|DOGE`.

---

## 9 · Withdrawals (on-chain, NowPayments)

| Rule | Litecoin default | Dogecoin default | Admin override |
|---|---|---|---|
| Minimum withdrawal | 0.05 LTC (≈ $4 USD) | 25 DOGE (≈ $4 USD) | unlimited |
| Maximum single | 50 LTC | 100,000 DOGE | unlimited |
| Maximum daily | 100 LTC | 250,000 DOGE | unlimited |
| Withdraw fee | 1.0% (capped at $5 USD) | 1.0% (capped at $5 USD) | 0% |
| Methods | `on_chain_ltc` | `on_chain_doge` | same |
| Fee disposition | Re-invested into platform pool | same | same |

`POST /api/withdraw` body: `{ coin: "LTC"|"DOGE", address: "<addr>", amount_native: N }`.

Address validation regex (client-side first, server-side authoritative):
- LTC: `^(ltc1[ac-hj-np-z02-9]{8,87}|[LM3][a-km-zA-HJ-NP-Z1-9]{26,33})$` (bech32 + legacy)
- DOGE: `^D[5-9A-HJ-NP-U][1-9A-HJ-NP-Za-km-z]{32}$`

Admin email bypasses every limit and pays no fee.

---

## 10 · iOS permissions

**Default: NONE.** Same as SCM. Do not declare any permission strings unless a feature in this spec demands one. None do, so leave the `infoPlist` minimal.

```jsonc
"ios": {
  "supportsTablet": false,
  "bundleIdentifier": "<BUNDLE_ID>",
  "buildNumber": "1",
  "config": { "usesNonExemptEncryption": false },
  "infoPlist": { "ITSAppUsesNonExemptEncryption": false }
}
```

---

## 11 · Database schema

```text
users
  _id
  email (unique)
  hashed_password
  role               "user" | "admin"
  balance_ltc_native     decimal   (LTC, 8 dp)
  balance_doge_native    decimal   (DOGE, 8 dp)
  preferred_coin     "LTC" | "DOGE"
  ad_free            bool
  referral_code      str (unique)
  free_forever_active_until ISODate | null
  free_forever_coin  "LTC" | "DOGE" | null
  auto_reinvest      bool
  auto_reinvest_min_balance_usd  float (default 4.99)
  created_at

machines
  _id
  user_id
  package_id
  coin               "LTC" | "DOGE"      ← assigned at purchase
  hash_rate          float
  daily_yield_usd    float
  expires_at         ISODate
  status             "active" | "expired"
  index: (user_id, status), (user_id, coin)

transactions
  _id
  user_id
  type               "iap_purchase" | "accrual" | "withdraw" | "admin_grant"
  coin               "LTC" | "DOGE"   (nullable for iap_purchase)
  amount_native      decimal
  amount_usd_at_time decimal          (for ledger fidelity)
  meta               {...}
  status             "pending" | "success" | "failed"
  created_at
  index: (user_id, created_at desc), (user_id, coin)

ai_snapshots
  date               "YYYY-MM-DD"
  coin               "LTC" | "DOGE"
  agents             [{ ... }]
  created_at
  index: (date, coin) unique

support_threads / support_messages
  (identical to SCM)
```

---

## 12 · API endpoints (canonical)

Public:
- `POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me`
- `GET /api/dashboard`
- `GET /api/packages`
- `GET /api/wallet?coin=LTC|DOGE`
- `GET /api/system/rates` → `{ ltc_usd, doge_usd, source, fetched_at }`
- `GET /api/withdraw/methods?coin=LTC|DOGE`
- `POST /api/withdraw` · body `{coin, address, amount_native}`
- `GET /api/ai/ticker?coin=LTC|DOGE`
- `GET /api/ai/agents?coin=LTC|DOGE`
- `GET /api/free-forever/status` · `POST /api/free-forever/activate?coin=LTC|DOGE`
- `POST /api/iap/validate`
- `GET /api/transactions?coin=LTC|DOGE`
- Support endpoints (same shape as SCM)
- `PATCH /api/auto/settings`

Admin:
- `GET /api/admin/analytics`         (returns split-by-coin totals)
- `GET /api/admin/users`
- `GET /api/admin/transactions?coin=...`
- `POST /api/admin/ai/regenerate?coin=LTC|DOGE`
- `POST /api/admin/withdraw/{id}/approve|reject`
- Support admin endpoints (same as SCM)

Diagnostics:
- `/api/diag/apple` · `/api/diag/nowpayments` · `/api/diag/llm`

---

## 13 · Marketing copy (use verbatim in App Store Connect)

**App Store description** (≤ 4000 chars):
> DogeLite Cloud Miner is a dark-themed, AI-driven cloud mining cockpit for **both Litecoin and Dogecoin** in one app. Pick your coin with one tap. Buy a rig with one tap. Watch yield accrue in real time against the live LTC/USD and DOGE/USD rates, then cash out on-chain via NowPayments. Six AI Trading Agents publish a daily performance report that adapts its commentary to whichever coin you are watching. One clean dashboard. No fluff. No simulated data.

**Keywords** (≤ 100 chars, comma-separated):
`litecoin,ltc,dogecoin,doge,cloud,miner,mining,wallet,crypto,ai`

**Promotional text** (≤ 170 chars):
`Two coins, one app. On-chain withdrawals, AI Trading Agents, 10 mining plans, and a clean dual-accent dashboard.`

**Support URL**: `https://<your-domain>/support`
**Marketing URL**: `https://<your-domain>`
**Primary category**: Finance
**Secondary category**: Utilities

---

## 14 · Acceptance criteria (Definition of Done)

The agent is done when ALL of these are true:
1. App Store Connect shows the iOS version in `WAITING_FOR_REVIEW` for `<MY_APP_NAME>`.
2. All 10 IAPs are bundled with the same reviewSubmission.
3. `expo-doctor` returns 18/18 pass.
4. `yarn tsc --noEmit` is clean.
5. `deep_testing_backend_v2` reports ≥ 25/25 green tests.
6. `/api/system/rates` returns BOTH a real `ltc_usd` and a real `doge_usd` value sourced from coingecko/coinbase/kraken (no hardcoded constants).
7. `/api/ai/agents?coin=LTC` and `/api/ai/agents?coin=DOGE` BOTH return six agents with `ai_generated: true`.
8. `/api/diag/nowpayments` shows a successful test-mode round-trip.
9. The `auto_ship` watcher is registered with APScheduler and has logged at least one tick.
10. The icon at `/app/frontend/assets/images/icon.png` is RGB-only, no alpha, with no near-white pixels within 80 px of any edge, AND shows BOTH the LTC and DOGE glyphs.
11. `/app/HANDOFF.md` exists and documents every credential, every cron, every diag endpoint, and the steps to swap NowPayments for BlockCypher or CoinGate without touching UI code.

---

## 15 · Apple gotchas (carry forward)

Same as SCM:
- First IAP must ship with first version (`reviewSubmissions` API).
- Screenshots lock at `WAITING_FOR_REVIEW`; upload BEFORE attaching the version.
- App Preview video: stereo or no audio (Apple rejects mono with `MOV_RESAVE_STEREO`).
- No declared permissions you do not use.

**One LTC+DOGE-specific watch-out**: NowPayments requires you to **whitelist payout addresses** in their dashboard before the API will release funds. Have the agent surface a clear error if a withdrawal fails for this reason rather than retrying blindly.

---

_End of PRODUCT_SPEC.md — DogeLite Cloud Miner (LTC + DOGE)._
