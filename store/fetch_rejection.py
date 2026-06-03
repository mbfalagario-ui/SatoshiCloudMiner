#!/usr/bin/env python3
"""Fetch the EXACT rejection message(s) from App Store Connect for the
latest submission. No interpretation, just raw Apple text."""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

SUB_ID = "6db2a564-fada-4716-b44b-fa1ddfedda56"
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def dump(label, obj):
    print(f"\n----- {label} -----")
    print(json.dumps(obj, indent=2, default=str)[:4000])


def main() -> int:
    with a._http() as c:
        # 1. Submission state
        r = c.get(f"/v1/reviewSubmissions/{SUB_ID}", headers=a._headers())
        dump("REVIEW SUBMISSION", r.json())

        # 2. Submission items
        r = c.get(f"/v1/reviewSubmissions/{SUB_ID}/items",
                  headers=a._headers(),
                  params={"include": "appStoreVersion,appCustomProductPageVersion"})
        dump("SUBMISSION ITEMS", r.json())

        # 3. Version state
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}",
                  headers=a._headers(),
                  params={"include": "appStoreReviewDetail"})
        dump("APP STORE VERSION", r.json())

        # 4. Look for actionable reviewer feedback / rejection reasons via
        # the betaAppReviewDetail/appReviewAttachments etc.
        endpoints = [
            f"/v1/appStoreVersions/{VERSION_ID}/customerReviews",
            f"/v1/apps/{a.APP_ID}/reviewSubmissions?filter[platform]=IOS&sort=-submittedDate&limit=5",
        ]
        for ep in endpoints:
            r = c.get(ep, headers=a._headers())
            print(f"\n----- {ep} HTTP {r.status_code} -----")
            print(r.text[:1500])

        # 5. List ALL submissions for full picture
        r = c.get("/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"filter[app]": a.APP_ID, "filter[platform]": "IOS",
                          "limit": 10, "sort": "-submittedDate"})
        print("\n----- ALL RECENT SUBMISSIONS -----")
        for s in r.json().get("data", []):
            at = s["attributes"]
            print(f"  {s['id']}  state={at.get('state'):<22} submittedDate={at.get('submittedDate')}")

        # 6. IAP states
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        print("\n----- IAP STATES -----")
        for i in sorted(r.json().get("data", []),
                        key=lambda i: i["attributes"]["productId"]):
            print(f"  {i['attributes']['productId']:<22} {i['attributes']['state']}")

        # 7. Build state
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/build", headers=a._headers())
        if r.status_code == 200:
            bd = r.json().get("data")
            if bd:
                rb = c.get(f"/v1/builds/{bd['id']}", headers=a._headers())
                print(f"\n----- BUILD -----")
                print(json.dumps(rb.json()["data"]["attributes"], indent=2, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
