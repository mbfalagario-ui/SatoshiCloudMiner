#!/usr/bin/env python3
"""Audit the EXACT current state of:
- App Store Connect app
- App Store Versions (which build is attached, what state, what items)
- Review Submissions (active ones + items inside them)
- All 10 IAPs and their states
- Whether IAPs are reviewable / submittable / linked

Read-only. Run before any mutating action.
"""
from __future__ import annotations
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a


def main() -> int:
    with a._http() as c:
        print("=" * 70)
        print(" ASC APP")
        print("=" * 70)
        r = c.get(f"/v1/apps/{a.APP_ID}", headers=a._headers())
        app = r.json()["data"]
        print(f"  bundleId : {app['attributes']['bundleId']}")
        print(f"  sku      : {app['attributes']['sku']}")
        print(f"  name     : {app['attributes']['name']}")
        print(f"  primaryLocale: {app['attributes']['primaryLocale']}")
        print()

        # ── App Store Versions
        print("=" * 70)
        print(" APP STORE VERSIONS")
        print("=" * 70)
        r = c.get(f"/v1/apps/{a.APP_ID}/appStoreVersions",
                  headers=a._headers(), params={"limit": 20})
        versions = r.json().get("data", [])
        for v in versions:
            at = v["attributes"]
            print(f"  • {at.get('versionString'):<10} state={at.get('appStoreState'):<25} id={v['id']}")
            # build attached?
            rr = c.get(f"/v1/appStoreVersions/{v['id']}/build", headers=a._headers())
            if rr.status_code < 400:
                bd = rr.json().get("data")
                if bd:
                    rb = c.get(f"/v1/builds/{bd['id']}", headers=a._headers())
                    if rb.status_code < 400:
                        bdat = rb.json()["data"]["attributes"]
                        print(f"      build attached: v{bdat.get('version')} ({bdat.get('uploadedDate')})  proc={bdat.get('processingState')}")
                    else:
                        print(f"      build id: {bd['id']}")
                else:
                    print(f"      ⚠ no build attached")

        print()
        # ── Review Submissions
        print("=" * 70)
        print(" REVIEW SUBMISSIONS")
        print("=" * 70)
        r = c.get(f"/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"limit": 50,
                          "filter[app]": a.APP_ID,
                          "filter[platform]": "IOS"})
        subs = r.json().get("data", [])
        for s in subs:
            at = s["attributes"]
            print(f"  • id={s['id']}")
            print(f"      state={at.get('state')}  submitted={at.get('submitted')}  submittedDate={at.get('submittedDate')}")
            # items
            rr = c.get(f"/v1/reviewSubmissions/{s['id']}/items",
                       headers=a._headers(), params={"limit": 50})
            items = rr.json().get("data", [])
            print(f"      items ({len(items)}):")
            for it in items:
                rels = it.get("relationships") or {}
                kinds = []
                for k, v in rels.items():
                    d = (v or {}).get("data")
                    if d:
                        kinds.append(f"{k}={d.get('type')}/{d.get('id','?')[:10]}")
                ist = (it.get("attributes") or {}).get("state")
                print(f"         · item={it['id'][:14]} state={ist} {' '.join(kinds)}")
        if not subs:
            print("  (no submissions found)")
        print()

        # ── IAPs
        print("=" * 70)
        print(" IN-APP PURCHASES (v2)")
        print("=" * 70)
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = r.json().get("data", [])
        for i in iaps:
            at = i["attributes"]
            print(f"  • {at.get('productId'):<22} {at.get('state'):<28} id={i['id']}")
            # Check submission readiness
            rr = c.get(f"/v2/inAppPurchases/{i['id']}",
                       headers=a._headers(),
                       params={"include": "appStoreReviewScreenshot,iapPriceSchedule"})
            if rr.status_code < 400:
                included = rr.json().get("included", [])
                has_screenshot = any(x.get("type") == "inAppPurchaseAppStoreReviewScreenshots" for x in included)
                has_price = any(x.get("type") == "inAppPurchasePriceSchedules" for x in included)
                print(f"         screenshot={has_screenshot}  priceSchedule={has_price}")
        print()
        print(f"  TOTAL IAPs: {len(iaps)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
