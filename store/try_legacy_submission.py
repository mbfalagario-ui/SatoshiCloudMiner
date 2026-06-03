#!/usr/bin/env python3
"""Try the LEGACY appStoreVersionSubmissions endpoint. Apple's deprecated
v1 submission auto-bundles all IAPs that are in WAITING_FOR_REVIEW with
the appStoreVersion. Many developers report it works when the new
reviewSubmissions endpoint refuses to add a REJECTED version.

Read-only inspect first, then try.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def main() -> int:
    with a._http() as c:
        # First check if there's already an open appStoreVersionSubmission
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionSubmission",
                  headers=a._headers())
        print(f"existing appStoreVersionSubmission: HTTP {r.status_code}")
        if r.status_code == 200:
            d = r.json().get("data")
            if d:
                print(f"  id: {d.get('id')}")
                print(f"  attributes: {d.get('attributes')}")
                # If exists, delete it first
                print("  DELETing existing submission…")
                dr = c.delete(f"/v1/appStoreVersionSubmissions/{d['id']}",
                              headers=a._headers())
                print(f"  delete HTTP {dr.status_code}: {dr.text[:200]}")
            else:
                print(f"  empty data")
        else:
            print(f"  {r.text[:300]}")

        # Now try to POST a fresh appStoreVersionSubmission
        print()
        print("Creating fresh appStoreVersionSubmission (legacy v1)…")
        r = c.post("/v1/appStoreVersionSubmissions",
                   headers=a._headers(),
                   json={
                       "data": {
                           "type": "appStoreVersionSubmissions",
                           "relationships": {
                               "appStoreVersion": {
                                   "data": {"type": "appStoreVersions",
                                            "id": VERSION_ID}
                               }
                           }
                       }
                   })
        print(f"HTTP {r.status_code}")
        print(f"  {r.text[:600]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
