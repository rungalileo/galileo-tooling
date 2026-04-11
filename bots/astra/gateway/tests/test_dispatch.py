from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from astra_gateway.app import app

client = TestClient(app)

ENV = {
    "GATEWAY_URL": "https://gateway.run.app",
    "GATEWAY_SA_EMAIL": "sa@project.iam.gserviceaccount.com",
    "GCP_PROJECT": "test-project",
    "GCP_REGION": "us-west1",
    "ASTRA_JOB_NAME": "astra-job",
}

TASK_PAYLOAD = {
    "repo_owner": "myorg",
    "repo_name": "myrepo",
    "pr_number": 42,
    "head_sha": "abc123",
    "installation_id": 111,
    "comment_id": 99,
    "command": "review",
    "requester": "testuser",
}


class TestDispatchAuth:
    @patch.dict("os.environ", ENV)
    def test_no_auth_returns_401(self):
        resp = client.post("/dispatch", json=TASK_PAYLOAD)
        assert resp.status_code == 401

    @patch.dict("os.environ", ENV)
    def test_invalid_oidc_returns_401(self):
        resp = client.post(
            "/dispatch",
            json=TASK_PAYLOAD,
            headers={"Authorization": "Bearer invalid"},
        )
        assert resp.status_code == 401


class TestDispatchHappyPath:
    @patch.dict("os.environ", ENV)
    @patch("astra_gateway.dispatch.validate_oidc_token", new_callable=AsyncMock, return_value=True)
    @patch("astra_gateway.dispatch._jobs_client")
    def test_valid_request_starts_job(self, mock_client, mock_oidc):
        mock_operation = MagicMock()
        mock_operation.metadata.name = "projects/p/locations/r/jobs/j/executions/e"
        mock_client.run_job = AsyncMock(return_value=mock_operation)

        resp = client.post(
            "/dispatch",
            json=TASK_PAYLOAD,
            headers={"Authorization": "Bearer valid-token"},
        )

        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        mock_client.run_job.assert_called_once()

        # Verify container overrides
        call_args = mock_client.run_job.call_args[0][0]
        overrides = call_args.overrides.container_overrides[0]
        assert overrides.args == ["review", "https://github.com/myorg/myrepo/pull/42"]
        env_dict = {e.name: e.value for e in overrides.env}
        assert env_dict["ASTRA_INSTALLATION_ID"] == "111"
        assert env_dict["ASTRA_COMMENT_ID"] == "99"
        assert env_dict["ASTRA_HEAD_SHA"] == "abc123"
