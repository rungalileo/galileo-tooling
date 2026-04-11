import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google.cloud import run_v2

from astra_gateway.auth import validate_oidc_token

log = logging.getLogger(__name__)

router = APIRouter()


@router.post("/dispatch")
async def handle_dispatch(request: Request) -> JSONResponse:
    # 1. Validate OIDC token
    gateway_url = os.environ["GATEWAY_URL"]
    gateway_sa = os.environ["GATEWAY_SA_EMAIL"]
    auth_header = request.headers.get("Authorization", "")
    if not validate_oidc_token(auth_header, gateway_url, gateway_sa):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # 2. Parse task payload
    payload = await request.json()
    repo_owner = payload["repo_owner"]
    repo_name = payload["repo_name"]
    pr_number = payload["pr_number"]
    installation_id = payload["installation_id"]
    command = payload["command"]
    comment_id = payload.get("comment_id")
    head_sha = payload.get("head_sha")

    log.info(
        "Dispatching %s for %s/%s#%d",
        command, repo_owner, repo_name, pr_number,
    )

    # 3. Construct PR URL matching existing CLI interface
    pr_url = f"https://github.com/{repo_owner}/{repo_name}/pull/{pr_number}"

    # 4. Start Cloud Run Job execution
    project = os.environ["GCP_PROJECT"]
    region = os.environ.get("GCP_REGION", "us-west1")
    job_name = os.environ.get("ASTRA_JOB_NAME", "astra-job")

    client = run_v2.JobsClient()
    job_path = f"projects/{project}/locations/{region}/jobs/{job_name}"

    override = run_v2.RunJobRequest.Overrides(
        container_overrides=[
            run_v2.RunJobRequest.Overrides.ContainerOverride(
                args=[command, pr_url],
                env=[
                    run_v2.EnvVar(
                        name="ASTRA_INSTALLATION_ID",
                        value=str(installation_id),
                    ),
                    *(
                        [run_v2.EnvVar(name="ASTRA_COMMENT_ID", value=str(comment_id))]
                        if comment_id else []
                    ),
                    *(
                        [run_v2.EnvVar(name="ASTRA_HEAD_SHA", value=str(head_sha))]
                        if head_sha else []
                    ),
                ],
            ),
        ],
    )

    operation = client.run_job(
        run_v2.RunJobRequest(name=job_path, overrides=override),
    )
    execution_name = operation.metadata.name
    log.info("Job execution started: %s", execution_name)

    return JSONResponse({"ok": True, "execution": execution_name})
