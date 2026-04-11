import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from astra_gateway.auth import validate_oidc_token, validate_webhook_signature
from astra_shared.github_auth import generate_jwt, mint_installation_token

# -- Test key pair for RS256 --
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_PRIVATE_KEY_PEM = _private_key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
TEST_PUBLIC_KEY = _private_key.public_key()


# ---- validate_webhook_signature ----


class TestValidateWebhookSignature:
    def test_valid_signature(self):
        secret = "test-secret"
        body = b'{"action":"created"}'
        sig = (
            "sha256="
            + hmac.new(
                secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
        )
        assert validate_webhook_signature(body, sig, secret) is True

    def test_invalid_signature(self):
        assert validate_webhook_signature(b"body", "sha256=bad", "secret") is False

    def test_empty_signature(self):
        assert validate_webhook_signature(b"body", "", "secret") is False

    def test_missing_prefix(self):
        secret = "s"
        body = b"x"
        digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert validate_webhook_signature(body, digest, secret) is False


# ---- generate_jwt ----


class TestGenerateJwt:
    def test_jwt_claims(self):
        token = generate_jwt("12345", TEST_PRIVATE_KEY_PEM)
        decoded = jwt.decode(
            token,
            TEST_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_exp": False},
        )
        assert decoded["iss"] == "12345"
        assert "iat" in decoded
        assert "exp" in decoded

    def test_jwt_algorithm(self):
        token = generate_jwt("1", TEST_PRIVATE_KEY_PEM)
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "RS256"


# ---- mint_installation_token ----


class TestMintInstallationToken:
    async def test_mints_token(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"token": "ghs_test123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "astra_shared.github_auth.httpx.AsyncClient", return_value=mock_client
        ):
            token = await mint_installation_token("123", TEST_PRIVATE_KEY_PEM, 456)

        assert token == "ghs_test123"
        call_url = mock_client.post.call_args[0][0]
        assert "/app/installations/456/access_tokens" in call_url


# ---- validate_oidc_token ----


class TestValidateOidcToken:
    async def test_no_bearer_prefix(self):
        assert await validate_oidc_token("Basic abc", "aud", "email") is False

    async def test_empty_header(self):
        assert await validate_oidc_token("", "aud", "email") is False

    @patch("astra_gateway.auth.google_requests")
    @patch("astra_gateway.auth.id_token")
    async def test_valid_token(self, mock_id_token, mock_greq):
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "sa@project.iam.gserviceaccount.com",
        }
        assert (
            await validate_oidc_token(
                "Bearer tok",
                "https://gateway.run.app",
                "sa@project.iam.gserviceaccount.com",
            )
            is True
        )

    @patch("astra_gateway.auth.google_requests")
    @patch("astra_gateway.auth.id_token")
    async def test_wrong_email(self, mock_id_token, mock_greq):
        mock_id_token.verify_oauth2_token.return_value = {
            "email": "wrong@project.iam.gserviceaccount.com",
        }
        assert (
            await validate_oidc_token(
                "Bearer tok",
                "https://gateway.run.app",
                "expected@project.iam.gserviceaccount.com",
            )
            is False
        )
