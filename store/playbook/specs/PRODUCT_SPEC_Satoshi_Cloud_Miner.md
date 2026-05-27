# PRODUCT_SPEC.md — Satoshi Cloud Miner (BTC)

> **HOW TO USE THIS FILE**
> Attach this file when you send **PROMPT 01** from the Foolproof iOS Clone Prompts Playbook. The agent will read every section and follow it as the canonical truth for what to build.
> Anywhere you see `<…>` placeholders, the agent will surface them and ask you to fill them in **once**. Otherwise you should not need to add anything.

---

## 0 · TL;DR

A dark-themed, neon-accent iOS app that simulates Bitcoin cloud mining. Users buy "mining rigs" via Apple In-App Purchase, accrue daily satoshi yields, and withdraw via the Bitcoin Lightning Network. Six AI Trading Agents publish a daily LLM-driven performance report. One admin console handles operations.

- **Platform**: iOS only (no iPad UI, no Android in v1).
- **Stack**: Expo Router + React Native (TypeScript) + FastAPI + MongoDB.
- **Monetisation**: 10 consumable IAPs + 1 non-consumable Ad-Free.
- **Withdrawals**: Real Bitcoin Lightning payouts via Blink Wallet.
- **AI**: Real LLM (Emergent universal LLM key) — no simulated data.

---

## 1 · Identity & Branding

| Field | Value |
|---|---|
| App name | Satoshi Cloud Miner |
| Bundle ID | `<BUNDLE_ID>` (suggested: `app.satoshicloudminer`) |
| App Store name | Satoshi Cloud Miner |
| App tagline | AI-driven Bitcoin cloud mining with instant Lightning withdrawals |
| Primary background | `#0B0E14` (deep ink) |
| Primary accent | `#5AF4AC` (neon green) |
| Secondary accent | `#0BA86F` (mint, used for buttons) |
| Text on dark | `#FFFFFF` |
| Muted text | `#5B6470` |
| Font | System default (San Francisco on iOS) |
| Icon style | 1024×1024 RGB no-alpha, full-bleed dark `#0B0E14`, large neon Bitcoin glyph centered |
| App theme | Dark only (no light mode) |

---

## 2 · Architecture (non-negotiable)

- **Frontend**: Expo SDK 51+, Expo Router (file-based, `app/` directory), TypeScript, Zustand for shared state, AsyncStorage for persistence, react-native-iap **v15 Nitro specs** for IAP.
- **Backend**: FastAPI on Python 3.11, Motor (async MongoDB driver), APScheduler for cron, JWT auth (HS256, 7-day expiry).
- **Database**: MongoDB (single replica, indexes on `users.email`, `users.referral_code`, `machines.user_id+status`, `transactions.user_id+created_at`).
- **No iPad UI**: `ios.supportsTablet: false` in `app.json`.
- **No tracking permission**: do NOT declare `NSUserTrackingUsageDescription`.

---

## 3 · Screens

5 tabs via `app/(tabs)/_layout.tsx`. Each screen is described as: **purpose → key UI elements → data fetched**.

### 3.1 Dashboard (`app/(tabs)/index.tsx`)
- **Purpose**: glanceable hero showing balance + activity.
- **UI**:
  - Hero card: total balance in sats + USD equivalent + live BTC/USD ticker.
  - "AI Market Update" line (one LLM-generated sentence, refresh every 30 s).
  - "AI Trading Agents" preview — top 3 agents with daily_pct + status pill.
  - Active machines summary (count + cumulative hashrate + earnings today).
  - Primary CTA: `Buy a rig →` (navigates to Plans).
- **Data**: `GET /api/dashboard`, `GET /api/ai/ticker`, `GET /api/ai/agents`.

### 3.2 Plans / Mine / Shop (`app/(tabs)/shop.tsx`)
- **Purpose**: present every IAP plan as a card; one tap to purchase via StoreKit.
- **UI**:
  - Scrollable list of 10 plan cards (see Section 5 for full ladder).
  - Each card: plan name, tagline, USD price, hashrate, daily yield in sats and USD, duration, profitability score (3.6 – 9.8), BOGO ribbon if applicable, BUY button.
  - "Free Forever" 24h plan available once per user, separate hero card.
  - On error from StoreKit: friendly **"Coming soon"** message (NOT "Purchase failed") when product is not in catalog.
