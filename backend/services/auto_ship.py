"""Background auto-ship pipeline.

Watches App Store Connect. As soon as the current "main" iOS App Store
version (currently 1.0) is APPROVED / READY_FOR_SALE / PENDING_APPLE_RELEASE,
this module:

  1. Finds the next editable version. If none exists with the bumped
     versionString (1.0.1), waits for ASC to auto-create one when the
     prebuilt Build #20 lands.
  2. Ensures Build #20 is uploaded to ASC via `eas submit`.
  3. Attaches Build #20 to version 1.0.1.
  4. Uploads the fresh /app/store/screenshots/* PNGs (now allowed because
     1.0.1 is in PREPARE_FOR_SUBMISSION).
  5. Sets a friendly whatsNew + description / keywords.
  6. Creates (or reuses) a reviewSubmission, attaches the version, and
     PATCHes submitted:true.

Run from APScheduler in the backend so it survives container restarts.
Idempotent — safe to call repeatedly; will no-op if the work is already
done.

State is stored at /app/store/.auto_ship_state.json:
    {"shipped_v": "1.0.1", "build_id": "...", "submitted_at": "..."}
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STORE_DIR = Path("/app/store")
STATE_FILE = STORE_DIR / ".auto_ship_state.json"
PREBUILT_BUILD_ID_FILE = STORE_DIR / ".pending_build_id"
FRONTEND_DIR = Path("/app/frontend")

# Target the version we want to ship after 1.0 is approved.
TARGET_NEXT_VERSION = os.environ.get("AUTO_SHIP_NEXT_VERSION", "1.0.1")
TARGET_NEXT_BUILD = os.environ.get("AUTO_SHIP_NEXT_BUILD", "20")
EXPO_TOKEN = os.environ.get("EXPO_TOKEN", "")

# "Approved-ish" states — any of these means we can safely ship 1.0.1
TRIGGER_STATES = {
    "READY_FOR_SALE",
    "PENDING_APPLE_RELEASE",
    "PROCESSING_FOR_APP_STORE",
    "READY_FOR_DISTRIBUTION",
}


def _load_state() -> Dict[str, Any]:
    try:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str))
    except Exception:
        logger.exception("auto_ship: failed to persist state")


def _client():
    """Lazy import so backend boot isn't blocked if the file is missing."""
    sys.path.insert(0, str(STORE_DIR))
    import asc_metadata_upload as asc  # type: ignore
    return asc


def _find_version_by_string(asc, client, version_string: str) -> Optional[Dict[str, Any]]:
    versions = asc._get_all(
        client,
        f"/v1/apps/{asc.APP_ID}/appStoreVersions",
        **{"filter[platform]": "IOS", "limit": "20"},
    )
    for v in versions:
        if v.get("attributes", {}).get("versionString") == version_string:
            return v
    return None


def _find_main_version(asc, client) -> Optional[Dict[str, Any]]:
    """Pick the canonical 1.0 version (not 1.0.1)."""
    versions = asc._get_all(
        client,
        f"/v1/apps/{asc.APP_ID}/appStoreVersions",
        **{"filter[platform]": "IOS", "limit": "20"},
    )
    # Heuristic: the lowest non-1.0.1 versionString = "1.0"
    versions = [v for v in versions if v["attributes"].get("versionString") != TARGET_NEXT_VERSION]
    if not versions:
        return None
    # Sort by createdDate ascending — original 1.0 was created first.
    versions.sort(key=lambda v: v["attributes"].get("createdDate") or "")
    return versions[0]


def _list_recent_builds(asc, client) -> List[Dict[str, Any]]:
    return asc._get_all(client, f"/v1/apps/{asc.APP_ID}/builds", **{"limit": "10"})


def _run_eas_submit(build_id: str) -> bool:
    """Submit a pre-built IPA to App Store Connect using eas-cli."""
    if not EXPO_TOKEN:
        logger.error("auto_ship: EXPO_TOKEN is not set; cannot run eas submit")
        return False
    cmd = [
        "npx", "eas", "submit",
        "--platform", "ios",
        "--profile", "production",
        "--non-interactive",
        "--id", build_id,
    ]
    env = os.environ.copy()
    env["EXPO_TOKEN"] = EXPO_TOKEN
    logger.info("auto_ship: $ %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(FRONTEND_DIR),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if proc.returncode == 0:
            logger.info("auto_ship: eas submit OK (build %s)", build_id)
            return True
        logger.error(
            "auto_ship: eas submit FAILED (rc=%s)\nSTDOUT: %s\nSTDERR: %s",
            proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:],
        )
        return False
    except subprocess.TimeoutExpired:
        logger.error("auto_ship: eas submit timed out")
        return False


