#!/usr/bin/env python3
"""Attach Build #24 to v1.0.1 and submit for App Review."""
from __future__ import annotations
import sys
import time

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

APP_ID = a.APP_ID
VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
TARGET_BUILD = "24"


def main() -> int:
    with a._http() as c:
        # ── 1) Find build 24's id ─────────────────────────────────────
        r = c.get(f"/v1/apps/{APP_ID}/builds", headers=a._headers(),
                  params={"limit": 50})
        builds = r.json().get("data", [])
        b24 = next((b for b in builds if b["attributes"].get("version") == TARGET_BUILD), None)
        if not b24:
            print(f"❌ Build {TARGET_BUILD} not yet visible in ASC.")
            return 1
        build_id = b24["id"]
        state = b24["attributes"].get("processingState")
        print(f"[1/4] Build {TARGET_BUILD} found: id={build_id[:12]}… state={state}")

        # ── 2) Wait for export-compliance / processing to settle ─────
        # Sometimes builds are VALID but the bitcodeProcessingState or
        # missingComplianceProvider is still PENDING.
        attrs = b24["attributes"]
        compliance_required = attrs.get("usesNonExemptEncryption")
        print(f"      usesNonExemptEncryption = {compliance_required}")
        # We set ITSAppUsesNonExemptEncryption=false in app.json infoPlist,
        # which Apple reads automatically. No action needed.

        # ── 3) Attach build to the app store version ─────────────────
        r = c.patch(
            f"/v1/appStoreVersions/{VERSION_ID}",
            headers=a._headers(),
            json={
                "data": {
                    "type": "appStoreVersions",
                    "id": VERSION_ID,
                    "relationships": {
                        "build": {
                            "data": {"type": "builds", "id": build_id}
                        }
                    },
                }
            },
        )
        if r.status_code >= 400:
            print(f"❌ attach build → version FAILED: {r.status_code}")
            print(r.text[:400])
            return 1
        print(f"[2/4] Attached Build {TARGET_BUILD} to v1.0.1 ✅")

        # ── 4) Check current submission state ────────────────────────
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        ver_state = r.json()["data"]["attributes"]["appStoreState"]
        print(f"[3/4] Current version state: {ver_state}")

        if ver_state == "WAITING_FOR_REVIEW":
            print(f"      ✅ Already in review queue — nothing more to do.")
            return 0

        # ── 5) Cancel any pending/in-progress submission ─────────────
        r = c.get(f"/v1/apps/{APP_ID}/reviewSubmissions",
                  headers=a._headers(), params={"limit": 25})
        submissions = r.json().get("data", [])
        active_states = {
            "READY_FOR_REVIEW", "WAITING_FOR_REVIEW", "IN_REVIEW",
            "UNRESOLVED_ISSUES", "REJECTED",
        }
        # Cancel anything that's READY/WAITING/IN_REVIEW. REJECTED is fine.
        for s in submissions:
            attrs = s.get("attributes", {})
            state = attrs.get("state")
            if state in {"WAITING_FOR_REVIEW", "READY_FOR_REVIEW", "IN_REVIEW"}:
                print(f"      cancelling submission {s['id'][:12]}… (state={state})")
                rr = c.patch(
                    f"/v1/reviewSubmissions/{s['id']}",
                    headers=a._headers(),
                    json={
                        "data": {
                            "type": "reviewSubmissions",
                            "id": s["id"],
                            "attributes": {"canceled": True},
                        }
                    },
                )
                print(f"        {'✅' if rr.status_code < 400 else '⚠'} HTTP {rr.status_code}")

        # ── 6) Create a new reviewSubmission tied to this version ────
        time.sleep(2)
        body = {
            "data": {
                "type": "reviewSubmissions",
                "attributes": {"platform": "IOS"},
                "relationships": {
                    "app": {"data": {"type": "apps", "id": APP_ID}},
                },
            }
        }
        r = c.post("/v1/reviewSubmissions", headers=a._headers(), json=body)
        if r.status_code >= 400:
            print(f"❌ create submission failed: {r.status_code}")
            print(r.text[:400])
            return 1
        sub_id = r.json()["data"]["id"]
        print(f"      ✅ created submission {sub_id[:12]}…")

        # ── 7) Add v1.0.1 as a submission item ───────────────────────
        body = {
            "data": {
                "type": "reviewSubmissionItems",
                "relationships": {
                    "appStoreVersion": {
                        "data": {"type": "appStoreVersions", "id": VERSION_ID}
                    },
                    "reviewSubmission": {
                        "data": {"type": "reviewSubmissions", "id": sub_id}
                    },
                },
            }
        }
        r = c.post("/v1/reviewSubmissionItems", headers=a._headers(), json=body)
        if r.status_code >= 400:
            print(f"❌ add item failed: {r.status_code}")
            print(r.text[:400])
            return 1
        print(f"      ✅ added v1.0.1 to submission")

        # ── 8) Submit ────────────────────────────────────────────────
        body = {
            "data": {
                "type": "reviewSubmissions",
                "id": sub_id,
                "attributes": {"submitted": True},
            }
        }
        r = c.patch(f"/v1/reviewSubmissions/{sub_id}",
                    headers=a._headers(), json=body)
        if r.status_code >= 400:
            print(f"❌ submit FAILED: {r.status_code}")
            print(r.text[:400])
            return 1
        result_attrs = r.json()["data"]["attributes"]
        print(f"[4/4] 🎉 SUBMITTED FOR REVIEW")
        print(f"      submission id : {sub_id}")
        print(f"      state         : {result_attrs.get('state')}")
        print(f"      submittedDate : {result_attrs.get('submittedDate')}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
