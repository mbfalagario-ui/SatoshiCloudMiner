# HashCloud — Product Requirements Document

> ## ⚠️ CURRENT STATE — 2026-06-10 (supersedes any conflicting text below)
> - **Product name**: Hashrate Cloud Miner · **Bundle ID**: `app.satoshicloudminer` · **ASC App ID**: 6773104756
> - **Version**: 1.0.3, iOS buildNumber **38**, `supportsTablet=false` (iPhone-only)
> - **Production backend**: https://api.hashratecloudminer.com (Fly.io `hashrate-cloud-miner-api`, MongoDB Atlas)
> - **IAP**: REAL StoreKit 2 — `/api/packages/buy` verifies the client JWS locally
>   (appstoreserverlibrary SignedDataVerifier + Apple Root CA, fail-closed with
>   `APPLE_VERIFY_REQUIRED=1` on prod). NOT mocked. Real-device purchase verified 2026-06-09.
> - **Ads**: AdMob rewarded only (prod unit ca-app-pub-6035003811280283/1502046287).
>   Interstitial/app-open DISABLED — deferred until user provides prod unit IDs.
> - **History**: Builds 23–37 each rejected by Apple for various 2.1/3.1/5.1 issues; Build 37
>   rejected for unresponsive cross-sell banner on iPad → banner fully removed for Build 38.
>
> ### Changelog — 2026-06-10 (zero-build forensic verification pass, this session)
> - Verified all 10 phases of the user's forensic checklist: secret audit, banner removal,
>   Profile FAQ dedup, page-load fix, prod FAQ purge (17 clean FAQs, no `faq_cross_sell`,
>   zero `Rig` strings on /faqs /dashboard /machines /transactions /packages), git diff scope,
>   build config, static checks (tsc ✓, 30/30 build38 pytest ✓), UI QA 12/12 (iteration_5.json).
> - Fixed during audit: (1) `eas.json` `production` + `production-prod-domain` profiles had
>   Google PUBLIC TEST ad units + preview backend URL → now prod rewarded unit, interstitial
>   disabled, prod URL. (2) Stale hardcoded "v1.0.1 (23)" label on Profile → dynamic via
>   expo-constants. (3) `EXPO_TOKEN` moved out of `backend/.env` → `/root/.expo_token` (600).
>   (4) Web preview bundler-block fixed via WEB-ONLY metro stub for
>   react-native-google-mobile-ads (`metro.config.js` + `src/utils/admob.web-stub.js`) —
>   iOS native builds unaffected; browser QA now possible.
> - ⚠️ FLAGGED (pre-existing, user action): all Apple API keys (ASC + IAP .p8) return 401
>   from Apple. Live JWS purchase path unaffected; affects only `eas submit` and the API
>   fallback. Rotate keys in ASC before relying on either.
> - ⚠️ The EAS Build 38 artifact from 2026-06-10 13:46 (commit 244f89a) predates the final
>   banner-removal commits (5fdea7a, 4cd7b96) — it is STALE and must NOT be submitted.
>   A fresh build from current HEAD is required; never submitted to ASC via EAS, so
>   buildNumber stays 38.
> - Latent hazard noted (P2, untouched): `backend/services/auto_ship.py` scheduled job is
>   inert (fails at first ASC call with 401) but should be removed/disabled in a future
>   cleanup to permanently rule out unintended `eas submit`.
>
> ### Backlog
> - P1: Interstitial/app-open AdMob ads — BLOCKED on user-provided prod unit IDs. Do not implement before then.
> - P2: Refactor `server.py` (~4700 lines) into routes/models modules; delete legacy `auto_ship.py` + stale tests (backend_test.py withdraw 400-vs-422, build33 env-dependent IAP gate tests).
> - User action: trigger Emergent Publish / EAS build for corrected Build 38; rotate Apple API keys.

## Summary
HashCloud is a cloud-computing performance monitoring and management mobile app
inspired by the cloud-mining genre on the App Store (functional concept similar
to apps like "MeMiner: Cloud Mining"). It is built fresh as an original product
with its own brand identity ("HashCloud"), original copy, and an original
modern dark crypto/neon visual design. The app is intended to be shipped on
the Apple App Store by an independent Apple Developer.

## Platforms
- iOS (primary, target SDK Expo SDK 54)
- Android (secondary, same codebase via Expo)

## Tech Stack
- Frontend: React Native (Expo Router, SDK 54)
- Backend: FastAPI (Python) + Motor (async MongoDB)
- Storage: MongoDB
- Auth: Custom JWT (email + bcrypt-hashed password)
- Theming: Custom design tokens, JetBrains Mono for numeric displays

