#!/usr/bin/env python3
"""Now that v1.0.1 has been renamed to v1.0.2, add it (along with all
10 IAPs) to the empty READY_FOR_REVIEW submission 6db2a564 and submit.
"""
from __future__ import annotations
import sys, time, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # now v1.0.2
EMPTY_SUB_ID = "6db2a564-fada-4716-b44b-fa1ddfedda56"

REVIEWER_NOTES = """
================================================================
HASHRATE CLOUD MINER — v1.0.2 review (IAPs now bundled)
================================================================

(1) What changed since the v1.0.1 rejection
    Apple's reviewer for the previous attempt could not complete
    in-app purchases in sandbox because the 10 IAPs were not bundled
    in the same review submission as the binary. The IAPs were stuck
    in WAITING_FOR_REVIEW outside of any submission. This resubmission
    bundles all 10 IAPs together with the IDENTICAL binary (Build 24)
    in the SAME reviewSubmission, so sandbox StoreKit will resolve
    every product correctly.

(2) Binary
    Build 24, uploaded 2026-06-02, processingState=VALID. Already on
    TestFlight. No code, asset, or feature changes.
    Bundle ID: app.satoshicloudminer

(3) IAPs bundled (all 10, non-consumable + consumable)
        welcome_199    — Newcomer Boost                ($1.99)
        rookie_299     — Daily Booster                 ($2.99)
        pro_499        — Pro Rig                       ($4.99)
        elite_999      — Elite Rig                     ($9.99)
        ultra_1999     — Ultra Rig                     ($19.99)
        mega_4999      — Mega Rig                      ($49.99)
        giga_9999      — Giga Rig                      ($99.99)
        titan_14999    — Titan Rig                     ($149.99)
        colossus_19999 — Colossus Rig                  ($199.99)
        adfree_399     — Ad-Free + Priority Support    ($3.99)

(4) Sandbox verification
    1. Install Build 24 via TestFlight (already processed).
    2. Sign in with any of the pre-provisioned reviewer accounts:
          appreview1@hashratecloudminer.app  /  AppReview2026!
          appreview2@hashratecloudminer.app  /  AppReview2026!
          appreview3@hashratecloudminer.app  /  AppReview2026!
    3. Open the Shop tab. Tap any of the 10 packages — the StoreKit
       sandbox sheet will appear and complete with an "Environment:
       Sandbox" badge. Server-side, we validate the receipt via the
       App Store Server API and credit the user's virtual hashrate.

(5) Production backend
    All app traffic goes to api.hashratecloudminer.com (Fly.io
    always-on, MongoDB Atlas, 100% uptime monitor since 2026-06-02).

(6) Public URLs (Guideline 1.5)
    https://hashratecloudminer.com/         (HTTP 200, branded HTML)
    https://hashratecloudminer.com/support  (HTTP 200, branded HTML)
    https://hashratecloudminer.com/privacy  (HTTP 200, branded HTML)

(7) Contact
    mbfalagario@gmail.com / +1 (416) 712-4710 (24-h response SLA)

Thank you again for your time.
""".strip()