- **Data**: `GET /api/packages`, `GET /api/free-forever/status`, `POST /api/free-forever/activate`, `POST /api/iap/validate`.

### 3.3 Wallet (`app/(tabs)/wallet.tsx`)
- **Purpose**: balance management + Lightning withdrawal.
- **UI**:
  - Balance breakdown: BTC, sats, USD equivalent.
  - Live BTC/USD rate card (source + age in seconds).
  - "Withdraw" CTA → modal with Lightning invoice paste field.
  - Transaction history list (deposits, accruals, withdrawals).
- **Data**: `GET /api/wallet`, `GET /api/system/btc_rate`, `GET /api/withdraw/methods`, `POST /api/withdraw`, `GET /api/transactions`.

### 3.4 Profile (`app/(tabs)/profile.tsx`)
- **Purpose**: user settings + referrals + auto-reinvest.
- **UI**:
  - Email, referral code (copyable).
  - Toggle: Auto-reinvest yield once balance ≥ $4.99 (admin-configurable threshold).
  - "Premium Support" → opens chat with admin.
  - Free-Forever activation status.
  - Sign out button.
- **Data**: `GET /api/auth/me`, `PATCH /api/auto/settings`, `GET /api/free-forever/status`.

### 3.5 Admin (`app/admin/*.tsx`, only visible if `user.role === "admin"`)
- **Purpose**: operate the platform.
- **UI**:
  - Analytics: total users, active machines, daily payouts, total yield distributed.
  - Users tab: list, search by email, grant admin / ban / reset.
  - Transactions tab: approve / reject pending withdrawals.
  - AI controls: regenerate today's agent snapshot.
  - Support inbox: list of threads, unread badges, reply UI.
- **Data**: `/api/admin/*` (admin JWT required).

### 3.6 Premium Support Chat (`app/support.tsx`)
- Bi-directional chat thread between user and admin.
- iOS-safe header (`useSafeAreaInsets`).
- `GET /api/support/thread`, `POST /api/support/thread/{id}/messages`, `GET /api/support/unread`.

---

## 4 · Authentication

| Endpoint | Method | Body | Returns |
|---|---|---|---|
| `/api/auth/register` | POST | `{email, password}` | `{access_token, user}` |
| `/api/auth/login` | POST | `{email, password}` | `{access_token, user}` |
| `/api/auth/me` | GET | _(Bearer JWT)_ | full user object |

- Passwords hashed with bcrypt (cost 12).
- Admin user seeded idempotently on backend startup from env: `ADMIN_EMAIL=<MY_EMAIL>` + `ADMIN_PASSWORD=<MY_PASSWORD>`. (For SCM: `mbfalagario@gmail.com`.)
- JWT: HS256, exp = 7 days, secret in `JWT_SECRET` env var.

---

## 5 · IAP product ladder (source of truth — must exist in App Store Connect)

> All prices are USD. Yields are stored in USD in the DB and converted to sats client-side using the live BTC/USD rate.

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

Apple Receipt Validation: every `POST /api/iap/validate` MUST verify with the App Store Server API using the IAP Server `.p8` key (NOT the App Manager key). Reject if `bundle_id != <BUNDLE_ID>`.

**Free Forever**: a 1× per-user 24-hour rig at 5 H/s / $0.05 day-yield, activated by `POST /api/free-forever/activate`. Countdown timer in UI.

---

## 6 · Mining mechanics

| Behaviour | Rule |
|---|---|
| Yield unit | USD per day per machine (stored). Converted to sats client-side using live BTC/USD. |
| Accrual cron | Every 5 minutes: each active machine accrues prorated yield ( `daily_yield_usd × 5/1440` ) → user balance in sats. |
| Machine expiry | When `expires_at < now()`, machine status flips to `expired`. |
| Auto-checkin cron | Every 1 hour: flags any user idle ≥ 7 days for engagement push. |
| Auto-reinvest cron | Every 2 hours: if user has `auto_reinvest: true` and balance USD ≥ threshold (default $4.99), buy the cheapest available plan with balance. |
| Daily AI snapshot cron | 00:05 UTC: refresh `/api/ai/agents` cache. |

