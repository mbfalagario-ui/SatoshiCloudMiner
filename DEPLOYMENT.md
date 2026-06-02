# Hashrate Cloud Miner — Production Deployment Runbook

This runbook moves the backend off the flaky `preview.emergentagent.com`
URL (which intermittently 404s and triggered Apple's 4th rejection) onto
a permanent, production-grade stack:

| Layer    | Service                  | Cost          |
|----------|--------------------------|---------------|
| Domain   | Cloudflare Registrar     | ~$10.44/yr    |
| DNS      | Cloudflare (free)        | $0            |
| Compute  | Fly.io shared-cpu-1x     | $0 (free tier)|
| Database | MongoDB Atlas M0         | $0 (free tier)|
| Monitor  | UptimeRobot              | $0 (free tier)|

Total: **~$10/yr + 1 EAS build credit** (only when you say "go").

---

## ⏱️ Approximate timeline

| Phase | Time | Cost | Who |
|-------|------|------|-----|
| 1. Domain registration         | 5 min  | $10.44 | You |
| 2. Cloudflare DNS setup        | 5 min  | $0     | You + me |
| 3. MongoDB Atlas cluster       | 10 min | $0     | You + me |
| 4. Fly.io app + deploy         | 15 min | $0     | Me (needs your token) |
| 5. DB migration                | 5 min  | $0     | Me |
| 6. ASC URL update              | 1 min  | $0     | Me (API) |
| 7. Pre-flight monitoring (24h) | wait   | $0     | UptimeRobot |
| 8. EAS Build #24 + ASC submit  | 30 min | 1 EAS  | Me (requires explicit GO) |
| **Total** | ~1 hour active + 24h burn-in | **~$10 + 1 EAS** | |

---

## Phase 1 — Register `hashratecloudminer.com`

**You do this:**

1. Open https://dash.cloudflare.com/ and create a free account (if you don't already have one).
2. Go to **Domain Registration → Register Domains**.
3. Search `hashratecloudminer.com` — current price is shown as `$10.44/yr` at cost.
4. Add it to cart and check out.  ✅
5. Domain will be auto-added to your Cloudflare account with default DNS.

> **Note**: Cloudflare Registrar is at-cost (no markup). The .com TLD is
> mandatory because Apple periodically rejects `.app` for non-application
> projects.

**Tell me when done.** Share:
- A screenshot of the domain in your CF account, OR just say "registered".

---

## Phase 2 — Cloudflare DNS records

I'll set these up once you give me API access — but you can do it manually:

| Type | Name | Content | Proxy | TTL |
|------|------|---------|-------|-----|
| A    | @ (root) | (Fly IP — I'll fetch after deploy) | DNS-only | Auto |
| A    | api  | (same Fly IP)                       | DNS-only | Auto |
| AAAA | @    | (Fly IPv6 — I'll fetch)             | DNS-only | Auto |
| AAAA | api  | (same Fly IPv6)                     | DNS-only | Auto |

> **Critical**: Set proxy mode to **DNS-only** (gray cloud), not Proxied (orange).
> Fly.io issues its own TLS cert via Let's Encrypt — the CF proxy would interfere.

**You either:**
- (a) Create a Cloudflare API token with `Zone: DNS: Edit` scope on
  hashratecloudminer.com and give it to me, OR
- (b) Click through the UI yourself after I run `fly ips list` to get the IPs.

Option (a) is faster (I do it). Option (b) is more transparent (you do it).

---

## Phase 3 — MongoDB Atlas free tier

**You do this** (5 min):

1. Open https://cloud.mongodb.com/ → Sign Up.
2. Create a free **M0** cluster (512MB shared, free forever).
3. Region: pick **AWS N. Virginia (us-east-1)** to match Fly.io `iad`.
4. **Database Access → Add New Database User**:
   - Username: `hashcloud_prod`
   - Password: generate strong (use the auto-gen button)
   - Role: `Read and write to any database`
5. **Network Access → Add IP Address → ALLOW ACCESS FROM ANYWHERE**
   (Fly.io has dynamic egress IPs; we'll restrict later if Atlas adds Fly support)
6. **Cluster → Connect → Drivers → Node.js (any driver)**:
   - Copy the connection string. It will look like:
     `mongodb+srv://hashcloud_prod:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
7. Replace `<password>` with the real one and **send it to me securely**.

I will use that string as `MONGO_URL` in `fly secrets`.

---

## Phase 4 — Fly.io deployment

**You do this** (5 min):

1. Install Fly CLI on your local machine (not strictly required since I can do it from here too):
   ```
   curl -L https://fly.io/install.sh | sh
   ```
2. Open https://fly.io/app/sign-up and create a free account.
3. **No credit card needed for the free tier**, but Fly may ask. You can add it later if we exceed the free quota (we won't).
4. Go to **https://fly.io/user/personal_access_tokens** → **Create access token**:
   - Name: `hashrate-cloud-miner-deploy`
   - Expiration: 90 days
5. Copy the token and send it to me.

**I will then run** (with your authorization):
```bash
cd /app/backend
flyctl auth login --access-token <YOUR_TOKEN>
flyctl launch --no-deploy           # creates the app from fly.toml
flyctl secrets set MONGO_URL="mongodb+srv://..." \
                   JWT_SECRET_KEY="<existing one>" \
                   EMERGENT_LLM_KEY="<from .env>" \
                   BLINK_API_KEY="<from .env>" \
                   BTCPAY_API_KEY="<from .env>" \
                   ADMIN_INITIAL_PASSWORD="<from .env>" \
                   APPLE_SHARED_SECRET="<from .env>" \
                   EXPO_TOKEN="<from .env>" \
                   APPLE_PRIVATE_KEY_B64="$(base64 -w 0 keys/SubscriptionKey_J55DSC44V5.p8)" \
                   ADMOB_SSV_PUBLIC_KEY="<from .env, multiline>"
flyctl deploy
flyctl status                       # confirm machine is "started"
flyctl logs                         # check no startup errors
```

After deploy I'll fetch the public IPs:
```bash
flyctl ips list
# v4   66.241.125.x   public, dedicated, 2026-06-02
# v6   2a09:8280:1::1234   public, dedicated, 2026-06-02
```

---

## Phase 5 — Point DNS at Fly + add custom domain

```bash
flyctl certs add hashratecloudminer.com
flyctl certs add api.hashratecloudminer.com
flyctl certs show hashratecloudminer.com    # waits for DNS to resolve
```

Then I create the A/AAAA records in Cloudflare (via API or you click through UI).
Within ~30 seconds, Fly issues Let's Encrypt certs and both domains return 200.

**Verification:**
```bash
curl -sI https://hashratecloudminer.com/support      # HTTP 200
curl -sI https://api.hashratecloudminer.com/api/system/btc_rate    # HTTP 200
curl -s -X POST https://api.hashratecloudminer.com/api/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"appreview1@hashratecloudminer.app","password":"AppReview2026!"}'
# should return {"access_token":"...","user":{...}}
```

---

## Phase 6 — Migrate database to Atlas

```bash
SRC_MONGO_URL="mongodb://localhost:27017" \
DST_MONGO_URL="mongodb+srv://..." \
DB_NAME="hashcloud_db" \
python3 /app/scripts/migrate_db_to_atlas.py
```

Output will show per-collection source/dest counts. Re-run is safe (idempotent upserts).

---

## Phase 7 — Update App Store Connect URLs (zero credits)

```bash
DOMAIN="hashratecloudminer.com" python3 /app/store/update_support_url_to_prod.py
```

This will:
1. Pre-flight `/support`, `/privacy`, `/` — abort if any aren't 200 OK.
2. PATCH the v1.0.1 en-US localization's `supportUrl` + `marketingUrl` via ASC API.
3. Print before/after values so we can verify.

---

## Phase 8 — 24-hour burn-in (UptimeRobot free monitoring)

**I do this**:

1. Sign you up at https://uptimerobot.com/ (free tier: 50 monitors, 5-min interval).
2. Add 3 monitors:
   - `https://api.hashratecloudminer.com/api/system/btc_rate` (HEAD)
   - `https://hashratecloudminer.com/support` (GET)
   - `https://hashratecloudminer.com/privacy` (GET)
3. Configure email alerts to your registered address.
4. Wait 24 hours. If all 3 stay 100% green → ready for EAS build.

> **Why 24 hours?** Apple reviewers can hit at any time. Confirming 24h of
> uninterrupted uptime catches any cold-start / DNS-propagation / cert-
> renewal issues BEFORE Apple sees them.

---

## Phase 9 — EAS Build #24 + Resubmit (requires your explicit "GO")

```bash
cd /app/frontend

# 1. Bump buildNumber 23 -> 24
node -e "let j=require('./app.json');j.expo.ios.buildNumber='24';require('fs').writeFileSync('app.json',JSON.stringify(j,null,2));"

# 2. Verify the production-prod-domain profile
cat eas.json | jq '.build."production-prod-domain"'

# 3. Build (THIS USES 1 CREDIT — only run after user says GO)
eas build --platform ios --profile production-prod-domain --non-interactive

# 4. Submit to TestFlight (free, auto via EAS)
eas submit --platform ios --latest --non-interactive
```

Then I'll:
- Wait for the IPA to upload and process (~10 min)
- Update ASC notes with: "Build 24 connects to production backend at api.hashratecloudminer.com (verified 24h uptime). Both register and login confirmed working with provided reviewer accounts."
- Resubmit for review via ASC API (zero credits).

---

## Rollback plan

If anything goes wrong post-deploy and Apple is breathing down our neck:

1. **Revert ASC URLs** to a known-good endpoint:
   ```
   DOMAIN="ios-clone-platform.preview.emergentagent.com" \
   python3 /app/store/update_support_url_to_prod.py
   ```
   (No, this would just re-introduce the 404. Don't do this. Better:)

2. **Fix forward** — Fly machines auto-restart on crash. Check `flyctl logs`
   and `flyctl status`. If the machine dies, `flyctl machine restart`.

3. **Frontend points to preview** — if the new build is broken for some
   unrelated reason, the existing Build #23 binary still hits the preview URL.
   Apple gets the same 404s but we have time to fix.

---

## Files created by this prep work

| File | Purpose |
|------|---------|
| `/app/backend/Dockerfile`            | Multi-stage prod image (slim, ~250MB) |
| `/app/backend/.dockerignore`         | Excludes secrets + dev artifacts from image |
| `/app/backend/start.sh`              | Entrypoint: decode Apple key, launch uvicorn |
| `/app/backend/fly.toml`              | Fly.io config (always-on, 512MB, healthchecks) |
| `/app/backend/server.py`             | Added clean `/`, `/support`, `/privacy` routes |
| `/app/scripts/migrate_db_to_atlas.py`| Idempotent Mongo→Atlas migration |
| `/app/store/update_support_url_to_prod.py` | ASC URL patcher (pre-flight + safe) |
| `/app/frontend/eas.json`             | Added `production-prod-domain` build profile |
| `/app/DEPLOYMENT.md`                 | This runbook |

---

## What I need from you before continuing

(Restated in the chat — see the previous message for the structured prompt.)

1. **Domain registration confirmation** (just say "registered" or share screenshot)
2. **MongoDB Atlas connection string** (with password swapped in)
3. **Fly.io access token** (the long string from fly.io/user/personal_access_tokens)
4. **Cloudflare API token** (optional — speeds up DNS setup) OR willingness to click DNS records yourself
