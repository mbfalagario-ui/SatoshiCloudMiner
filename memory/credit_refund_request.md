# Emergent Credit Adjustment Request — Case File (prepared 2026-06-10)

**To:** support@emergent.sh
**Subject:** Credit adjustment request — agent-caused out-of-scope regression/deployment loop during Apple hotfix task

## Account / job identifiers
- Workspace: ios-clone-platform (preview: ios-clone-platform.preview.emergentagent.com)
- App: Hashrate Cloud Miner (iOS bundle app.satoshicloudminer, ASC App ID 6773104756)
- Job ID: [user: click the "i" button in top-right of the Emergent chat to copy it]

## Reason
Agent introduced out-of-scope regression/deployment loop during Apple hotfix task.

## Credits requested back — exact actions that consumed them
1. **Stale EAS Build 38** — EAS build id `d2b73462-ec2a-4e2d-b4df-e38f6ed43f22`,
   built 2026-06-10 13:46 UTC from commit `244f89a`, BEFORE the final hotfix commits
   (`5fdea7a` 14:52, `4cd7b96` 15:28) landed. The IPA is unusable for App Store
   submission; one EAS build credit + associated Emergent agent credits wasted.
2. **Regression repair loops** — agent credits consumed across the Build 37 → Build 38
   repair cycle (banner-removal fix that introduced page-load delay + duplicate FAQ
   regressions, then required a second full repair session).
3. **Out-of-scope deployment/Kubernetes cleanup** — agent credits consumed on
   Emergent-deployment readiness work and broad diagnostics beyond the narrow Apple
   Build 38 hotfix, which then required a containment/rollback session to undo
   (.gitignore/.dockerignore .env changes, api.ts change — all reverted 2026-06-10).

## Request
- Credit adjustment/refund for the above per Emergent policy.
- Confirmation that no additional credits will be charged for correcting the
  agent-caused loop, if policy allows.
- A ticket/reference ID and expected timeline.

## Status
- 2026-06-10: Agent attempted internal processing via Emergent support channel —
  confirmed NO internal/automated credit-refund mechanism is available to agents.
  Official channel is support@emergent.sh. This file is the complete case; forward as-is.
