#!/bin/bash
# Convenience wrapper to finish the App Store submission AFTER:
#   1. `eas build --platform ios --profile production` succeeds (Build #18)
#   2. `eas submit --platform ios` uploads the .ipa to App Store Connect
#   3. Apple finishes processing the binary (~5-15 minutes after upload).
#
# At that point the App Store version 1.0 will have a Build attached,
# and we can finally add it to the reviewSubmission and submit the whole
# thing (binary + 10 IAPs auto-bundled) for review.
#
# Usage:
#   ./submit_when_ready.sh           # one-shot — check now, attach if ready
#   ./submit_when_ready.sh --watch   # poll every 60s until version is ready
#
set -e
cd "$(dirname "$0")"

watch=false
[ "$1" = "--watch" ] && watch=true

while true; do
    echo "--- $(date) checking App Store Connect ---"
    out=$(python3 - <<'PY'
import asc_metadata_upload as a
with a._http() as c:
    v = a.find_editable_version(c)
    vid = v["id"]
    r = c.get(f'/v1/appStoreVersions/{vid}', headers=a._headers(),
              params={'include':'build'})
    d = r.json()
    rels = d.get('data',{}).get('relationships',{})
    build = rels.get('build',{}).get('data')
    print('BUILD_READY' if build else 'NO_BUILD_YET')
    print(vid)
PY
)
    state=$(echo "$out" | head -1)
    vid=$(echo "$out" | tail -1)
    echo "  version $vid → $state"
    if [ "$state" = "BUILD_READY" ]; then
        echo ">>> Build is attached. Submitting for review…"
        python3 asc_metadata_upload.py --skip-metadata --skip-media --submit
        echo ">>> Done. Check https://appstoreconnect.apple.com"
        exit 0
    fi
    if ! $watch; then
        echo "Build not yet attached to version. Re-run with --watch to poll."
        exit 1
    fi
    sleep 60
done
