#!/usr/bin/env python3
"""Apply fixes A + B + C2 to ASC for v1.0.1 / Build #23.

A) Age-rating declaration: zero out the 7 fields contradicting the app
   (parentalControls, ageAssurance, unrestrictedWebAccess,
   userGeneratedContent, messagingAndChat) + remove the
   ageRatingOverride / ageRatingOverrideV2 / koreaAgeRatingOverride.
   Keep `advertising=True` (AdMob is real) and `gambling=False`.

B) Description: rewrite to remove every "Satoshi Cloud Miner" mention.

C2) URLs: keep satoshicloudminer.app domain but move to /hashrate/* path
    so the displayed URL clearly reflects the new app brand. The reply
    to Apple will explain why the legacy domain is retained.

After these writes, the script does NOT submit the reply nor re-trigger
review. We re-audit and let the operator approve next.
"""
from __future__ import annotations
import json
import sys

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # v1.0.1
APP_ID = a.APP_ID


# --- New description: zero "Satoshi" mentions, Apple-safe wording ---
NEW_DESCRIPTION = """Hashrate Cloud Miner is a Bitcoin cloud-mining dashboard with virtual hashpower, daily check-in rewards, optional rewarded video ads, and instant Lightning Network redeems. The app does not hold, manage, or custody on-chain assets — your wallet remains in your sole control.

Indicative earnings shown are estimates based on your share of the live Bitcoin network hashrate and depend on real network conditions and operator-controlled settings. Earnings are not guaranteed, and the displayed values are illustrative only.

Features:
• 10 hashpower boost packs (in-app purchase) with one-time first-time bonus boosts (15%–50%).
• 7-day daily check-in rewards (1.2 → 8.0 GH/s, 24-hour active boost per day).
• Rewarded video ads for additional virtual hashpower (1.5 → 12 GH/s per ad, capped at 30 ads per day).
• Indicative earnings dashboard with live sub-satoshi ticker.
• Lightning Network redeems (BOLT11 invoices or LN addresses like user@speed.app or user@zbd.gg).
• Non-custodial design: the app never holds your private keys, seed phrase, or on-chain assets.
• In-app FAQ + AI-powered support chat.

Read the in-app Help & FAQs section for full details on hashrate, ad rewards, IAP boost packs, and redemption.
"""

# --- C2: legacy domain, new path so URL itself signals re-brand ---
NEW_MARKETING_URL = "https://satoshicloudminer.app/hashrate"
NEW_SUPPORT_URL = "https://satoshicloudminer.app/hashrate/support"
NEW_PRIVACY_URL = "https://satoshicloudminer.app/hashrate/privacy"


def patch(client, path: str, payload: dict, label: str) -> None:
    r = client.patch(path, headers=a._headers(), json=payload)
    if r.status_code >= 400:
        print(f"  ❌ {label} FAILED  {r.status_code}\n     {r.text[:400]}")
        return
    print(f"  ✅ {label}")


def step_a_age_rating(client):
    print("\n=== STEP A — Age Rating ===")
    # Fetch ageRatingDeclaration ID via appInfo.include
    r = client.get(
        f"/v1/apps/{APP_ID}/appInfos",
        headers=a._headers(),
        params={"include": "ageRatingDeclaration", "limit": 5},
    )
    body = r.json()
    decls = [x for x in (body.get("included") or [])
             if x.get("type") == "ageRatingDeclarations"]
    if not decls:
        print("  ❌ no ageRatingDeclaration to patch")
        return
    # Use the first (current) declaration.
    decl_id = decls[0]["id"]
    print(f"  → ageRatingDeclaration id={decl_id}")
    body_patch = {
        "data": {
            "type": "ageRatingDeclarations",
            "id": decl_id,
            "attributes": {
                # ---- The exact field that triggered the 2.3.6 rejection ----
                "parentalControls": False,
                # ---- Other fields that lied about app capabilities ----
                "ageAssurance": False,
                "unrestrictedWebAccess": False,
                "userGeneratedContent": False,
                "messagingAndChat": False,
                # ---- Korea override → NONE (safe even when V1+V2 conflict) ----
                "koreaAgeRatingOverride": "NONE",
                # ---- Keep AdMob ads disclosed (truthful) ----
                "advertising": True,
            },
        }
    }
    patch(client, f"/v1/ageRatingDeclarations/{decl_id}", body_patch,
          "ageRatingDeclaration: clean content flags")

    # Apple rejects setting `ageRatingOverride` and `ageRatingOverrideV2`
    # in the same PATCH. Do them in two separate writes so the API can
    # transition cleanly. Set V2 → NONE first (this is the current source
    # of truth in newer ASC); if V1 still exists, clear it second.
    patch(client, f"/v1/ageRatingDeclarations/{decl_id}",
          {"data": {"type": "ageRatingDeclarations", "id": decl_id,
                    "attributes": {"ageRatingOverrideV2": "NONE"}}},
          "ageRatingDeclaration: ageRatingOverrideV2 → NONE")
    patch(client, f"/v1/ageRatingDeclarations/{decl_id}",
          {"data": {"type": "ageRatingDeclarations", "id": decl_id,
                    "attributes": {"ageRatingOverride": "NONE"}}},
          "ageRatingDeclaration: ageRatingOverride → NONE")


def step_b_c2_description_urls(client):
    print("\n=== STEP B + C2 — Description + URLs ===")
    r = client.get(
        f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
        headers=a._headers(),
    )
    for loc in r.json().get("data", []):
        if (loc.get("attributes") or {}).get("locale") != "en-US":
            continue
        lid = loc["id"]
        body_patch = {
            "data": {
                "type": "appStoreVersionLocalizations",
                "id": lid,
                "attributes": {
                    "description": NEW_DESCRIPTION,
                    "marketingUrl": NEW_MARKETING_URL,
                    "supportUrl": NEW_SUPPORT_URL,
                },
            }
        }
        patch(client, f"/v1/appStoreVersionLocalizations/{lid}",
              body_patch, "en-US: description + marketingUrl + supportUrl")
        break

    # AppInfoLocalization — privacyPolicyUrl
    r = client.get(
        f"/v1/apps/{APP_ID}/appInfos",
        headers=a._headers(),
        params={"include": "appInfoLocalizations"},
    )
    body = r.json()
    for inc in (body.get("included") or []):
        if inc.get("type") != "appInfoLocalizations":
            continue
        if (inc.get("attributes") or {}).get("locale") != "en-US":
            continue
        aid = inc["id"]
        body_patch = {
            "data": {
                "type": "appInfoLocalizations",
                "id": aid,
                "attributes": {
                    "privacyPolicyUrl": NEW_PRIVACY_URL,
                },
            }
        }
        patch(client, f"/v1/appInfoLocalizations/{aid}",
              body_patch, "en-US appInfo: privacyPolicyUrl")
        break


def main():
    print("==================================================================")
    print("  ASC METADATA FIX — A (age rating) + B (description) + C2 (URLs)")
    print("==================================================================")
    print(f"  App     : {APP_ID}")
    print(f"  Version : {VERSION_ID}  (1.0.1)")
    with a._http() as client:
        step_a_age_rating(client)
        step_b_c2_description_urls(client)
    print()
    print("==================================================================")
    print("  Done. Re-audit next.")
    print("==================================================================")


if __name__ == "__main__":
    main()
