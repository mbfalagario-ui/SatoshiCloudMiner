#!/usr/bin/env python3
"""Fetch the most recent crash diagnostic for Build #29 from App Store Connect.

ASC exposes per-build crash diagnostic signatures via:
  GET /v1/builds/{id}/diagnosticSignatures
  GET /v1/diagnosticSignatures/{id}/logs   (returns a downloadable .crash URL)

The 'logs' endpoint returns a presigned S3 URL — we follow it and dump the
symbolicated crash text.
"""
from __future__ import annotations
import sys, json, time
sys.path.insert(0, "/app/store")
import asc_metadata_upload as a
import httpx

# Build #29
ASC_BUILD_ID = "c03e4339-5955-4fbf-abe5-c9153dfac9e4"


def main() -> int:
    with a._http() as c:
        # 1) List diagnostic signatures for this build
        r = c.get(
            f"/v1/builds/{ASC_BUILD_ID}/diagnosticSignatures?limit=20",
            headers=a._headers(),
        )
        if r.status_code >= 400:
            print(f"❌ /diagnosticSignatures HTTP {r.status_code}: {r.text[:400]}")
            return 1
        sigs = r.json().get("data", [])
        print(f"Build #29 diagnosticSignatures count: {len(sigs)}\n")
        if not sigs:
            print("(No crash signatures yet for Build #29. TestFlight crash uploads can lag by a few minutes.)")
            return 0
        for sig in sigs:
            attrs = sig["attributes"]
            print(f"  • signature id={sig['id']}")
            print(f"    diagnosticType: {attrs.get('diagnosticType')}")
            print(f"    signature:      {attrs.get('signature')}")
            print(f"    weight:         {attrs.get('weight')}")
            print()

        # 2) Pull logs for the highest-weight signature
        sig_id = max(sigs, key=lambda s: s["attributes"].get("weight") or 0)["id"]
        print(f"\n=== Pulling logs for signature {sig_id} ===\n")
        r = c.get(
            f"/v1/diagnosticSignatures/{sig_id}/logs?limit=3",
            headers=a._headers(),
        )
        if r.status_code >= 400:
            print(f"❌ /logs HTTP {r.status_code}: {r.text[:400]}")
            return 1
        logs = r.json().get("data", [])
        print(f"log entries: {len(logs)}\n")
        for L in logs[:3]:
            url = L["attributes"].get("url")
            if not url:
                continue
            print(f"\n----- crash log {L['id']} -----\n")
            with httpx.Client(timeout=30.0) as plain:
                rr = plain.get(url)
                text = rr.text
                # Print only the most diagnostic parts to save tokens
                lines = text.split("\n")
                # Header (first 40 lines) usually contains crashed thread + exception
                head = lines[:60]
                print("\n".join(head))
                # And the first crashing-thread backtrace
                in_crash_thread = False
                tail = []
                for i, line in enumerate(lines):
                    if "Crashed:" in line or "Last Exception Backtrace" in line:
                        in_crash_thread = True
                        tail.append(line)
                        continue
                    if in_crash_thread:
                        tail.append(line)
                        if line.strip() == "" and len(tail) > 10:
                            break
                if tail:
                    print("\n--- crashed thread / exception ---")
                    print("\n".join(tail[:50]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
