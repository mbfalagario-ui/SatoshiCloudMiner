#!/usr/bin/env python3
"""Inspect v1.0.1 deeply: state, releaseType, manualRelease bit, and the
full set of fields. Also see if there's any pending submission that still
holds this version. Read-only.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def main() -> int:
    with a._http() as c:
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        v = r.json()["data"]
        print("=== APP STORE VERSION ===")
        print(json.dumps(v["attributes"], indent=2, default=str))
        print()
        print("=== RELATIONSHIPS ===")
        rels = v.get("relationships") or {}
        for k, val in rels.items():
            d = (val or {}).get("data")
            if d:
                print(f"  {k}: {d}")
            elif (val or {}).get("links"):
                pass

        # Are there any reviewSubmissionItems still pointing at this version?
        print()
        print("=== REVIEW SUBMISSION ITEMS POINTING AT THIS VERSION ===")
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/reviewSubmissionItems",
                  headers=a._headers())
        if r.status_code < 400:
            for it in r.json().get("data", []):
                at = it.get("attributes") or {}
                print(f"  item={it['id'][:24]}  state={at.get('state')}")
        else:
            print(f"  HTTP {r.status_code}: {r.text[:200]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
