"""AdMob Server-Side Verification (SSV) callback validator.

Google AdMob signs every rewarded-ad reward callback with ECDSA over the
query-string (minus the `signature` and `key_id` params themselves). We
verify the signature using the public key the publisher saved in AdMob
console. If verification succeeds AND the `ad_view_id` has not been seen
before, the reward is credited.

Reference: https://developers.google.com/admob/android/ssv (same format for iOS)

Environment:
    ADMOB_SSV_KEY_ID   — key ID shown in AdMob console
    ADMOB_SSV_PUBLIC_KEY — PEM-encoded EC public key (P-256)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _public_key():
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except ImportError:
        logger.error("admob: cryptography package missing")
        return None
    pem = os.environ.get("ADMOB_SSV_PUBLIC_KEY", "")
    if not pem:
        return None
    # Normalize: env may have literal "\n" or real newlines.
    pem_clean = pem.replace("\\n", "\n").strip()
    if not pem_clean.startswith("-----BEGIN"):
        return None
    try:
        return load_pem_public_key(pem_clean.encode("ascii"))
    except Exception as e:
        logger.exception("admob: failed to load public key: %s", e)
        return None


def _b64url_decode(s: str) -> bytes:
    pad = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad))


def _ecdsa_p1363_to_der(p1363: bytes) -> bytes:
    """Convert raw (r||s) signature to DER for OpenSSL/cryptography verify."""
    if len(p1363) % 2 != 0:
        raise ValueError("bad signature length")
    half = len(p1363) // 2
    r = int.from_bytes(p1363[:half], "big")
    s = int.from_bytes(p1363[half:], "big")
    # Minimal DER encoding
    def _enc_int(i: int) -> bytes:
        b = i.to_bytes((i.bit_length() + 7) // 8 or 1, "big")
        if b[0] & 0x80:
            b = b"\x00" + b
        return b"\x02" + len(b).to_bytes(1, "big") + b
    body = _enc_int(r) + _enc_int(s)
    return b"\x30" + len(body).to_bytes(1, "big") + body


def verify_ssv_query(query_string: str) -> Tuple[bool, Optional[Dict[str, str]]]:
    """Verify a raw query string from AdMob's SSV callback.

    Returns (ok, parsed_params).  parsed_params includes
    `ad_network`, `ad_unit`, `reward_amount`, `reward_item`,
    `timestamp`, `transaction_id`, `user_id`, `custom_data`, etc.
    """
    if not query_string:
        return False, None
    # AdMob signs everything BEFORE `&signature=`. Find it.
    sig_idx = query_string.find("&signature=")
    if sig_idx < 0:
        return False, None
    signed_data = query_string[:sig_idx].encode("ascii")
    tail = query_string[sig_idx + 1:]  # `signature=...&key_id=...`
    # Parse tail
    parts = dict(p.split("=", 1) for p in tail.split("&") if "=" in p)
    sig_b64 = parts.get("signature")
    key_id = parts.get("key_id")
    if not sig_b64 or not key_id:
        return False, None
    expected_key_id = os.environ.get("ADMOB_SSV_KEY_ID", "")
    if expected_key_id and key_id != expected_key_id:
        logger.warning("admob: key_id mismatch %s != %s", key_id, expected_key_id)
        return False, None
    try:
        sig_p1363 = _b64url_decode(sig_b64)
        sig_der = _ecdsa_p1363_to_der(sig_p1363)
    except Exception as e:
        logger.warning("admob: signature decode failed: %s", e)
        return False, None

    pub = _public_key()
    if not pub:
        logger.warning("admob: no public key available")
        return False, None
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        pub.verify(sig_der, signed_data, ec.ECDSA(hashes.SHA256()))
    except Exception as e:
        logger.warning("admob: signature verify failed: %s", e)
        return False, None

    # Parse params for caller
    all_params = dict(p.split("=", 1) for p in query_string.split("&") if "=" in p)
    return True, all_params


def is_fresh(timestamp_ms: int, max_age_minutes: int = 60) -> bool:
    """SSV callbacks should arrive within the last hour; reject older."""
    try:
        ts = int(timestamp_ms) / 1000.0
        age = time.time() - ts
        return 0 <= age <= max_age_minutes * 60
    except Exception:
        return False
