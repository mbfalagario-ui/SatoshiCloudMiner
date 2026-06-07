#!/usr/bin/env python3
"""End-to-end App Store Connect uploader for Satoshi Cloud Miner.

What this script does (idempotent, safe to re-run):
  1. Authenticate to App Store Connect API using the App Manager .p8 key
     (AuthKey_WFQJ6L9KXS.p8, Issuer d3284874-...).
  2. Find the editable iOS App Store version (1.0.0). Create it if missing.
  3. Refresh localized metadata (description, keywords, what's new,
     promotional text, marketing URL, support URL).
  4. Attach all 10 in-app purchases + the Ad-Free entitlement to the
     editable version via the v2 IAP relationships endpoint. This is THE
     fix for the "Purchase failed — SKU starter_099" sandbox error: until
     each IAP is bundled with a submitted version, StoreKit returns
     E_PRODUCT_NOT_AVAILABLE.
  5. Upload App Preview video (1290x2796) + four screenshots per device
     family (6.7", 6.5", 5.5"), replacing whatever was there before.

Usage:
    python3 asc_metadata_upload.py                  # everything
    python3 asc_metadata_upload.py --skip-media     # only metadata + IAPs
    python3 asc_metadata_upload.py --skip-iaps     # only metadata + media
    python3 asc_metadata_upload.py --dry-run        # print plan, no writes

Env vars (read from /app/backend/.env automatically if python-dotenv is
installed, otherwise set them in your shell):
    ASC_KEY_ID       = WFQJ6L9KXS
    ASC_ISSUER_ID    = d3284874-7bd8-4eff-b272-c9ef0122df9a
    ASC_KEY_PATH     = /app/backend/keys/AuthKey_WFQJ6L9KXS.p8
    ASC_APP_ID       = 6773104756  (Satoshi Cloud Miner)

Reference: https://developer.apple.com/documentation/appstoreconnectapi
"""
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import os
import sys
import time
from hashlib import md5
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import jwt as pyjwt

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv("/app/backend/.env")
except Exception:
    pass

ASC_BASE = "https://api.appstoreconnect.apple.com"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("asc")


# ---------------------------------------------------------------------------
# CONFIG (overridable by env)
# ---------------------------------------------------------------------------
KEY_ID = os.environ.get("ASC_KEY_ID", "WFQJ6L9KXS")
ISSUER_ID = os.environ.get("ASC_ISSUER_ID", "d3284874-7bd8-4eff-b272-c9ef0122df9a")
KEY_PATH = os.environ.get("ASC_KEY_PATH", "/app/backend/keys/AuthKey_WFQJ6L9KXS.p8")
# Production-safe key delivery: when ASC_PRIVATE_KEY_PEM is set in the
# environment (e.g. via `fly secrets set`), it overrides KEY_PATH so no
# .p8 file ever has to touch the filesystem in prod. The value must be
# the full PEM body including the BEGIN/END markers.
KEY_PEM = os.environ.get("ASC_PRIVATE_KEY_PEM") or None
APP_ID = os.environ.get("ASC_APP_ID", "6773104756")
TARGET_VERSION = os.environ.get("ASC_TARGET_VERSION", "1.0.0")
LOCALE = os.environ.get("ASC_LOCALE", "en-US")
PLATFORM = "IOS"

# Store directory layout (must match the repo layout used elsewhere in the
# project — see /app/store/{description,keywords,whats-new}.txt and
# /app/store/screenshots/*).
STORE_DIR = Path(__file__).parent.resolve()
DESCRIPTION_PATH = STORE_DIR / "description.txt"
KEYWORDS_PATH = STORE_DIR / "keywords.txt"
WHATS_NEW_PATH = STORE_DIR / "whats-new.txt"
SUPPORT_URL = "https://satoshicloudminer.app/support"
MARKETING_URL = "https://satoshicloudminer.app"
PRIVACY_URL = "https://satoshicloudminer.app/privacy"

