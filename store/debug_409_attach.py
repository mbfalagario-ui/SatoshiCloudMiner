#!/usr/bin/env python3
"""Inspect why POST /reviewSubmissionItems returned 409 for v1.0.2."""
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # v1.0.2

with a._http() as c:
    print("=== ALL appStoreVersions for this app ===")
    r = c.get(f"/v1/apps/{APP_ID}/appStoreVersions?limit=20",
              headers=a._headers())
    for v in r.json().get("data", []):
        attrs = v["attributes"]
        print(f"  id={v['id']}  versionString={attrs.get('versionString')}  state={attrs.get('appStoreState')}  releaseType={attrs.get('releaseType')}")
    print()

    print(f"=== v1.0.2 ({VERSION_ID}) detail ===")
    r = c.get(f"/v1/appStoreVersions/{VERSION_ID}",
              headers=a._headers())
    attrs = r.json()["data"]["attributes"]
    for k in ("versionString", "appStoreState", "releaseType", "copyright", "earliestReleaseDate", "downloadable", "platform"):
        print(f"  {k}: {attrs.get(k)}")
    print()

    print("=== Most recent reviewSubmissions (all states) ===")
    r = c.get("/v1/reviewSubmissions",
              headers=a._headers(),
              params={"filter[app]": APP_ID, "filter[platform]": "IOS", "limit": 10})
    for s in r.json().get("data", []):
        print(f"  id={s['id']}  state={s['attributes'].get('state')}  platform={s['attributes'].get('platform')}  submittedDate={s['attributes'].get('submittedDate')}")
    print()

    print("=== Latest submission ababd766 — full ===")
    r = c.get("/v1/reviewSubmissions/ababd766-f1b0-4613-b911-923c75c208cd?include=items",
              headers=a._headers())
    print(json.dumps(r.json(), indent=2)[:2000])
    print()

    print("=== Try POST /reviewSubmissionItems again with FULL error body ===")
    r = c.post("/v1/reviewSubmissionItems",
               headers=a._headers(),
               json={"data": {
                   "type": "reviewSubmissionItems",
                   "relationships": {
                       "appStoreVersion": {"data": {"type": "appStoreVersions", "id": VERSION_ID}},
                       "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": "ababd766-f1b0-4613-b911-923c75c208cd"}}
                   }
               }})
    print(f"HTTP {r.status_code}")
    print(r.text)
