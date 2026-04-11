import hashlib
import hmac
import logging
import time

import httpx
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


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


def generate_jwt(app_id: str, private_key_pem: str) -> str:
    """Generate a short-lived JWT to authenticate as the GitHub App."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


async def mint_installation_token(
    app_id: str, private_key_pem: str, installation_id: int,
) -> str:
    """Exchange a JWT for a short-lived installation access token."""
    jwt_token = generate_jwt(app_id, private_key_pem)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        resp.raise_for_status()
        return resp.json()["token"]


def validate_oidc_token(
    auth_header: str, expected_audience: str, expected_email: str,
) -> bool:
    """Validate a Google OIDC token from Cloud Tasks."""
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
