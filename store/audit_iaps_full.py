#!/usr/bin/env python3
"""Full IAP audit — pull every field for every IAP so the moment we know
what Apple flagged, we can identify which IAP attribute is the problem.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a


def main() -> int:
    with a._http() as c:
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = sorted(r.json().get("data", []),
                      key=lambda i: i["attributes"]["productId"])

        print(f"Total IAPs: {len(iaps)}\n")
        for iap in iaps:
            iid = iap["id"]
            at = iap["attributes"]
            print("=" * 72)
            print(f"  {at['productId']:<22} state={at['state']}  type={at['inAppPurchaseType']}")
            print(f"     internal name : {at.get('name')}")
            print(f"     familySharable: {at.get('familySharable')}")
            print(f"     contentHosting: {at.get('contentHosting')}")
            print(f"     reviewNote    : {(at.get('reviewNote') or '')[:200]}")

            # Localization
            rr = c.get(f"/v2/inAppPurchases/{iid}/inAppPurchaseLocalizations",
                       headers=a._headers(), params={"limit": 20})
            for loc in rr.json().get("data", []):
                la = loc["attributes"]
                print(f"     loc[{la.get('locale')}]:")
                print(f"        name  : {la.get('name')}")
                print(f"        desc  : {(la.get('description') or '')[:140]}")
                print(f"        state : {la.get('state')}")

            # Screenshot
            rr = c.get(f"/v2/inAppPurchases/{iid}/appStoreReviewScreenshot",
                       headers=a._headers())
            sd = rr.json().get("data")
            if sd:
                sa = sd.get("attributes") or {}
                print(f"     screenshot   : state={sa.get('assetDeliveryState', {}).get('state')}  fileName={sa.get('fileName')}")
            else:
                print(f"     screenshot   : ❌ NONE")

            # Price schedule
            rr = c.get(f"/v2/inAppPurchases/{iid}/iapPriceSchedule",
                       headers=a._headers(),
                       params={"include": "manualPrices"})
            psd = rr.json().get("data")
            if psd:
                print(f"     priceSchedule: id={psd.get('id')}")
                inc = rr.json().get("included", []) or []
                for p in inc:
                    pa = p.get("attributes") or {}
                    print(f"        manualPrice: startDate={pa.get('startDate')} endDate={pa.get('endDate')}")
            else:
                print(f"     priceSchedule: ❌ NONE")

            # Availability
            rr = c.get(f"/v2/inAppPurchases/{iid}/inAppPurchaseAvailability",
                       headers=a._headers())
            ad = rr.json().get("data")
            if ad:
                aa = ad.get("attributes") or {}
                print(f"     availability : availableInNewTerritories={aa.get('availableInNewTerritories')}")
            else:
                print(f"     availability : ❌ NONE")

            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
