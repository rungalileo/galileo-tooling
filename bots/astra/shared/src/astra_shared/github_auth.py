import logging
import time

import httpx
import jwt

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


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
        data = resp.json()
        log.info(
            "Installation token permissions: %s",
            data.get("permissions"),
        )
        return data["token"]
