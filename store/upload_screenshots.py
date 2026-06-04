#!/usr/bin/env python3
"""Replace existing App Store screenshots with fresh ones captured from
the running app. ASC API flow:
 1. For each target device set, DELETE all existing screenshots
 2. For each target device set, POST new appScreenshot records
 3. PUT-upload bytes to the URL returned in uploadOperations
 4. PATCH each screenshot with sourceFileChecksum + uploaded=true
"""
from __future__ import annotations
import sys, json, hashlib, pathlib, mimetypes
import httpx
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
SHOTS = pathlib.Path("/tmp/asc_shots")

# Device family → display type → file pattern (in order)
DEVICES = [
    ("APP_IPHONE_67",      "iphone_67_*.png"),
    ("APP_IPHONE_65",      "iphone_65_*.png"),
    ("APP_IPAD_PRO_3GEN_129", "ipad_129_*.png"),
]


def file_md5(p: pathlib.Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    with a._http() as c:
        # 1. Find the en-US version localization
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
                  headers=a._headers())
        locs = r.json().get("data", [])
        en_us = next((l for l in locs if l["attributes"].get("locale") == "en-US"), None)
        if not en_us:
            print("❌ no en-US localization")
            return 1
        loc_id = en_us["id"]
        print(f"en-US loc id: {loc_id}")

        # 2. Get current screenshot sets
        r = c.get(f"/v1/appStoreVersionLocalizations/{loc_id}/appScreenshotSets",
                  headers=a._headers(), params={"limit": 50})
        existing_sets = {s["attributes"]["screenshotDisplayType"]: s["id"]
                         for s in r.json().get("data", [])}
        print(f"existing sets: {list(existing_sets.keys())}")

        for display_type, pattern in DEVICES:
            print(f"\n=== {display_type} ===")
            shots = sorted(SHOTS.glob(pattern))
            if not shots:
                print(f"  ⚠ no source files matching {pattern}")
                continue
            print(f"  source files: {[p.name for p in shots]}")

            # 3a. Ensure set exists
            set_id = existing_sets.get(display_type)
            if not set_id:
                print(f"  creating new set…")
                rr = c.post("/v1/appScreenshotSets",
                            headers=a._headers(),
                            json={"data": {
                                "type": "appScreenshotSets",
                                "attributes": {"screenshotDisplayType": display_type},
                                "relationships": {
                                    "appStoreVersionLocalization": {
                                        "data": {"type": "appStoreVersionLocalizations",
                                                 "id": loc_id}
                                    }
                                }
                            }})
                if rr.status_code >= 400:
                    print(f"  ❌ create set: {rr.status_code} {rr.text[:300]}")
                    continue
                set_id = rr.json()["data"]["id"]
                print(f"  set id: {set_id}")

            # 3b. Delete existing screenshots in this set
            rr = c.get(f"/v1/appScreenshotSets/{set_id}/appScreenshots",
                       headers=a._headers(), params={"limit": 20})
            for s in rr.json().get("data", []):
                d = c.delete(f"/v1/appScreenshots/{s['id']}", headers=a._headers())
                print(f"  deleted old {s['attributes'].get('fileName')} → {d.status_code}")

            # 3c. Upload each new screenshot
            for shot in shots:
                size = shot.stat().st_size
                fname = shot.name
                print(f"  uploading {fname} ({size} bytes)…")

                # 1. POST appScreenshots (reserves an upload)
                rr = c.post("/v1/appScreenshots",
                            headers=a._headers(),
                            json={"data": {
                                "type": "appScreenshots",
                                "attributes": {
                                    "fileSize": size,
                                    "fileName": fname,
                                },
                                "relationships": {
                                    "appScreenshotSet": {
                                        "data": {"type": "appScreenshotSets", "id": set_id}
                                    }
                                }
                            }})
                if rr.status_code >= 400:
                    print(f"    ❌ create record: {rr.status_code} {rr.text[:300]}")
                    continue
                rec = rr.json()["data"]
                shot_id = rec["id"]
                upload_ops = rec["attributes"].get("uploadOperations") or []

                # 2. PUT bytes to each upload operation URL
                with open(shot, "rb") as f:
                    data = f.read()
                for op in upload_ops:
                    method = op["method"]
                    url = op["url"]
                    offset = op["offset"]
                    length = op["length"]
                    hdrs = {h["name"]: h["value"] for h in op.get("requestHeaders") or []}
                    chunk = data[offset:offset + length]
                    with httpx.Client(timeout=60.0) as upload_c:
                        ur = upload_c.request(method, url, content=chunk, headers=hdrs)
                    if ur.status_code >= 400:
                        print(f"    ❌ chunk PUT: {ur.status_code} {ur.text[:200]}")
                        break
                else:
                    # 3. PATCH uploaded=true with checksum
                    md5 = file_md5(shot)
                    pr = c.patch(f"/v1/appScreenshots/{shot_id}",
                                 headers=a._headers(),
                                 json={"data": {
                                     "type": "appScreenshots",
                                     "id": shot_id,
                                     "attributes": {
                                         "uploaded": True,
                                         "sourceFileChecksum": md5,
                                     }
                                 }})
                    print(f"    ✅ finalize {fname} → HTTP {pr.status_code}")
                    if pr.status_code >= 400:
                        print(f"       {pr.text[:300]}")

    print("\nDONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
