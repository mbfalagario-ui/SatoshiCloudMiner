#!/usr/bin/env python3
"""FINAL pre-flight audit before EAS Build #25.

Goes through EVERY Apple Review Guideline that could conceivably
apply to this app, prints PASS/FAIL with evidence, and exits non-zero
on any FAIL. NO build/submit may proceed if this exits non-zero.
"""
from __future__ import annotations
import sys, json, re, pathlib, urllib.request
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
APPINFO_ID = "8a8f0db4-3fd2-4759-90df-30f4791673e2"
APP_ID = a.APP_ID

PASS, FAIL = "✅", "❌"
results = []  # (guideline, status, evidence)


def chk(g: str, ok: bool, ev: str):
    results.append((g, ok, ev))


def http_status(url: str, timeout: int = 10) -> int:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "preflight"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.getcode()
    except Exception:
        return -1


def main() -> int:
    # ── App.json sanity ────────────────────────────────────────
    app_json = json.loads(pathlib.Path("/app/frontend/app.json").read_text())
    ej = app_json["expo"]
    chk("app.json/version",
        ej.get("version") == "1.0.2",
        f"version={ej.get('version')}")
    chk("app.json/buildNumber",
        ej["ios"].get("buildNumber") == "25",
        f"buildNumber={ej['ios'].get('buildNumber')}")
    chk("2.4.1 iPad supportsTablet",
        ej["ios"].get("supportsTablet") is True,
        f"supportsTablet={ej['ios'].get('supportsTablet')}")
    desc_lower = (ej.get("description") or "").lower()
    chk("app.json/description has no 'mining' on-device claim",
        "on-device" not in desc_lower or "no on-device mining" in desc_lower,
        f"description starts: {(ej.get('description') or '')[:80]}…")

    # ── ASC live state ─────────────────────────────────────────
    with a._http() as c:
        # AppInfo
        r = c.get(f"/v1/appInfos/{APPINFO_ID}",
                  headers=a._headers(),
                  params={"include": "primaryCategory,secondaryCategory"})
        aij = r.json()
        prim = (aij["data"]["relationships"].get("primaryCategory") or {}).get("data")
        sec = (aij["data"]["relationships"].get("secondaryCategory") or {}).get("data")
        chk("2.3.6 / 2.3.10 primaryCategory set",
            bool(prim and prim.get("id")),
            f"primary={prim}")
        chk("2.3.6 secondaryCategory set",
            bool(sec and sec.get("id")),
            f"secondary={sec}")
        chk("2.3.6 categories match recommendation",
            (prim or {}).get("id") == "FINANCE" and (sec or {}).get("id") == "UTILITIES",
            f"primary={prim}, secondary={sec}")

        # appInfo localization (name, subtitle, privacyPolicy)
        rr = c.get(f"/v1/appInfos/{APPINFO_ID}/appInfoLocalizations",
                   headers=a._headers())
        en = next((l for l in rr.json().get("data", [])
                   if l["attributes"].get("locale") == "en-US"), None)
        if en:
            la = en["attributes"]
            sub = la.get("subtitle") or ""
            chk("2.3.7 app name (no forbidden words)",
                la.get("name") == "Hashrate Cloud Miner",
                f"name={la.get('name')!r}")
            chk("3.1.5 subtitle does not claim on-device mining",
                "mining" not in sub.lower(),
                f"subtitle={sub!r}")
            chk("subtitle length ≤ 30 chars",
                len(sub) <= 30,
                f"subtitle len={len(sub)}")
            chk("5.1.1(i) privacyPolicyUrl present",
                bool(la.get("privacyPolicyUrl")),
                f"privacyPolicyUrl={la.get('privacyPolicyUrl')!r}")

        # Version localization (description, promo, urls)
        rr = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
                   headers=a._headers())
        vl = next((l for l in rr.json().get("data", [])
                   if l["attributes"].get("locale") == "en-US"), None)
        if vl:
            vla = vl["attributes"]
            d = vla.get("description") or ""
            chk("2.3.1 description does NOT claim on-device mining",
                "no on-device mining" in d.lower()
                or "does not mine on your device" in d.lower(),
                f"description has explicit no-mining clause: "
                f"{'YES' if 'no on-device mining' in d.lower() or 'does not mine on your device' in d.lower() else 'NO'}")
            chk("3.1.5(a) description states non-custodial",
                "non-custodial" in d.lower() or "no private key" in d.lower(),
                f"non-custodial wording: {'YES' if 'non-custodial' in d.lower() else 'NO'}")
            chk("3.1.5(v) description clarifies indicative not guaranteed",
                "indicative" in d.lower() or "illustrative" in d.lower(),
                f"indicative wording: {'YES' if 'indicative' in d.lower() else 'NO'}")
            chk("1.5 supportUrl present and 200",
                http_status(vla.get("supportUrl", "")) == 200,
                f"supportUrl={vla.get('supportUrl')!r}")
            chk("1.5 marketingUrl present and 200",
                http_status(vla.get("marketingUrl", "")) == 200,
                f"marketingUrl={vla.get('marketingUrl')!r}")

        # Review detail
        rr = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
                   headers=a._headers())
        if rr.json().get("data"):
            rd = rr.json()["data"]["attributes"]
            notes = rd.get("notes") or ""
            chk("2.1 reviewer notes ≥ 1500 chars (deep context)",
                len(notes) >= 1500,
                f"notes len={len(notes)}")
            for q in ("mining", "wallet", "lightning", "delete account", "iap", "build #25", "ipad"):
                chk(f"reviewer notes mentions '{q}'",
                    q.lower() in notes.lower(),
                    f"present: {q.lower() in notes.lower()}")
            chk("D demo accounts referenced",
                "appreview1@hashratecloudminer.app" in notes,
                "")
            chk("contact email present",
                "mbfalagario@gmail.com" in notes,
                "")

        # Build attached
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/build", headers=a._headers())
        bd = r.json().get("data")
        if bd:
            rb = c.get(f"/v1/builds/{bd['id']}", headers=a._headers())
            ba = rb.json()["data"]["attributes"]
            chk("build present and VALID",
                ba.get("processingState") == "VALID",
                f"v={ba.get('version')} state={ba.get('processingState')}")

        # IAPs
        r = c.get(f"/v1/apps/{APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = r.json().get("data", [])
        chk("3.1.1 IAP catalog has 10 products",
            len(iaps) == 10,
            f"count={len(iaps)}")
        adfree_ok = False
        all_review_notes_have_consumable_disclaimer = True
        for i in iaps:
            iat = i["attributes"]
            pid = iat["productId"]
            iaptype = iat.get("inAppPurchaseType")
            note = (iat.get("reviewNote") or "").lower()
            if pid == "adfree_399":
                adfree_ok = (iaptype == "NON_CONSUMABLE")
            elif iaptype != "CONSUMABLE":
                chk(f"3.1.2 IAP type {pid}", False,
                    f"expected CONSUMABLE, got {iaptype}")
            if pid != "adfree_399" and "consumable" not in note:
                all_review_notes_have_consumable_disclaimer = False
        chk("3.1.2 adfree_399 is NON_CONSUMABLE", adfree_ok, "")
        chk("3.1.2 review notes mention 'consumable' on 9 packs",
            all_review_notes_have_consumable_disclaimer, "")

        # Production backend health
        prod_urls = [
            "https://api.hashratecloudminer.com/api/system/btc_rate",
            "https://hashratecloudminer.com/",
            "https://hashratecloudminer.com/support",
            "https://hashratecloudminer.com/privacy",
        ]
        for u in prod_urls:
            chk(f"prod 200 {u.split('//')[1].split('/')[1] or 'root'}",
                http_status(u) == 200,
                f"{u}")

        # /api/auth/me DELETE endpoint exists (returns 401 unauth, NOT 404)
        try:
            req = urllib.request.Request(
                "https://api.hashratecloudminer.com/api/auth/me",
                method="DELETE",
                headers={"User-Agent": "preflight"},
            )
            urllib.request.urlopen(req, timeout=10)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception:
            code = -1
        chk("5.1.1(v) DELETE /api/auth/me reachable (401 unauth ok)",
            code == 401, f"code={code}")

        # Frontend code grep — make sure no '30 day' copy remains
        frontend_files = [
            "/app/frontend/app/(tabs)/profile.tsx",
            "/app/frontend/app/(tabs)/shop.tsx",
            "/app/frontend/src/components/AdInterstitial.tsx",
            "/app/frontend/src/utils/iap.ts",
        ]
        for f in frontend_files:
            txt = pathlib.Path(f).read_text()
            chk(f"no '30 day' copy in {f.split('/')[-1]}",
                "30 day" not in txt and "30-day" not in txt,
                "")

    # Print results
    pad = max(len(g) for g, _, _ in results)
    fails = 0
    for g, ok, ev in results:
        sym = PASS if ok else FAIL
        if not ok:
            fails += 1
        print(f"  {sym} {g:<{pad}}  {ev}")

    print()
    if fails:
        print(f"❌ {fails} FAIL(S) — DO NOT PROCEED WITH BUILD")
        return 1
    print(f"🎉 ALL {len(results)} CHECKS PASS — safe to build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
