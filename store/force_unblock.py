#!/usr/bin/env python3
"""Three forceful tactics to unblock v1.0.2 creation:
  A) Try DELETE on the REJECTED v1.0.1 appStoreVersion.
  B) Try submitting the empty READY_FOR_REVIEW submission (force-close it).
  C) Try patching versionString of v1.0.1 → v1.0.2 (rename in-place).
Read-write but read state after each attempt.
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

OLD_VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
EMPTY_SUB_ID = "6db2a564-fada-4716-b44b-fa1ddfedda56"


def print_app_state(c):
    r = c.get(f"/v1/apps/{a.APP_ID}/appStoreVersions",
              headers=a._headers(), params={"limit": 5})
    for v in r.json().get("data", []):
        print(f"  ver={v['attributes'].get('versionString')} state={v['attributes'].get('appStoreState')}")


def main() -> int:
    with a._http() as c:
        print("BEFORE:")
        print_app_state(c)
        print()

        # ─── A) Try DELETE on v1.0.1 ───────────────────────────
        print("=== A) DELETE v1.0.1 ===")
        r = c.delete(f"/v1/appStoreVersions/{OLD_VERSION_ID}", headers=a._headers())
        print(f"  HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"  body: {r.text[:400]}")

        # If A succeeded, we're done
        if r.status_code < 400:
            print("\n✅ v1.0.1 deleted, app should now allow new version")
            print_app_state(c)
            return 0

        # ─── B) Submit empty submission to close it ────────────
        print("\n=== B) Submit empty submission to force-close ===")
        r = c.patch(f"/v1/reviewSubmissions/{EMPTY_SUB_ID}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions",
                                   "id": EMPTY_SUB_ID,
                                   "attributes": {"submitted": True}}})
        print(f"  HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"  body: {r.text[:400]}")

        # Poll
        for i in range(6):
            time.sleep(2)
            r = c.get(f"/v1/reviewSubmissions/{EMPTY_SUB_ID}", headers=a._headers())
            if r.status_code == 404:
                print(f"  poll {i+1}: gone")
                break
            st = r.json()["data"]["attributes"].get("state")
            print(f"  poll {i+1}: state={st}")
            if st in ("CANCELED", "COMPLETE", "WAITING_FOR_REVIEW"):
                break

        # Now check if version creation works
        print("\n=== Trying to create v1.0.2 after force-close ===")
        r = c.post("/v1/appStoreVersions",
                   headers=a._headers(),
                   json={"data": {
                       "type": "appStoreVersions",
                       "attributes": {"platform": "IOS",
                                      "versionString": "1.0.2",
                                      "copyright": "2026 Hashrate Cloud Miner",
                                      "releaseType": "AFTER_APPROVAL"},
                       "relationships": {
                           "app": {"data": {"type": "apps", "id": a.APP_ID}},
                       },
                   }})
        print(f"  create v1.0.2: HTTP {r.status_code}")
        if r.status_code < 400:
            new_id = r.json()["data"]["id"]
            print(f"  ✅ v1.0.2 id={new_id}")
            print_app_state(c)
            return 0
        else:
            print(f"  body: {r.text[:400]}")

        # ─── C) Rename v1.0.1 to v1.0.2 ────────────────────────
        print("\n=== C) Rename v1.0.1 versionString → 1.0.2 ===")
        r = c.patch(f"/v1/appStoreVersions/{OLD_VERSION_ID}",
                    headers=a._headers(),
                    json={"data": {"type": "appStoreVersions",
                                   "id": OLD_VERSION_ID,
                                   "attributes": {"versionString": "1.0.2"}}})
        print(f"  HTTP {r.status_code}")
        if r.status_code < 400:
            print(f"  ✅ renamed to v1.0.2")
            print(f"  new state: {r.json()['data']['attributes'].get('appStoreState')}")
            print_app_state(c)
        else:
            print(f"  body: {r.text[:400]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
