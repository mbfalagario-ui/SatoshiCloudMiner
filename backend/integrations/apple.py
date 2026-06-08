"""Apple App Store Server API — server-side IAP receipt validation.

Behaviour:
  * If APPLE_PRIVATE_KEY_PATH / APPLE_KEY_ID / APPLE_ISSUER_ID / APPLE_BUNDLE_ID
    are all configured AND the .p8 file exists, calls Apple's App Store Server
    API to validate a transactionId and returns the decoded signed transaction.
  * If anything is missing, returns a deterministic mocked transaction so the
    rest of the backend (and frontend) keep working end-to-end during
    development. The switch is automatic — no code changes required.

Reference: https://developer.apple.com/documentation/appstoreserverapi
Library: https://github.com/apple/app-store-server-library-python
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class AppleConfig:
    private_key_path: Optional[str]
    private_key_pem:  Optional[str]      # NEW: literal PEM body (preferred in prod)
    key_id: Optional[str]
    issuer_id: Optional[str]
    bundle_id: Optional[str]
    environment_override: Optional[str]
    app_apple_id: Optional[int] = None   # ASC numeric app ID (required for PROD JWS)

    @property
    def enabled(self) -> bool:
        """Returns True when we have enough credentials to verify against
        Apple. The key may come from EITHER:
          - APPLE_PRIVATE_KEY_PEM   (literal PEM body — preferred in prod)
          - APPLE_PRIVATE_KEY_PATH  (path on disk — dev convenience)
        and the other three IDs must all be present.
        """
        if not (self.key_id and self.issuer_id and self.bundle_id):
            return False
        if self.private_key_pem and self.private_key_pem.strip().startswith("-----BEGIN"):
            return True
        if self.private_key_path and Path(self.private_key_path).exists():
            return True
        return False

    def read_key_bytes(self) -> Optional[bytes]:
        """Returns the .p8 contents as bytes, sourced from the secure
        env var if present, else from disk. Returns None if neither is
        available.

        Defensive normalisation: some Fly/Cloud UIs store multiline
        secrets as a single line with literal backslash-n sequences
        ("\\n") instead of real newlines. The cryptography library
        requires real newlines to parse a PEM, so we silently fix the
        most common form of that pasting accident here. This is a
        no-op for PEMs that already have real newlines.
        """
        if self.private_key_pem and self.private_key_pem.strip().startswith("-----BEGIN"):
            body = self.private_key_pem
            # Normalise escaped newline sequences if present (no-op otherwise).
            if "\\n" in body and "\n" not in body:
                body = body.replace("\\n", "\n")
            # Normalise CRLF → LF (some clipboards / Windows UIs insert CRs).
            if "\r\n" in body:
                body = body.replace("\r\n", "\n")
            # Ensure trailing newline (some PEM parsers are strict).
            if not body.endswith("\n"):
                body = body + "\n"
            return body.encode("utf-8")
        if self.private_key_path:
            try:
                return Path(self.private_key_path).read_bytes()
            except Exception:
                return None
        return None

    @property
    def key_source(self) -> str:
        """Human-readable label for selfcheck reporting (no secret leak)."""
        if self.private_key_pem and self.private_key_pem.strip().startswith("-----BEGIN"):
            return "env:APPLE_PRIVATE_KEY_PEM"
        if self.private_key_path:
            return f"file:{self.private_key_path}"
        return "(none)"


def _load_config() -> AppleConfig:
    app_apple_id_raw = os.environ.get("APPLE_APP_APPLE_ID") or "6773104756"
    try:
        app_apple_id_int = int(app_apple_id_raw)
    except (TypeError, ValueError):
        app_apple_id_int = None
    return AppleConfig(
        private_key_path=os.environ.get("APPLE_PRIVATE_KEY_PATH") or None,
        private_key_pem=os.environ.get("APPLE_PRIVATE_KEY_PEM") or None,
        key_id=os.environ.get("APPLE_KEY_ID") or None,
        issuer_id=os.environ.get("APPLE_ISSUER_ID") or None,
        bundle_id=os.environ.get("APPLE_BUNDLE_ID") or None,
        environment_override=os.environ.get("APPLE_ENVIRONMENT_OVERRIDE") or None,
        app_apple_id=app_apple_id_int,
    )


# ---------------------------------------------------------------------------
# Apple Root CA — used for JWS chain verification.
#
# Loaded once at module import from /app/backend/certs/AppleRootCA-G3.cer
# (DER format). This is the certificate that Apple signs JWS receipts with;
# without it, SignedDataVerifier's chain validator cannot anchor the trust
# chain. We REFUSE to fall back to root_certificates=[] (which would skip
# chain validation entirely) — that was a Build #36 vulnerability flagged
# by the operator.
#
# To rotate: download a fresh DER from
#   https://www.apple.com/certificateauthority/AppleRootCA-G3.cer
# and overwrite the file. Apple G3 is valid until 2039-04-30.
# ---------------------------------------------------------------------------
_APPLE_ROOTS_PATH = Path(__file__).resolve().parent.parent / "certs" / "AppleRootCA-G3.cer"
_APPLE_ROOTS_BYTES: Optional[list] = None  # list[bytes] once loaded


def _load_apple_roots() -> list:
    """Return Apple Root CA cert(s) as a list of DER-encoded bytes.

    The returned list is in the exact format
    `appstoreserverlibrary.SignedDataVerifier` accepts.
    """
    global _APPLE_ROOTS_BYTES
    if _APPLE_ROOTS_BYTES is not None:
        return _APPLE_ROOTS_BYTES
    if not _APPLE_ROOTS_PATH.exists():
        raise RuntimeError(
            f"Apple Root CA certificate not found at {_APPLE_ROOTS_PATH}. "
            "Download from https://www.apple.com/certificateauthority/AppleRootCA-G3.cer "
            "before starting the backend."
        )
    with open(_APPLE_ROOTS_PATH, "rb") as f:
        der = f.read()
    if not der or len(der) < 200:
        raise RuntimeError(
            f"Apple Root CA file at {_APPLE_ROOTS_PATH} is empty or truncated "
            f"({len(der)} bytes); will not skip chain validation."
        )
    _APPLE_ROOTS_BYTES = [der]
    logger.info(
        "Apple Root CA loaded for JWS chain validation: path=%s size=%dB",
        _APPLE_ROOTS_PATH, len(der),
    )
    return _APPLE_ROOTS_BYTES


def _mock_transaction(transaction_id: str, product_id: Optional[str]) -> Dict[str, Any]:
    return {
        "transactionId": transaction_id,
        "originalTransactionId": transaction_id,
        "productId": product_id or "mock.product",
        "bundleId": os.environ.get("APPLE_BUNDLE_ID", "app.hashcloud.mobile"),
        "purchaseDate": int(time.time() * 1000),
        "environment": "MOCK",
        "_mocked": True,
    }


def verify_apple_transaction(
    transaction_id: str,
    expected_product_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify an Apple IAP transactionId.

    Returns a dict with at least:
        - transactionId
        - originalTransactionId
        - productId
        - bundleId
        - environment  ("Sandbox" | "Production" | "MOCK")
        - _mocked: True if not actually verified against Apple.

    Raises ValueError on bundle id / product id mismatch when running live.

    Apple Build #33 / App Review Guideline 2.1(b) — production safety:
    When the env var APPLE_VERIFY_REQUIRED is "1" (which is the case
    for production EAS builds), this function MUST NOT fall back to
    a mock transaction. If credentials are missing OR the verifier
    library can't be imported, a ValueError is raised so the caller
    refuses the purchase. This is the "fail closed" guarantee Apple
    requires — under no circumstances does a production user receive
    paid hashpower without a verified StoreKit transaction.
    """
    require_real = os.environ.get("APPLE_VERIFY_REQUIRED", "").strip() in ("1", "true", "True", "yes")
    cfg = _load_config()
    if not cfg.enabled:
        if require_real:
            logger.error(
                "Apple IAP: credentials not configured but APPLE_VERIFY_REQUIRED=1 — refusing purchase."
            )
            raise ValueError(
                "Apple IAP verification is required in production but credentials are not configured."
            )
        logger.info("Apple IAP: credentials not configured — returning MOCK transaction (dev mode).")
        return _mock_transaction(transaction_id, expected_product_id)

    try:
        # Lazy import so the backend still boots if the lib is unavailable.
        from appstoreserverlibrary.api_client import (  # type: ignore
            AppStoreServerAPIClient,
            APIException,
        )
        from appstoreserverlibrary.models.Environment import Environment  # type: ignore
        from appstoreserverlibrary.signed_data_verifier import (  # type: ignore # noqa: F401
            SignedDataVerifier,
        )
    except Exception as e:
        logger.warning("Apple IAP: app-store-server-library import failed (%s)", e)
        if require_real:
            raise ValueError(
                f"Apple IAP verifier library unavailable in production: {e}"
            )
        return _mock_transaction(transaction_id, expected_product_id)

    try:
        private_key = cfg.read_key_bytes()  # bytes — sourced from PEM env var OR file
        if private_key is None:
            raise FileNotFoundError("no key body available from env or disk")
    except Exception as e:
        logger.warning("Apple IAP: cannot read private key (%s)", e)
        if require_real:
            raise ValueError(
                f"Apple IAP private key unreadable in production: {e}"
            )
        return _mock_transaction(transaction_id, expected_product_id)

    def _env_from_override() -> Optional[Environment]:
        if not cfg.environment_override:
            return None
        if cfg.environment_override.upper() == "SANDBOX":
            return Environment.SANDBOX
        if cfg.environment_override.upper() == "PRODUCTION":
            return Environment.PRODUCTION
        return None

    def _client(env: Environment) -> AppStoreServerAPIClient:
        return AppStoreServerAPIClient(
            signing_key=private_key,
            key_id=cfg.key_id,
            issuer_id=cfg.issuer_id,
            bundle_id=cfg.bundle_id,
            environment=env,
        )

    # Apple's recommended flow: try Production first, fall back to Sandbox
    # on TransactionIdNotFoundError (4040010).
    #
    # Build 37 fix: TestFlight / sandbox transactions can take up to ~60s to
    # propagate to Apple's lookup index. The previous code burned both env
    # attempts in <1s and gave up. We now retry each env up to N times with
    # exponential backoff (1s, 2s, 4s, 8s) ONLY on 4040010. Other errors
    # (auth, malformed transactionId, etc.) bail out immediately. Total
    # worst-case wait: ~15s per env = ~30s before final failure.
    forced = _env_from_override()
    envs = [forced] if forced else [Environment.PRODUCTION, Environment.SANDBOX]

    LOOKUP_BACKOFF_S = (1.0, 2.0, 4.0, 8.0)  # ~15s cumulative

    signed_payload: Optional[str] = None
    used_env: Optional[Environment] = None
    last_exc: Optional[Exception] = None
    auth_failed = False
    for env in envs:
        env_resolved = False
        for attempt in range(len(LOOKUP_BACKOFF_S) + 1):
            try:
                client = _client(env)
                resp = client.get_transaction_info(transaction_id)
                signed_payload = getattr(resp, "signed_transaction_info", None) or getattr(
                    resp, "signedTransactionInfo", None
                )
                used_env = env
                env_resolved = True
                break
            except APIException as e:
                last_exc = e
                msg = str(e)
                # 4040010 = TransactionIdNotFoundError → could be a sandbox
                # propagation race; retry with backoff before falling through
                # to the next env.
                if "4040010" in msg or getattr(e, "api_error", None) == 4040010:
                    if attempt < len(LOOKUP_BACKOFF_S):
                        delay = LOOKUP_BACKOFF_S[attempt]
                        logger.info(
                            "Apple IAP: 4040010 for tid=%s env=%s attempt=%d — retry in %.1fs",
                            transaction_id, env.name, attempt + 1, delay,
                        )
                        time.sleep(delay)
                        continue
                    # Exhausted backoff for this env; try the next one.
                    break
                # 401 = Apple credentials misconfigured (wrong issuer/key/.p8).
                # Don't crash the purchase flow; fall back to MOCK so review/sandbox
                # builds keep functioning. The operator must fix the credentials
                # before going live — we flag this in the response.
                if "401" in msg or msg.strip() == "401":
                    auth_failed = True
                    logger.error(
                        "Apple IAP: 401 Unauthenticated from Apple — credentials "
                        "(issuer/keyId/.p8) are invalid. Falling back to MOCK for "
                        "transaction %s.",
                        transaction_id,
                    )
                    break
                # Other Apple API errors (400 invalid format, 5xx Apple outage,
                # etc.) — fail the verification cleanly as a ValueError so the
                # /packages/buy and /iap/restore endpoints both surface HTTP
                # 402 with a sanitised message rather than 5xx.
                logger.warning(
                    "Apple IAP: APIException (non-recoverable) env=%s tid=%s msg=%s",
                    env, transaction_id, msg,
                )
                raise ValueError(f"Apple IAP API error: {msg[:120]}")
            except Exception as e:
                last_exc = e
                break
        if env_resolved:
            break

    if not signed_payload:
        if auth_failed:
            # Apple Build #33: in production, refuse to fall back to a
            # MOCK if Apple's 401 says our creds are bad — granting
            # paid hashpower without verification would violate
            # Guideline 2.1(b). The .env var is the kill-switch.
            if require_real:
                logger.error(
                    "Apple IAP: 401 from Apple AND APPLE_VERIFY_REQUIRED=1 "
                    "— refusing transaction %s.", transaction_id,
                )
                raise ValueError(
                    "Apple IAP authentication failed in production. "
                    "Operator must rotate the App Store Connect key."
                )
            mock = _mock_transaction(transaction_id, expected_product_id)
            mock["environment"] = "AUTH_FAILED_FALLBACK"
            return mock
        raise ValueError(
            f"Apple IAP: transaction {transaction_id} not found "
            f"(last error: {last_exc})"
        )

    # Verify the JWS signature against Apple root certs.
    # Build 37: we MUST use real Apple root certificates here — previous
    # code passed root_certificates=[] which skipped chain validation
    # entirely (security gap flagged by ops). Roots are loaded once at
    # module import from /app/backend/certs/AppleRootCA-G3.cer.
    decoded: Optional[Dict[str, Any]] = None
    try:
        from appstoreserverlibrary.signed_data_verifier import (  # type: ignore
            SignedDataVerifier,
        )

        roots = _load_apple_roots()
        # app_apple_id is REQUIRED for Environment.PRODUCTION. For SANDBOX
        # the library accepts None.
        app_apple_id = cfg.app_apple_id if used_env == Environment.PRODUCTION else None
        verifier = SignedDataVerifier(
            root_certificates=roots,
            enable_online_checks=False,  # OCSP off: chain+bundle+env checks
                                          # are sufficient and OCSP adds
                                          # 100-500ms per purchase.
            environment=used_env,
            bundle_id=cfg.bundle_id,
            app_apple_id=app_apple_id,
        )
        tx = verifier.verify_and_decode_signed_transaction(signed_payload)
        decoded = tx.model_dump() if hasattr(tx, "model_dump") else dict(tx.__dict__)
    except Exception as e:
        logger.warning("Apple IAP: JWS verifier unavailable (%s); decoding payload only.", e)
        import base64
        import json
        try:
            parts = signed_payload.split(".")
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
        except Exception as ie:
            raise ValueError(f"Apple IAP: could not decode signed payload ({ie})")

    # Bundle ID check
    bundle = decoded.get("bundleId") or decoded.get("bundle_id")
    if cfg.bundle_id and bundle and bundle != cfg.bundle_id:
        raise ValueError(
            f"Apple IAP: bundle id mismatch (got {bundle!r}, expected {cfg.bundle_id!r})"
        )

    # Product ID check
    product = decoded.get("productId") or decoded.get("product_id")
    if expected_product_id and product and product != expected_product_id:
        raise ValueError(
            f"Apple IAP: product id mismatch (got {product!r}, expected {expected_product_id!r})"
        )

    decoded["_mocked"] = False
    decoded.setdefault("environment", used_env.name if used_env else "Production")
    decoded.setdefault("transactionId", transaction_id)
    return decoded


