#!/usr/bin/env python3
"""Update reviewer notes for Build #28 — Apple Guideline 2.1(a) fix.

Build #27 was rejected because the in-app "Watch Ad" feature was a
placeholder (a 5-second custom timer modal with a fake "Sponsored" label,
no real ad served). Build #28 replaces it with the official Google AdMob
SDK (`react-native-google-mobile-ads` v16.3.3) so Apple's reviewer sees
a real Google ad render when they tap Watch.

Max 4000 chars.
"""
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"

NOTES = """HASHRATE CLOUD MINER — v1.0.2 reviewer notes (Build #28)

WHAT CHANGED IN BUILD #28 (vs #27)
Per your Build #27 rejection (2.1(a) — "no ads available"):
the previous "Watch Ad" UI was a placeholder timer with no real
ad backend. Build #28 ships the actual Google AdMob SDK and a
real rewarded-ad flow:

  • Installed react-native-google-mobile-ads v16.3.3 (Invertase,
    official Google Mobile Ads RN wrapper, New-Arch compatible).
  • Installed expo-tracking-transparency for ATT prompt.
  • Info.plist now contains GADApplicationIdentifier
    (ca-app-pub-6035003811280283~6151737735), the full 83-entry
    SKAdNetworkItems list, and NSUserTrackingUsageDescription.
  • SDK is initialised at app launch (mobileAds().initialize())
    after the ATT prompt. A rewarded ad is preloaded immediately
    so the Watch button is responsive.
  • Home → "Watch ad — free hashrate" → button is DISABLED with
    label "Loading…" until the rewarded ad finishes loading. When
    the user taps Watch, the native Google ad fullscreen UI opens,
    plays, and on EARNED_REWARD fires the server credits the
    hashrate boost.
  • AdMob SSV: backend already had /api/ads/ssv_callback wired
    with the ADMOB_SSV_PUBLIC_KEY; Google now posts the signed
    SSV request alongside the client-side claim for defence-in-
    depth verification.
  • All Build #27 fixes preserved: Restore Purchases, Delete
    Account, StoreKit 402 gate, permanent IAP packs, Bitcoin coin
    image on /machines.

(A) ANSWERS TO YOUR 3 CRYPTO QUESTIONS (2.1)
1. Mining: NOWHERE on the user's device. No proof-of-work, no
   hashing, no background compute. The app is a display-only
   DASHBOARD; hashpower is a virtual number kept server-side and
   incremented when the user buys an IAP, watches an ad, or does a
   daily check-in. There is no off-device mining pool either —
   yields are an indicator funded by IAP + ad revenue, explicitly
   labeled "indicative" and "illustrative".
2. Wallet features: NONE. No private keys, no seed phrase, no
   on-chain custody. The user provides a Lightning Network address
   they already control (BOLT11 invoice or LN address such as
   user@speed.app). Payouts route through Blink Lightning
   (blink.sv — regulated LN provider).
3. Other crypto features: Display-only. BTC/USD ticker, virtual
   hashpower, accumulated sats. NO trading, NO exchange, NO NFTs,
   NO DEX, NO staking, NO ICO.

(B) HOW TO TEST
1. Install Build #28 from TestFlight on iPhone or iPad.
2. Sign in: appreview1@hashratecloudminer.app / AppReview2026!
3. Accept the ATT prompt on first launch.
4. Home → "Watch ad — free hashrate" → tap "Watch". A REAL
   Google AdMob rewarded video plays fullscreen. After the
   video completes, +0.5 GH/s boost is granted for 24h.
5. Store → tap any pack: NATIVE STOREKIT SHEET appears; the
   pack is granted server-side only after Apple validates the
   transactionId (402 gate from Build #26 preserved).
6. Store → tap "Restore" (top-right): re-fetches entitlements.
7. Profile → "Delete account" → erases everything (5.1.1(v)).

(C) IAP CATALOG — 10 products, all single-purchase, no subs
welcome_199    $1.99   single-use 50 GH/s
rookie_299     $2.99   single-use 100 GH/s
pro_499        $4.99   single-use 230 GH/s
elite_999      $9.99   single-use 500 GH/s
ultra_1999    $19.99   single-use 1100 GH/s
mega_4999     $49.99   single-use 2300 GH/s
giga_9999     $99.99   single-use 3500 GH/s
titan_14999  $149.99   single-use 4700 GH/s
colossus_19999 $199.99  single-use 7500 GH/s
adfree_399     $3.99   non-consumable lifetime ad-free

(D) INFRASTRUCTURE
Backend: api.hashratecloudminer.com (Fly.io always-on, blue-green
deploy). LN payouts: Blink Lightning. Ads: AdMob rewarded.

(E) CONTACT — Pastry Puffz Inc · Team UHF3KNM9F9
Michael Falagario · mbfalagario@gmail.com · +1 (416) 712-4710

Thank you for your time.""".strip()


def main():
    print(f"reviewer notes len: {len(NOTES)}")
    if len(NOTES) > 4000:
        print("❌ too long")
        return 1
    with a._http() as c:
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
                  headers=a._headers())
        rd_id = r.json()["data"]["id"]
        r = c.patch(f"/v1/appStoreReviewDetails/{rd_id}",
                    headers=a._headers(),
                    json={"data": {"type": "appStoreReviewDetails",
                                   "id": rd_id,
                                   "attributes": {"notes": NOTES}}})
        print(f"PATCH: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:400])
            return 1
    print("✅ reviewer notes refreshed for Build #28 — AdMob SDK fix documented")
    return 0


if __name__ == "__main__":
    sys.exit(main())
