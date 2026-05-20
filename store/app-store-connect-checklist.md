# App Store Connect submission checklist

> Demo account for Apple review (also in `/app/memory/test_credentials.md`):
> **Email:** test@hashcloud.app
> **Password:** password123

## Required fields (App Information)
- **App name:** HashCloud
- **Subtitle:** Cloud Computing Monitor
- **Primary category:** Utilities
- **Secondary category:** Finance (optional)
- **Content rights:** Your app does NOT contain, show, or access third-party content (uncheck)
- **Age rating:** 17+ (Frequent/Intense Simulated Gambling = NO, Unrestricted Web Access = NO)
- **Bundle ID:** `app.hashcloud.mobile`  ← must match `app.json`
- **SKU:** `HASHCLOUD-IOS-001`

## Pricing & Availability
- **Price:** Free
- **In-App Purchases:** Yes — set up these 10 product IDs in App Store Connect → Features → In-App Purchases (type = Consumable for each):

| Product ID         | Reference name        | Price |
| ------------------ | --------------------- | ----- |
| starter_099        | Starter Boost         | $0.99 |
| welcome_199        | Welcome Miner (BOGO)  | $1.99 |
| rookie_299         | Rookie Rig            | $2.99 |
| pro_499            | Pro Rig               | $4.99 |
| elite_999          | Elite Cluster         | $9.99 |
| ultra_1999         | Ultra Cluster         | $19.99 |
| mega_4999          | Mega Farm             | $49.99 |
| giga_9999          | Giga Farm             | $99.99 |
| titan_14999        | Titan Farm            | $149.99 |
| colossus_19999     | Colossus Farm         | $199.99 |

> The product ID **must equal** the package id our backend already knows about — that's how the
> StoreKit `transactionId` flows into `/api/packages/buy` and gets matched to the right miner.

## Description / Marketing
- Pull copy from `/app/store/description.txt`
- Pull keywords (100 chars max) from `/app/store/keywords.txt`
- Pull "What's new in this version" from `/app/store/whats-new.txt`
- Support URL: https://hashcloud.app/support  ← you must host this page
- Marketing URL (optional): https://hashcloud.app
- Privacy Policy URL (required): https://hashcloud.app/privacy  ← you must host this page

## Required assets
- **App icon 1024×1024:** see `/app/store/assets-todo.md`
- **Screenshots:**
  - 6.7" iPhone (1290 × 2796)
  - 6.5" iPhone (1242 × 2688)
  - 5.5" iPhone (1242 × 2208)
  - iPad 12.9" (2048 × 2732) — optional
- **App preview videos:** optional

## App Privacy questionnaire answers
Data types collected and linked to user:
- Contact Info → Email Address (App functionality, Account management)
- Identifiers → User ID (App functionality, Analytics)
- Diagnostics → Crash Data (App functionality)
Data NOT collected: Health, Location, Contacts, Photos, Browsing, Search History, Sensitive Info.
Tracking: enabled if you add ads. The app already declares `NSUserTrackingUsageDescription`.

## App Review Information
- Sign-in required: **YES**
- Demo account: `test@hashcloud.app` / `password123`
- Contact info: your name + email + phone
- Notes for the reviewer (paste into App Review Information → Notes):
  > HashCloud is a cloud-computing performance monitoring app. In-App Purchases unlock
  > simulated cloud computing-power packages. The "Wallet" tab demonstrates how a real
  > Lightning/BTC payout works via BTCPay Server — for this review build, payouts settle
  > to our demo BTCPay store. Demo account is pre-funded so you can exercise every flow.

## Encryption (ITSAppUsesNonExemptEncryption)
Already declared in `app.json` as `false` — covers standard HTTPS only.

## Build & upload
- Use Emergent's "Publish" button (top-right). It bumps the build number, runs Expo's
  EAS build for iOS, and uploads to TestFlight. No EAS CLI work needed on your end.
- Once in TestFlight, click "Submit for Review" inside App Store Connect.
