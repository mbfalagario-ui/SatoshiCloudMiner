#!/usr/bin/env python3
"""Exhaustively scan for any reviewer-message endpoint Apple may expose.
We already know customerReviews is empty. Try the long-tail endpoints."""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
SUB_ID = "6db2a564-fada-4716-b44b-fa1ddfedda56"
REVIEW_DETAIL_ID = "c53f1adc-e566-40aa-9672-c4c3efeaf5bf"
SUB_ITEM_ID = "NmRiMmE1NjQtZmFkYS00NzE2LWI0NGItZmExZGRmZWRkYTU2fDZ8ODg2MTIxMzg0"


def try_get(c, path, **params):
    print(f"\n>>> GET {path} params={params}")
    r = c.get(path, headers=a._headers(), params=params or None)
    print(f"  HTTP {r.status_code}")
    print(f"  {r.text[:1200]}")


def main() -> int:
    with a._http() as c:
        paths = [
            # review attachments (sometimes contain Apple's screenshots/messages)
            (f"/v1/appStoreReviewDetails/{REVIEW_DETAIL_ID}/appStoreReviewAttachments", {}),
            (f"/v1/appStoreReviewDetails/{REVIEW_DETAIL_ID}", {"include": "appStoreReviewAttachments"}),
            # review submission item details
            (f"/v1/reviewSubmissionItems/{SUB_ITEM_ID}", {}),
            # check IAP-level review screenshot & state extras
            (f"/v1/apps/{a.APP_ID}/inAppPurchasesV2", {"limit": 5,
                "include": "appStoreReviewScreenshot,iapPriceSchedule,inAppPurchaseLocalizations"}),
        ]
        for p, kw in paths:
            try_get(c, p, **kw)

        # Pull every IAP and inspect its individual relationships for a review-action field
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = r.json().get("data", [])
        if iaps:
            iap_id = iaps[0]["id"]
            print(f"\n=== Deep-scan IAP {iaps[0]['attributes']['productId']} (id={iap_id}) ===")
            # All relationships
            rr = c.get(f"/v2/inAppPurchases/{iap_id}", headers=a._headers())
            j = rr.json().get("data", {})
            rels = (j.get("relationships") or {}).keys()
            print("Relationships:", list(rels))
            print()
            # Print attributes in full
            print("Attributes:")
            print(json.dumps(j.get("attributes", {}), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
