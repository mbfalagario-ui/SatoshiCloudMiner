#!/usr/bin/env python3
"""Cancel the in-flight (half-built) submission 6db2a564 + check the
state machine of the appStoreVersion and try to nudge it back to
PREPARE_FOR_SUBMISSION via a no-op metadata PATCH.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

NEW_SUB_ID = "6db2a564-fada-4716-b44b-fa1ddfedda56"
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def main() -> int:
    with a._http() as c:
        # 1. Cancel the half-built submission so the version is freed
        print("[1] Cancelling half-built submission")
        r = c.patch(f"/v1/reviewSubmissions/{NEW_SUB_ID}",
                    headers=a._headers(),
                    json={"data": {"type": "reviewSubmissions", "id": NEW_SUB_ID,
                                   "attributes": {"canceled": True}}})
        print(f"  HTTP {r.status_code}: {r.text[:200]}")

        # 2. List its items (should be empty)
        print("[2] Items in cancelled submission:")
        r = c.get(f"/v1/reviewSubmissions/{NEW_SUB_ID}/items", headers=a._headers())
        for it in r.json().get("data", []):
            print(f"  {it['id']} state={it.get('attributes', {}).get('state')}")

        # 3. Try a noop metadata patch on the version to "wake it up"
        print("[3] Trying noop metadata PATCH on appStoreVersion to nudge state")
        r = c.patch(f"/v1/appStoreVersions/{VERSION_ID}",
                    headers=a._headers(),
                    json={"data": {"type": "appStoreVersions", "id": VERSION_ID,
                                   "attributes": {"copyright": "2026 Hashrate Cloud Miner"}}})
        print(f"  HTTP {r.status_code}")
        if r.status_code < 400:
            print(f"  new state: {r.json()['data']['attributes'].get('appStoreState')}")
        else:
            print(f"  {r.text[:400]}")

        # 4. Re-check the version state
        print("[4] Current version state after nudge:")
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        att = r.json()["data"]["attributes"]
        print(f"  appStoreState={att.get('appStoreState')}  appVersionState={att.get('appVersionState')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
