#!/usr/bin/env python3
"""For each IAP, the en-US localization is in REJECTED state and refuses
edits. Workaround per Apple: DELETE the rejected localization, POST a
fresh one with corrected content. This is the documented "edit-rejected"
pattern.

Also re-checks all IAP states post top-level PATCH.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

# productId → (display name, description) — description MAX 45 chars per Apple
CANONICAL = {
    "welcome_199":    ("Newcomer Boost",             "One-time 50 GH/s boost credit"),
    "rookie_299":     ("Daily Booster",              "One-time 100 GH/s boost credit"),
    "pro_499":        ("Pro Rig",                    "One-time 230 GH/s boost credit"),
    "elite_999":      ("Elite Rig",                  "One-time 500 GH/s boost credit"),
    "ultra_1999":     ("Ultra Rig",                  "One-time 1100 GH/s boost credit"),
    "mega_4999":      ("Mega Rig",                   "One-time 2300 GH/s boost credit"),
    "giga_9999":      ("Giga Rig",                   "One-time 3500 GH/s boost credit"),
    "titan_14999":    ("Titan Rig",                  "One-time 4700 GH/s boost credit"),
    "colossus_19999": ("Colossus Rig",               "One-time 7500 GH/s boost credit"),
    "adfree_399":     ("Ad-Free + Priority Support", "Removes ads. Priority support."),
}


def main() -> int:
    with a._http() as c:
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = sorted(r.json().get("data", []),
                      key=lambda i: i["attributes"]["productId"])

        for iap in iaps:
            iid = iap["id"]
            pid = iap["attributes"]["productId"]
            if pid not in CANONICAL:
                continue
            disp_name, desc = CANONICAL[pid]
            print(f"\n──────────  {pid}  (state={iap['attributes']['state']})  ──────────")

            # Get current en-US localization
            rr = c.get(f"/v2/inAppPurchases/{iid}/inAppPurchaseLocalizations",
                       headers=a._headers(), params={"limit": 20})
            locs = rr.json().get("data", [])
            en_us = next((l for l in locs
                          if l["attributes"].get("locale") == "en-US"), None)
            en_gb = next((l for l in locs
                          if l["attributes"].get("locale") == "en-GB"), None)

            # Step 1: ensure an en-GB localization exists so en-US is not "last"
            if not en_gb:
                print(f"  [1/3] POST en-GB scaffold localization…")
                pr = c.post("/v1/inAppPurchaseLocalizations",
                            headers=a._headers(),
                            json={"data": {
                                "type": "inAppPurchaseLocalizations",
                                "attributes": {
                                    "locale": "en-GB",
                                    "name": disp_name,
                                    "description": desc,
                                },
                                "relationships": {
                                    "inAppPurchaseV2": {
                                        "data": {"type": "inAppPurchases", "id": iid}
                                    }
                                }
                            }})
                print(f"        HTTP {pr.status_code}")
                if pr.status_code >= 400:
                    print(f"        {pr.text[:300]}")
                    continue

            # Step 2: delete rejected en-US (now safe since en-GB exists)
            if en_us:
                lstate = en_us["attributes"].get("state")
                print(f"  [2/3] DELETE rejected en-US (state={lstate}) id={en_us['id']}…")
                dr = c.delete(f"/v1/inAppPurchaseLocalizations/{en_us['id']}",
                              headers=a._headers())
                print(f"        HTTP {dr.status_code}")
                if dr.status_code >= 400 and dr.status_code != 404:
                    print(f"        {dr.text[:300]}")
                    continue

            # Step 3: create fresh en-US with corrected content
            print(f"  [3/3] POST fresh en-US localization…")
            pr = c.post("/v1/inAppPurchaseLocalizations",
                        headers=a._headers(),
                        json={"data": {
                            "type": "inAppPurchaseLocalizations",
                            "attributes": {
                                "locale": "en-US",
                                "name": disp_name,
                                "description": desc,
                            },
                            "relationships": {
                                "inAppPurchaseV2": {
                                    "data": {"type": "inAppPurchases", "id": iid}
                                }
                            }
                        }})
            print(f"        HTTP {pr.status_code}")
            if pr.status_code >= 400:
                print(f"        {pr.text[:400]}")

    # Final state recap
    print("\n=== Final IAP states ===")
    with a._http() as c:
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        for i in sorted(r.json().get("data", []),
                        key=lambda i: i["attributes"]["productId"]):
            print(f"  {i['attributes']['productId']:<22} {i['attributes']['state']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
