#!/usr/bin/env python3
"""Background watcher: polls ASC every 2 min until version 1.0.1 is
submittable, then triggers App Store Review submission automatically.

Why: Apple's API returned "Version is not ready to be submitted yet,
please try again later" right after Build #23 was attached because
Apple needs ~15-30 min to fully ingest the build before allowing a
review submission. Instead of asking the user to babysit, this script
sleeps and retries.

Run as:
    nohup python3 /app/store/submit_1_0_1_when_ready.py > /tmp/eas/submit_v101.log 2>&1 &

Idempotent — safe to re-run.
"""
from __future__ import annotations
import logging
import sys
import time

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # v1.0.1
SUB_ID = "2668dda8-c3f1-468d-8388-544a0671b859"       # existing reviewSubmission
MAX_POLLS = 60       # × 120s sleep = 2 hours
SLEEP_S = 120

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def try_submit() -> tuple[bool, str]:
    """Returns (success, message). Tries to (re)add the version + IAPs to
    the reviewSubmission, then PATCH submitted=true."""
    with a._http() as c:
        # 1) Make sure the version is in PREPARE_FOR_SUBMISSION
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        vstate = r.json().get("data", {}).get("attributes", {}).get("appStoreState")
        log.info("version state=%s", vstate)
        if vstate not in {"PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED",
                          "METADATA_REJECTED", "REJECTED"}:
            return False, f"version state={vstate} (not editable yet)"

        # 2) Try to add the version to the submission. Apple will tell us
        #    whether the version is "ready" via the response.
        add_body = {
            "data": {
                "type": "reviewSubmissionItems",
                "relationships": {
                    "reviewSubmission": {"data": {"type":"reviewSubmissions","id":SUB_ID}},
                    "appStoreVersion": {"data": {"type":"appStoreVersions","id":VERSION_ID}},
                }
            }
        }
        r = c.post("/v1/reviewSubmissionItems", headers=a._headers(), json=add_body)
        if r.status_code == 201:
            log.info("  ✅ version added to submission")
        elif r.status_code == 409 and "already" in r.text.lower():
            log.info("  ✓ version already on submission")
        else:
            return False, f"add-item returned {r.status_code}: {r.text[:300]}"

        # 3) PATCH submitted=true
        patch = {"data":{"type":"reviewSubmissions","id":SUB_ID,
                         "attributes":{"submitted":True}}}
        r = c.patch(f"/v1/reviewSubmissions/{SUB_ID}", headers=a._headers(), json=patch)
        if 200 <= r.status_code < 300:
            return True, "submitted!"
        return False, f"submit returned {r.status_code}: {r.text[:300]}"


def main():
    log.info("=== Submit-when-ready watcher started for v1.0.1 / Build #23 ===")
    for i in range(1, MAX_POLLS + 1):
        try:
            ok, msg = try_submit()
            log.info("attempt %d/%d → ok=%s · %s", i, MAX_POLLS, ok, msg)
            if ok:
                log.info("🚀 SUBMITTED FOR APPLE REVIEW")
                log.info("Track: https://appstoreconnect.apple.com/apps/%s/appstore", a.APP_ID)
                return
        except Exception:
            log.exception("attempt %d failed", i)
        time.sleep(SLEEP_S)
    log.warning("max polls reached (%d) — submission still not accepted by ASC.", MAX_POLLS)
    log.warning("Manual review needed at https://appstoreconnect.apple.com/apps/%s/appstore",
                a.APP_ID)


if __name__ == "__main__":
    main()
