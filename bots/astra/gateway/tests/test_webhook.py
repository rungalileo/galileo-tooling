import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

import pytest
from fastapi.testclient import TestClient

from astra_gateway.app import app

WEBHOOK_SECRET = "test-secret"

ENV = {
    "ASTRA_WEBHOOK_SECRET": WEBHOOK_SECRET,
    "ASTRA_APP_ID": "12345",
    "ASTRA_APP_PRIVATE_KEY": "fake-key",
    "GCP_PROJECT": "test-project",
    "GCP_REGION": "us-west1",
    "CLOUD_TASKS_QUEUE": "astra-task-queue",
    "GATEWAY_URL": "https://gateway.run.app",
    "GATEWAY_SA_EMAIL": "sa@project.iam.gserviceaccount.com",
}


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256,
    ).hexdigest()


def _issue_comment_payload(
    comment_body: str = "/astra review",
    *,
    is_pr: bool = True,
    action: str = "created",
) -> dict:
    payload = {
        "action": action,
        "issue": {"number": 42},
        "comment": {
            "id": 99,
            "body": comment_body,
            "user": {"login": "testuser"},
        },
        "repository": {
            "name": "myrepo",
            "owner": {"login": "myorg"},
        },
        "installation": {"id": 111},
    }
    if is_pr:
        payload["issue"]["pull_request"] = {
            "url": "https://api.github.com/repos/myorg/myrepo/pulls/42",
        }
    return payload


@pytest.fixture
def client():
    return TestClient(app)


class TestWebhookSignature:
    @patch.dict("os.environ", ENV)
    def test_invalid_signature_returns_401(self, client):
        body = b'{"action":"created"}'
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "issue_comment",
            },
        )
        assert resp.status_code == 401

    @patch.dict("os.environ", ENV)
    def test_missing_signature_returns_401(self, client):
        resp = client.post(
            "/webhook",
            content=b"{}",
            headers={"X-GitHub-Event": "issue_comment"},
        )
        assert resp.status_code == 401


class TestWebhookFiltering:
    @patch.dict("os.environ", ENV)
    def test_ping_event_ignored(self, client):
        body = b"{}"
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "ping",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ignored"] == "event=ping"

    @patch.dict("os.environ", ENV)
    def test_edited_action_ignored(self, client):
        payload = _issue_comment_payload(action="edited")
        body = json.dumps(payload).encode()
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "issue_comment",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ignored"] == "action=edited"

    @patch.dict("os.environ", ENV)
    def test_issue_not_pr_ignored(self, client):
        payload = _issue_comment_payload(is_pr=False)
        body = json.dumps(payload).encode()
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "issue_comment",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ignored"] == "not_pr"

    @patch.dict("os.environ", ENV)
    def test_non_astra_command_ignored(self, client):
        payload = _issue_comment_payload("looks good!")
        body = json.dumps(payload).encode()
        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "issue_comment",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["ignored"] == "not_astra_command"


class TestWebhookHappyPath:
    @patch.dict("os.environ", ENV)
    @patch("astra_gateway.webhook.enqueue_task")
    @patch("astra_gateway.webhook.mint_installation_token", new_callable=AsyncMock)
    @patch("astra_gateway.webhook.httpx.AsyncClient")
    def test_valid_command_enqueues_task(
        self, mock_client_cls, mock_mint, mock_enqueue, client,
    ):
        mock_mint.return_value = "ghs_token"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        pr_response = MagicMock()
        pr_response.json.return_value = {"head": {"sha": "abc123"}}
        pr_response.raise_for_status = MagicMock()

        reaction_response = MagicMock()
        reaction_response.raise_for_status = MagicMock()

        mock_client.get.return_value = pr_response
        mock_client.post.return_value = reaction_response
        mock_client_cls.return_value = mock_client

        payload = _issue_comment_payload("/astra review")
        body = json.dumps(payload).encode()

        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "issue_comment",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_enqueue.assert_called_once()
        task_payload = mock_enqueue.call_args[0][0]
        assert task_payload["repo_owner"] == "myorg"
        assert task_payload["repo_name"] == "myrepo"
        assert task_payload["pr_number"] == 42
        assert task_payload["head_sha"] == "abc123"
        assert task_payload["command"] == "review"


class TestWebhookHeadShaFailure:
    @patch.dict("os.environ", ENV)
    @patch("astra_gateway.webhook.enqueue_task")
    @patch("astra_gateway.webhook.mint_installation_token", new_callable=AsyncMock)
    @patch("astra_gateway.webhook.httpx.AsyncClient")
    def test_head_sha_failure_posts_error_and_confused_reaction(
        self, mock_client_cls, mock_mint, mock_enqueue, client,
    ):
        mock_mint.return_value = "ghs_token"

        # First client: GET raises HTTPStatusError
        mock_client_fail = AsyncMock()
        mock_client_fail.__aenter__ = AsyncMock(return_value=mock_client_fail)
        mock_client_fail.__aexit__ = AsyncMock(return_value=False)

        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 404
        mock_client_fail.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=error_response,
        )

        # Second client: error recovery posts
        mock_client_recover = AsyncMock()
        mock_client_recover.__aenter__ = AsyncMock(return_value=mock_client_recover)
        mock_client_recover.__aexit__ = AsyncMock(return_value=False)
        mock_client_recover.post.return_value = MagicMock()

        mock_client_cls.side_effect = [mock_client_fail, mock_client_recover]

        payload = _issue_comment_payload("/astra review")
        body = json.dumps(payload).encode()

        resp = client.post(
            "/webhook",
            content=body,
            headers={
                "X-Hub-Signature-256": _sign(body),
                "X-GitHub-Event": "issue_comment",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["error"] == "failed to fetch PR head SHA"
        mock_enqueue.assert_not_called()

        # Verify error comment and confused reaction were posted
        assert mock_client_recover.post.call_count == 2
        comment_call, reaction_call = mock_client_recover.post.call_args_list
        assert "/issues/42/comments" in comment_call.args[0]
        assert "404" in comment_call.kwargs["json"]["body"]
        assert "/issues/comments/99/reactions" in reaction_call.args[0]
        assert reaction_call.kwargs["json"]["content"] == "confused"
