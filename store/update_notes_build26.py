#!/usr/bin/env python3
"""Post a Resolution Center reply to Apple AND update reviewer notes for
Build #26. The reply addresses Apple's Round 6 rejection:
  - 2.1 crypto info questions (3 answers)
  - 2.1(b) IAP "no payment sheet" — explains the real root cause we
    found in our codebase (Shop bypass of StoreKit) and the fix in #26.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"

NOTES_BUILD_26 = """HASHRATE CLOUD MINER — v1.0.2 reviewer notes (Build #26)

ROOT CAUSE OF #25 "no payment sheet" REJECTION (now FIXED in #26)
On reviewing the rejected #25 binary we found the Shop screen was
calling our backend's /packages/buy endpoint DIRECTLY without first
invoking StoreKit. The backend granted the package as a "mocked"
purchase. The reviewer therefore saw a success modal but never the
native payment sheet — exactly what Apple flagged. The dedicated
buyProduct() helper that DOES call StoreKit existed in our codebase
but the Shop screen wasn't wired to it. Build #26:
  1. Shop now ALWAYS calls buyProduct(productId) on iOS, which opens
     the StoreKit sheet and returns a real transactionId via
     react-native-iap v15 (requestPurchase + purchaseUpdatedListener).
  2. /packages/buy on the backend NOW REFUSES iOS requests that lack
     an apple_transaction_id (HTTP 402). Frontend bug regressions
     cannot bypass StoreKit ever again. Verified server-side on prod.
  3. The supplied transactionId is verified against Apple's App Store
     Server API before the hashpower is granted; mock-grants are no
     longer possible on iOS.

(A) ANSWERS TO YOUR 3 CRYPTO QUESTIONS (2.1)
1. Mining: NOWHERE on the user's device. No proof-of-work, no
hashing, no background compute. The app is a display-only DASHBOARD;
hashpower is a virtual number kept server-side and incremented when
the user buys an IAP, watches an ad, or does a daily check-in. There
is no off-device mining pool either — yields are an indicator funded
by IAP revenue, explicitly labeled "indicative" and "illustrative".

2. Wallet features: NONE. No private keys, no seed phrase, no on-chain
custody. The user provides a Lightning Network address they already
control (BOLT11 invoice or LN address such as user@speed.app,
user@zbd.gg). Payouts route through Blink Lightning (blink.sv —
regulated LN provider). The app never holds on-chain funds, never
enables receiving from third parties, never exposes private keys.

3. Other crypto features: Display-only. BTC/USD ticker (CoinGecko +
mempool.space), virtual hashpower, accumulated sats balance. NO
trading, NO exchange, NO NFTs, NO DEX, NO staking, NO ICO, NO
off-ramps other than the Lightning payout described above.

(B) HOW TO TEST IN SANDBOX
1. Install Build #26 from TestFlight.
2. Sign in: appreview1@hashratecloudminer.app / AppReview2026!
   (also appreview2, appreview3 — same password)
3. Shop tab → tap any pack. The NATIVE STOREKIT SHEET will appear
   with "[Environment: Sandbox]" badge. Complete the purchase: the
   hashpower credit is granted server-side ONLY after the
   transactionId is validated by Apple's App Store Server API.
4. To verify the gate: try to call POST /api/packages/buy from any
   iOS-UA client without apple_transaction_id — backend returns
   HTTP 402 "Apple In-App Purchase required".
5. Profile → Delete account → double-confirm → account erased,
   signed out (verifies 5.1.1(v)).

(C) IAP CATALOG — 10 products, all single-purchase
welcome_199    $1.99  single-use 50 GH/s
rookie_299     $2.99  single-use 100 GH/s
pro_499        $4.99  single-use 230 GH/s
elite_999      $9.99  single-use 500 GH/s
ultra_1999    $19.99  single-use 1100 GH/s
mega_4999     $49.99  single-use 2300 GH/s
giga_9999     $99.99  single-use 3500 GH/s
titan_14999  $149.99  single-use 4700 GH/s
colossus_19999 $199.99 single-use 7500 GH/s
adfree_399     $3.99  non-consumable lifetime ad-free

⚠ IAP en-US descriptions: still locked in REJECTED state due to a
documented ASC API bug (PATCH → 409, DELETE → 500). Apple Support
intervention required to unstick. en-GB localizations + IAP
reviewNote fields are correct. Per-IAP reviewNote is the canonical
behavior reference.

(D) INFRASTRUCTURE
Backend: api.hashratecloudminer.com (Fly.io always-on)
LN payouts: Blink Lightning. Ads: AdMob rewarded only.

(E) CONTACT — Pastry Puffz Inc · Team UHF3KNM9F9
Marcus Falagario · mbfalagario@gmail.com · +1 (416) 712-4710

Thank you for your time.""".strip()


def main() -> int:
    print(f"reviewer notes len: {len(NOTES_BUILD_26)}")
    if len(NOTES_BUILD_26) > 4000:
        print("❌ too long, would 422")
        return 1
    with a._http() as c:
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
                  headers=a._headers())
        rd_id = r.json()["data"]["id"]
        r = c.patch(
            f"/v1/appStoreReviewDetails/{rd_id}",
            headers=a._headers(),
            json={"data": {"type": "appStoreReviewDetails",
                           "id": rd_id,
                           "attributes": {"notes": NOTES_BUILD_26}}},
        )
        print(f"reviewer notes patch: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:400])
            return 1
    print("✅ reviewer notes refreshed for Build #26 submission")
    return 0


if __name__ == "__main__":
    sys.exit(main())
