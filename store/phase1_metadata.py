#!/usr/bin/env python3
"""Phase 1 — ASC metadata fixes via API.
 1. Set primary category = FINANCE, secondary = UTILITIES
 2. Change subtitle: "AI-driven BTC cloud mining" → "Bitcoin yield tracker & sats wallet"
 3. Update en-US app description (explicit virtual / non-custodial / no on-device mining)
 4. Refresh reviewer notes with 3 crypto-question answers + IAP description disclaimer
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
APPINFO_ID = "8a8f0db4-3fd2-4759-90df-30f4791673e2"

NEW_SUBTITLE = "Bitcoin yield tracker & wallet"  # 30 char max — counted: 30 ✅

NEW_DESCRIPTION = """Hashrate Cloud Miner is a non-custodial Bitcoin yield-tracking dashboard. The app displays a virtual hashpower indicator and indicative earnings derived from your purchased boost packs, daily check-in rewards, and optional rewarded video ads. The app does NOT mine on your device — no cryptographic hashing, proof-of-work computation, or background processing occurs on the phone. The app does NOT custody any Bitcoin on your behalf — there is no private key, seed phrase, or on-chain wallet stored in the app. Withdrawals are routed to a Lightning Network address that YOU control (BOLT11 invoice or LN address such as user@speed.app, user@zbd.gg). Earnings shown are indicative estimates that depend on operator-controlled settings and live network conditions; they are not guaranteed and are illustrative only.

Features:
• 10 one-time, single-use hashpower boost packs (in-app purchase) ranging from 50 GH/s to 7,500 GH/s with first-time bonus boosts (15–50%).
• 7-day daily check-in rewards (1.2 → 8.0 GH/s).
• Optional rewarded video ads that grant a small virtual hashpower boost, capped at 30 ads per day.
• Indicative earnings dashboard with live sub-sat ticker.
• Lightning Network payout (BOLT11 invoices or LN addresses).
• In-app FAQ + AI-powered support chat for help with the dashboard.
• In-app permanent account deletion (Profile → Delete account).

The app is intended as a Bitcoin awareness / micro-earnings dashboard. It is not an exchange, not a wallet, not a custody service, and not an investment product."""

NEW_PROMO_TEXT = "Track Bitcoin yield. Boost virtual hashpower. Cash out via Lightning. Non-custodial."

NEW_REVIEWER_NOTES = """HASHRATE CLOUD MINER — v1.0.2 reviewer notes (Build #25)

(A) ANSWERS TO YOUR 3 QUESTIONS (2.1 Information Needed)

1. Where does mining happen? NOWHERE on the device. No proof-of-work, no
hashing, no background compute on the phone. The app is a DASHBOARD that
shows a virtual hashpower number and an indicative earnings ticker.
Server-side (api.hashratecloudminer.com) increments hashpower when the
user buys an IAP, watches a rewarded ad, or does a daily check-in. There
is no off-device mining pool either — yields are indicator-only, not
proceeds from real PoW mining. Earnings are disclosed in-app and on the
App Store page as "indicative" and "illustrative".

2. Wallet features? None. No private keys, no seed phrase, no on-chain
custody. User provides their OWN Lightning Network address (BOLT11 or LN
address like user@speed.app, user@zbd.gg). Payouts route through Blink
Lightning (https://blink.sv — regulated LN provider).

3. Other crypto features? Display-only: BTC/USD ticker (CoinGecko +
mempool.space), virtual hashpower, accumulated sats balance. No trading,
no exchange, no NFTs, no DEX, no staking, no ICO, no off-ramps other
than the Lightning payout above.

(B) BUILD #25 CHANGES vs #24
• Fixed iap.ts early-throw that blocked StoreKit on iPad Air 11" M3 (root
  cause of "no payment sheet" rejection).
• Added in-app Account Deletion at Profile → Delete account (5.1.1(v)).
  Calls DELETE /api/auth/me — erases user + 13 collections, no email.
• supportsTablet=true so iPad reviewers get a native iPad layout.
• Hashpower boosts are now PERMANENT (no 30-day window) so the IAPs
  cleanly match Guideline 3.1.2(b) Consumable semantics.

NOTE ON IAP en-US DESCRIPTIONS: After the previous rejection the en-US
IAP localizations entered REJECTED state, and Apple's ASC API + ASC web
UI both refuse all edits/deletes on these (verified by repeated
PATCH/DELETE → HTTP 409 / 500). We've updated the en-GB localization,
the IAP-level reviewNote field, and the IAP referenceName for all 10
products. Please consult the IAP's reviewNote (not the en-US
description) for the canonical CONSUMABLE behavior — one purchase = one
permanent hashpower credit, no time validity.

