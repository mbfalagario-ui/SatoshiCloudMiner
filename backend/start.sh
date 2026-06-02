#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# Fly.io entrypoint.
#
# Responsibilities:
#   1. Decode the Apple .p8 private key from the APPLE_PRIVATE_KEY_B64 secret
#      back into a file at APPLE_PRIVATE_KEY_PATH so the server can read it.
#   2. Launch uvicorn on $PORT (Fly assigns 8080; we default to 8001).
#
# The base64 secret is set with:
#   fly secrets set APPLE_PRIVATE_KEY_B64="$(base64 -w 0 SubscriptionKey_J55DSC44V5.p8)"
# ─────────────────────────────────────────────────────────────────────────────
set -e

PORT="${PORT:-8001}"
KEY_PATH="${APPLE_PRIVATE_KEY_PATH:-/app/keys/SubscriptionKey.p8}"

if [ -n "$APPLE_PRIVATE_KEY_B64" ]; then
  mkdir -p "$(dirname "$KEY_PATH")"
  echo "$APPLE_PRIVATE_KEY_B64" | base64 -d > "$KEY_PATH"
  chmod 600 "$KEY_PATH"
  echo "[start.sh] decoded Apple private key to $KEY_PATH ($(wc -c < "$KEY_PATH") bytes)"
else
  echo "[start.sh] APPLE_PRIVATE_KEY_B64 not set — Apple JWS validation will be unavailable."
fi

exec uvicorn server:app \
  --host 0.0.0.0 \
  --port "$PORT" \
  --workers 1 \
  --loop uvloop \
  --http httptools \
  --proxy-headers \
  --forwarded-allow-ips="*"
