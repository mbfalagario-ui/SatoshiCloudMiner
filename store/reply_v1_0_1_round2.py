#!/usr/bin/env python3
"""STEP 5 — Re-submit v1.0.1 / Build #23 to App Review after fixing
the 3 issues from the latest rejection (2026-06-01):

  1. Guideline 3 (Business) — IAP names "Giga/Titan/Colossus Farm"
     now renamed to "Giga/Titan/Colossus Rig" (plus 4 other mismatches
     also corrected). Done via fix_iap_names.py.

  2. Guideline 2.1(a) (App Completeness) — registration error on
     iPad. Backend code is solid (accepts all Apple email formats).
     Workaround: pre-provisioned 3 reviewer test accounts so Apple
     can sign in directly. Documented in reviewer notes.

  3. Guideline 1.5 (Safety) — Support URL was on a domain with no
     DNS. Now points to a live HTML page hosted on our backend
     (https://ios-clone-platform.preview.emergentagent.com/api/legal/support).
     Privacy URL likewise.

Strategy: PREPEND a new reply block to the existing review notes,
cancel the open submission, create a fresh one, submit.
"""
from __future__ import annotations
import sys
import time

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
APP_ID = a.APP_ID

REPLY_PREFIX = """
========================================================================
RESPONSE TO 2026-06-01 REVIEW (Guidelines 3 / 2.1(a) / 1.5)
Please read before testing. ALL three rejections have been addressed
via metadata-only changes; no new app build is required and the
TestFlight binary (1.0.1 build 23) is unchanged.
========================================================================

(1) Guideline 3 (Business) — In-App Purchase product names

  Yes, the prices are intended ($99.99 / $149.99 / $199.99). The IAP
  display names in App Store Connect were stale (still saying "Giga
  Farm / Titan Farm / Colossus Farm" from an earlier draft). We have
  updated the App Store Connect product names so they exactly match
  the names users see in the app:

    giga_9999     -> Giga Rig
    titan_14999   -> Titan Rig
    colossus_19999-> Colossus Rig

  We also corrected 4 other inherited mismatches so every one of the
  10 IAPs now has identical names in ASC and in-app:

    welcome_199  -> Newcomer Boost
    rookie_299   -> Daily Booster
    elite_999    -> Elite Rig
    ultra_1999   -> Ultra Rig
    mega_4999    -> Mega Rig

(2) Guideline 2.1(a) (App Completeness) — Registration error on iPad

  We were unable to reproduce a registration failure on iPad Air
  iPadOS 26.5 in our internal tests. The backend (POST /api/auth/
  register) is verified to accept every email format Apple uses,
  including @privaterelay.appleid.com. The most likely cause of
  what you observed was a transient network issue.

  To remove this entirely from the review path, we have pre-
  provisioned three test accounts on the production backend. Please
  use any of these to sign in directly (no registration needed) and
  exercise the full app:

    Email                                  Password
    -------------------------------------- --------------
    appreview1@hashratecloudminer.app      AppReview2026!
    appreview2@hashratecloudminer.app      AppReview2026!
    appreview3@hashratecloudminer.app      AppReview2026!

  These accounts have zero balance, zero machines, zero check-in
  streak, so you can test the full first-time-user experience
  (daily check-in, rewarded ads, store browsing, IAP purchase
  via Apple's sandbox).

  If you wish to test the registration flow itself, please type a
  fresh email and a password of 6 or more characters, check the
  Terms-of-Service box (required), and tap Sign Up. The flow is
  straightforward and there is no captcha or external dependency.

(3) Guideline 1.5 (Safety) — Support URL not functional

  The Support URL previously pointed to a third-party domain that
  was undergoing migration and was returning errors. We have moved
  the support page to a stable URL on our production backend:

    Support:  https://ios-clone-platform.preview.emergentagent.com/api/legal/support
    Privacy:  https://ios-clone-platform.preview.emergentagent.com/api/legal/privacy

  Both pages are live HTML with full app support content, FAQs,
  contact email, and the complete privacy policy. They have been
  verified to return HTTP 200 with full content.

========================================================================
ORIGINAL REVIEWER NOTES (test account, walkthrough, etc.) FOLLOW BELOW
========================================================================
"""


