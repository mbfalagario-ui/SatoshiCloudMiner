#!/usr/bin/env python3
"""Cancel ALL non-terminal review submissions for this app, including
the original UNRESOLVED_ISSUES one. Then verify the app is ready for
a new version. Read-write but only on submissions.
"""
from __future__ import annotations
import sys, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a


def main() -> int:
    with a._http() as c:
        # List ALL submissions (no filter)
        r = c.get("/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"filter[app]": a.APP_ID,
                          "filter[platform]": "IOS",
                          "limit": 50})
        subs = r.json().get("data", []) if r.status_code < 400 else []
        print(f"Found {len(subs)} submissions total")
        for s in subs:
            sid = s["id"]
            st = s["attributes"].get("state")
            sub_date = s["attributes"].get("submittedDate")
            print(f"  {sid}  state={st}  submittedDate={sub_date}")

        # Cancel each non-terminal one
        targets = [s for s in subs
                   if s["attributes"].get("state") not in ("COMPLETE", "CANCELED")]
        print(f"\nWill cancel {len(targets)} non-terminal submissions")

        for s in targets:
            sid = s["id"]
            st = s["attributes"].get("state")
            print(f"\n→ Cancelling {sid} (state={st})…")
            # Strategy 1: PATCH canceled=True
            r = c.patch(f"/v1/reviewSubmissions/{sid}",
                        headers=a._headers(),
                        json={"data": {"type": "reviewSubmissions",
                                       "id": sid,
                                       "attributes": {"canceled": True}}})
            print(f"  PATCH canceled=True → HTTP {r.status_code}")
            if r.status_code >= 400:
                print(f"  body: {r.text[:400]}")

                # Strategy 2: DELETE
                rr = c.delete(f"/v1/reviewSubmissions/{sid}", headers=a._headers())
                print(f"  DELETE → HTTP {rr.status_code}")
                if rr.status_code >= 400:
                    print(f"  body: {rr.text[:400]}")

            # Poll until non-active
            for i in range(8):
                time.sleep(2)
                rr = c.get(f"/v1/reviewSubmissions/{sid}", headers=a._headers())
                if rr.status_code == 404:
                    print(f"  poll {i+1}: deleted (404)")
                    break
                nst = rr.json()["data"]["attributes"].get("state")
                print(f"  poll {i+1}: state={nst}")
                if nst in ("CANCELED", "COMPLETE"):
                    break

        # Final state
        r = c.get("/v1/reviewSubmissions",
                  headers=a._headers(),
                  params={"filter[app]": a.APP_ID,
                          "filter[platform]": "IOS",
                          "limit": 20,
                          "sort": "-submittedDate"})
        print("\nFinal submission states:")
        for s in r.json().get("data", []):
            sid = s["id"]
            st = s["attributes"].get("state")
            print(f"  {sid}: {st}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
