# Deploy Trigger

This file exists solely to trigger Fly.io auto-deploy on commits to `main`.
Touching it (timestamp bumps) re-runs the FastAPI backend build/deploy
pipeline without changing any application code, secrets, or behaviour.

| Field | Value |
|---|---|
| Trigger reason | Apple App Store remediation — Build #34 backend deploy |
| Triggered at | 2026-06-07T17:48:00Z |
| Triggered by | Main agent (per user instruction) |
| Pod HEAD at trigger time | (recorded on commit) |

> No application logic, Apple keys, IAP code, secrets, or iOS source were
> modified to produce this trigger. The sole purpose is to cause Fly's
> GitHub-auto-deploy hook to rebuild the `backend/` Dockerfile against
> the current `main`.
