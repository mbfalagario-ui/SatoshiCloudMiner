# App Store Connect — Satoshi Cloud Miner submission checklist

> **App name:** Satoshi Cloud Miner
> **Bundle ID:** `app.satoshicloudminer`
> **Apple App Store Connect App ID:** 6773104756
> **Apple Team ID:** UHF3KNM9F9
> **Current build:** 1.0.0 (12) — submitted via EAS

> Demo account for Apple review (also in `/app/memory/test_credentials.md`):
> **Email:** `test@testeraccount.com`
> **Password:** `password123`

## Required fields (App Information)
- **App name:** Satoshi Cloud Miner
- **Subtitle:** Bitcoin Mining Performance Monitor
- **Primary category:** Utilities
- **Secondary category:** Finance (optional)
- **Content rights:** Your app does NOT contain, show, or access third-party content (uncheck)
- **Age rating:** 17+ (Frequent/Intense Simulated Gambling = NO, Unrestricted Web Access = NO)
- **Bundle ID:** `app.satoshicloudminer`  ← matches `app.json`
- **SKU:** `SCMINER-IOS-001`

## Pricing & Availability
- **Price:** Free
- **In-App Purchases:** Yes — 11 products, all Consumable except `adfree_399` (Non-Consumable):

| Product ID         | Reference name        | Type           | Price |
| ------------------ | --------------------- | -------------- | ------ |
| starter_099        | Starter Boost         | Consumable     | $0.99  |
| welcome_199        | Welcome Miner (BOGO)  | Consumable     | $1.99  |
| rookie_299         | Rookie Rig            | Consumable     | $2.99  |
| pro_499            | Pro Rig               | Consumable     | $4.99  |
| elite_999          | Elite Cluster         | Consumable     | $9.99  |
| ultra_1999         | Ultra Cluster         | Consumable     | $19.99 |
| mega_4999          | Mega Farm             | Consumable     | $49.99 |
| giga_9999          | Giga Farm             | Consumable     | $99.99 |
| titan_14999        | Titan Farm            | Consumable     | $149.99 |
| colossus_19999     | Colossus Farm         | Consumable     | $199.99 |
| **adfree_399**     | Ad-Free Upgrade       | Non-Consumable | $3.99  |

> The product ID **must equal** the package id our backend already knows about — that's how the
> StoreKit `transactionId` flows into `/api/packages/buy` and gets matched to the right miner /
> entitlement.

## Description / Marketing
- Pull copy from `/app/store/description.txt`
- Pull keywords (100 chars max) from `/app/store/keywords.txt`
- Pull "What's new in this version" from `/app/store/whats-new.txt`
- Support URL: https://satoshicloudminer.app/support
- Marketing URL (optional): https://satoshicloudminer.app
- Privacy Policy URL (required): https://satoshicloudminer.app/privacy

## Required assets
- **App icon 1024×1024:** baked into `app.json` / EAS prebuild
- **Screenshots (already generated in `/app/store/screenshots/`):**
  - 6.7" iPhone (1290 × 2796) — `screenshots/6.7/`
  - 6.5" iPhone (1242 × 2688) — `screenshots/6.5/`
  - 5.5" iPhone (1242 × 2208) — `screenshots/5.5/`
  - iPad 12.9" (2048 × 2732) — optional, not generated
- **App preview videos:** optional, not generated

## App Privacy questionnaire answers
Data types collected and linked to user:
- Contact Info → Email Address (App functionality, Account management)
- Identifiers → User ID (App functionality, Analytics)
- Financial Info → Other Financial Info (BTC balance) (App functionality)
- Diagnostics → Crash Data (App functionality)
Data NOT collected: Health, Location, Contacts, Photos, Browsing, Search History, Sensitive Info.
Tracking: enabled if you add ads (currently no IDFA usage). The app already declares
`NSUserTrackingUsageDescription` for future AdMob integration.

## App Review Information
- Sign-in required: **YES**
- Demo account: `test@testeraccount.com` / `password123`
- Contact info: your name + email + phone
- Notes for the reviewer (paste into App Review Information → Notes):
  > Satoshi Cloud Miner is a cloud-computing performance monitoring app. In-App Purchases
  > unlock simulated cloud computing-power packages (10 plans, all Consumable) plus a
  > Non-Consumable "Ad-Free" entitlement at $3.99 that disables tab-transition
  > interstitial ads.
  >
  > Every IAP receipt is verified server-side against the Apple App Store Server API
  > using our `.p8` key (no client-trust). On success the matching mining package /
  > entitlement is granted to the user account.
  >
  > The "Wallet" tab demonstrates how a real Lightning Network payout works — for this
  > review build, payouts settle through our production Blink Lightning wallet
  > (`btc.satoshi`). Minimum withdrawal: 150,000 sats (0.00150 BTC). Flat fee: 10%.
  >
  > The demo account above is pre-funded so you can exercise every flow including
  > Mine purchase, Ad-Free upgrade, Lightning withdrawal address validation, and the
  > AI Trading Agents dashboard.

## Encryption (ITSAppUsesNonExemptEncryption)
Already declared in `app.json` as `false` — covers standard HTTPS only.

## Build & upload
- EAS build was triggered with `eas build --platform ios --profile production`.
- `buildNumber` auto-increments remotely via `eas.json` `"appVersionSource": "remote"`.
- Once the IPA is uploaded to App Store Connect via `eas submit --platform ios --latest`,
  assign Build #12 to the v1.0.0 release in App Store Connect and click **Submit for Review**.

## TestFlight notes for Build #12 (over Build #11)
- Fixed: rare native crash on sign-out (replaced render-time `<Redirect>` with an
  effect-driven `router.replace` post-commit; deferred `setUser(null)` via
  `InteractionManager.runAfterInteractions`).
- Fixed: Home dashboard not refreshing after returning from Mine tab — now uses
  `useFocusEffect` so the active-miners card updates automatically on focus.
- Fixed: post-purchase toast text said "0 miner added to your account" for the
  Ad-Free purchase. Now branches on entitlement: shows "Ad-Free Unlocked" for the
  ad-free tier and the miner-count copy for mining plans.
- Polish: after a successful mining-plan purchase, the app auto-navigates to Home so
  the user immediately sees their new hashrate.