def main() -> int:
    with a._http() as c:
        # Sanity check: version state
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        v = r.json()["data"]["attributes"]
        print(f"Version: {v.get('versionString')}  state={v.get('appStoreState')}")
        assert v.get("versionString") == "1.0.2", "Expected v1.0.2"

        # Refresh reviewer notes on appStoreReviewDetail
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
                  headers=a._headers())
        if r.status_code == 200 and r.json().get("data"):
            rd_id = r.json()["data"]["id"]
            print(f"reviewDetail id: {rd_id}")
            rr = c.patch(f"/v1/appStoreReviewDetails/{rd_id}",
                         headers=a._headers(),
                         json={"data": {"type": "appStoreReviewDetails",
                                        "id": rd_id,
                                        "attributes": {"notes": REVIEWER_NOTES}}})
            print(f"  notes PATCH → {rr.status_code}")

        # Empty submission state
        r = c.get(f"/v1/reviewSubmissions/{EMPTY_SUB_ID}", headers=a._headers())
        print(f"Submission state: {r.json()['data']['attributes'].get('state')}")

        # Items currently in the submission
        r = c.get(f"/v1/reviewSubmissions/{EMPTY_SUB_ID}/items", headers=a._headers())
        items = r.json().get("data", [])
        print(f"Submission has {len(items)} items already")

        def add_item(rel_key: str, rel_type: str, item_id: str, label: str) -> bool:
            body = {"data": {
                "type": "reviewSubmissionItems",
                "relationships": {
                    rel_key: {"data": {"type": rel_type, "id": item_id}},
                    "reviewSubmission": {
                        "data": {"type": "reviewSubmissions", "id": EMPTY_SUB_ID}
                    },
                }
            }}
            rr = c.post("/v1/reviewSubmissionItems",
                        headers=a._headers(), json=body)
            ok = rr.status_code < 400
            tag = "✅" if ok else "❌"
            print(f"   {tag} {label:<48} HTTP {rr.status_code}")
            if not ok:
                print(f"      {rr.text[:300]}")
            return ok

        # 1. Add the version
        print("\n[A] Adding appStoreVersion v1.0.2…")
        ok = add_item("appStoreVersion", "appStoreVersions", VERSION_ID,
                      "appStoreVersion v1.0.2")
        if not ok:
            print("FATAL: cannot attach version. Stopping.")
            return 1

        # 2. Add all 10 IAPs
        print("\n[B] Adding 10 IAPs…")
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = sorted(r.json().get("data", []),
                      key=lambda i: i["attributes"]["productId"])
        added = 0
        for iap in iaps:
            pid = iap["attributes"]["productId"]
            if add_item("inAppPurchaseV2", "inAppPurchases", iap["id"], f"IAP {pid}"):
                added += 1
        print(f"\n  IAPs added: {added}/{len(iaps)}")

        # 3. Submit
        print("\n[C] PATCH submitted=True…")
        r = c.patch(f"/v1/reviewSubmissions/{EMPTY_SUB_ID}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions",
                                   "id": EMPTY_SUB_ID,
                                   "attributes": {"submitted": True}}})
        print(f"   HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"   body: {r.text[:600]}")
            return 1
        att = r.json()["data"]["attributes"]
        print(f"   ✅ state={att.get('state')}  submittedDate={att.get('submittedDate')}")

        # Poll
        print("\n[D] Polling until WAITING_FOR_REVIEW…")
        final_state = att.get("state")
        for i in range(20):
            time.sleep(4)
            r = c.get(f"/v1/reviewSubmissions/{EMPTY_SUB_ID}", headers=a._headers())
            final_state = r.json()["data"]["attributes"].get("state")
            print(f"  poll {i+1}: state={final_state}")
            if final_state in ("WAITING_FOR_REVIEW", "IN_REVIEW", "COMPLETE"):
                break

        # Final IAP states
        print("\n[E] Final IAP states:")
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        for iap in sorted(r.json().get("data", []),
                          key=lambda i: i["attributes"]["productId"]):
            print(f"   {iap['attributes']['productId']:<22} {iap['attributes']['state']}")

        # Save summary
        summary = {
            "version_id": VERSION_ID,
            "version_string": "1.0.2",
            "submission_id": EMPTY_SUB_ID,
            "iaps_added": added,
            "iaps_total": len(iaps),
            "final_state": final_state,
        }
        with open("/app/store/last_submission.json", "w") as f:
            json.dump(summary, f, indent=2)

        print()
        print("=" * 70)
        if added == len(iaps) and final_state in ("WAITING_FOR_REVIEW", "IN_REVIEW"):
            print(" 🎉 SUBMITTED WITH ALL 10 IAPs BUNDLED")
        else:
            print(" ⚠ Submission completed but check results above")
        print(f"     v1.0.2 + {added}/{len(iaps)} IAPs in {EMPTY_SUB_ID}")
        print(f"     state: {final_state}")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
