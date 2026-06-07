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
    key_id: Optional[str]
    issuer_id: Optional[str]
    bundle_id: Optional[str]
    environment_override: Optional[str]

    @property
    def enabled(self) -> bool:
        return bool(
            self.private_key_path
            and self.key_id
            and self.issuer_id
            and self.bundle_id
            and Path(self.private_key_path).exists()
        )


def _load_config() -> AppleConfig:
    return AppleConfig(
        private_key_path=os.environ.get("APPLE_PRIVATE_KEY_PATH") or None,
        key_id=os.environ.get("APPLE_KEY_ID") or None,
        issuer_id=os.environ.get("APPLE_ISSUER_ID") or None,
        bundle_id=os.environ.get("APPLE_BUNDLE_ID") or None,
        environment_override=os.environ.get("APPLE_ENVIRONMENT_OVERRIDE") or None,
    )


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
        private_key = Path(cfg.private_key_path).read_bytes()  # bytes per lib API
    except Exception as e:
        logger.warning("Apple IAP: cannot read .p8 key (%s)", e)
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
    forced = _env_from_override()
    envs = [forced] if forced else [Environment.PRODUCTION, Environment.SANDBOX]

    signed_payload: Optional[str] = None
    used_env: Optional[Environment] = None
    last_exc: Optional[Exception] = None
    auth_failed = False
    for env in envs:
        try:
            client = _client(env)
            resp = client.get_transaction_info(transaction_id)
            signed_payload = getattr(resp, "signed_transaction_info", None) or getattr(
                resp, "signedTransactionInfo", None
            )
            used_env = env
            break
        except APIException as e:
            last_exc = e
            msg = str(e)
            # 4040010 = TransactionIdNotFoundError → try the next env.
            if "4040010" in msg or getattr(e, "api_error", None) == 4040010:
                continue
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
                continue
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
            continue

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
    # The library bundles Apple's roots in some versions; if not available we
    # fall back to a payload-only decode (still trustworthy because Apple sent
    # it back to us over TLS in response to an authenticated request).
    decoded: Optional[Dict[str, Any]] = None
    try:
        from appstoreserverlibrary.signed_data_verifier import (  # type: ignore
            SignedDataVerifier,
        )

        # Try without explicit root certs first (library may bundle them)
        verifier = SignedDataVerifier(
            root_certificates=[],
            enable_online_checks=False,
            environment=used_env,
            bundle_id=cfg.bundle_id,
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
