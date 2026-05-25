# Sandbox IAP Testing — Step-by-Step

> Only works on a **real device** running a TestFlight or development build
> of Satoshi Cloud Miner. The web preview and Expo Go cannot trigger Apple's
> in-app purchase sheet.

## 1. Create a Sandbox Tester (one time)

1. Open https://appstoreconnect.apple.com → **Users and Access** → **Sandbox**
   → **Testers** → "+"
2. Fill in any email that you control (Apple sends a confirmation, but you
   can use a never-existed alias like `scm.sandbox.tester1@yourdomain.com`).
3. Set First/Last name, password, region (must match your IAP region),
   birthdate.
4. Save.

> ⚠️ Do **not** sign in to this account in `Settings → Apple ID`. Sandbox
> testers must only be signed in under `Settings → App Store → Sandbox
> Account` (step 3 below).

## 2. Make sure IAP products exist and are "Ready to Submit"

Each in-app purchase in App Store Connect must:
- Have the **exact same Product ID** as the backend `SHOP_PACKAGES` entries
  (`starter_099`, `welcome_199`, `rookie_299`, `pro_499`, `elite_999`,
  `ultra_1999`, `mega_4999`, `giga_9999`, `titan_14999`, `colossus_19999`)
- Be type **Consumable**
- Have a localized **display name** and **description** filled in for every
  language tied to your app
- Have a price tier assigned (matching the USD price in `SHOP_PACKAGES`)
- Status: **Ready to Submit** (or already Approved)

If status is "Missing Metadata" → click in, fill remaining fields, hit Save.

## 3. Install the build on a real iPhone

After `eas build --platform ios --profile preview` (or `production`) finishes:

- **TestFlight path** (recommended): `eas submit --platform ios --latest`
  → in ~10 min App Store Connect → TestFlight → invite yourself as
  internal tester → install via TestFlight app on the iPhone.
- **Internal install path**: in the EAS build details page click "Install"
  → scan the QR code on the iPhone → install profile → install build.

## 4. Sign the iPhone into your Sandbox Tester

1. On iPhone: **Settings → App Store**
2. Scroll to bottom → **Sandbox Account**
3. Sign in with the sandbox tester email + password you created in step 1.

Now any IAP triggered by **non-production** signed builds (TestFlight or
dev) will charge the sandbox tester instead of a real card.

## 5. Trigger a purchase

1. Open Satoshi Cloud Miner on the iPhone.
2. Sign up / sign in.
3. Tap **Mine** tab → tap **Buy $0.99** on the Starter Boost card.
4. Confirm in the dialog → Apple's native purchase sheet appears.
5. Face ID / passcode confirm → "You're all set".
6. The app shows "Purchase successful — 1 miner added".

## 6. Confirm receipt validation hit the backend

Tail the backend log right after the purchase:

```bash
ssh your-server "tail -n 50 /var/log/supervisor/backend.out.log"
```

You should see:

```
INFO:  ... - "POST /api/packages/buy HTTP/1.1" 200 OK
```

If `verify_apple_transaction` succeeded, the response includes
`apple.verified: true` and `apple.environment: "Sandbox"`.  
If Apple JWS auth still fails it returns 200 with
`apple.environment: "AUTH_FAILED_FALLBACK"` — fix the JWT credentials
before going to App Review.

## 7. Common sandbox failures

| Symptom                                  | Fix                                                                          |
|------------------------------------------|------------------------------------------------------------------------------|
| Purchase sheet shows "Cannot connect"    | iPhone is signed into a real Apple ID at Settings → App Store. Sign out.     |
| Product list returns empty in app        | IAP not in "Ready to Submit" yet — set the price tier + display name.        |
| "Your purchase could not be completed"   | Sandbox tester region ≠ app pricing region. Recreate tester in correct region|
| Receipt validation 401 in backend log    | Issuer ID or Key ID in `backend/.env` doesn't match the in-app-purchase key. |
| Same purchase keeps re-prompting          | StoreKit is redelivering an unfinished transaction; backend already calls    |
|                                          | `finishTransaction` in `src/utils/iap.ts` — make sure the latest build is on |
|                                          | the device.                                                                  |

## 8. Reset / repeat

To test the BOGO product or any consumable again:

1. iPhone: Settings → App Store → Sandbox Account → Manage → **Clear
   Purchase History** (this lets sandbox products be re-purchased).
2. Or sign out and back into a different sandbox tester.
