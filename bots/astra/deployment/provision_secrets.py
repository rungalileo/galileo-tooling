#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-cloud-secret-manager>=2.20",
# ]
# ///
"""Provision GCP Secret Manager secrets for Astra GitHub App.

Creates or updates three secrets:
  - astra-webhook-secret: HMAC webhook secret
  - astra-app-id: GitHub App ID
  - astra-app-private-key: GitHub App private key (.pem)

Reads credentials from a .env file in the current directory with:
  ASTRA_WEBHOOK_SECRET=...
  ASTRA_APP_ID=...
  ASTRA_PEM_FILE=/path/to/key.pem

Requires:
  - uv (https://docs.astral.sh/uv/)
  - gcloud CLI with an active project: gcloud config set project <PROJECT_ID>
  - Application Default Credentials: gcloud auth application-default login
  - Secret Manager Admin role on the project

Usage:
  uv run provision_secrets.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from google.api_core import exceptions as gcp_exceptions
from google.cloud import secretmanager

SECRETS = {
    "astra-webhook-secret": "HMAC webhook secret for validating GitHub webhook payloads",
    "astra-app-id": "GitHub App ID (integer)",
    "astra-app-private-key": "GitHub App private key (PEM)",
}

REQUIRED_ENV_VARS = ["ASTRA_WEBHOOK_SECRET", "ASTRA_APP_ID", "ASTRA_PEM_FILE"]

LABEL = {"app": "astra"}


def load_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Supports KEY=VALUE and quoted values."""
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip matching quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        env[key] = value
    return env


def get_active_project() -> str:
    """Get the active GCP project from gcloud config, or exit."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print("Error: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install")
        sys.exit(1)

    project = result.stdout.strip()
    if not project or project == "(unset)":
        print("Error: No active GCP project. Run: gcloud config set project <PROJECT_ID>")
        sys.exit(1)
    return project


def verify_gcp_access(
    client: secretmanager.SecretManagerServiceClient, project_id: str
) -> None:
    """Verify GCP authentication and permissions by listing secrets."""
    try:
        parent = f"projects/{project_id}"
        next(iter(client.list_secrets(request={"parent": parent, "page_size": 1})), None)
    except gcp_exceptions.Unauthenticated:
        print("Error: GCP authentication failed. Run: gcloud auth application-default login")
        sys.exit(1)
    except gcp_exceptions.PermissionDenied:
        print(
            f"Error: Permission denied on project '{project_id}'. "
            "Ensure you have the Secret Manager Admin role."
        )
        sys.exit(1)
    except Exception as exc:
        print(f"Error: Could not connect to GCP Secret Manager: {exc}")
        sys.exit(1)


def create_or_update_secret(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_id: str,
    data: bytes,
) -> str:
    """Create a secret if it doesn't exist, then add a new version.

    Returns a status string: 'created' or 'updated'.
    """
    parent = f"projects/{project_id}"
    secret_path = f"{parent}/secrets/{secret_id}"

    try:
        client.get_secret(request={"name": secret_path})
        status = "updated"
    except gcp_exceptions.NotFound:
        client.create_secret(
            request={
                "parent": parent,
                "secret_id": secret_id,
                "secret": {
                    "replication": {"automatic": {}},
                    "labels": LABEL,
                },
            }
        )
        status = "created"

    client.add_secret_version(
        request={
            "parent": secret_path,
            "payload": {"data": data},
        }
    )

    return status


def main() -> None:
    # --- Preflight checks (all before any GCP calls or prompts) ---

    # 1. Load .env
    dotenv_path = Path(".env")
    if not dotenv_path.exists():
        print("Error: .env file not found in current directory.")
        print(f"Create a .env file with: {', '.join(REQUIRED_ENV_VARS)}")
        sys.exit(1)

    env = load_dotenv(dotenv_path)

    missing = [var for var in REQUIRED_ENV_VARS if not env.get(var)]
    if missing:
        print(f"Error: Missing variables in .env: {', '.join(missing)}")
        sys.exit(1)

    # 2. Validate values
    webhook_secret = env["ASTRA_WEBHOOK_SECRET"]

    app_id = env["ASTRA_APP_ID"]
    try:
        int(app_id)
    except ValueError:
        print(f"Error: ASTRA_APP_ID must be an integer, got: {app_id}")
        sys.exit(1)

    pem_path = Path(env["ASTRA_PEM_FILE"]).expanduser()
    if not pem_path.exists():
        print(f"Error: PEM file not found: {pem_path}")
        sys.exit(1)

    pem_data = pem_path.read_bytes()
    if not pem_data.startswith(b"-----BEGIN"):
        print(f"Warning: {pem_path} doesn't look like a PEM file. Continuing anyway.")

    # 3. Verify GCP project and access
    project_id = get_active_project()

    print(f"\nGCP Project : {project_id}")
    print("Verifying GCP access...")
    client = secretmanager.SecretManagerServiceClient()
    verify_gcp_access(client, project_id)
    print("GCP access verified.")

    # --- Confirm before proceeding ---

    print(f"\nThis will create or update the following secrets in project '{project_id}':\n")
    for secret_id, description in SECRETS.items():
        print(f"  - {secret_id}: {description}")

    print()
    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # --- Provision secrets ---

    print("\nProvisioning secrets...\n")

    results = {}
    secrets_to_create = [
        ("astra-webhook-secret", webhook_secret.encode()),
        ("astra-app-id", app_id.encode()),
        ("astra-app-private-key", pem_data),
    ]

    for secret_id, data in secrets_to_create:
        status = create_or_update_secret(client, project_id, secret_id, data)
        results[secret_id] = status
        print(f"  {secret_id}: {status}")

    print(f"\nDone. {len(results)} secrets provisioned in project '{project_id}'.")
    print("\nVerify with:")
    print(f"  gcloud secrets list --filter='labels.app=astra' --project={project_id}")


if __name__ == "__main__":
    main()