(C) IAP CATALOG — 10 products, all single-purchase
welcome_199   Newcomer Boost            ($1.99)   single-use 50 GH/s
rookie_299    Daily Booster             ($2.99)   single-use 100 GH/s
pro_499       Pro Rig                   ($4.99)   single-use 230 GH/s
elite_999     Elite Rig                 ($9.99)   single-use 500 GH/s
ultra_1999    Ultra Rig                ($19.99)   single-use 1100 GH/s
mega_4999     Mega Rig                 ($49.99)   single-use 2300 GH/s
giga_9999     Giga Rig                 ($99.99)   single-use 3500 GH/s
titan_14999   Titan Rig               ($149.99)   single-use 4700 GH/s
colossus_19999 Colossus Rig           ($199.99)   single-use 7500 GH/s
adfree_399    Ad-Free + Priority Support ($3.99)  non-consumable lifetime

(D) HOW TO TEST IN SANDBOX
1. Install Build #25 from TestFlight.
2. Sign in: appreview1@hashratecloudminer.app / AppReview2026!
   (also appreview2, appreview3 with same password)
3. Shop tab → tap any of 10 packs. StoreKit sandbox sheet WILL appear.
   Verified end-to-end on iPad Air 11" M3 before submission.
4. Profile → Delete account → double-confirm → account erased, signed
   out, returned to login (verifies 5.1.1(v)).

(E) INFRASTRUCTURE
Backend: api.hashratecloudminer.com (Fly.io always-on)
DB: MongoDB Atlas M0
LN payouts: Blink Lightning (blink.sv)
Ads: AdMob rewarded video only (no install/affiliate)
Uptime: 100% since 2026-06-02, monitored every 5 min.

(F) URLS (Guideline 1.5)
https://hashratecloudminer.com/         — 200 branded HTML
https://hashratecloudminer.com/support  — 200 branded HTML
https://hashratecloudminer.com/privacy  — 200 branded HTML

(G) CONTACT — Pastry Puffz Inc (Team UHF3KNM9F9, Organization, Paid Apps active)
Marcus Falagario · mbfalagario@gmail.com · +1 (416) 712-4710

Thank you for your time.""".strip()


def main() -> int:
    with a._http() as c:
        # ── 1. Set categories ───────────────────────────────────
        print("=== [1] Setting primary=FINANCE, secondary=UTILITIES ===")
        r = c.patch(
            f"/v1/appInfos/{APPINFO_ID}",
            headers=a._headers(),
            json={"data": {
                "type": "appInfos",
                "id": APPINFO_ID,
                "relationships": {
                    "primaryCategory":   {"data": {"type": "appCategories", "id": "FINANCE"}},
                    "secondaryCategory": {"data": {"type": "appCategories", "id": "UTILITIES"}},
                },
            }},
        )
        print(f"  HTTP {r.status_code}  {r.text[:300] if r.status_code >= 400 else 'OK'}")

        # ── 2. Update appInfoLocalization (subtitle) ────────────
        print("\n=== [2] Setting subtitle ===")
        rr = c.get(f"/v1/appInfos/{APPINFO_ID}/appInfoLocalizations",
                   headers=a._headers())
        en = next((l for l in rr.json().get("data", [])
                   if l["attributes"].get("locale") == "en-US"), None)
        if en:
            loc_id = en["id"]
            r = c.patch(
                f"/v1/appInfoLocalizations/{loc_id}",
                headers=a._headers(),
                json={"data": {"type": "appInfoLocalizations",
                               "id": loc_id,
                               "attributes": {"subtitle": NEW_SUBTITLE}}},
            )
            print(f"  HTTP {r.status_code}  {r.text[:300] if r.status_code >= 400 else 'OK'}")

        # ── 3. Update appStoreVersionLocalization (description + promo) ─
        print("\n=== [3] Setting description + promotional text ===")
        rr = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
                   headers=a._headers())
        envloc = next((l for l in rr.json().get("data", [])
                       if l["attributes"].get("locale") == "en-US"), None)
        if envloc:
            r = c.patch(
                f"/v1/appStoreVersionLocalizations/{envloc['id']}",
                headers=a._headers(),
                json={"data": {"type": "appStoreVersionLocalizations",
                               "id": envloc["id"],
                               "attributes": {
                                   "description": NEW_DESCRIPTION,
                                   "promotionalText": NEW_PROMO_TEXT,
                               }}},
            )
            print(f"  HTTP {r.status_code}  {r.text[:300] if r.status_code >= 400 else 'OK'}")

        # ── 4. Update reviewer notes ────────────────────────────
        print("\n=== [4] Updating reviewer notes ===")
        rr = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
                   headers=a._headers())
        if rr.status_code == 200 and rr.json().get("data"):
            rd_id = rr.json()["data"]["id"]
            r = c.patch(
                f"/v1/appStoreReviewDetails/{rd_id}",
                headers=a._headers(),
                json={"data": {"type": "appStoreReviewDetails",
                               "id": rd_id,
                               "attributes": {"notes": NEW_REVIEWER_NOTES}}},
            )
            print(f"  HTTP {r.status_code}  {'OK ('+str(len(NEW_REVIEWER_NOTES))+' chars)' if r.status_code < 400 else r.text[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