## Core Features (parity with the "cloud mining" genre)
1. **Onboarding** — Brand intro with hero illustration and feature list.
2. **Auth** — Email/password sign up & sign in, JWT issued, stored in secure storage.
3. **Home Dashboard** — Total balance (USD + BTC), live ticking earnings,
   active hashpower (TH/s), today's & lifetime earnings, animated active-miner
   card, quick actions.
4. **Cloud Mining Power Shop** — Predefined packages at the same MeMiner price
   tiers ($0.99 → $199.99): Starter Boost, Welcome Miner (BOGO), Rookie Rig,
   Pro Rig, Elite Cluster, Ultra Cluster, Mega Farm, Giga Farm, Titan Farm,
   Colossus Farm. Each has hashpower, duration, daily yield, total est. return.
5. **Withdrawals** — Methods: Lightning Network, Coinbase, ZBD, Speed Wallet,
   Cash App. Min withdrawal $1.00, 24h cap $2.00 (mirrors the genre's caps).
6. **Transaction History** — Mining payouts, purchases, withdrawals, bonuses,
   referrals with status badges.
7. **Daily Check-in** — 7-day streak calendar, +20% per consecutive day bonus.
8. **Invite Friends** — Unique referral code, share sheet, $0.50 per signup
   bonus to the referrer.
9. **Profile & Legal** — Account info, support, Terms of Service, Privacy
   Policy, logout.

## Mining Simulation
- Each owned machine has `hash_rate (TH/s)`, `daily_yield_usd`, `duration_days`,
  `expires_at`, `status (active|expired)`.
- Earnings accrue on-demand: every authenticated dashboard/me/etc. request
  computes `(now - last_accrual) * sum(per_second_yield_of_active_machines)`
  and credits the user's BTC balance.
- BTC↔USD conversion uses a fixed simulated rate (`BTC_USD_RATE = 65000`) to
  match the genre's typical UX (real rates are not required for this concept).

## API Surface (all under `/api`)
- `POST /auth/register` — register, returns JWT + user
- `POST /auth/login` — login, returns JWT + user
- `GET /auth/me` — current user (also accrues earnings)
- `GET /dashboard` — full dashboard payload
- `GET /machines` — owned miners
- `GET /packages` — shop catalogue
- `POST /packages/buy` — simulated purchase (in production, gated by Apple
  IAP receipt validation — clearly marked in code)
- `GET /withdraw/methods` — wallet methods + limits
- `POST /withdraw` — request withdrawal
- `GET /transactions` — history
- `GET /daily-checkin/status` — check-in status
- `POST /daily-checkin` — claim daily reward
- `GET /referral` — referral code + invited count

## Apple App Store Readiness
- Bundle ID: `app.hashcloud.mobile`
- Version: 1.0.0, build number 1
- Encryption disclosure: `ITSAppUsesNonExemptEncryption = false`
- Age rating: 18+ (consistent with the category)
- Category: Utilities
- Mandatory documents shipped in-app:
  - Terms of Service (`app/legal.tsx?doc=terms`)
  - Privacy Policy (`app/legal.tsx?doc=privacy`)
- Privacy-required InfoPlist key `NSUserTrackingUsageDescription` provided in
  `app.json` for ad tracking.
- Splash + adaptive icon configured via expo-splash-screen plugin.
- In-app purchases will be integrated via Apple StoreKit when the developer
  configures product IDs in App Store Connect. The current `/packages/buy`
  endpoint is the post-purchase server-side hook and accepts a stub for
  development. A receipt-validation step (e.g., using `app-store-server-api`)
  must be added before App Store submission with live IAP.
- Required App Store Connect assets (to be added by the developer in ASC):
  - App icon 1024x1024 (use `assets/images/icon.png`)
  - Launch screen (handled by expo-splash-screen)
  - 6.7" / 6.5" / 5.5" iPhone screenshots (App Store Connect upload)
  - App preview videos (optional)
  - Description, keywords, support URL, marketing URL
  - Privacy policy URL (host the Privacy text from `app/legal.tsx`)
  - Demo account: `test@hashcloud.app` / `password123`

## Smart Business Enhancement
- Referral viral loop ($0.50 per signup) acts as low-cost user acquisition.
- BOGO "Welcome Miner" at $1.99 reduces psychological barrier to first
  purchase and drives initial conversion — a proven pattern in this category.

## Notes / Mocked items
- **MOCKED**: Apple IAP receipt validation is NOT implemented. `/packages/buy`
  simulates a successful purchase without verifying a receipt. Replace with
  StoreKit + server-side receipt validation before production submission.
- **MOCKED**: Withdrawal processing remains in `pending` state — no real
  cryptocurrency transfer is performed. Operator must wire up a real BTC /
  Lightning payout backend before going live.
- BTC/USD rate is fixed in code (not pulled from an exchange).
