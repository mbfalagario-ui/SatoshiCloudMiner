# Satoshi Cloud Miner — iOS Build & Submission Playbook

Everything below runs **on your local Mac**, not in this container.
Expo CLI cannot do interactive Apple sign-in from a server.

## 0. Prerequisites

- Apple Developer account in good standing
- Xcode 16+ installed (only needed if you choose `--local`)
- Node 20+ and `npm i -g eas-cli`
- Clone the repo to your Mac

## 1. One-time EAS setup

```bash
cd frontend
eas login                      # use your Apple ID + 2FA
eas init --id <your-eas-project-id>   # creates project if missing
eas device:create              # register your iPhone for internal builds (optional)
```

## 2. Register the bundle ID in App Store Connect

1. App Store Connect → My Apps → "+" → New App
2. Platform: iOS
3. Name: **Satoshi Cloud Miner**
4. Primary language: English (U.S.)
5. Bundle ID: `app.satoshicloudminer`  (must match `app.json -> ios.bundleIdentifier`)
6. SKU: `scm-ios-001`

## 3. Add in-app purchase products

In App Store Connect → your app → Monetization → In-App Purchases, create
**Consumable** products with these exact IDs (matching the backend
`SHOP_PACKAGES` ids):

| Product ID         | Reference name   | USD price |
|--------------------|------------------|-----------|
| starter_099        | Starter Boost    | 0.99      |
| welcome_199        | Welcome Miner    | 1.99      |
| rookie_299         | Rookie Rig       | 2.99      |
| pro_499            | Pro Rig          | 4.99      |
| elite_999          | Elite Cluster    | 9.99      |
| ultra_1999         | Ultra Cluster    | 19.99     |
| mega_4999          | Mega Farm        | 49.99     |
| giga_9999          | Giga Farm        | 99.99     |
| titan_14999        | Titan Farm       | 149.99    |
| colossus_19999     | Colossus Farm    | 199.99    |

Fill in localized name + description for each (App Review will reject
"missing metadata"). Submit each product for review **with the binary**.

## 4. Build for TestFlight

```bash
cd frontend
eas build --platform ios --profile production
# OR for a faster device-only build:
eas build --platform ios --profile preview
```

EAS will prompt for the App Store Connect API Key. Use:
- Key ID: `WFQJ6L9KXS`
- Issuer ID: `d3284874-7bd8-4eff-b272-c9ef0122df9a`
- `.p8` file: `backend/keys/AuthKey_WFQJ6L9KXS.p8`

EAS handles signing certificates and provisioning profiles automatically
the first time.

## 5. Submit to TestFlight

```bash
eas submit --platform ios --latest
```

EAS uploads to App Store Connect. Once Apple finishes processing (~10 min)
you can invite internal testers in the TestFlight tab.

## 6. Verify IAP in Sandbox

1. On your test iPhone: Settings → App Store → Sandbox Account → sign in
   with a sandbox Apple ID created in App Store Connect → Users and Access
   → Sandbox.
2. Install the TestFlight build.
3. Tap "Mine" tab → any plan → "Buy …".
4. Apple's purchase sheet appears.
5. Confirm with Face ID — the receipt is sent to
   `POST /api/packages/buy` and validated server-side against the App Store
   Server API (with `J55DSC44V5` In-App Purchase key).

## 7. Submit for App Review

App Store Connect → your app → Prepare for Submission:

- Upload screenshots from `/app/store/screenshots/{6.7,6.5,5.5}/`
- Paste `/app/store/description.txt` into "Description"
- Paste `/app/store/keywords.txt` into "Keywords"
- Paste `/app/store/whats-new.txt` into "What's New in This Version"
- Set Category: **Utilities**  (Bitcoin-mining themed)
- Pricing: Free + IAP
- Privacy URL: `https://satoshicloudminer.app/privacy`
- Support URL: `https://satoshicloudminer.app/support`
- Demo Account for review: `mbfalagario@gmail.com` /
  `SCMiner!Adm-9k4Vp2QrZxNb7sLe` (also shows Admin / Operator Console)

## 8. Apple App Review notes

Provide this note in App Review Information → Notes:

> Satoshi Cloud Miner is a cloud computing simulator with Bitcoin theming.
> Lightning withdrawals are real (powered by Blink Wallet, api.blink.sv)
> but the mining process itself is simulated for illustrative purposes —
> users buy hashpower plans, view AI-projected yield, and can withdraw
> credited sats over Lightning. The disclaimer is shown on Profile and
> in the App Store description. No external website is required to use
> the app.

## 9. Production go-live checklist

- [ ] `EXPO_PUBLIC_BACKEND_URL` points to your production API (HTTPS)
- [ ] `JWT_SECRET_KEY` rotated to a long random string
- [ ] `ADMIN_INITIAL_PASSWORD` rotated and saved in a password manager
- [ ] Blink wallet funded above 100k sats
- [ ] `EMERGENT_LLM_KEY` quota verified for the expected daily volume
- [ ] MongoDB backup schedule configured
- [ ] `app.json` `version` and `buildNumber` incremented for each upload
- [ ] All IAP product IDs created, priced, and submitted for review
