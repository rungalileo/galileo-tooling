#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Deploy Astra Cloud Run resources.

Deploys:
  - astra-gateway  (Cloud Run service)
  - astra-job      (Cloud Run job)

After deploying both, binds Cloud Run IAM (run.invoker) if not already bound,
and prints the gateway URL for configuring the GitHub App webhook.

Prerequisites:
  - uv (https://docs.astral.sh/uv/)
  - gcloud CLI with an active project: gcloud config set project <PROJECT_ID>
  - Images built and pushed via build_and_push.py
  - Secrets provisioned via provision_secrets.py
  - Infrastructure provisioned via provision_infra.py

Usage:
  uv run deploy.py               # Deploy both gateway and job
  uv run deploy.py --gateway     # Deploy gateway only
  uv run deploy.py --job         # Deploy job only
  uv run deploy.py --tag v1.2.3  # Deploy a specific image tag (default: latest)
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from _helpers import get_active_project, resource_exists, run_gcloud, sa_email

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION = "us-west1"
REGISTRY = "us-west1-docker.pkg.dev"
REPO = "astra"

GATEWAY_SERVICE = "astra-gateway"
GATEWAY_SA = "astra-gateway"
GATEWAY_IMAGE = "astra-gateway"

JOB_NAME = "astra-job"
JOB_SA = "astra-job"
JOB_IMAGE = "astra-job"

TASK_QUEUE = "astra-task-queue"

# Secrets: mapping of env-var-name -> secret-name:version
GATEWAY_SECRETS = {
    "ASTRA_WEBHOOK_SECRET": "astra-webhook-secret:latest",
    "ASTRA_APP_PRIVATE_KEY": "astra-app-private-key:latest",
    "ASTRA_APP_ID": "astra-app-id:latest",
}

JOB_SECRETS = {
    "ASTRA_APP_PRIVATE_KEY": "astra-app-private-key:latest",
    "ASTRA_APP_ID": "astra-app-id:latest",
    "ANTHROPIC_API_KEY": "astra-anthropic-api-key:latest",
    "SHORTCUT_API_TOKEN": "astra-shortcut-api-token:latest",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def image_ref(project: str, name: str, tag: str) -> str:
    return f"{REGISTRY}/{project}/{REPO}/{name}:{tag}"


def format_secrets(secrets: dict[str, str]) -> str:
    """Format secrets dict as a --set-secrets value."""
    return ",".join(f"{env}={secret}" for env, secret in secrets.items())


def get_service_url(service: str, project: str) -> str | None:
    """Get the URL of a deployed Cloud Run service."""
    result = run_gcloud(
        [
            "run", "services", "describe", service,
            f"--region={REGION}",
            f"--project={project}",
            "--format=value(status.url)",
        ],
        check=False,
        quiet=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


# ---------------------------------------------------------------------------
# Deploy functions
# ---------------------------------------------------------------------------


def deploy_gateway(project: str, tag: str) -> str:
    """Deploy the gateway Cloud Run service. Returns the service URL."""
    print("\n--- Deploying astra-gateway ---\n")

    image = image_ref(project, GATEWAY_IMAGE, tag)
    sa = sa_email(GATEWAY_SA, project)

    # Check if service already exists (deploy vs create behavior is the same
    # for `gcloud run deploy`, but we need to know for the GATEWAY_URL env var).
    existing_url = get_service_url(GATEWAY_SERVICE, project)

    # First deploy: set everything except GATEWAY_URL (chicken-and-egg).
    # If the service already exists, we know its URL and can set it directly.
    env_vars = {
        "GCP_PROJECT": project,
        "GCP_REGION": REGION,
        "GATEWAY_SA_EMAIL": sa,
    }
    if existing_url:
        env_vars["GATEWAY_URL"] = existing_url

    env_str = ",".join(f"{k}={v}" for k, v in env_vars.items())

    args = [
        "run", "deploy", GATEWAY_SERVICE,
        f"--image={image}",
        f"--region={REGION}",
        "--allow-unauthenticated",
        "--ingress=all",
        f"--service-account={sa}",
        "--memory=256Mi",
        "--cpu=1",
        "--concurrency=80",
        "--min-instances=0",
        "--max-instances=10",
        "--timeout=30",
        f"--set-secrets={format_secrets(GATEWAY_SECRETS)}",
        f"--set-env-vars={env_str}",
        f"--project={project}",
    ]

    run_gcloud(args)

    # Get the URL from the deployed service.
    url = get_service_url(GATEWAY_SERVICE, project)
    if not url:
        print("Error: Could not retrieve gateway URL after deploy.")
        sys.exit(1)

    # If this was a fresh deploy, update the service with its own URL.
    if not existing_url:
        print(f"\n  Setting GATEWAY_URL={url} ...")
        run_gcloud([
            "run", "services", "update", GATEWAY_SERVICE,
            f"--region={REGION}",
            f"--update-env-vars=GATEWAY_URL={url}",
            f"--project={project}",
        ])

    print(f"\n  Gateway URL: {url}")
    return url


def deploy_job(project: str, tag: str) -> None:
    """Create or update the Cloud Run job."""
    print("\n--- Deploying astra-job ---\n")

    image = image_ref(project, JOB_IMAGE, tag)
    sa = sa_email(JOB_SA, project)

    exists = resource_exists([
        "run", "jobs", "describe", JOB_NAME,
        f"--region={REGION}",
        f"--project={project}",
    ])

    verb = "update" if exists else "create"
    print(f"  Job {'exists, updating...' if exists else 'does not exist, creating...'}")

    args = [
        "run", "jobs", verb, JOB_NAME,
        f"--image={image}",
        f"--region={REGION}",
        "--task-timeout=3600s",
        "--max-retries=0",
        "--parallelism=1",
        "--memory=4Gi",
        "--cpu=2",
        f"--service-account={sa}",
        f"--set-secrets={format_secrets(JOB_SECRETS)}",
        f"--project={project}",
    ]

    run_gcloud(args)
    print(f"\n  Job '{JOB_NAME}' {verb}d.")


def bind_cloud_run_iam(project: str) -> None:
    """Bind run.invoker on Cloud Run resources for the gateway SA."""
    print("\n--- Binding Cloud Run IAM ---\n")

    member = f"serviceAccount:{sa_email(GATEWAY_SA, project)}"
    role = "roles/run.invoker"

    bindings = [
        ("jobs", JOB_NAME),
        ("services", GATEWAY_SERVICE),
    ]

    for resource_type, resource_name in bindings:
        args = [
            "run", resource_type, "add-iam-policy-binding", resource_name,
            f"--member={member}",
            f"--role={role}",
            f"--region={REGION}",
            f"--project={project}",
        ]
        result = run_gcloud(args, check=False)
        label = f"{GATEWAY_SA} -> run.invoker ({resource_type}: {resource_name})"
        if result.returncode == 0:
            print(f"  {label}: bound")
        else:
            print(f"  {label}: FAILED")
            print(f"    {result.stderr.strip()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy Astra Cloud Run resources")
    parser.add_argument("--gateway", action="store_true", help="Deploy gateway only")
    parser.add_argument("--job", action="store_true", help="Deploy job only")
    parser.add_argument("--tag", default="latest", help="Image tag to deploy (default: latest)")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    deploy_both = not args.gateway and not args.job

    project = get_active_project()
    print(f"\nGCP Project: {project}")

    # --- Plan ---
    tag = args.tag
    print(f"\nThis will deploy the following (tag: {tag}):\n")
    if deploy_both or args.gateway:
        print(f"  Service: {GATEWAY_SERVICE}")
        print(f"    Image:   {image_ref(project, GATEWAY_IMAGE, tag)}")
        print(f"    SA:      {sa_email(GATEWAY_SA, project)}")
        print(f"    Secrets: {', '.join(GATEWAY_SECRETS.values())}")
    if deploy_both or args.job:
        print(f"  Job: {JOB_NAME}")
        print(f"    Image:   {image_ref(project, JOB_IMAGE, tag)}")
        print(f"    SA:      {sa_email(JOB_SA, project)}")
        print(f"    Secrets: {', '.join(JOB_SECRETS.values())}")
    print()

    if not args.yes:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    # --- Deploy ---
    gateway_url = None

    try:
        if deploy_both or args.gateway:
            gateway_url = deploy_gateway(project, tag)

        if deploy_both or args.job:
            deploy_job(project, tag)

        if deploy_both:
            bind_cloud_run_iam(project)

    except subprocess.CalledProcessError as exc:
        print(f"\nError: gcloud command failed (exit code {exc.returncode}):")
        print(f"  $ gcloud {' '.join(exc.cmd[1:]) if len(exc.cmd) > 1 else exc.cmd}")
        if exc.stderr:
            print(f"  {exc.stderr.strip()}")
        sys.exit(1)

    # --- Summary ---
    print("\n" + "=" * 60)
    print("Deploy complete.")
    if gateway_url:
        print(f"\n  Gateway URL: {gateway_url}")
        print(f"  Webhook URL: {gateway_url}/webhook")
        print(f"\n  Update the GitHub App webhook URL to: {gateway_url}/webhook")
    print()


if __name__ == "__main__":
    main()
