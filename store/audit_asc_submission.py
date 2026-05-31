#!/usr/bin/env python3
"""ASC submission audit for v1.0.1 / Build #23 — read-only.

Inspects every metadata field that has historically triggered Apple
rejections for crypto / cloud-mining / IAP / AdMob apps.

Output: structured PASS/FAIL report on stdout. NO writes.
"""
from __future__ import annotations
import json
import sys

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"   # v1.0.1
BUILD_ID = "c0a39062-453f-4690-b867-f35e0295dfc3"     # Build #23

results: list[tuple[str, str, str, str]] = []  # (section, item, status, detail)


def add(section, item, status, detail=""):
    results.append((section, item, status, detail))


def check(section, item, ok, ok_detail="", fail_detail=""):
    add(section, item, "PASS" if ok else "FAIL", ok_detail if ok else fail_detail)


def short(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    s = str(s).replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")


with a._http() as c:
    H = a._headers()

    # ----------------------------------------------------------------
    # APP-LEVEL: name, bundle ID, age-rating declaration relationships
    # ----------------------------------------------------------------
    r = c.get(f"/v1/apps/{a.APP_ID}", headers=H, params={"include": "appInfos"})
    r.raise_for_status()
    app = r.json().get("data", {})
    name = app.get("attributes", {}).get("name")
    bundle = app.get("attributes", {}).get("bundleId")
    sku = app.get("attributes", {}).get("sku")
    check("App", "Name", "satoshi" not in (name or "").lower(),
          f"name={name}", f"name still contains 'satoshi': {name}")
    check("App", "Bundle ID", bundle == "app.satoshicloudminer",
          f"bundle={bundle}", f"unexpected bundle id: {bundle}")
    add("App", "SKU", "INFO", f"sku={sku}")

    # ----------------------------------------------------------------
    # AGE-RATING DECLARATION (the field that just rejected us)
    # ----------------------------------------------------------------
    r = c.get(
        f"/v1/apps/{a.APP_ID}/appInfos",
        headers=H,
        params={"include": "ageRatingDeclaration", "limit": 5},
    )
    r.raise_for_status()
    body = r.json()
    age_decls = [
        inc for inc in (body.get("included") or [])
        if inc.get("type") == "ageRatingDeclarations"
    ]
    if not age_decls:
        add("Age Rating", "ageRatingDeclaration", "WARN",
            "No ageRatingDeclaration found on any appInfo.")
    else:
        for decl in age_decls:
            attrs = decl.get("attributes") or {}
            parental = attrs.get("seventeenPlus")  # placeholder; full list below
            keys_of_interest = [
                "alcoholTobaccoOrDrugUseOrReferences",
                "contests",
                "gamblingSimulated",
                "gamblingAndContests",
                "horrorOrFearThemes",
                "matureOrSuggestiveThemes",
                "medicalOrTreatmentInformation",
                "profanityOrCrudeHumor",
                "sexualContentGraphicAndNudity",
                "sexualContentOrNudity",
                "violenceCartoonOrFantasy",
                "violenceRealistic",
                "violenceRealisticProlongedGraphicOrSadistic",
                "kidsAgeBand",
                "unrestrictedWebAccess",
                "seventeenPlus",
                "gambling",
                # Parental-controls / In-App-Controls field (camelCase per ASC API)
                "appearsToBeFortuneTellingApp",
                "appropriateForKidsCategory",
            ]
            for k in keys_of_interest:
                v = attrs.get(k)
                if v is not None:
                    add("Age Rating",
                        f"attr.{k}",
                        "INFO",
                        f"value={v}")
            # The literal "Parental Controls" question maps to either
            # `appearsToBeFortuneTellingApp`, `gambling`, OR none. Apple has
            # a separate `parentalControlsBuiltIn` style field; surface ANY
            # non-NONE value so we don't miss it.
            non_none = {k: v for k, v in attrs.items()
                        if isinstance(v, str) and v.upper() not in {"NONE", "NO"}}
            check("Age Rating",
                  "non-NONE entries (any of these caused the rejection)",
                  len(non_none) == 0,
                  "All entries set to NONE/NO.",
                  f"{len(non_none)} non-NONE: {json.dumps(non_none)[:240]}")

    # ----------------------------------------------------------------
    # VERSION 1.0.1 — review notes, demo account, encryption
    # ----------------------------------------------------------------
    r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=H,
              params={"include": "appStoreReviewDetail,build"})
    r.raise_for_status()
    body = r.json()
    v_attrs = body.get("data", {}).get("attributes", {})
    add("Version", "versionString", "INFO", v_attrs.get("versionString"))
    add("Version", "state", "INFO", v_attrs.get("appStoreState"))
    add("Version", "releaseType", "INFO", v_attrs.get("releaseType"))

    review_detail = next(
        (inc for inc in (body.get("included") or [])
         if inc.get("type") == "appStoreReviewDetails"),
        None,
    )
    if not review_detail:
        # Fetch directly
        r2 = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail", headers=H)
        if r2.status_code == 200:
            review_detail = r2.json().get("data")
    if review_detail:
        ra = review_detail.get("attributes") or {}
        check("Review", "contact_first_name", bool(ra.get("contactFirstName")),
              ra.get("contactFirstName"), "missing contactFirstName")
        check("Review", "contact_last_name", bool(ra.get("contactLastName")),
              ra.get("contactLastName"), "missing contactLastName")
        check("Review", "contact_phone", bool(ra.get("contactPhone")),
              ra.get("contactPhone"), "missing contactPhone")
        check("Review", "contact_email", bool(ra.get("contactEmail")),
              ra.get("contactEmail"), "missing contactEmail")
        check("Review", "demo_account_required",
              ra.get("demoAccountRequired") is not None,
              f"demoAccountRequired={ra.get('demoAccountRequired')}",
              "demoAccountRequired not set")
        check("Review", "demo_account_name",
              bool(ra.get("demoAccountName")),
              f"demo user={ra.get('demoAccountName')}",
              "demoAccountName missing — reviewer can't sign in")
        check("Review", "demo_account_password",
              bool(ra.get("demoAccountPassword")),
              "set",
              "demoAccountPassword missing — reviewer can't sign in")
        check("Review", "notes",
              bool(ra.get("notes")) and len(ra.get("notes", "")) > 80,
              f"notes={short(ra.get('notes'), 80)} (len={len(ra.get('notes') or '')})",
              "Notes too short — needed to explain AdMob + non-custodial flow")
    else:
        add("Review", "appStoreReviewDetail", "FAIL", "No reviewer details set!")

    # ----------------------------------------------------------------
    # BUILD-LEVEL: encryption export compliance
    # ----------------------------------------------------------------
    r = c.get(f"/v1/builds/{BUILD_ID}", headers=H)
    r.raise_for_status()
    b_attrs = r.json().get("data", {}).get("attributes", {})
    add("Build", "version", "INFO", b_attrs.get("version"))
    add("Build", "processingState", "INFO", b_attrs.get("processingState"))
    add("Build", "expirationDate", "INFO", b_attrs.get("expirationDate"))
    enc = b_attrs.get("usesNonExemptEncryption")
    check("Build", "Encryption Export Compliance",
          enc is not None,
          f"usesNonExemptEncryption={enc}",
          "usesNonExemptEncryption not declared — Apple may reject")

    # ----------------------------------------------------------------
    # LOCALIZATION: name, subtitle, description, keywords, promo text, URLs
    # ----------------------------------------------------------------
    r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
              headers=H)
    r.raise_for_status()
    locs = r.json().get("data", [])
    for loc in locs:
        la = loc.get("attributes") or {}
        lang = la.get("locale", "?")
        check("Localization",
              f"{lang} name no 'satoshi'",
              "satoshi" not in (la.get("description") or "").lower()
              and "satoshi" not in (la.get("keywords") or "").lower()
              and "satoshi" not in (la.get("promotionalText") or "").lower(),
              "no 'satoshi' references",
              f"'satoshi' STILL present in description/keywords/promo")
        check("Localization", f"{lang} description",
              bool(la.get("description")) and len(la.get("description") or "") > 200,
              f"len={len(la.get('description') or '')}",
              f"description too short ({len(la.get('description') or '')} chars)")
        check("Localization", f"{lang} keywords",
              bool(la.get("keywords")),
              f"keywords={short(la.get('keywords'), 80)}",
              "keywords missing")
        check("Localization", f"{lang} marketingUrl",
              bool(la.get("marketingUrl")),
              la.get("marketingUrl"),
              "marketingUrl missing")
        check("Localization", f"{lang} supportUrl",
              bool(la.get("supportUrl")),
              la.get("supportUrl"),
              "supportUrl missing")
        check("Localization", f"{lang} privacyPolicyUrl (via appInfo)",
              True, "(checked via appInfo below)", "")
        check("Localization", f"{lang} promotionalText",
              bool(la.get("promotionalText")),
              short(la.get("promotionalText"), 80),
              "promotionalText missing")
        check("Localization", f"{lang} whatsNew",
              True if v_attrs.get("versionString") == "1.0.1" else bool(la.get("whatsNew")),
              "1.0 family — whatsNew not required",
              "whatsNew missing on update")

    # ----------------------------------------------------------------
    # APP-INFO LOCALIZATIONS: privacyPolicyUrl, privacy choices
    # ----------------------------------------------------------------
    r = c.get(
        f"/v1/apps/{a.APP_ID}/appInfos",
        headers=H,
        params={"limit": 5,
                "include": "appInfoLocalizations"},
    )
    r.raise_for_status()
    body = r.json()
    ail = [inc for inc in (body.get("included") or [])
           if inc.get("type") == "appInfoLocalizations"]
    for loc in ail:
        la = loc.get("attributes") or {}
        lang = la.get("locale", "?")
        check("App Info", f"{lang} privacyPolicyUrl",
              bool(la.get("privacyPolicyUrl")),
              la.get("privacyPolicyUrl"),
              "privacyPolicyUrl MISSING — 2.3.6 / 5.1.1 risk")
        check("App Info", f"{lang} name no 'satoshi'",
              "satoshi" not in (la.get("name") or "").lower(),
              la.get("name"),
              f"App Info name still has 'satoshi': {la.get('name')}")
        check("App Info", f"{lang} subtitle no 'satoshi'",
              "satoshi" not in (la.get("subtitle") or "").lower(),
              la.get("subtitle"),
              f"subtitle still has 'satoshi': {la.get('subtitle')}")

    # ----------------------------------------------------------------
    # SCREENSHOTS — must have on iPhone 6.5" and 6.7" at minimum
    # ----------------------------------------------------------------
    r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
              headers=H)
    locs = r.json().get("data", [])
    for loc in locs:
        loc_id = loc["id"]
        r2 = c.get(
            f"/v1/appStoreVersionLocalizations/{loc_id}/appScreenshotSets",
            headers=H,
        )
        sets = r2.json().get("data", [])
        per_type: dict[str, int] = {}
        for s in sets:
            kind = (s.get("attributes") or {}).get("screenshotDisplayType")
            r3 = c.get(
                f"/v1/appScreenshotSets/{s['id']}/appScreenshots",
                headers=H,
            )
            n = len(r3.json().get("data", []))
            per_type[kind] = n
        required = ["APP_IPHONE_67", "APP_IPHONE_65"]
        for k in required:
            check("Screenshots",
                  f"{loc.get('attributes',{}).get('locale')} {k}",
                  per_type.get(k, 0) >= 3,
                  f"{per_type.get(k, 0)} screenshots",
                  f"only {per_type.get(k, 0)} screenshots (need ≥3)")
        for k, n in per_type.items():
            if k not in required:
                add("Screenshots",
                    f"{loc.get('attributes',{}).get('locale')} {k}",
                    "INFO", f"{n} screenshots")

    # ----------------------------------------------------------------
    # IAP STATUS — every 10 SKUs must be APPROVED / READY for review
    # ----------------------------------------------------------------
    r = c.get(f"/v2/apps/{a.APP_ID}/inAppPurchases", headers=H,
              params={"limit": 50})
    if r.status_code == 200:
        iaps = r.json().get("data", [])
        add("IAP", "Count", "INFO", f"{len(iaps)} products")
        bad = []
        for p in iaps:
            attrs = p.get("attributes") or {}
            pid = attrs.get("productId")
            state = attrs.get("state")
            name_iap = attrs.get("name")
            if "satoshi" in (name_iap or "").lower():
                bad.append(f"{pid}: name contains 'satoshi' ({name_iap})")
            if state not in {"READY_TO_SUBMIT", "WAITING_FOR_REVIEW",
                             "APPROVED", "IN_REVIEW", "READY_FOR_SALE",
                             "AUTOMATICALLY_APPROVED", "PROCESSING_CONTENT"}:
                bad.append(f"{pid}: state={state}")
        check("IAP", "All products clean",
              len(bad) == 0,
              "All IAPs in good state, no 'satoshi' leftovers.",
              "; ".join(bad))

# ----------------------------------------------------------------
# REPORT
# ----------------------------------------------------------------
print()
print("=" * 78)
print(f"  ASC SUBMISSION AUDIT — v1.0.1 / Build #23")
print("=" * 78)
counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}
by_section: dict[str, list[tuple[str, str, str]]] = {}
for section, item, status, detail in results:
    by_section.setdefault(section, []).append((item, status, detail))
    counts[status] = counts.get(status, 0) + 1

icons = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️ ", "INFO": "ℹ️ "}
for section, rows in by_section.items():
    print()
    print(f"── {section} " + "─" * (66 - len(section)))
    for item, status, detail in rows:
        print(f"  {icons[status]} {item:<55s} {detail}")

print()
print("=" * 78)
print(f"  TOTAL: {counts['PASS']} PASS · {counts['FAIL']} FAIL · "
      f"{counts['WARN']} WARN · {counts['INFO']} INFO")
print("=" * 78)