SCREENSHOTS = {
    # ASC display type -> directory of PNGs (numbered 1..N in filename order).
    "APP_IPHONE_67": STORE_DIR / "screenshots" / "6.7",   # iPhone 14/15 Pro Max
    "APP_IPHONE_65": STORE_DIR / "screenshots" / "6.5",   # iPhone XS Max
    "APP_IPHONE_55": STORE_DIR / "screenshots" / "5.5",   # iPhone 8 Plus
}
APP_PREVIEW_VIDEO = STORE_DIR / "marketing" / "app-preview-15-30s.mp4"

# The full list of IAPs that must be attached to the editable version
# (same order as App Store Connect "Drafts" tab in the screenshot).
TARGET_IAP_PRODUCT_IDS = [
    "welcome_199",
    "rookie_299",
    "pro_499",
    "elite_999",
    "ultra_1999",
    "mega_4999",
    "giga_9999",
    "titan_14999",
    "colossus_19999",
    "adfree_399",
]


# ---------------------------------------------------------------------------
# JWT + HTTP helpers
# ---------------------------------------------------------------------------
def _make_token() -> str:
    # Production-safe: prefer the in-memory PEM body delivered via env var
    # (ASC_PRIVATE_KEY_PEM); fall back to disk only for local dev.
    if KEY_PEM and KEY_PEM.strip().startswith("-----BEGIN"):
        private_key = KEY_PEM
    elif Path(KEY_PATH).exists():
        private_key = Path(KEY_PATH).read_text()
    else:
        raise FileNotFoundError(
            f"ASC key not found — set ASC_PRIVATE_KEY_PEM env var "
            f"(preferred) or place the .p8 at {KEY_PATH}"
        )
    now = int(time.time())
    payload = {
        "iss": ISSUER_ID,
        "iat": now,
        "exp": now + 60 * 18,  # 18 minutes (Apple allows max 20)
        "aud": "appstoreconnect-v1",
    }
    token = pyjwt.encode(
        payload, private_key, algorithm="ES256",
        headers={"kid": KEY_ID, "typ": "JWT"},
    )
    return token if isinstance(token, str) else token.decode("utf-8")


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_make_token()}",
        "Accept": "application/json",
    }


def _http() -> httpx.Client:
    return httpx.Client(
        base_url=ASC_BASE,
        timeout=httpx.Timeout(60.0, connect=15.0),
        headers={"Accept": "application/json"},
    )


def _raise_for_status(resp: httpx.Response, ctx: str) -> None:
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(
            f"ASC API error during {ctx}: HTTP {resp.status_code}\n"
            f"{json.dumps(body, indent=2, default=str) if isinstance(body, (dict, list)) else body}"
        )


def _get_all(client: httpx.Client, path: str, **params) -> List[Dict[str, Any]]:
    """Pagination helper — returns all `data` entries across pages."""
    out: List[Dict[str, Any]] = []
    url: Optional[str] = path
    qp = dict(params)
    while url:
        resp = client.get(url, headers=_headers(), params=qp)
        _raise_for_status(resp, f"GET {url}")
        body = resp.json()
        out.extend(body.get("data", []))
        # Only the first call carries query params; pagination links are absolute.
        qp = {}
        nxt = body.get("links", {}).get("next")
        if nxt and nxt.startswith(ASC_BASE):
            url = nxt[len(ASC_BASE):]
        else:
            url = None
    return out


# ---------------------------------------------------------------------------
# App + version discovery
# ---------------------------------------------------------------------------
def get_app(client: httpx.Client) -> Dict[str, Any]:
    resp = client.get(f"/v1/apps/{APP_ID}", headers=_headers())
    _raise_for_status(resp, "fetch app")
    return resp.json()["data"]


