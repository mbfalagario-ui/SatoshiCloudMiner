# ─────────────────────────────────────────────────────────────────────────────
# Hashrate Cloud Miner — production backend image (Fly.io)
#
# Multi-stage build for a slim final image:
#   • Stage 1: install Python deps into a venv
#   • Stage 2: copy venv + app, run uvicorn
# Image size goal: ~250 MB (down from ~1 GB for a naive single-stage build).
#
# Build:  fly deploy   (run from /app/backend)
# Run:    /app/start.sh
# Health: GET /api/system/btc_rate (cheap, no auth)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Build deps for native wheels (cryptography, bcrypt, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
      gcc g++ libffi-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip wheel setuptools && \
    /opt/venv/bin/pip install \
        --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ \
        -r requirements.txt

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8001

WORKDIR /app

# Runtime libs only (libffi for cryptography, libssl3 for TLS)
RUN apt-get update && apt-get install -y --no-install-recommends \
      libffi8 libssl3 ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# App source
COPY server.py ./
COPY integrations/ ./integrations/
COPY services/ ./services/
COPY start.sh ./
RUN chmod +x ./start.sh

# NOTE: keys/ and .env are NOT copied. Both are provided at runtime via:
#   • fly secrets set (env vars)
#   • fly secrets set APPLE_PRIVATE_KEY_B64="$(base64 < SubscriptionKey_J55DSC44V5.p8)"
# The start.sh script decodes the B64 secret into the expected file path.

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8001/api/system/btc_rate || exit 1

CMD ["./start.sh"]
