# HashCloud — Product Requirements Document

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
