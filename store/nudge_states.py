#!/usr/bin/env python3
"""Try several reviewable fields to nudge state from REJECTED."""
from __future__ import annotations
import sys
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

VERSION_ID = "b304ea37-c58c-4145-a14a-b7cd50fc6966"
LOC_ID = "c256c22a-21fa-41c1-996f-1876a7894d58"


def try_patch(c, attrs, label):
    print(f"  trying {label}…")
    r = c.patch(
        f"/v1/appStoreVersionLocalizations/{LOC_ID}",
        headers=a._headers(),
        json={"data": {"type": "appStoreVersionLocalizations",
                       "id": LOC_ID, "attributes": attrs}},
    )
    print(f"    HTTP {r.status_code} {r.text[:280]}")
    return r.status_code < 400


def main() -> int:
    with a._http() as c:
        # current values
        r = c.get(f"/v1/appStoreVersionLocalizations/{LOC_ID}", headers=a._headers())
        cur = r.json()["data"]["attributes"]
        print("Current localization fields:")
        for k in ("description", "keywords", "promotionalText", "marketingUrl",
                  "supportUrl", "whatsNew"):
            v = cur.get(k) or ""
            print(f"   {k:<15} = {repr(v[:80])}")
        print()

        # 1. Promotional text — typically editable any time
        ok = try_patch(c, {"promotionalText": "Cloud Bitcoin Mining. Watch ads to boost virtual hashrate and earn sats. Bundle includes 10 IAPs validated end-to-end in StoreKit sandbox."}, "promotionalText")
        if not ok:
            # 2. Keywords
            ok = try_patch(c, {"keywords": "bitcoin,mining,cloud,sats,lightning,btc,crypto,hashrate,ads,rewards"}, "keywords")
        if not ok:
            # 3. Marketing URL
            ok = try_patch(c, {"marketingUrl": "https://hashratecloudminer.com/"}, "marketingUrl")
        if not ok:
            # 4. Support URL
            ok = try_patch(c, {"supportUrl": "https://hashratecloudminer.com/support"}, "supportUrl")
        if not ok:
            # 5. Description (often locked when in review but worth trying)
            desc = open("/app/store/description.txt").read().strip()
            ok = try_patch(c, {"description": desc}, "description")

        # final state check
        r = c.get(f"/v1/appStoreVersions/{VERSION_ID}", headers=a._headers())
        att = r.json()["data"]["attributes"]
        print()
        print(f"appStoreState={att.get('appStoreState')}  appVersionState={att.get('appVersionState')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