def find_editable_version(client: httpx.Client) -> Dict[str, Any]:
    """Find an iOS version that's still editable. The editable states are
    PREPARE_FOR_SUBMISSION, WAITING_FOR_REVIEW, METADATA_REJECTED, REJECTED,
    DEVELOPER_REJECTED, INVALID_BINARY, WAITING_FOR_EXPORT_COMPLIANCE.
    Falls back to the latest version of any state.
    """
    versions = _get_all(
        client,
        f"/v1/apps/{APP_ID}/appStoreVersions",
        **{"filter[platform]": PLATFORM, "limit": "20"},
    )
    if not versions:
        raise RuntimeError("No App Store versions found for this app.")
    editable_states = {
        "PREPARE_FOR_SUBMISSION",
        "WAITING_FOR_REVIEW",
        "METADATA_REJECTED",
        "REJECTED",
        "DEVELOPER_REJECTED",
        "INVALID_BINARY",
        "WAITING_FOR_EXPORT_COMPLIANCE",
        "DEVELOPER_REMOVED_FROM_SALE",
    }
    chosen = None
    for v in versions:
        attrs = v.get("attributes", {})
        log.info("Found version %s (%s)", attrs.get("versionString"), attrs.get("appStoreState"))
        if attrs.get("appStoreState") in editable_states:
            chosen = v
            if attrs.get("versionString") == TARGET_VERSION:
                break
    if not chosen:
        # Latest version (Apple sorts versions desc by default? Let's pick first.)
        chosen = versions[0]
        log.warning(
            "No editable version found; falling back to latest version %s (%s).",
            chosen["attributes"].get("versionString"),
            chosen["attributes"].get("appStoreState"),
        )
    return chosen


def get_version_localization(client: httpx.Client, version_id: str) -> Dict[str, Any]:
    locs = _get_all(
        client,
        f"/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations",
        **{"limit": "50"},
    )
    for loc in locs:
        if loc["attributes"].get("locale") == LOCALE:
            return loc
    if not locs:
        raise RuntimeError(f"No localizations found for version {version_id}")
    return locs[0]


# ---------------------------------------------------------------------------
# 1) Metadata refresh
# ---------------------------------------------------------------------------
def _read_text(p: Path, fallback: str = "") -> str:
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return fallback


def update_metadata(client: httpx.Client, version_id: str, dry_run: bool,
                    version_attrs: Optional[Dict[str, Any]] = None) -> None:
    log.info("=== Phase 1: metadata refresh ===")
    desc = _read_text(DESCRIPTION_PATH)
    kwd = _read_text(KEYWORDS_PATH)[:100]
    wn = _read_text(WHATS_NEW_PATH)

    # Truncate description to Apple's 4000 char limit.
    if len(desc) > 4000:
        desc = desc[:3997] + "..."
    if len(wn) > 4000:
        wn = wn[:3997] + "..."

    loc = get_version_localization(client, version_id)
    loc_id = loc["id"]
    # Build attributes incrementally — whatsNew is only valid for app updates,
    # not the initial 1.0 release. Apple returns HTTP 409 STATE_ERROR if we
    # try to set it on a first-release version.
    is_first_release = (
        version_attrs is not None and version_attrs.get("versionString", "").startswith("1.0")
    )
    attrs: Dict[str, Any] = {
        "description": desc or loc["attributes"].get("description"),
        "keywords": kwd or loc["attributes"].get("keywords"),
        "supportUrl": SUPPORT_URL,
        "marketingUrl": MARKETING_URL,
        "promotionalText": (
            "Live Lightning withdrawals, AI Trading Agents, 10 mining "
            "plans, and a clean dark/neon dashboard."
        ),
    }
    if wn and not is_first_release:
        attrs["whatsNew"] = wn
    payload = {
        "data": {
            "type": "appStoreVersionLocalizations",
            "id": loc_id,
            "attributes": attrs,
        }
    }
    log.info("Will update localization %s with:", loc_id)
    log.info("  description: %d chars", len(desc))
    log.info("  keywords:    %s", kwd)
    log.info("  whatsNew:    %d chars (%s)", len(wn),
             "first-release skip" if is_first_release else "applied")
    if dry_run:
        return
    resp = client.patch(
        f"/v1/appStoreVersionLocalizations/{loc_id}",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(payload),
    )
    _raise_for_status(resp, "patch localization")
    log.info("Localization updated.")


