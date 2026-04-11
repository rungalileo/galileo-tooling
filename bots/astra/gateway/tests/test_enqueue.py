from unittest.mock import AsyncMock, patch

from astra_gateway.enqueue import enqueue_task

ENV = {
    "GCP_PROJECT": "test-project",
    "GCP_REGION": "us-west1",
    "CLOUD_TASKS_QUEUE": "astra-task-queue",
    "GATEWAY_URL": "https://gateway.run.app",
    "GATEWAY_SA_EMAIL": "sa@project.iam.gserviceaccount.com",
}

PAYLOAD = {
    "repo_owner": "myorg",
    "repo_name": "myrepo",
    "pr_number": 42,
    "head_sha": "abc123",
    "installation_id": 111,
    "comment_id": 99,
    "command": "review",
    "requester": "testuser",
}


class TestEnqueueTask:
    @patch.dict("os.environ", ENV)
    @patch("astra_gateway.enqueue._tasks_client")
    async def test_creates_task_with_correct_name(self, mock_client):
        mock_client.create_task = AsyncMock()
        mock_client.queue_path.return_value = (
            "projects/test-project/locations/us-west1/queues/astra-task-queue"
        )
        mock_client.task_path.return_value = (
            "projects/test-project/locations/us-west1/queues/astra-task-queue"
            "/tasks/myorg-myrepo-pr42-c99"
        )

        await enqueue_task(PAYLOAD)

        mock_client.create_task.assert_called_once()
        call_kwargs = mock_client.create_task.call_args[1]
        task = call_kwargs["request"]["task"]
        assert "myorg-myrepo-pr42-c99" in task.name

    @patch.dict("os.environ", ENV)
    @patch("astra_gateway.enqueue._tasks_client")
    async def test_task_targets_dispatch_url(self, mock_client):
        mock_client.create_task = AsyncMock()
        mock_client.queue_path.return_value = "parent"
        mock_client.task_path.return_value = "task-name"

        await enqueue_task(PAYLOAD)

        task = mock_client.create_task.call_args[1]["request"]["task"]
        assert task.http_request.url == "https://gateway.run.app/dispatch"

    @patch.dict("os.environ", ENV)
    @patch("astra_gateway.enqueue._tasks_client")
    async def test_task_has_oidc_token(self, mock_client):
        mock_client.create_task = AsyncMock()
        mock_client.queue_path.return_value = "parent"
        mock_client.task_path.return_value = "task-name"

        await enqueue_task(PAYLOAD)

        task = mock_client.create_task.call_args[1]["request"]["task"]
        oidc = task.http_request.oidc_token
        assert oidc.service_account_email == "sa@project.iam.gserviceaccount.com"
        assert oidc.audience == "https://gateway.run.app"
