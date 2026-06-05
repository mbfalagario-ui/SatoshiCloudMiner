#!/usr/bin/env python3
"""Submit Build #32 to Apple App Review (version 1.0.2).

This is the parallel-track submission per Michael's SUBMIT decision. The
crash on iOS 26.5 beta is most likely beta-specific; Apple reviewers run
stable iOS. If approved → done. If rejected → Build #33 (with the JS
exception fence and crash telemetry) is the fallback.
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # v1.0.2
TARGET_BUILD_VERSION = "32"


def find_build(c, want):
    r = c.get(f"/v1/builds?filter[app]={APP_ID}&filter[version]={want}&limit=5",
              headers=a._headers())
    for b in r.json().get("data", []):
        if b["attributes"].get("version") == want:
            return b
    return None


def main():
    with a._http() as c:
        # 1) Verify build #32 is VALID
        b = find_build(c, TARGET_BUILD_VERSION)
        if not b or b["attributes"].get("processingState") != "VALID":
            print(f"❌ Build #{TARGET_BUILD_VERSION} not VALID in ASC")
            return 1
        print(f"✓ Build #{TARGET_BUILD_VERSION} VALID, id={b['id']}")

        # 2) Cancel any stuck submissions
        r = c.get("/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"filter[app]": APP_ID, "filter[platform]": "IOS",
                          "filter[state]": "READY_FOR_REVIEW,WAITING_FOR_REVIEW,UNRESOLVED_ISSUES,IN_REVIEW",
                          "limit": 20})
        for s in r.json().get("data", []):
            sid = s["id"]
            st = s["attributes"].get("state")
            print(f"  cancelling old submission {sid} state={st}")
            c.patch(f"/v1/reviewSubmissions/{sid}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions", "id": sid,
                                   "attributes": {"canceled": True}}})
            time.sleep(2)

        # 3) Attach build #32 to v1.0.2
        print(f"  attaching build #{TARGET_BUILD_VERSION} to v1.0.2...")
        r = c.patch(f"/v1/appStoreVersions/{VERSION_ID}/relationships/build",
                    headers=a._headers(),
                    json={"data": {"type": "builds", "id": b["id"]}})
        print(f"  attach build: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:400]); return 1

        # 4) Create review submission
        r = c.post("/v1/reviewSubmissions",
                   headers=a._headers(),
                   json={"data": {"type": "reviewSubmissions",
                                  "attributes": {"platform": "IOS"},
                                  "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}})
        if r.status_code >= 400:
            print(f"❌ create reviewSubmission: HTTP {r.status_code} {r.text[:300]}")
            return 1
        sub_id = r.json()["data"]["id"]
        print(f"  submission id={sub_id}")

        # 5) Attach version to submission
        for attempt in range(3):
            r = c.post("/v1/reviewSubmissionItems",
                       headers=a._headers(),
                       json={"data": {
                           "type": "reviewSubmissionItems",
                           "relationships": {
                               "appStoreVersion": {"data": {"type": "appStoreVersions", "id": VERSION_ID}},
                               "reviewSubmission":  {"data": {"type": "reviewSubmissions", "id": sub_id}},
                           }
                       }})
            print(f"  attach item attempt {attempt+1}: HTTP {r.status_code}")
            if r.status_code < 400:
                break
            time.sleep(4)
        if r.status_code >= 400:
            print(r.text[:400]); return 1

        # 6) Submit
        r = c.patch(f"/v1/reviewSubmissions/{sub_id}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions", "id": sub_id,
                                   "attributes": {"submitted": True}}})
        print(f"  submit: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:400]); return 1

        time.sleep(6)
        r = c.get(f"/v1/reviewSubmissions/{sub_id}", headers=a._headers())
        st = r.json()["data"]["attributes"].get("state")
        print(f"\n✅ Build #{TARGET_BUILD_VERSION} submitted for App Review.")
        print(f"   submission={sub_id}  state={st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
