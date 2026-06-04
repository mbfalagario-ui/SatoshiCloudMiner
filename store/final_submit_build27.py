#!/usr/bin/env python3
"""Final submit of reviewSubmission ababd766 (Build #27 attached)."""
import sys, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a

SUB_ID = "ababd766-f1b0-4613-b911-923c75c208cd"

with a._http() as c:
    print(f"=== Submitting reviewSubmission {SUB_ID} ===")
    r = c.patch(f"/v1/reviewSubmissions/{SUB_ID}",
                headers=a._headers(),
                json={"data": {"type": "reviewSubmissions",
                               "id": SUB_ID,
                               "attributes": {"submitted": True}}})
    print(f"HTTP {r.status_code}")
    if r.status_code >= 400:
        print(r.text)
        sys.exit(1)

    time.sleep(5)
    r = c.get(f"/v1/reviewSubmissions/{SUB_ID}?include=items", headers=a._headers())
    d = r.json()["data"]["attributes"]
    print(f"\n✅ Submission state: {d.get('state')}")
    print(f"   submittedDate: {d.get('submittedDate')}")
    items = r.json().get("included", [])
    print(f"   items attached: {len(items)}")
    for it in items:
        print(f"     - {it['type']} id={it['id']} state={it['attributes'].get('state')}")
