#!/usr/bin/env python3
"""Update reviewer notes for Build #27 — Restore Purchases compliance
fix per Apple Guideline 3.1.1, plus corrected contact name (Michael
Falagario, not Marcus). Max 4000 chars.
"""
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"

NOTES = """HASHRATE CLOUD MINER — v1.0.2 reviewer notes (Build #27)

WHAT CHANGED IN BUILD #27 (vs #26)
Per your 3.1.1 feedback we added an explicit user-initiated Restore
Purchases action.
  • Visible "Restore" button at the top-right of the Store tab.
  • Tapping it calls react-native-iap.getAvailablePurchases() which
    invokes StoreKit (StoreKit2 Transaction.currentEntitlements) and
    returns all previously-purchased entitlements on this Apple ID.
  • Frontend forwards each (transactionId, productId) to a new
    backend endpoint POST /api/iap/restore.
  • Backend verifies each transactionId with Apple's App Store Server
    API and idempotently re-grants any entitlement this user is
    missing — across reinstalls and different devices on the same
    Apple ID. Already-owned items return "skipped". Bad transactions
    return "error" with a precise reason.
  • Toast reports how many were restored, skipped, or errored.
  • Verified live against production: POST /api/iap/restore returns
    HTTP 200 with the full counts; the 402 StoreKit gate from #26
    remains in place for /packages/buy.

(A) ANSWERS TO YOUR 3 CRYPTO QUESTIONS (2.1)
1. Mining: NOWHERE on the user's device. No proof-of-work, no
   hashing, no background compute. The app is a display-only
   DASHBOARD; hashpower is a virtual number kept server-side and
   incremented when the user buys an IAP, watches an ad, or does a
   daily check-in. There is no off-device mining pool either —
   yields are an indicator funded by IAP revenue, explicitly
   labeled "indicative" and "illustrative".
2. Wallet features: NONE. No private keys, no seed phrase, no
   on-chain custody. The user provides a Lightning Network address
   they already control (BOLT11 invoice or LN address such as
   user@speed.app, user@zbd.gg). Payouts route through Blink
   Lightning (blink.sv — regulated LN provider). The app never
   holds on-chain funds, never enables receiving from third
   parties, never exposes private keys.
3. Other crypto features: Display-only. BTC/USD ticker (CoinGecko
   + mempool.space), virtual hashpower, accumulated sats balance.
   NO trading, NO exchange, NO NFTs, NO DEX, NO staking, NO ICO,
   NO off-ramps other than the Lightning payout described above.

(B) HOW TO TEST
1. Install Build #27 from TestFlight.
2. Sign in: appreview1@hashratecloudminer.app / AppReview2026!
   (also appreview2, appreview3 — same password)
3. Shop tab → tap any pack: NATIVE STOREKIT SHEET appears
   ([Environment: Sandbox] badge); hashpower granted server-side
   only after Apple validates the transactionId.
4. Shop tab → tap "Restore" (top-right): re-fetches entitlements
   from Apple, server re-grants anything missing on this account.
   Verified end-to-end on iPad Air 11" M3 and iPhone 17 Pro Max.
5. Profile → "Delete account" → double-confirm → account + all
   data erased; signed out (5.1.1(v)).

(C) IAP CATALOG — 10 products, all single-purchase
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

⚠ IAP en-US descriptions: still locked in REJECTED state due to a
documented ASC API bug (PATCH → 409, DELETE → 500). en-GB
localizations + IAP reviewNote fields are correct. Apple Support
intervention required to unstick; approving this build itself
unsticks them.

(D) INFRASTRUCTURE
Backend: api.hashratecloudminer.com (Fly.io always-on, blue-green
deploy). LN payouts: Blink Lightning. Ads: AdMob rewarded only.

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
    print("✅ reviewer notes refreshed for Build #27 — name corrected to Michael, Restore section added")
    return 0


if __name__ == "__main__":
    sys.exit(main())
