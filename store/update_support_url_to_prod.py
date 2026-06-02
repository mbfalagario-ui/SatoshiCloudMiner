#!/usr/bin/env python3
"""Update App Store Connect Support URL + Marketing URL to point to the
production custom domain instead of the flaky `preview.emergentagent.com`.

Must be run AFTER:
  1. hashratecloudminer.com is registered + DNS resolves.
  2. The Fly.io backend is deployed and `https://hashratecloudminer.com/support`
     + `/privacy` both return HTTP 200 with valid HTML.

Usage:
    DOMAIN="hashratecloudminer.com" python3 /app/store/update_support_url_to_prod.py

Defaults to hashratecloudminer.com if DOMAIN env var is unset.

What it does:
  • Locates the en-US appStoreVersionLocalization for v1.0.1.
  • PATCHes supportUrl + marketingUrl to the new domain.
  • Verifies the URLs return HTTP 200 with a fresh GET before patching.
  • Will refuse to patch if the live URLs aren't healthy.
"""
from __future__ import annotations
import os
import sys
import httpx

sys.path.insert(0, "/app/store")
import asc_metadata_upload as a   # provides _http, _headers, APP_ID, etc.

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"


def _check(url: str) -> tuple[int, int]:
    r = httpx.get(url, follow_redirects=True, timeout=10.0,
                  headers={"User-Agent": "AppleReviewer/1.0"})
    return r.status_code, len(r.content)


def main() -> int:
    domain = os.environ.get("DOMAIN", "hashratecloudminer.com").rstrip("/")
    support_url = f"https://{domain}/support"
    marketing_url = f"https://{domain}/"
    privacy_url = f"https://{domain}/privacy"

    print("=" * 70)
    print(f"  Updating ASC URLs to production domain: {domain}")
    print("=" * 70)
    print(f"  Support:   {support_url}")
    print(f"  Privacy:   {privacy_url}")
    print(f"  Marketing: {marketing_url}")
    print()

    # 1) Pre-flight: confirm the new URLs are healthy.
    for label, url in (("Support", support_url), ("Privacy", privacy_url),
                       ("Marketing", marketing_url)):
        try:
            code, size = _check(url)
        except Exception as exc:
            print(f"❌ {label} URL fetch FAILED ({exc!r}). Aborting.")
            return 1
        ok = code == 200 and size > 200
        flag = "✅" if ok else "❌"
        print(f"  {flag} {label:<10} {url}   HTTP {code}  {size} bytes")
        if not ok:
            print("  → URL is not healthy. Aborting. Fix the deployment first.")
            return 1

    # 2) Find the en-US localization on v1.0.1.
    with a._http() as c:
        r = c.get(
            f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
            headers=a._headers(),
        )
        if r.status_code >= 400:
            print(f"❌ list localizations failed: {r.status_code} {r.text[:300]}")
            return 1
        locs = r.json().get("data", [])
        en = next(
            (lc for lc in locs if (lc.get("attributes") or {}).get("locale") == "en-US"),
            None,
        )
        if not en:
            print("❌ no en-US localization found.")
            return 1
        loc_id = en["id"]
        cur = en["attributes"]
        print(f"\n  loc id={loc_id}")
        print(f"  current supportUrl   = {cur.get('supportUrl')}")
        print(f"  current marketingUrl = {cur.get('marketingUrl')}")

        # 3) PATCH new URLs.
        body = {
            "data": {
                "type": "appStoreVersionLocalizations",
                "id": loc_id,
                "attributes": {
                    "supportUrl": support_url,
                    "marketingUrl": marketing_url,
                },
            }
        }
        rr = c.patch(
            f"/v1/appStoreVersionLocalizations/{loc_id}",
            headers=a._headers(),
            json=body,
        )
        if rr.status_code >= 400:
            print(f"❌ patch failed: {rr.status_code} {rr.text[:300]}")
            return 1
        new_attrs = rr.json()["data"]["attributes"]
        print()
        print("  ✅ patched. New ASC values:")
        print(f"     supportUrl   = {new_attrs.get('supportUrl')}")
        print(f"     marketingUrl = {new_attrs.get('marketingUrl')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
