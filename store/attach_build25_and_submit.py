#!/usr/bin/env python3
"""Wait until Apple processes Build #25, attach to v1.0.2, create a new
review submission, and submit it. One-shot script.
"""
import sys, time, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def find_build_25(c):
    for prefix in ["filter[preReleaseVersion.version]=1.0.2&filter[version]=25",
                   "filter[version]=25"]:
        r = c.get(f"/v1/builds?filter[app]={APP_ID}&{prefix}",
                  headers=a._headers())
        for b in r.json().get("data", []):
            if b["attributes"].get("version") == "25":
                return b
    return None


def main():
    # Wait up to 15 min for processing
    deadline = time.time() + 15 * 60
    build = None
    with a._http() as c:
        while time.time() < deadline:
            b = find_build_25(c)
            if b:
                st = b["attributes"].get("processingState")
                print(f"  Build #25 found id={b['id']} processingState={st}", flush=True)
                if st == "VALID":
                    build = b
                    break
                if st == "FAILED":
                    print("❌ build processing FAILED")
                    return 1
            else:
                print("  Build #25 not visible to ASC yet…", flush=True)
            time.sleep(30)

        if not build:
            print("⏱ build not VALID within 15 min — Apple still processing")
            print("   You can finish manually by running this script again")
            return 2

        # Cancel any active submissions
        r = c.get("/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"filter[app]": APP_ID,
                          "filter[platform]": "IOS",
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

        # Attach Build #25 to v1.0.2
        print(f"\n  Attaching Build #25 (id={build['id']}) to v1.0.2…")
        r = c.patch(f"/v1/appStoreVersions/{VERSION_ID}/relationships/build",
                    headers=a._headers(),
                    json={"data": {"type": "builds", "id": build["id"]}})
        print(f"    HTTP {r.status_code}")

        # Create + submit review
        print("\n  Creating new review submission…")
        r = c.post("/v1/reviewSubmissions",
                   headers=a._headers(),
                   json={"data": {
                       "type": "reviewSubmissions",
                       "attributes": {"platform": "IOS"},
                       "relationships": {
                           "app": {"data": {"type": "apps", "id": APP_ID}}
                       },
                   }})
        sub_id = r.json()["data"]["id"]
        print(f"    submission id={sub_id}")

        # Attach the version
        r = c.post("/v1/reviewSubmissionItems",
                   headers=a._headers(),
                   json={"data": {
                       "type": "reviewSubmissionItems",
                       "relationships": {
                           "appStoreVersion": {
                               "data": {"type": "appStoreVersions", "id": VERSION_ID}
                           },
                           "reviewSubmission": {
                               "data": {"type": "reviewSubmissions", "id": sub_id}
                           },
                       }
                   }})
        print(f"  attach version: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"   {r.text[:400]}")
            return 1

        # Submit
        r = c.patch(f"/v1/reviewSubmissions/{sub_id}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions",
                                   "id": sub_id,
                                   "attributes": {"submitted": True}}})
        print(f"\n  submit: HTTP {r.status_code}")
        if r.status_code >= 400:
            print(r.text[:400])
            return 1
        st = r.json()["data"]["attributes"].get("state")
        print(f"\n✅ Submitted. submission={sub_id} state={st}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
