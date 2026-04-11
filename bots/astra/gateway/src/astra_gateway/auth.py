import asyncio
import hashlib
import hmac
import logging

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from astra_shared.github_auth import generate_jwt, mint_installation_token

log = logging.getLogger(__name__)

# Re-export so existing imports keep working
__all__ = [
    "generate_jwt",
    "mint_installation_token",
    "validate_oidc_token",
    "validate_webhook_signature",
]


def validate_webhook_signature(
    payload_body: bytes, signature_header: str, secret: str,
) -> bool:
    """Validate GitHub webhook HMAC-SHA256 signature.

    Must be called with the raw request body bytes, not re-serialized JSON.
    """
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _validate_oidc_token_sync(
    auth_header: str, expected_audience: str, expected_email: str,
) -> bool:
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:]
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=expected_audience,
        )
        if claims.get("email") != expected_email:
            log.warning(
                "OIDC email mismatch: got %s, expected %s",
                claims.get("email"), expected_email,
            )
            return False
        return True
    except Exception:
        log.warning("OIDC token validation failed", exc_info=True)
        return False


async def validate_oidc_token(
    auth_header: str, expected_audience: str, expected_email: str,
) -> bool:
    """Validate a Google OIDC token from Cloud Tasks."""
    return await asyncio.to_thread(
        _validate_oidc_token_sync, auth_header, expected_audience, expected_email,
    )