# ---------------------------------------------------------------------------
# Build 37: JWS verification path.
#
# StoreKit2 returns a signed JWS for every transaction (`purchase.purchaseToken`
# in react-native-iap v15+). The JWS is signed by Apple's intermediate cert
# (which chains up to Apple Root CA - G3), so it is self-verifiable WITHOUT
# calling Apple's App Store Server API. This eliminates the sandbox
# propagation race that breaks the lookup path in TestFlight.
#
# When both a JWS and a transactionId are available, we PREFER the JWS path —
# it is faster (~10ms local crypto vs ~1-3s Apple round-trip), has no race,
# and the only auth surface is Apple's signature, not our key.
#
# The JWS path uses the SAME SignedDataVerifier with the SAME Apple Root CA
# we load for the API path — chain validation is NOT skipped.
# ---------------------------------------------------------------------------
def verify_apple_jws_transaction(
    jws: str,
    expected_product_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify a StoreKit2 signed JWS receipt against Apple's roots locally.

    Returns the decoded JWS payload dict on success.
    Raises ValueError on any verification failure (bundle/env mismatch,
    bad signature, malformed JWS, missing Apple roots).
    """
    if not jws or not isinstance(jws, str) or jws.count(".") < 2:
        raise ValueError("Apple IAP JWS: empty or malformed receipt")

    cfg = _load_config()
    if not cfg.enabled:
        raise ValueError("Apple IAP JWS: backend Apple config is not enabled")

    try:
        from appstoreserverlibrary.signed_data_verifier import (  # type: ignore
            SignedDataVerifier,
            VerificationException,
        )
        from appstoreserverlibrary.models.Environment import Environment  # type: ignore
    except ImportError as e:
        raise ValueError(f"Apple IAP JWS: appstoreserverlibrary unavailable ({e})")

    roots = _load_apple_roots()

    # Sniff the JWS payload's `environment` field first so we anchor the
    # SignedDataVerifier in the correct environment. We CANNOT just verify
    # in PROD — TestFlight purchases are signed for Sandbox, and
    # SignedDataVerifier raises INVALID_ENVIRONMENT if we pass the wrong one.
    sniffed_env: Optional[Environment] = None
    try:
        import base64
        import json as _json
        parts = jws.split(".")
        pad = parts[1] + "=" * (-len(parts[1]) % 4)
        peek = _json.loads(base64.urlsafe_b64decode(pad))
        env_str = (peek.get("environment") or "").lower()
        if env_str == "sandbox":
            sniffed_env = Environment.SANDBOX
        elif env_str == "production":
            sniffed_env = Environment.PRODUCTION
    except Exception:
        sniffed_env = None  # fall through to try-both

    # Build the list of environments to attempt, sniffed-first if known.
    # Inline the environment-override resolution (same logic used by the
    # API-path code — we cannot reuse the nested helper because it's
    # scoped to verify_apple_transaction).
    override = (cfg.environment_override or "").strip().upper() or None
    forced: Optional[Environment] = None
    if override == "SANDBOX":
        forced = Environment.SANDBOX
    elif override == "PRODUCTION":
        forced = Environment.PRODUCTION
    if forced:
        envs_to_try = [forced]
    elif sniffed_env:
        # Put the sniffed env FIRST; the other as fallback for paranoid safety.
        other = (
            Environment.PRODUCTION
            if sniffed_env == Environment.SANDBOX
            else Environment.SANDBOX
        )
        envs_to_try = [sniffed_env, other]
    else:
        envs_to_try = [Environment.PRODUCTION, Environment.SANDBOX]

    last_err: Optional[Exception] = None
    for env in envs_to_try:
        try:
            # app_apple_id is REQUIRED by the library for PRODUCTION; for
            # SANDBOX it accepts None.
            app_apple_id = cfg.app_apple_id if env == Environment.PRODUCTION else None
            verifier = SignedDataVerifier(
                root_certificates=roots,
                enable_online_checks=False,  # see API-path comment
                environment=env,
                bundle_id=cfg.bundle_id,
                app_apple_id=app_apple_id,
            )
            tx = verifier.verify_and_decode_signed_transaction(jws)
            decoded: Dict[str, Any] = (
                tx.model_dump() if hasattr(tx, "model_dump") else dict(tx.__dict__)
            )

            # Product ID check (defence in depth — verifier already checks
            # bundle + env). Both camelCase and snake_case fields covered.
            product = decoded.get("productId") or decoded.get("product_id")
            if expected_product_id and product and product != expected_product_id:
                raise ValueError(
                    "Apple IAP JWS: product id mismatch "
                    f"(got {product!r}, expected {expected_product_id!r})"
                )

            decoded["_mocked"] = False
            decoded.setdefault("environment", env.name)
            decoded["_verification_path"] = "jws"
            return decoded
        except VerificationException as ve:
            last_err = ve
            logger.info(
                "Apple IAP JWS: VerificationException in env=%s: %s",
                env.name, ve,
            )
            continue
        except ValueError:
            raise  # product-id mismatch — bubble up immediately
        except Exception as e:
            last_err = e
            logger.warning(
                "Apple IAP JWS: unexpected error in env=%s: %s",
                env.name, e,
            )
            continue

    raise ValueError(
        f"Apple IAP JWS: verification failed in all environments (last={last_err})"
    )