# ---------------------------------------------------------------------------
# 2) IAP attach
# ---------------------------------------------------------------------------
def list_all_iaps(client: httpx.Client) -> List[Dict[str, Any]]:
    """List all v2 in-app purchases for the app, paginating across `state`."""
    return _get_all(
        client,
        f"/v1/apps/{APP_ID}/inAppPurchasesV2",
        **{"limit": "200"},
    )


def _find_or_create_review_submission(client: httpx.Client) -> Dict[str, Any]:
    """Find the in-progress review submission (state IN_REVIEW or READY_FOR_REVIEW
    or COMPLETE-but-not-canceled) for this app+platform, or create one."""
    # Apple's filter syntax: ?filter[state]=READY_FOR_REVIEW etc. We just list
    # all and pick the editable one.
    subs = _get_all(
        client,
        f"/v1/apps/{APP_ID}/reviewSubmissions",
        **{"filter[platform]": PLATFORM, "limit": "20"},
    )
    editable_states = {"READY_FOR_REVIEW", "WAITING_FOR_REVIEW", "UNRESOLVED_ISSUES"}
    chosen: Optional[Dict[str, Any]] = None
    for s in subs:
        st = s.get("attributes", {}).get("state")
        log.info("Found review submission state=%s id=%s", st, s["id"])
        if st in editable_states:
            chosen = s
            break
    if chosen:
        return chosen
    # Create
    body = {
        "data": {
            "type": "reviewSubmissions",
            "attributes": {"platform": PLATFORM},
            "relationships": {
                "app": {"data": {"type": "apps", "id": APP_ID}}
            },
        }
    }
    resp = client.post(
        "/v1/reviewSubmissions",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    _raise_for_status(resp, "create reviewSubmission")
    return resp.json()["data"]


def _list_submission_items(client: httpx.Client, sub_id: str) -> List[Dict[str, Any]]:
    return _get_all(
        client,
        f"/v1/reviewSubmissions/{sub_id}/items",
        **{"limit": "100"},
    )


def _add_submission_item(
    client: httpx.Client,
    sub_id: str,
    relationship_key: str,
    relationship_type: str,
    relationship_id: str,
) -> bool:
    """Add one item (appStoreVersion or inAppPurchaseV2) to the review
    submission. Returns True on success, False if already attached / can't add.
    """
    body = {
        "data": {
            "type": "reviewSubmissionItems",
            "relationships": {
                "reviewSubmission": {
                    "data": {"type": "reviewSubmissions", "id": sub_id}
                },
                relationship_key: {
                    "data": {"type": relationship_type, "id": relationship_id}
                },
            },
        }
    }
    resp = client.post(
        "/v1/reviewSubmissionItems",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    if resp.status_code in (200, 201):
        return True
    try:
        err = resp.json()
    except Exception:
        err = resp.text
    log.warning(
        "  ⚠  could NOT add %s/%s to submission (HTTP %s): %s",
        relationship_type, relationship_id, resp.status_code,
        json.dumps(err, default=str)[:300],
    )
    return False


def attach_iaps_to_version(client: httpx.Client, version_id: str, dry_run: bool) -> None:
    """Build #18 — for the FIRST IAP submission Apple requires the unified
    reviewSubmissions endpoint. The ASC API (June-2025) does NOT accept
    inAppPurchaseV2 as a reviewSubmissionItems relationship — the web UI
    auto-bundles every READY_TO_SUBMIT IAP with the app version when the
    first version is submitted for review. So this function only needs to:

      1. Ensure a reviewSubmission exists (or create one).
      2. Attach the app version once a Build is uploaded to it.
      3. Apple's review pipeline auto-includes every READY_TO_SUBMIT IAP.
    """
    log.info("=== Phase 2: review submission (version + IAPs auto-bundled) ===")
    all_iaps = list_all_iaps(client)
    log.info("App has %d IAPs in App Store Connect.", len(all_iaps))
    pending = [i for i in all_iaps if i["attributes"].get("state") == "READY_TO_SUBMIT"]
    log.info("  %d IAPs in READY_TO_SUBMIT state — these will auto-bundle "
             "with the version submission:", len(pending))
    for i in pending:
        log.info("    → %s (%s)",
                 i["attributes"].get("productId"),
                 i["attributes"].get("name"))

    if dry_run:
        log.info("  (dry-run) would attach app version %s to a "
                 "reviewSubmission", version_id)
        return

    sub = _find_or_create_review_submission(client)
    sub_id = sub["id"]
    sub_state = sub.get("attributes", {}).get("state")
    log.info("Review submission %s (state=%s)", sub_id, sub_state)

    items = _list_submission_items(client, sub_id)
    already_version = any(
        it.get("relationships", {}).get("appStoreVersion", {}).get("data", {}).get("id") == version_id
        for it in items
    )
    if already_version:
        log.info("  ✓ App version %s already in submission.", version_id)
        return

    if _add_submission_item(
        client, sub_id, "appStoreVersion", "appStoreVersions", version_id
    ):
        log.info("  ✅ Added app version %s — IAPs will auto-bundle on submit.",
                 version_id)
    else:
        log.warning(
            "  ⚠  Could not attach version yet (likely because no Build "
            "has been uploaded for it). After EAS Build #18 lands in "
            "App Store Connect, re-run this script: it is idempotent."
        )


def submit_review_submission_if_ready(client: httpx.Client, dry_run: bool) -> None:
    """Final phase: actually submit the review submission to Apple."""
    log.info("=== Phase 4: SUBMIT review submission ===")
    subs = _get_all(
        client,
        f"/v1/apps/{APP_ID}/reviewSubmissions",
        **{"filter[platform]": PLATFORM, "limit": "20"},
    )
    pending = [s for s in subs if s.get("attributes", {}).get("state") == "READY_FOR_REVIEW"]
    if not pending:
        log.warning(
            "No reviewSubmission in READY_FOR_REVIEW state. Either nothing was "
            "added, or the submission is already in flight. Done."
        )
        return
    sub = pending[0]
    sub_id = sub["id"]
    if dry_run:
        log.info("  (dry-run) would submit reviewSubmission %s", sub_id)
        return
    # The new ASC API submission verb is a PATCH that sets `submitted: true`
    # OR a POST to /actions/submit. Both work; PATCH is simpler.
    body = {
        "data": {
            "type": "reviewSubmissions",
            "id": sub_id,
            "attributes": {"submitted": True},
        }
    }
    resp = client.patch(
        f"/v1/reviewSubmissions/{sub_id}",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    if resp.status_code in (200, 201, 204):
        log.info("  ✅ Submitted reviewSubmission %s.", sub_id)
    else:
        try:
            err = resp.json()
        except Exception:
            err = resp.text
        log.warning(
            "  ⚠  Submit attempt returned %s: %s",
            resp.status_code, json.dumps(err, default=str)[:500],
        )


# ---------------------------------------------------------------------------
# 3) Screenshots + App Preview video
# ---------------------------------------------------------------------------
def list_screenshot_sets(client: httpx.Client, version_id: str) -> List[Dict[str, Any]]:
    return _get_all(
        client,
        f"/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations",
    )


def _ensure_set(
    client: httpx.Client,
    parent_loc_id: str,
    display_type: str,
    set_kind: str,
) -> str:
    """Find or create a screenshotSet / appPreviewSet for the given display."""
    rel_path = (
        "appScreenshotSets" if set_kind == "screenshot" else "appPreviewSets"
    )
    payload_type = (
        "appScreenshotSets" if set_kind == "screenshot" else "appPreviewSets"
    )
    sets = _get_all(
        client,
        f"/v1/appStoreVersionLocalizations/{parent_loc_id}/{rel_path}",
        **{"limit": "50"},
    )
    for s in sets:
        if s["attributes"].get("screenshotDisplayType") == display_type or s[
            "attributes"
        ].get("previewType") == display_type:
            return s["id"]

    # Create
    body = {
        "data": {
            "type": payload_type,
            "attributes": (
                {"screenshotDisplayType": display_type}
                if set_kind == "screenshot"
                else {"previewType": display_type}
            ),
            "relationships": {
                "appStoreVersionLocalization": {
                    "data": {
                        "type": "appStoreVersionLocalizations",
                        "id": parent_loc_id,
                    }
                }
            },
        }
    }
    resp = client.post(
        f"/v1/{rel_path}",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    _raise_for_status(resp, f"create {set_kind} set for {display_type}")
    return resp.json()["data"]["id"]


def _wipe_set(client: httpx.Client, set_id: str, set_kind: str) -> None:
    rel_path = (
        "appScreenshots" if set_kind == "screenshot" else "appPreviews"
    )
    parent_rel = (
        "appScreenshotSets" if set_kind == "screenshot" else "appPreviewSets"
    )
    items = _get_all(client, f"/v1/{parent_rel}/{set_id}/{rel_path}",
                     **{"limit": "50"})
    for it in items:
        client.delete(f"/v1/{rel_path}/{it['id']}", headers=_headers())


def _upload_asset(
    client: httpx.Client,
    asset_endpoint: str,
    asset_type: str,
    set_id: str,
    set_rel_type: str,  # "appScreenshotSets" or "appPreviewSets"
    file_path: Path,
) -> None:
    """Three-step upload (reservation → PUT chunks → commit)."""
    fsz = file_path.stat().st_size
    mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    rel_key = "appScreenshotSet" if set_rel_type == "appScreenshotSets" else "appPreviewSet"
    create_body = {
        "data": {
            "type": asset_type,
            "attributes": {
                "fileSize": fsz,
                "fileName": file_path.name,
                **({"mimeType": mime} if asset_type == "appPreviews" else {}),
            },
            "relationships": {
                rel_key: {
                    "data": {"type": set_rel_type, "id": set_id},
                }
            },
        }
    }
    resp = client.post(
        f"/v1/{asset_endpoint}",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(create_body),
    )
    _raise_for_status(resp, f"reserve upload {file_path.name}")
    data = resp.json()["data"]
    asset_id = data["id"]
    ops = data["attributes"].get("uploadOperations") or []
    if not ops:
        raise RuntimeError(f"No upload operations returned for {file_path.name}")

    blob = file_path.read_bytes()
    for op in ops:
        method = op.get("method", "PUT")
        url = op["url"]
        headers = {h["name"]: h["value"] for h in op.get("requestHeaders", [])}
        offset = int(op.get("offset", 0))
        length = int(op.get("length", len(blob)))
        chunk = blob[offset : offset + length]
        up = client.request(method, url, content=chunk, headers=headers)
        if up.status_code >= 400:
            raise RuntimeError(
                f"Chunk upload failed for {file_path.name}: {up.status_code} {up.text[:200]}"
            )

    # Commit
    file_hash = md5(blob).hexdigest()
    commit_body = {
        "data": {
            "type": asset_type,
            "id": asset_id,
            "attributes": {"uploaded": True, "sourceFileChecksum": file_hash},
        }
    }
    cmt = client.patch(
        f"/v1/{asset_endpoint}/{asset_id}",
        headers={**_headers(), "Content-Type": "application/json"},
        content=json.dumps(commit_body),
    )
    _raise_for_status(cmt, f"commit upload {file_path.name}")
    log.info("    ✅ uploaded %s (%d bytes)", file_path.name, fsz)


def upload_screenshots(client: httpx.Client, version_id: str, dry_run: bool) -> None:
    log.info("=== Phase 3a: screenshots ===")
    loc = get_version_localization(client, version_id)
    loc_id = loc["id"]
    for display, src_dir in SCREENSHOTS.items():
        if not src_dir.exists():
            log.warning("  skip %s — directory missing: %s", display, src_dir)
            continue
        pngs = sorted([p for p in src_dir.glob("*.png")])
        if not pngs:
            log.warning("  skip %s — no PNGs in %s", display, src_dir)
            continue
        log.info("  %s — %d screenshots", display, len(pngs))
        if dry_run:
            for p in pngs:
                log.info("    plan: upload %s", p.name)
            continue
        set_id = _ensure_set(client, loc_id, display, "screenshot")
        _wipe_set(client, set_id, "screenshot")
        for p in pngs:
            _upload_asset(
                client,
                "appScreenshots",
                "appScreenshots",
                set_id,
                "appScreenshotSets",
                p,
            )


def upload_app_preview(client: httpx.Client, version_id: str, dry_run: bool) -> None:
    log.info("=== Phase 3b: App Preview video ===")
    if not APP_PREVIEW_VIDEO.exists():
        log.warning("  skip — no preview video at %s", APP_PREVIEW_VIDEO)
        return
    loc = get_version_localization(client, version_id)
    loc_id = loc["id"]
    # App PreviewSet.previewType uses a DIFFERENT enum than appScreenshotSets.
    # Screenshots: "APP_IPHONE_67" -- previews: "IPHONE_67".
    preview_type = "IPHONE_67"
    log.info("  uploading %s (%d bytes) to %s",
             APP_PREVIEW_VIDEO.name, APP_PREVIEW_VIDEO.stat().st_size, preview_type)
    if dry_run:
        return
    set_id = _ensure_set(client, loc_id, preview_type, "preview")
    _wipe_set(client, set_id, "preview")
    _upload_asset(
        client,
        "appPreviews",
        "appPreviews",
        set_id,
        "appPreviewSets",
        APP_PREVIEW_VIDEO,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-media", action="store_true",
                    help="Skip screenshots + app preview uploads")
    ap.add_argument("--skip-iaps", action="store_true",
                    help="Skip IAP submissions")
    ap.add_argument("--skip-metadata", action="store_true",
                    help="Skip text/url metadata refresh")
    ap.add_argument("--submit", action="store_true",
                    help="After uploading, actually submit the review submission to Apple")
    args = ap.parse_args()

    log.info("App Store Connect uploader")
    log.info("  app_id=%s  version=%s  locale=%s", APP_ID, TARGET_VERSION, LOCALE)
    log.info("  key=%s  issuer=%s", KEY_ID, ISSUER_ID)

    with _http() as client:
        try:
            app = get_app(client)
        except Exception as e:
            log.error("Cannot reach App Store Connect: %s", e)
            return 2
        attrs = app.get("attributes", {})
        log.info("App: %s  bundle=%s", attrs.get("name"), attrs.get("bundleId"))

        version = find_editable_version(client)
        version_id = version["id"]
        log.info(
            "Editable version: %s  state=%s  id=%s",
            version["attributes"].get("versionString"),
            version["attributes"].get("appStoreState"),
            version_id,
        )

        if not args.skip_metadata:
            update_metadata(client, version_id, args.dry_run, version["attributes"])
        if not args.skip_iaps:
            attach_iaps_to_version(client, version_id, args.dry_run)
        if not args.skip_media:
            upload_screenshots(client, version_id, args.dry_run)
            upload_app_preview(client, version_id, args.dry_run)
        if args.submit:
            submit_review_submission_if_ready(client, args.dry_run)

    log.info("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
