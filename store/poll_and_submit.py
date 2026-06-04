#!/usr/bin/env python3
"""Poll EAS build status until finished, then auto-submit to TestFlight
via `eas submit`, then resubmit v1.0.2 review in ASC.
"""
import os, subprocess, time, sys, re

BUILD_ID = "c17bd13a-0a9e-42f9-ad32-74c76f4b88d6"
ENV = os.environ.copy()
ENV["EXPO_TOKEN"] = "0qV7z8s8sP5Ql53GhFcv-S_swRWl_nSTvDTymDxA"


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, env=ENV, cwd="/app/frontend", **kw)


def poll() -> str:
    r = run(["eas", "build:view", BUILD_ID])
    out = r.stdout + r.stderr
    m = re.search(r"Status\s+(\S+)", out)
    return m.group(1) if m else "unknown"


def main():
    print(f"[{time.strftime('%H:%M:%S')}] Polling build {BUILD_ID}…", flush=True)
    while True:
        st = poll()
        print(f"[{time.strftime('%H:%M:%S')}] status: {st}", flush=True)
        if st in ("finished", "errored", "canceled"):
            break
        time.sleep(60)

    if st != "finished":
        print(f"❌ Build did not finish cleanly (status={st}). Aborting submit.")
        return 1

    print("\n[submit] Running eas submit…")
    r = run(["eas", "submit",
             "--platform", "ios",
             "--profile", "production-prod-domain",
             "--id", BUILD_ID,
             "--non-interactive"])
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        return 1
    print("\n✅ Submitted to App Store Connect. Apple will now process the binary (5-10 min).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