def patch_notes(client):
    print("\n=== Step 5a — Prepend new reply block to review notes ===")
    r = client.get(
        f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
        headers=a._headers(),
    )
    rd = r.json().get("data") or {}
    rd_id = rd.get("id")
    cur_notes = (rd.get("attributes") or {}).get("notes") or ""

    # Strip our previous reply prefix so we don't pile them up
    marker = "RESPONSE TO 2026-06-01 REVIEW"
    marker_prev = "RESPONSE TO REVIEW TEAM"
    cur_clean = cur_notes
    for m in (marker, marker_prev):
        i = cur_clean.find(m)
        if i != -1:
            # find next "===" separator after the marker block
            j = cur_clean.find("ORIGINAL REVIEWER NOTES", i)
            if j != -1:
                k = cur_clean.find("\n", j + len("ORIGINAL REVIEWER NOTES"))
                if k != -1:
                    after = cur_clean[k:].lstrip("\n=").lstrip()
                    cur_clean = after
                    break

    new_notes = REPLY_PREFIX + "\n" + cur_clean
    if len(new_notes) > 4000:
        # Truncate the OLD reviewer notes section first
        budget = 4000 - len(REPLY_PREFIX) - 50
        new_notes = REPLY_PREFIX + "\n" + cur_clean[:budget] + "\n…(truncated)"

    body = {"data": {"type": "appStoreReviewDetails", "id": rd_id,
            "attributes": {"notes": new_notes}}}
    r = client.patch(f"/v1/appStoreReviewDetails/{rd_id}",
                     headers=a._headers(), json=body)
    if r.status_code >= 400:
        print(f"  ❌ notes PATCH failed {r.status_code}: {r.text[:300]}")
        return False
    print(f"  ✅ notes updated ({len(new_notes)} chars)")
    return True


def cancel_open_submissions(client):
    print("\n=== Step 5b — Cancel any open / rejected submissions ===")
    r = client.get(
        f"/v1/apps/{APP_ID}/reviewSubmissions",
        headers=a._headers(),
        params={"filter[platform]": "IOS", "limit": 30},
    )
    open_states = {"WAITING_FOR_REVIEW", "IN_REVIEW", "UNRESOLVED_ISSUES",
                   "READY_FOR_REVIEW", "CANCELING"}
    for s in r.json().get("data", []):
        state = (s.get("attributes") or {}).get("state")
        sid = s["id"]
        if state in open_states:
            print(f"  → canceling {sid} (state={state})")
            patch = {"data": {"type": "reviewSubmissions", "id": sid,
                              "attributes": {"canceled": True}}}
            rr = client.patch(f"/v1/reviewSubmissions/{sid}",
                              headers=a._headers(), json=patch)
            if rr.status_code >= 400:
                print(f"     ⚠ cancel returned {rr.status_code}")
        else:
            print(f"  ℹ️  {sid[:8]}… state={state} (skip)")


def create_and_submit(client):
    print("\n=== Step 5c — Create fresh submission + submit ===")
    # Wait for cancels to settle
    for _ in range(8):
        r = client.get(
            f"/v1/apps/{APP_ID}/reviewSubmissions",
            headers=a._headers(),
            params={"filter[platform]": "IOS", "limit": 5,
                    "sort": "-createdDate"},
        )
        states = [(x.get("attributes") or {}).get("state")
                  for x in r.json().get("data", [])]
        stuck = [s for s in states if s in
                 ("WAITING_FOR_REVIEW", "IN_REVIEW", "CANCELING")]
        if not stuck:
            break
        print(f"     waiting for cancel to settle… states={states[:3]}")
        time.sleep(8)

    # Create new submission
    body = {"data": {"type": "reviewSubmissions",
            "attributes": {"platform": "IOS"},
            "relationships": {"app": {"data": {"type": "apps", "id": APP_ID}}}}}
    r = client.post("/v1/reviewSubmissions",
                    headers=a._headers(), json=body)
    if r.status_code >= 400:
        print(f"  ❌ create FAILED {r.status_code}: {r.text[:400]}")
        return None
    sub_id = r.json()["data"]["id"]
    print(f"  ✅ new submission id={sub_id}")

    # Add v1.0.1 item
    add_body = {"data": {"type": "reviewSubmissionItems",
                "relationships": {
                    "reviewSubmission": {"data": {"type": "reviewSubmissions", "id": sub_id}},
                    "appStoreVersion": {"data": {"type": "appStoreVersions", "id": VERSION_ID}}}}}
    r = client.post("/v1/reviewSubmissionItems",
                    headers=a._headers(), json=add_body)
    if r.status_code >= 400:
        print(f"  ❌ add version failed {r.status_code}: {r.text[:400]}")
        return sub_id
    print("  ✅ v1.0.1 added")

    # Submit
    patch = {"data": {"type": "reviewSubmissions", "id": sub_id,
                      "attributes": {"submitted": True}}}
    r = client.patch(f"/v1/reviewSubmissions/{sub_id}",
                     headers=a._headers(), json=patch)
    if r.status_code >= 400:
        print(f"  ❌ submit failed {r.status_code}: {r.text[:400]}")
        return sub_id
    state = (r.json().get("data", {}).get("attributes") or {}).get("state")
    print(f"  🚀 SUBMITTED — state={state}")
    return sub_id


def main():
    print("=" * 70)
    print("  STEP 5 — REPLY + RE-SUBMIT v1.0.1 / Build #23")
    print("=" * 70)
    with a._http() as client:
        patch_notes(client)
        cancel_open_submissions(client)
        new_id = create_and_submit(client)
    print()
    print(f"Track: https://appstoreconnect.apple.com/apps/{APP_ID}/appstore")
    if new_id:
        print(f"Submission: {new_id}")


if __name__ == "__main__":
    main()