def _attach_build_to_version(asc, client, build_id: str, version_id: str) -> bool:
    body = {"data": {"type": "builds", "id": build_id}}
    resp = client.patch(
        f"/v1/appStoreVersions/{version_id}/relationships/build",
        headers={**asc._headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    if resp.status_code in (200, 204):
        logger.info("auto_ship: attached build %s to version %s", build_id, version_id)
        return True
    logger.warning("auto_ship: attach build → version failed: HTTP %s %s",
                   resp.status_code, resp.text[:400])
    return False


def _upload_screenshots(asc, client, version_id: str) -> bool:
    try:
        asc.upload_screenshots(client, version_id, dry_run=False)
        return True
    except Exception:
        logger.exception("auto_ship: screenshot upload failed")
        return False


def _update_localization(asc, client, version_id: str) -> bool:
    try:
        asc.update_metadata(
            client,
            version_id,
            dry_run=False,
            version_attrs={"versionString": TARGET_NEXT_VERSION},
        )
        return True
    except Exception:
        logger.exception("auto_ship: localization update failed")
        return False


def _submit_review(asc, client, version_id: str) -> bool:
    """Create-or-reuse a reviewSubmission, attach the version, submit."""
    try:
        sub = asc._find_or_create_review_submission(client)
        sub_id = sub["id"]
        # Add version
        if not asc._add_submission_item(
            client, sub_id, "appStoreVersion", "appStoreVersions", version_id
        ):
            logger.warning("auto_ship: could not add version to reviewSubmission")
            # Don't bail — version might already be attached
        # Submit
        body = {"data": {"type": "reviewSubmissions", "id": sub_id,
                         "attributes": {"submitted": True}}}
        resp = client.patch(
            f"/v1/reviewSubmissions/{sub_id}",
            headers={**asc._headers(), "Content-Type": "application/json"},
            content=json.dumps(body),
        )
        if resp.status_code in (200, 201, 204):
            logger.info("auto_ship: reviewSubmission %s SUBMITTED", sub_id)
            return True
        logger.warning("auto_ship: submit review FAILED HTTP %s %s",
                       resp.status_code, resp.text[:600])
        return False
    except Exception:
        logger.exception("auto_ship: review submission failed")
        return False


async def auto_ship_tick() -> None:
    """One iteration. Called by APScheduler every 30 minutes."""
    state = _load_state()
    if state.get("shipped_v") == TARGET_NEXT_VERSION:
        logger.debug("auto_ship: already shipped %s — nothing to do", TARGET_NEXT_VERSION)
        return

    try:
        asc = _client()
    except Exception as e:
        logger.warning("auto_ship: asc module unavailable: %s", e)
        return

    with asc._http() as client:
        main_v = _find_main_version(asc, client)
        if not main_v:
            logger.info("auto_ship: no 1.0 version found yet — waiting")
            return
        main_state = main_v["attributes"].get("appStoreState")
        logger.info("auto_ship: main version 1.0 state=%s", main_state)
        if main_state not in TRIGGER_STATES:
            return  # Still waiting for Apple

        logger.info("auto_ship: TRIGGER — main version is %s. Shipping %s…",
                    main_state, TARGET_NEXT_VERSION)

        # Step 1: ensure next version exists. ASC auto-creates it when the
        # IPA with version=1.0.1 is uploaded, OR we can POST one.
        next_v = _find_version_by_string(asc, client, TARGET_NEXT_VERSION)
        if not next_v:
            # Try to create it
            body = {"data": {
                "type": "appStoreVersions",
                "attributes": {
                    "platform": "IOS",
                    "versionString": TARGET_NEXT_VERSION,
                    "copyright": "2026 Hashrate Cloud Miner",
                    "releaseType": "AFTER_APPROVAL",
                },
                "relationships": {
                    "app": {"data": {"type": "apps", "id": asc.APP_ID}},
                },
            }}
            resp = client.post(
                "/v1/appStoreVersions",
                headers={**asc._headers(), "Content-Type": "application/json"},
                content=json.dumps(body),
            )
            if resp.status_code in (200, 201):
                next_v = resp.json()["data"]
                logger.info("auto_ship: created version %s id=%s",
                            TARGET_NEXT_VERSION, next_v["id"])
            else:
                logger.warning("auto_ship: cannot create %s: HTTP %s %s",
                               TARGET_NEXT_VERSION, resp.status_code, resp.text[:400])
                return

        next_v_id = next_v["id"]

        # Step 2: ensure Build #20 is uploaded to ASC
        builds = _list_recent_builds(asc, client)
        b20 = next((b for b in builds
                    if b["attributes"].get("version") == TARGET_NEXT_BUILD
                    and b["attributes"].get("processingState") == "VALID"),
                   None)
        if not b20:
            # Try to submit it via EAS using the pending build id
            pending_id = None
            try:
                if PREBUILT_BUILD_ID_FILE.exists():
                    pending_id = PREBUILT_BUILD_ID_FILE.read_text().strip()
            except Exception:
                pending_id = None
            if not pending_id:
                logger.warning("auto_ship: no pending EAS build id; cannot submit")
                return
            ok = await asyncio.to_thread(_run_eas_submit, pending_id)
            if not ok:
                return
            # ASC takes 5-15 min to process — return now, check next tick
            logger.info("auto_ship: eas submit done; Apple is processing build "
                        "%s. Will continue on next tick.", pending_id)
            return

        b20_id = b20["id"]
        logger.info("auto_ship: Build #%s id=%s found and VALID",
                    TARGET_NEXT_BUILD, b20_id)

        # Step 3: attach build to version 1.0.1
        if not _attach_build_to_version(asc, client, b20_id, next_v_id):
            return

        # Step 4: refresh localization (sets whatsNew "Polished icon…" etc.)
        _update_localization(asc, client, next_v_id)

        # Step 5: upload fresh screenshots
        _upload_screenshots(asc, client, next_v_id)

        # Step 6: submit review
        ok = _submit_review(asc, client, next_v_id)
        if not ok:
            return

        # Done — persist state so we never re-run
        _save_state({
            "shipped_v": TARGET_NEXT_VERSION,
            "build_id": b20_id,
            "submitted_at": time.time(),
        })
        logger.info("auto_ship: ✅ v%s shipped automatically", TARGET_NEXT_VERSION)


def auto_ship_sync_wrapper():
    """APScheduler-friendly sync entrypoint that runs the async tick."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(auto_ship_tick())
        loop.close()
    except Exception:
        logger.exception("auto_ship tick crashed")
