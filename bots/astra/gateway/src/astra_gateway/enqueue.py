import json
import logging
import os
import re

from google.api_core.exceptions import AlreadyExists
from google.cloud import tasks_v2

log = logging.getLogger(__name__)

_tasks_client = tasks_v2.CloudTasksAsyncClient()


async def enqueue_task(payload: dict) -> None:
    """Enqueue a Cloud Tasks HTTP task targeting the gateway's /dispatch route."""
    project = os.environ["GCP_PROJECT"]
    region = os.environ.get("GCP_REGION", "us-west1")
    queue = os.environ.get("CLOUD_TASKS_QUEUE", "astra-task-queue")
    gateway_url = os.environ["GATEWAY_URL"]
    gateway_sa = os.environ["GATEWAY_SA_EMAIL"]

    parent = _tasks_client.queue_path(project, region, queue)

    owner = payload["repo_owner"]
    repo = payload["repo_name"]
    pr_number = payload["pr_number"]
    comment_id = payload["comment_id"]
    task_id = re.sub(r'[^a-zA-Z0-9_-]', '_', f"{owner}-{repo}-pr{pr_number}-c{comment_id}")

    task = tasks_v2.Task(
        name=_tasks_client.task_path(project, region, queue, task_id),
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=f"{gateway_url}/dispatch",
            headers={"Content-Type": "application/json"},
            body=json.dumps(payload).encode(),
            oidc_token=tasks_v2.OidcToken(
                service_account_email=gateway_sa,
                audience=gateway_url,
            ),
        ),
    )

    try:
        await _tasks_client.create_task(request={"parent": parent, "task": task})
        log.info("Enqueued task %s", task_id)
    except AlreadyExists:
        log.info("Task %s already exists (duplicate webhook delivery), skipping", task_id)
