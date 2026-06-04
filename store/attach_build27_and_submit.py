#!/usr/bin/env python3
"""Once Build #27 lands in TestFlight (processingState=VALID), swap it
onto v1.0.2 (replacing #26), create a new reviewSubmission, attach
the version, and submit.

Build #27 fixes Apple Rejection #6 (3.1.1 — missing Restore Purchases),
plus two pre-emptive fixes caught in the verification table:
  • machines.tsx now uses cryptoCoin image (was mining-rig PNG)
  • machines.tsx treats expires_at=null as "Permanent · Active"

Loops with sane timeouts.
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
TARGET_BUILD_VERSION = "27"


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
        # Wait for build #27 to be VALID
        while time.time() < deadline:
            b = find_build(c, TARGET_BUILD_VERSION)
            if b:
                st = b["attributes"].get("processingState")
                print(f"  build {TARGET_BUILD_VERSION} id={b['id']} processingState={st}", flush=True)
                if st == "VALID":
                    build = b
                    break
                if st == "FAILED":
                    print("❌ build failed Apple processing")
                    return 1
            else:
                print(f"  build {TARGET_BUILD_VERSION} not visible to ASC yet…", flush=True)
            time.sleep(30)

        if not build:
            print(f"⏱ build {TARGET_BUILD_VERSION} not VALID within 25 min")
            return 2

        # Cancel any in-flight submissions so the new one can be created
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

        # Swap build #27 onto v1.0.2
        print(f"\n  attaching build {TARGET_BUILD_VERSION} ({build['id']}) to v1.0.2…")
        r = c.patch(f"/v1/appStoreVersions/{VERSION_ID}/relationships/build",
                    headers=a._headers(),
                    json={"data": {"type": "builds", "id": build["id"]}})
        print(f"    HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"   {r.text[:400]}")
            return 1

        # Nudge state (small metadata PATCH) so version is fresh in ASC
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
        if r.status_code >= 400:
            print(f"❌ create reviewSubmission failed HTTP {r.status_code}: {r.text[:400]}")
            return 1
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
        print(f"\n✅ Submitted Build #{TARGET_BUILD_VERSION} for App Review.")
        print(f"   submission={sub_id}")
        print(f"   state={st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
