#!/usr/bin/env python3
"""Fix the 10 IAPs Apple flagged with DEVELOPER_ACTION_NEEDED:
  1. Sync internal name (referenceName) = localized display name
     so reviewers don't see "Mega Farm" vs "Mega Rig" mismatch.
  2. Rewrite localized descriptions to drop "for 30 days" — that's
     subscription language on a CONSUMABLE product (Guideline 3.1.2(b)
     landmine).
  3. Refresh review notes so reviewer knows exactly what the IAP does.

Read-only audit + dry-run prints proposed changes first. Pass --apply
to actually PATCH.
"""
from __future__ import annotations
import sys, argparse
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a


# Canonical SKU → (referenceName, displayName, description, reviewNote)
CANONICAL = {
    "welcome_199": (
        "Newcomer Boost",
        "Newcomer Boost",
        "One-time, single-use 50 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 50 GH/s to the user's virtual cloud-mining rig once. Server-side accounting only; no on-device computation. Not a subscription. Pricing reflects operational compute costs.",
    ),
    "rookie_299": (
        "Daily Booster",
        "Daily Booster",
        "One-time, single-use 100 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 100 GH/s to the user's virtual cloud-mining rig once. Server-side accounting only.",
    ),
    "pro_499": (
        "Pro Rig",
        "Pro Rig",
        "One-time, single-use 230 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 230 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "elite_999": (
        "Elite Rig",
        "Elite Rig",
        "One-time, single-use 500 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 500 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "ultra_1999": (
        "Ultra Rig",
        "Ultra Rig",
        "One-time, single-use 1100 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 1100 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "mega_4999": (
        "Mega Rig",
        "Mega Rig",
        "One-time, single-use 2300 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 2300 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "giga_9999": (
        "Giga Rig",
        "Giga Rig",
        "One-time, single-use 3500 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 3500 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "titan_14999": (
        "Titan Rig",
        "Titan Rig",
        "One-time, single-use 4700 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 4700 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "colossus_19999": (
        "Colossus Rig",
        "Colossus Rig",
        "One-time, single-use 7500 GH/s hashpower credit applied to your cloud rig immediately upon purchase. No subscription, no recurring charges.",
        "Consumable, single-use hashpower boost credit. Adds 7500 GH/s to the user's virtual cloud-mining rig once.",
    ),
    "adfree_399": (
        "Ad-Free + Priority Support",
        "Ad-Free + Priority Support",
        "Permanent, non-consumable upgrade that removes interstitial cross-promotional content from the app and grants access to a priority email support queue. Single purchase, lifetime entitlement.",
        "Non-consumable lifetime entitlement. Removes interstitial cross-promotion in-app and enables priority email support. No subscription.",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually PATCH ASC. Default is dry-run.")
    args = parser.parse_args()

    with a._http() as c:
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = sorted(r.json().get("data", []),
                      key=lambda i: i["attributes"]["productId"])

        for iap in iaps:
            iid = iap["id"]
            pid = iap["attributes"]["productId"]
            cur_name = iap["attributes"].get("name", "")
            cur_note = (iap["attributes"].get("reviewNote") or "")

            if pid not in CANONICAL:
                print(f"  ⚠ {pid} not in canonical map — skipping")
                continue
            ref_name, disp_name, desc, note = CANONICAL[pid]

            print(f"\n──────────  {pid}  ──────────")
            if cur_name != ref_name:
                print(f"  ref-name: {cur_name!r} → {ref_name!r}")
            if cur_note != note:
                print(f"  note    : {cur_note[:60]}… → {note[:60]}…")

            if args.apply:
                # 1. Update internal/reference name + review note
                rr = c.patch(f"/v2/inAppPurchases/{iid}",
                             headers=a._headers(),
                             json={"data": {"type": "inAppPurchases",
                                            "id": iid,
                                            "attributes": {
                                                "name": ref_name,
                                                "reviewNote": note,
                                            }}})
                ok1 = rr.status_code < 400
                print(f"    PATCH IAP attrs → HTTP {rr.status_code}"
                      + ("" if ok1 else f"  {rr.text[:200]}"))

            # 2. Update en-US localization
            rr = c.get(f"/v2/inAppPurchases/{iid}/inAppPurchaseLocalizations",
                       headers=a._headers(), params={"limit": 20})
            locs = rr.json().get("data", [])
            en_loc = next((l for l in locs
                           if l["attributes"].get("locale") == "en-US"), None)
            if en_loc:
                loc_id = en_loc["id"]
                cur_disp = en_loc["attributes"].get("name", "")
                cur_desc = en_loc["attributes"].get("description", "")
                if cur_disp != disp_name:
                    print(f"  disp-name: {cur_disp!r} → {disp_name!r}")
                if cur_desc != desc:
                    print(f"  desc    : {cur_desc[:60]}… → {desc[:60]}…")

                if args.apply:
                    rr = c.patch(f"/v1/inAppPurchaseLocalizations/{loc_id}",
                                 headers=a._headers(),
                                 json={"data": {"type": "inAppPurchaseLocalizations",
                                                "id": loc_id,
                                                "attributes": {
                                                    "name": disp_name,
                                                    "description": desc,
                                                }}})
                    ok2 = rr.status_code < 400
                    print(f"    PATCH localization → HTTP {rr.status_code}"
                          + ("" if ok2 else f"  {rr.text[:200]}"))

    return 0


if __name__ == "__main__":
    sys.exit(main())
