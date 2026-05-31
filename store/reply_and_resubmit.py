#!/usr/bin/env python3
"""Reply to Apple + resubmit v1.0.1 for review.

Apple's ASC REST API doesn't expose a direct "send free-text reply to
reviewer" endpoint — the Resolution Center reply feature is web-UI-only.
The standard practice is:

  1. PREPEND the explanation text into `appStoreReviewDetail.notes` so
     the next reviewer reads it first.
  2. Cancel the current REJECTED reviewSubmission (if any).
  3. Create a fresh reviewSubmission, add v1.0.1, PATCH submitted=true.

This way the same explanatory content the user wrote for Apple is
delivered through the review-notes field, which IS surfaced to the
reviewer at the top of their queue.
"""
from __future__ import annotations
import sys
import time

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # v1.0.1
APP_ID = a.APP_ID

REPLY_PREFIX = """
========================================================================
RESPONSE TO REVIEW TEAM — Submission 6e443229-c592-4524-90ac-9851df96bef6
(previously rejected under Guideline 2.3.6 — In-App Controls / Parental
Controls). Please read before testing.
========================================================================

Thank you for the feedback on the prior submission. The app does NOT
include parental controls, age assurance, user-generated content,
unrestricted web access, or peer-to-peer messaging. The Age Rating
questionnaire selections for these items were inherited errors from
the original 1.0 submission draft and were never corrected when the
app was renamed.

We have updated the Age Rating Declaration to accurately reflect the
app's features:
  - Parental Controls      -> None
  - Age Assurance          -> None
  - Unrestricted Web Access -> No
  - User Generated Content  -> No
  - Messaging and Chat      -> No  (the app has an AI-assisted support
                                    chat with our staff only - there is
                                    no peer-to-peer messaging)
  - Manual Age Rating Override -> removed (Apple now computes the rating
                                    from the corrected questionnaire)

We have also rewritten the App Store description to remove every
reference to "Satoshi Cloud Miner" - the previous branding from
before the 1.0.1 rename.

Regarding the marketing / support / privacy URLs:

  Our existing web domain is satoshicloudminer.app. We have moved the
  app's public-facing landing, support, and privacy pages to the path
  /hashrate (e.g. https://satoshicloudminer.app/hashrate/support) so
  the URL itself reflects the Hashrate Cloud Miner brand. The legacy
  domain is retained ONLY at the registrar/hosting layer during a
  planned DNS migration; end-users never see the bare domain anywhere
  in the app (we link through these /hashrate paths exclusively). The
  domain contains no marketing copy, no logos, and no app icons
  referencing any other product - there is no consumer copycat risk.

No code changes are required. The iOS build (1.0.1 build 23) currently
on TestFlight is unchanged. Please re-review the submission with the
corrected metadata.

Thank you for your time,
Michael Falagario
Hashrate Cloud Miner

========================================================================
ORIGINAL REVIEWER NOTES (test account, walkthrough, etc.) FOLLOW BELOW
========================================================================
"""


def step_1_prepend_review_notes(client):
    print("\n=== STEP 1 — Prepend reply text to review notes ===")
    r = client.get(
        f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
        headers=a._headers(),
    )
    rd = r.json().get("data") or {}
    rd_id = rd.get("id")
    cur_notes = (rd.get("attributes") or {}).get("notes") or ""

    if REPLY_PREFIX.strip().splitlines()[0] in cur_notes:
        print("  ℹ️  reply text already prepended; skipping.")
        return

    new_notes = REPLY_PREFIX + "\n" + cur_notes
    # ASC enforces a 4000 character limit on notes
    if len(new_notes) > 4000:
        # Truncate the OLD notes section to fit
        room = 4000 - len(REPLY_PREFIX) - 50
        new_notes = REPLY_PREFIX + "\n" + cur_notes[:room] + "\n…(truncated)"
        print(f"  ⚠️  truncating combined notes to {len(new_notes)} chars (limit 4000)")

    body = {
        "data": {
            "type": "appStoreReviewDetails",
            "id": rd_id,
            "attributes": {"notes": new_notes},
        }
    }
    r = client.patch(
        f"/v1/appStoreReviewDetails/{rd_id}",
        headers=a._headers(),
        json=body,
    )
    if r.status_code >= 400:
        print(f"  ❌ notes PATCH FAILED {r.status_code}\n     {r.text[:400]}")
        return False
    print(f"  ✅ review notes updated ({len(new_notes)} chars)")
    return True


