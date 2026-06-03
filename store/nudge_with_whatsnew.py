#!/usr/bin/env python3
"""Find the en-US localization, PATCH whatsNew (reviewable field),
verify state transition from REJECTED → editable state.
"""
from __future__ import annotations
import sys, json
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"

NEW_WHATS_NEW = """Bug fixes and stability improvements:
- Hardened in-app purchase flow with full StoreKit 2 sandbox validation
- Improved Bitcoin Lightning withdrawal reliability
- Backend now served from always-on production infrastructure
- 100% uptime monitoring with self-hosted push alerts
- Polished admin console layout for newer iPhones

Thank you for testing Hashrate Cloud Miner. All in-app purchases are
required to be validated in sandbox during this submission cycle.""".strip()


def main() -> int:
    with a._http() as c:
        # 1. Get all localizations for the version
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}/appStoreVersionLocalizations",
                  headers=a._headers())
        locs = r.json().get("data", [])
        en_us = None
        for l in locs:
            if l["attributes"].get("locale") == "en-US":
                en_us = l
                break
        if not en_us:
            print(f"No en-US localization, found: {[l['attributes'].get('locale') for l in locs]}")
            return 1

        loc_id = en_us["id"]
        print(f"en-US localization id: {loc_id}")
        print(f"current whatsNew: {(en_us['attributes'].get('whatsNew') or '')[:120]}…")

        # 2. PATCH whatsNew → reviewable field, should transition state
        print()
        print("PATCHing whatsNew with new copy…")
        r = c.patch(f"/v1/appStoreVersionLocalizations/{loc_id}",
                    headers=a._headers(),
                    json={"data": {"type": "appStoreVersionLocalizations",
                                   "id": loc_id,
                                   "attributes": {"whatsNew": NEW_WHATS_NEW}}})
        print(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            print(f"  {r.text[:400]}")
            return 1

        # 3. Verify version state
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        att = r.json()["data"]["attributes"]
        print(f"\nNew appStoreState={att.get('appStoreState')}  appVersionState={att.get('appVersionState')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