---

## 7 · External integrations

| Integration | Purpose | Env var | Diag endpoint |
|---|---|---|---|
| Apple App Store Server API | Validate IAP receipts | `IAP_KEY_ID`, `IAP_ISSUER_ID`, `IAP_P8_PATH` | `/api/diag/apple` |
| Blink Wallet (Lightning) | Real BTC payouts | `BLINK_API_KEY`, `BLINK_USD_WALLET_ID` | `/api/diag/blink` |
| Emergent universal LLM | AI Trading Agents + ticker | `EMERGENT_LLM_KEY` | `/api/diag/llm` |
| CoinGecko / Coinbase / Kraken | Live BTC/USD price cascade | _(no key)_ | `/api/system/btc_rate` |

Every integration must have a `/api/diag/*` endpoint proving the live wire before being merged.

---

## 8 · AI Trading Agents (real LLM, no fakes)

Six agents. The daily snapshot is generated **once per UTC day** by a single LLM call (`gpt-4o-mini` via Emergent LLM key) and cached in `ai_snapshots`. Falls back to deterministic seeded values on LLM failure.

| ID | Name | Strategy | Baseline daily_pct | Focus |
|---|---|---|---|---|
| agent_arbiter | Arbiter | Latency arbitrage | 0.018 | Cross-pool block-propagation latency |
| agent_helios | Helios | Hashrate momentum | 0.022 | Global hashrate trend |
| agent_orbital | Orbital | Difficulty hedging | 0.015 | Upcoming difficulty retarget |
| agent_quasar | Quasar | Lightning flow router | 0.020 | LN channel rebalancing yield |
| agent_voltage | Voltage | Energy-cost rebalance | 0.012 | Shift to cheap power zones |
| agent_sentinel | Sentinel | Mempool MEV guard | 0.014 | Protect from sandwich attacks |

Each agent returns: `daily_pct, win_rate, signal_strength (low|medium|high), action (Hold|Increase|Decrease|Rebalance), commentary (one short sentence), ai_generated: true`.

Endpoint: `GET /api/ai/agents`. Admin re-roll: `POST /api/admin/ai/regenerate`.

---

## 9 · Withdrawals (Lightning)

| Rule | Default | Admin override |
|---|---|---|
| Minimum single withdrawal | 1,000 sats | unlimited |
| Maximum single withdrawal | 1,000,000 sats | unlimited |
| Maximum daily withdrawal | 5,000,000 sats | unlimited |
| Withdraw fee | 1.0% + 50 sats flat (capped at 1000 sats) | 0% |
| Methods | `lightning` (Blink Wallet) | same |
| Fee disposition | Re-invested into platform pool | same |

`POST /api/withdraw` body: `{ method: "lightning", invoice: "lnbc...", amount_sats: N }`. Returns `{ tx_id, status }`. Admin email (`mbfalagario@gmail.com`) bypasses all limits + fees.

---

## 10 · iOS permissions

**Default: NONE.**

Do NOT declare any of: `NSUserTrackingUsageDescription`, `NSCameraUsageDescription`, `NSLocationWhenInUseUsageDescription`, `NSPhotoLibraryUsageDescription`, etc. If a future feature requires one, add it together with the feature's code path — never preemptively.

`app.json`:
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
  email (unique index)
  hashed_password
  role            "user" | "admin"
  balance_sats    int
  ad_free         bool
  referral_code   str (unique)
  free_forever_active_until  ISODate | null
  auto_reinvest   bool
  auto_reinvest_min_balance_usd  float (default 4.99)
  created_at

machines
  _id
  user_id
  package_id      ref → IAP product_id
  hash_rate       float (H/s)
  daily_yield_usd float
  expires_at      ISODate
  status          "active" | "expired"
  created_at
  index: (user_id, status)

transactions
  _id
  user_id
  type            "iap_purchase" | "accrual" | "withdraw" | "admin_grant"
  amount_sats     int
  meta            { ... }
  status          "pending" | "success" | "failed"
  created_at
  index: (user_id, created_at desc)

