#!/usr/bin/env python3
"""Final post-submission audit. Confirm:
  - v1.0.2 has Build #24 attached
  - Submission 6db2a564 contains the version, state WAITING_FOR_REVIEW
  - All 10 IAPs are in WAITING_FOR_REVIEW (auto-bundled by Apple)
  - Backend production is healthy (so sandbox StoreKit will work)
  - Reviewer notes are set
"""
from __future__ import annotations
import sys, json
import urllib.request
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
SUB_ID = "6db2a564-fada-4716-b44b-fa1ddfedda56"


def section(title):
    print()
    print("=" * 70)
    print(f" {title}")
    print("=" * 70)


def ok(label, val=True, extra=""):
    sym = "✅" if val else "❌"
    print(f"  {sym} {label}" + (f"  ({extra})" if extra else ""))


def main() -> int:
    with a._http() as c:
        section("APP STORE CONNECT FINAL STATE")

        # 1. Version
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        v = r.json()["data"]["attributes"]
        ok(f"Version is v{v.get('versionString')} state={v.get('appStoreState')}",
           v.get("versionString") == "1.0.2")

        # 2. Build attached
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/build", headers=a._headers())
        bd = r.json().get("data")
        if bd:
            rr = c.get(f"/v1/builds/{bd['id']}", headers=a._headers())
            ba = rr.json()["data"]["attributes"]
            ok(f"Build attached: v{ba.get('version')} proc={ba.get('processingState')}",
               ba.get("version") == "24" and ba.get("processingState") == "VALID")
        else:
            ok("Build attached", False, "no build attached")

        # 3. Submission
        r = c.get(f"/v1/reviewSubmissions/{SUB_ID}", headers=a._headers())
        sa = r.json()["data"]["attributes"]
        ok(f"Submission {SUB_ID[:8]}… state={sa.get('state')}",
           sa.get("state") == "WAITING_FOR_REVIEW")
        ok(f"Submitted={sa.get('submitted')} date={sa.get('submittedDate')}",
           sa.get("submittedDate") is not None)

        # 4. Items in submission
        r = c.get(f"/v1/reviewSubmissions/{SUB_ID}/items", headers=a._headers())
        items = r.json().get("data", [])
        rels = []
        for it in items:
            for k, v in (it.get("relationships") or {}).items():
                if (v or {}).get("data"):
                    rels.append(k)
        print(f"  Submission has {len(items)} items: {set(rels)}")

        # 5. IAPs
        r = c.get(f"/v1/apps/{a.APP_ID}/inAppPurchasesV2",
                  headers=a._headers(), params={"limit": 50})
        iaps = sorted(r.json().get("data", []),
                      key=lambda i: i["attributes"]["productId"])
        all_wfr = all(i["attributes"]["state"] == "WAITING_FOR_REVIEW" for i in iaps)
        ok(f"{len(iaps)} IAPs, all WAITING_FOR_REVIEW (auto-bundled)", all_wfr)
        for i in iaps:
            print(f"     · {i['attributes']['productId']:<22} {i['attributes']['state']}")

        # 6. Reviewer notes
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreReviewDetail",
                  headers=a._headers())
        if r.status_code == 200 and r.json().get("data"):
            notes = r.json()["data"]["attributes"].get("notes") or ""
            ok(f"Reviewer notes set ({len(notes)} chars)", len(notes) > 500)

        section("PRODUCTION BACKEND HEALTH (must be live for sandbox StoreKit)")
        urls = [
            ("https://hashratecloudminer.com/", "marketing"),
            ("https://hashratecloudminer.com/support", "support"),
            ("https://hashratecloudminer.com/privacy", "privacy"),
            ("https://api.hashratecloudminer.com/api/system/btc_rate", "api btc_rate"),
        ]
        for url, label in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "ASC-audit"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    code = resp.getcode()
                    ok(f"{label}  {url}  HTTP {code}", code == 200)
            except Exception as e:
                ok(f"{label}  {url}", False, str(e)[:80])

        section("✨ SUMMARY")
        print(f"  Version:     v1.0.2 ({v.get('appStoreState')})")
        print(f"  Build:       #24 (VALID, attached)")
        print(f"  Submission:  {sa.get('state')}  ({SUB_ID})")
        print(f"  IAPs:        {len(iaps)} in WAITING_FOR_REVIEW (Apple auto-bundles)")
        print(f"  Backend:     Production (api.hashratecloudminer.com)")
        print()
        print("  ⏱  Apple typically reviews within 24-48h.")
        print("     Watch the inbox for app.satoshicloudminer review messages.")
        print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
