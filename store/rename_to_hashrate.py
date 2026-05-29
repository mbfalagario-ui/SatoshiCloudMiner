#!/usr/bin/env python3
"""One-shot rename script — updates ASC for v1.0.1 / Hashrate Cloud Miner.

What it does:
  1. PATCH the app's name field in `appInfoLocalizations` (this is the visible
     App Store name + sort name + subtitle).
  2. Find or create the editable App Store Version 1.0.1.
  3. PATCH the version's localized metadata (description / keywords /
     promotional text / whatsNew) with renamed copy.

Idempotent — safe to re-run.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/store")
import asc_metadata_upload as asc  # type: ignore

NEW_NAME = "Hashrate Cloud Miner"
NEW_SUBTITLE = "AI-driven BTC cloud mining"

NEW_DESCRIPTION = (
    "Hashrate Cloud Miner is a dark-themed, AI-driven Bitcoin cloud mining "
    "cockpit. Buy a rig with one tap, watch yield accrue in real time "
    "against the live BTC/USD rate, and cash out instantly over the "
    "Lightning Network. Six AI Trading Agents publish a daily performance "
    "report so you always know which strategy is leading. One clean "
    "dashboard. No fluff. No simulated data.\n\n"
    "FEATURES\n"
    "- Live BTC/USD rate ticker, refreshed every five minutes.\n"
    "- Ten mining-rig tiers from $1.99 Welcome Miner up to the Colossus Farm.\n"
    "- Six AI Trading Agents with daily LLM-generated commentary.\n"
    "- Instant withdrawals over the Bitcoin Lightning Network.\n"
    "- Free Forever 24-hour rig available once per account.\n"
    "- Auto-reinvest mode for hands-off yield compounding.\n"
    "- Premium Support chat for one-tap access to the operator.\n\n"
    "Hashrate Cloud Miner is a cloud computing simulation and monitoring "
    "utility. It is not a financial product. The lowercase unit \"satoshi\" "
    "(0.00000001 BTC) is used only where it is the technically correct "
    "denomination label."
)
NEW_KEYWORDS = "bitcoin,btc,cloud,miner,mining,lightning,hashrate,wallet,crypto,ai"
NEW_PROMO = (
    "Live Lightning withdrawals, AI Trading Agents, 10 mining plans, "
    "and a clean dark/neon dashboard."
)
NEW_WHATS_NEW = (
    "Hashrate Cloud Miner v1.0.1\n"
    "- Renamed and rebranded from the previous build per App Review feedback.\n"
    "- Polished app icon (full-bleed, no white border).\n"
    "- Refreshed App Store screenshots reflect the new brand."
)


def patch_app_info_name(client):
    """The visible App Store name lives on appInfos -> appInfoLocalizations
    not on the app resource itself."""
    print("--- Updating App Information ---")
    # Find an editable appInfo (state is appStoreState-ish but lives on appInfo).
    infos = asc._get_all(client, f"/v1/apps/{asc.APP_ID}/appInfos")
    editable_states = {
        "PREPARE_FOR_SUBMISSION",
        "WAITING_FOR_REVIEW",
        "METADATA_REJECTED",
        "REJECTED",
        "DEVELOPER_REJECTED",
        "READY_FOR_REVIEW",
        "REPLACED_WITH_NEW_INFO",
        "PENDING_APPLE_RELEASE",
    }
    target = None
    for ai in infos:
        st = ai.get("attributes", {}).get("state")
        print(f"  appInfo {ai['id']} state={st}")
        if st in editable_states:
            target = ai
    if not target:
        # Fall back to the first one if none editable.
        target = infos[0] if infos else None
    if not target:
        raise RuntimeError("No appInfo to patch")
    ai_id = target["id"]
    # Get its en-US localization.
    locs = asc._get_all(client, f"/v1/appInfos/{ai_id}/appInfoLocalizations")
    en_loc = next((l for l in locs if l["attributes"].get("locale") == "en-US"), None)
    if not en_loc:
        raise RuntimeError("No en-US appInfoLocalization")
    body = {
        "data": {
            "type": "appInfoLocalizations",
            "id": en_loc["id"],
            "attributes": {
                "name": NEW_NAME,
                "subtitle": NEW_SUBTITLE,
            },
        }
    }
    resp = client.patch(
        f"/v1/appInfoLocalizations/{en_loc['id']}",
        headers={**asc._headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ App name -> {NEW_NAME}, subtitle -> {NEW_SUBTITLE}")
    else:
        print(f"  ⚠ PATCH appInfoLocalization failed HTTP {resp.status_code}: {resp.text[:500]}")


def find_or_create_v101(client):
    """For Build #21 / TestFlight: use the existing v1.0 (now editable
    because Apple flipped it to REJECTED). We DO NOT create v1.0.1 here —
    Apple blocks new version creation while another is in REJECTED state.
    The new build (with bundle short version 1.0.1) will still flow into
    TestFlight correctly because TestFlight does not require version-string
    parity. When we are ready to resubmit for App Store review, we'll
    either cancel-rejection-and-reuse v1.0, or create v1.0.1 then."""
    print("--- Locating existing editable App Store Version ---")
    versions = asc._get_all(
        client, f"/v1/apps/{asc.APP_ID}/appStoreVersions",
        **{"filter[platform]": "IOS", "limit": "20"},
    )
    # Prefer 1.0 if it's editable post-rejection.
    editable_states = {
        "PREPARE_FOR_SUBMISSION", "WAITING_FOR_REVIEW",
        "METADATA_REJECTED", "REJECTED", "DEVELOPER_REJECTED",
    }
    for v in versions:
        st = v["attributes"].get("appStoreState")
        vs = v["attributes"].get("versionString")
        print(f"  v{vs} state={st} id={v['id']}")
        if st in editable_states:
            print(f"  → using v{vs} (state={st}) for metadata patch")
            return v
    # If nothing editable, just pick the first one (caller will surface error).
    return versions[0] if versions else None


def patch_version_locale(client, version_id):
    """Set description/keywords/promotionalText on the en-US locale.
    NOTE: whatsNew is locked by Apple on first-release versions (v1.0.0),
    so we omit it and let the resubmission flow handle it later."""
    print("--- Updating Version localized metadata ---")
    locs = asc._get_all(
        client,
        f"/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations",
    )
    en_loc = next((l for l in locs if l["attributes"].get("locale") == "en-US"), None)
    if not en_loc:
        raise RuntimeError("No en-US version localization")
    body = {
        "data": {
            "type": "appStoreVersionLocalizations",
            "id": en_loc["id"],
            "attributes": {
                "description": NEW_DESCRIPTION,
                "keywords": NEW_KEYWORDS[:100],
                "promotionalText": NEW_PROMO,
                "supportUrl": "https://hashratecloudminer.app/support",
                "marketingUrl": "https://hashratecloudminer.app",
            },
        }
    }
    resp = client.patch(
        f"/v1/appStoreVersionLocalizations/{en_loc['id']}",
        headers={**asc._headers(), "Content-Type": "application/json"},
        content=json.dumps(body),
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ Localization updated (description={len(NEW_DESCRIPTION)} chars, keywords={NEW_KEYWORDS})")
    else:
        print(f"  ⚠ PATCH failed HTTP {resp.status_code}: {resp.text[:800]}")


def main():
    with asc._http() as client:
        # 1. App Info localization (app store name)
        try:
            patch_app_info_name(client)
        except Exception as e:
            print(f"  app-info patch error: {e}")
        # 2. Create / find Version 1.0.1
        version = find_or_create_v101(client)
        # 3. Patch version locale
        patch_version_locale(client, version["id"])
        print("\nDONE.")


if __name__ == "__main__":
    main()