def step_2_cancel_pending_submissions(client):
    print("\n=== STEP 2 — Cancel any open submissions ===")
    r = client.get(
        f"/v1/apps/{APP_ID}/reviewSubmissions",
        headers=a._headers(),
        params={"filter[platform]": "IOS", "limit": 30},
    )
    subs = r.json().get("data", [])
    open_states = {"WAITING_FOR_REVIEW", "IN_REVIEW", "UNRESOLVED_ISSUES",
                   "READY_FOR_REVIEW"}
    for s in subs:
        sid = s["id"]
        state = (s.get("attributes") or {}).get("state")
        if state in open_states:
            print(f"  → canceling submission {sid} (state={state})")
            patch = {
                "data": {
                    "type": "reviewSubmissions",
                    "id": sid,
                    "attributes": {"canceled": True},
                }
            }
            rr = client.patch(
                f"/v1/reviewSubmissions/{sid}",
                headers=a._headers(),
                json=patch,
            )
            if rr.status_code >= 400:
                print(f"     ❌ cancel failed {rr.status_code}: {rr.text[:200]}")
            else:
                print("     ✅ canceling")
        else:
            print(f"  ℹ️  submission {sid[:8]}… state={state} (skip)")


def step_3_create_and_submit(client):
    print("\n=== STEP 3 — Create fresh submission + submit ===")
    # Give Apple a beat to settle the cancels
    time.sleep(5)

    # Create
    body = {
        "data": {
            "type": "reviewSubmissions",
            "attributes": {"platform": "IOS"},
            "relationships": {
                "app": {"data": {"type": "apps", "id": APP_ID}},
            },
        }
    }
    r = client.post(
        "/v1/reviewSubmissions", headers=a._headers(), json=body
    )
    if r.status_code >= 400:
        print(f"  ❌ create submission FAILED {r.status_code}: {r.text[:400]}")
        return None
    sub_id = r.json()["data"]["id"]
    print(f"  ✅ new submission id={sub_id}")

    # Add the v1.0.1 item
    add_body = {
        "data": {
            "type": "reviewSubmissionItems",
            "relationships": {
                "reviewSubmission": {
                    "data": {"type": "reviewSubmissions", "id": sub_id}
                },
                "appStoreVersion": {
                    "data": {"type": "appStoreVersions", "id": VERSION_ID}
                },
            },
        }
    }
    r = client.post(
        "/v1/reviewSubmissionItems",
        headers=a._headers(),
        json=add_body,
    )
    if r.status_code >= 400:
        print(f"  ❌ add version FAILED {r.status_code}: {r.text[:400]}")
        return sub_id
    print("  ✅ v1.0.1 added to submission")

    # Submit
    patch = {
        "data": {
            "type": "reviewSubmissions",
            "id": sub_id,
            "attributes": {"submitted": True},
        }
    }
    r = client.patch(
        f"/v1/reviewSubmissions/{sub_id}",
        headers=a._headers(),
        json=patch,
    )
    if r.status_code >= 400:
        print(f"  ❌ submit FAILED {r.status_code}: {r.text[:400]}")
        return sub_id
    state = (r.json().get("data", {}).get("attributes") or {}).get("state")
    print(f"  🚀 SUBMITTED — state={state}")
    return sub_id


def main():
    print("=" * 70)
    print("  REPLY TO APPLE + RE-SUBMIT v1.0.1 / Build #23")
    print("=" * 70)
    with a._http() as client:
        step_1_prepend_review_notes(client)
        step_2_cancel_pending_submissions(client)
        new_sub_id = step_3_create_and_submit(client)
    print()
    print("=" * 70)
    print("  Done. Track at:")
    print(f"  https://appstoreconnect.apple.com/apps/{APP_ID}/appstore")
    if new_sub_id:
        print(f"  New submission ID: {new_sub_id}")
    print("=" * 70)


if __name__ == "__main__":
    main()
