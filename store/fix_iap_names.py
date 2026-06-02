#!/usr/bin/env python3
"""STEP 2 — Fix all IAP localized names to match SHOP_PACKAGES.

Apple specifically flagged 3 (Giga Farm / Titan Farm / Colossus Farm)
but the audit found 7 total mismatches. We fix every one in a single
script run. Zero EAS credits — pure ASC metadata PATCH.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

# (productId → desired localized name + description)
# Apple's inAppPurchaseLocalization.description is limited to 45 chars.
TARGETS = {
    "welcome_199":    ("Newcomer Boost",             "50 GH/s for 30 days. +15% bonus once."),
    "rookie_299":     ("Daily Booster",              "100 GH/s for 30 days. +19% bonus once."),
    "pro_499":        ("Pro Rig",                    "230 GH/s for 30 days. +24% bonus once."),
    "elite_999":      ("Elite Rig",                  "500 GH/s for 30 days. +28% bonus once."),
    "ultra_1999":     ("Ultra Rig",                  "1100 GH/s for 30 days. +33% bonus once."),
    "mega_4999":      ("Mega Rig",                   "2300 GH/s for 30 days. +37% bonus once."),
    "giga_9999":      ("Giga Rig",                   "3500 GH/s for 30 days. +42% bonus once."),
    "titan_14999":    ("Titan Rig",                  "4700 GH/s for 30 days. +46% bonus once."),
    "colossus_19999": ("Colossus Rig",               "7500 GH/s for 30 days. +50% bonus once."),
    "adfree_399":     ("Ad-Free + Priority Support", "Removes ads. Priority support queue."),
}


def main():
    print("=" * 70)
    print("  STEP 2 — Renaming IAPs to match SHOP_PACKAGES (zero EAS credits)")
    print("=" * 70)
    with a._http() as c:
        # Fetch all IAPs with their localizations
        r = c.get(
            f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
            headers=a._headers(),
            params={"limit": 50, "include": "inAppPurchaseLocalizations"},
        )
        body = r.json()
        iaps = body.get("data", [])
        locs = {x["id"]: x for x in body.get("included", [])
                if x.get("type") == "inAppPurchaseLocalizations"}

        for iap in iaps:
            attrs = iap.get("attributes") or {}
            pid = attrs.get("productId")
            target = TARGETS.get(pid)
            if not target:
                print(f"  ℹ️  {pid}: no target — skip")
                continue
            new_name, new_desc = target
            rels = (iap.get("relationships") or {}).get(
                "inAppPurchaseLocalizations", {}).get("data") or []
            patched = False
            for rel in rels:
                ld = locs.get(rel["id"])
                if not ld: continue
                la = ld.get("attributes") or {}
                if la.get("locale") != "en-US":
                    continue
                cur_name = la.get("name")
                cur_desc = la.get("description") or ""
                if cur_name == new_name and cur_desc == new_desc:
                    print(f"  ✅ {pid}: already correct ({cur_name})")
                    patched = True
                    break
                body_patch = {
                    "data": {
                        "type": "inAppPurchaseLocalizations",
                        "id": ld["id"],
                        "attributes": {
                            "name": new_name,
                            "description": new_desc,
                        },
                    }
                }
                rr = c.patch(
                    f"/v1/inAppPurchaseLocalizations/{ld['id']}",
                    headers=a._headers(),
                    json=body_patch,
                )
                if rr.status_code >= 400:
                    print(f"  ❌ {pid} PATCH failed {rr.status_code}: {rr.text[:200]}")
                else:
                    print(f"  ✅ {pid}: \"{cur_name}\" → \"{new_name}\"")
                patched = True
                break
            if not patched:
                print(f"  ⚠️  {pid}: no en-US localization found")
    print()
    print("Done. Run audit to verify.")


if __name__ == "__main__":
    main()
