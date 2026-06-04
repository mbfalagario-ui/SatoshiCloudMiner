#!/usr/bin/env python3
"""Once Build #26 lands in TestFlight (processingState=VALID), swap it
onto v1.0.2 (replacing #25), create a new reviewSubmission, attach
the version, and submit. Loops with sane timeouts.
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def find_build(c, want_version: str):
    r = c.get(f"/v1/builds?filter[app]={APP_ID}&filter[version]={want_version}&limit=5",
              headers=a._headers())
    for b in r.json().get("data", []):
        if b["attributes"].get("version") == want_version:
            return b
    return None


def main():
    deadline = time.time() + 25 * 60
    build = None
    with a._http() as c:
        # Wait for build #26 to be VALID
        while time.time() < deadline:
            b = find_build(c, "26")
            if b:
                st = b["attributes"].get("processingState")
                print(f"  build 26 id={b['id']} processingState={st}", flush=True)
                if st == "VALID":
                    build = b
                    break
                if st == "FAILED":
                    print("❌ build failed")
                    return 1
            else:
                print("  not visible to ASC yet…", flush=True)
            time.sleep(30)

        if not build:
            print("⏱ build 26 not VALID within 25 min")
            return 2

        # Cancel any in-flight submissions
        r = c.get("/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"filter[app]": APP_ID, "filter[platform]": "IOS",
                          "filter[state]": "READY_FOR_REVIEW,WAITING_FOR_REVIEW,UNRESOLVED_ISSUES,IN_REVIEW",
                          "limit": 20})
        for s in r.json().get("data", []):
            sid = s["id"]
            print(f"  cancelling old submission {sid} (state={s['attributes'].get('state')})")
            c.patch(f"/v1/reviewSubmissions/{sid}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions",
                                   "id": sid,
                                   "attributes": {"canceled": True}}})
            time.sleep(2)

        # Swap build #26 onto v1.0.2
        print(f"\n  attaching build 26 ({build['id']}) to v1.0.2…")
        r = c.patch(f"/v1/appStoreVersions/{VERSION_ID}/relationships/build",
                    headers=a._headers(),
                    json={"data": {"type": "builds", "id": build["id"]}})
        print(f"    HTTP {r.status_code}")

        # Nudge state (some metadata PATCH) so version is fresh
        r = c.patch(f"/v1/appStoreVersions/{VERSION_ID}",
                    headers=a._headers(),
                    json={"data": {"type": "appStoreVersions", "id": VERSION_ID,
                                   "attributes": {"copyright": "2026 Pastry Puffz Inc"}}})
        print(f"  metadata nudge: HTTP {r.status_code}")

        # Create + submit
        r = c.post("/v1/reviewSubmissions",
                   headers=a._headers(),
                   json={"data": {"type": "reviewSubmissions",
                                  "attributes": {"platform": "IOS"},
                                  "relationships": {
                                      "app": {"data": {"type": "apps", "id": APP_ID}}
                                  }}})
        sub_id = r.json()["data"]["id"]
        print(f"\n  submission id={sub_id}")

        r = c.post("/v1/reviewSubmissionItems",
                   headers=a._headers(),
                   json={"data": {
                       "type": "reviewSubmissionItems",
                       "relationships": {
                           "appStoreVersion": {"data": {"type": "appStoreVersions", "id": VERSION_ID}},
                           "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sub_id}}
                       }
                   }})
        print(f"  attach version: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"   {r.text[:400]}")
            return 1

        r = c.patch(f"/v1/reviewSubmissions/{sub_id}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions",
                                   "id": sub_id,
                                   "attributes": {"submitted": True}}})
        print(f"  submit: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:400])
            return 1
        time.sleep(6)
        r = c.get(f"/v1/reviewSubmissions/{sub_id}", headers=a._headers())
        st = r.json()["data"]["attributes"].get("state")
        print(f"\n✅ Submitted. submission={sub_id} state={st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