ai_snapshots
  date            "YYYY-MM-DD" (unique)
  agents          [{ ...AgentReport }]
  created_at

support_threads
  _id
  user_id
  status          "open" | "closed"
  unread_user_count
  unread_admin_count
  updated_at

support_messages
  _id
  thread_id
  sender_id
  sender_role     "user" | "admin"
  content
  created_at
```

---

## 12 · API endpoints (canonical)

Public:
- `POST /api/auth/register` · `POST /api/auth/login` · `GET /api/auth/me`
- `GET /api/dashboard` · `GET /api/packages` · `GET /api/wallet`
- `GET /api/system/btc_rate` · `GET /api/withdraw/methods`
- `GET /api/ai/ticker` · `GET /api/ai/agents`
- `GET /api/free-forever/status` · `POST /api/free-forever/activate`
- `POST /api/iap/validate` · `POST /api/withdraw`
- `GET /api/transactions`
- `GET /api/support/thread` · `POST /api/support/thread/{id}/messages` · `GET /api/support/unread`
- `PATCH /api/auto/settings`

Admin:
- `GET /api/admin/analytics` · `GET /api/admin/users` · `GET /api/admin/transactions`
- `POST /api/admin/ai/regenerate`
- `POST /api/admin/withdraw/{id}/approve` · `POST /api/admin/withdraw/{id}/reject`
- `GET /api/admin/support/threads` · `POST /api/admin/support/thread/{id}/reply`

Diagnostics (no auth, internal-only):
- `/api/diag/apple` · `/api/diag/blink` · `/api/diag/llm`

---

## 13 · Marketing copy (use verbatim in App Store Connect)

**App Store description** (≤ 4000 chars):
> Satoshi Cloud Miner is a dark-themed, AI-driven Bitcoin cloud mining cockpit. Buy a rig with one tap, watch yield accrue in real time against the live BTC/USD rate, and cash out instantly over the Lightning Network. Six AI Trading Agents publish a daily performance report so you always know which strategy is leading. One clean dashboard. No fluff. No simulated data.

**Keywords** (≤ 100 chars, comma-separated):
`bitcoin,btc,cloud,miner,mining,lightning,satoshi,wallet,crypto,ai`

**Promotional text** (≤ 170 chars):
`Live Lightning withdrawals, AI Trading Agents, 10 mining plans, and a clean dark/neon dashboard.`

**Support URL**: `https://<your-domain>/support`
**Marketing URL**: `https://<your-domain>`
**Primary category**: Finance
**Secondary category**: Utilities

---

## 14 · Acceptance criteria (Definition of Done)

The agent is done when ALL of these are true:
1. App Store Connect shows the iOS version in `WAITING_FOR_REVIEW`.
2. All 10 IAPs are bundled with the same reviewSubmission.
3. `expo-doctor` returns 18/18 pass.
4. `yarn tsc --noEmit` is clean.
5. `deep_testing_backend_v2` reports ≥ 25/25 green tests.
6. `/api/system/btc_rate` returns a real value sourced from coingecko/coinbase/kraken (NOT a hardcoded constant).
7. `/api/ai/agents` returns six agents all with `ai_generated: true`.
8. The `auto_ship` watcher is registered with APScheduler and has logged at least one tick.
9. The icon at `/app/frontend/assets/images/icon.png` is RGB-only, no alpha, with no near-white pixels within 80 px of any edge (verified by PIL sample).
10. `/app/HANDOFF.md` exists and documents every credential, every cron, and every diag endpoint.

---

## 15 · Known Apple gotchas (carry forward from the playbook)

- **First IAP must ship with first version** — use the unified `reviewSubmissions` API, not `inAppPurchaseSubmissions`.
- **Screenshots lock at WAITING_FOR_REVIEW** — upload BEFORE attaching the version.
- **App Preview video** — stereo audio or no audio at all (Apple rejects mono with `MOV_RESAVE_STEREO`).
- **No declared permissions you do not use** — otherwise Apple forces the App Privacy questionnaire.

---

_End of PRODUCT_SPEC.md — Satoshi Cloud Miner._
