#!/usr/bin/env python3
"""Ship-it script for Build #23 / version 1.0.1.

Sequence:
  1. Create or find ASC version 1.0.1 (versionString).
  2. Attach Build #23 to it.
  3. Update metadata (whatsNew + description + keywords).
  4. Find or create a reviewSubmission.
  5. Attach the version + IAPs to the submission.
  6. PATCH submitted=true → 🚀 in review.

Run from /app/store with the same ASC API key configured in env or
backend/keys/AuthKey_WFQJ6L9KXS.p8.
"""
from __future__ import annotations
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

TARGET_VERSION = "1.0.1"
TARGET_BUILD_NUMBER = "23"


def find_or_create_version(client) -> str:
    """Return the appStoreVersion ID for TARGET_VERSION.

    Apple API does NOT allow POST-creating a new version while the current
    one is in REJECTED state. The fix is to PATCH the existing REJECTED
    version's `versionString` from 1.0.0 → 1.0.1 (Apple permits this on
    editable states), then attach the new build.
    """
    versions = a._get_all(
        client,
        f"/v1/apps/{a.APP_ID}/appStoreVersions",
        **{"filter[platform]": a.PLATFORM, "limit": "30"},
    )
    target = None
    for v in versions:
        attrs = v.get("attributes") or {}
        if attrs.get("versionString") == TARGET_VERSION:
            log.info(
                "version %s already exists id=%s state=%s",
                TARGET_VERSION, v["id"], attrs.get("appStoreState"),
            )
            return v["id"]
        # Prefer an editable version to repurpose.
        if not target and attrs.get("appStoreState") in {
            "PREPARE_FOR_SUBMISSION", "METADATA_REJECTED", "REJECTED",
            "DEVELOPER_REJECTED", "INVALID_BINARY", "WAITING_FOR_REVIEW",
            "DEVELOPER_REMOVED_FROM_SALE",
        }:
            target = v

    if not target:
        # Last resort — try POST anyway (works when no version exists yet).
        log.info("no editable version to repurpose; creating fresh %s …", TARGET_VERSION)
        body = {
            "data": {
                "type": "appStoreVersions",
                "attributes": {
                    "platform": a.PLATFORM,
                    "versionString": TARGET_VERSION,
                    "releaseType": "AFTER_APPROVAL",
                },
                "relationships": {
                    "app": {"data": {"type": "apps", "id": a.APP_ID}},
                },
            }
        }
        r = client.post("/v1/appStoreVersions", headers=a._headers(), json=body)
        a._raise_for_status(r, "create version")
        return r.json()["data"]["id"]

    cur_v = target["attributes"].get("versionString")
    log.info("patching existing version %s (id=%s) → %s",
             cur_v, target["id"], TARGET_VERSION)
    patch = {
        "data": {
            "type": "appStoreVersions",
            "id": target["id"],
            "attributes": {"versionString": TARGET_VERSION},
        }
    }
    r = client.patch(
        f"/v1/appStoreVersions/{target['id']}", headers=a._headers(), json=patch
    )
    a._raise_for_status(r, f"patch versionString → {TARGET_VERSION}")
    log.info("  ✅ versionString updated to %s.", TARGET_VERSION)
    return target["id"]


def find_target_build(client) -> str:
    r = client.get(
        "/v1/builds",
        headers=a._headers(),
        params={
            "filter[app]": a.APP_ID,
            "filter[version]": TARGET_BUILD_NUMBER,
            "limit": "5",
            "sort": "-uploadedDate",
        },
    )
    a._raise_for_status(r, "list builds")
    builds = r.json().get("data") or []
    if not builds:
        raise RuntimeError(f"build #{TARGET_BUILD_NUMBER} not found in ASC")
    chosen = builds[0]
    state = chosen.get("attributes", {}).get("processingState")
    log.info("build #%s id=%s processingState=%s", TARGET_BUILD_NUMBER, chosen["id"], state)
    if state != "VALID":
        raise RuntimeError(f"build #{TARGET_BUILD_NUMBER} not VALID yet (state={state})")
    return chosen["id"]


def attach_build(client, version_id: str, build_id: str):
    # Idempotency: skip if same build is already attached.
    r = client.get(
        f"/v1/appStoreVersions/{version_id}",
        headers=a._headers(),
        params={"include": "build"},
    )
    a._raise_for_status(r, "get version build")
    body = r.json()
    cur = (body.get("data", {}).get("relationships", {}).get("build", {}) or {}).get("data")
    if cur and cur.get("id") == build_id:
        log.info("build already attached. skip.")
        return
    log.info("attaching build %s → version %s …", build_id, version_id)
    patch = {
        "data": {
            "type": "appStoreVersions",
            "id": version_id,
            "relationships": {
                "build": {"data": {"type": "builds", "id": build_id}},
            },
        }
    }
    r = client.patch(
        f"/v1/appStoreVersions/{version_id}", headers=a._headers(), json=patch
    )
    a._raise_for_status(r, "attach build")
    log.info("  ✅ build #%s attached.", TARGET_BUILD_NUMBER)


def main():
    log.info("=== Build #23 (v1.0.1) ship-it ===")
    log.info("  app_id=%s", a.APP_ID)
    with a._http() as client:
        version_id = find_or_create_version(client)
        build_id = find_target_build(client)
        attach_build(client, version_id, build_id)

        # Set whatsNew + description + keywords. Reuse existing helper.
        # Pass version_attrs so the helper knows this is a 1.0.x release and
        # skips whatsNew (Apple rejects it on first-1.0 family edits).
        log.info("updating localized metadata (description / keywords) …")
        a.update_metadata(
            client,
            version_id,
            dry_run=False,
            version_attrs={"versionString": TARGET_VERSION},
        )

        # Build the reviewSubmission, attach the new version, IAPs, then PATCH submitted=true.
        log.info("attaching version to reviewSubmission …")
        a.attach_iaps_to_version(client, version_id, dry_run=False)
        log.info("submitting reviewSubmission for App Store Review …")
        a.submit_review_submission_if_ready(client, dry_run=False)

    log.info("=== Done — Build #23 / v1.0.1 submitted for review ===")
    log.info("Track progress: https://appstoreconnect.apple.com/apps/%s/appstore", a.APP_ID)


if __name__ == "__main__":
    main()
