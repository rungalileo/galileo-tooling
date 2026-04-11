#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "google-cloud-secret-manager>=2.20",
# ]
# ///
"""Provision GCP Secret Manager secrets for Astra.

Creates or updates secrets in GCP Secret Manager. Only secrets that don't
already exist require a value in the .env file.

.env variables:
  ASTRA_WEBHOOK_SECRET=...          -> astra-webhook-secret
  ASTRA_APP_ID=...                  -> astra-app-id
  ASTRA_PEM_FILE=/path/to/key.pem  -> astra-app-private-key
  ASTRA_ANTHROPIC_API_KEY=...       -> astra-anthropic-api-key
  ASTRA_SHORTCUT_API_TOKEN=...      -> astra-shortcut-api-token (optional)

If a secret already exists in GCP, the corresponding env var is not required.
Set an env var to update an existing secret with a new version.

Requires:
  - uv (https://docs.astral.sh/uv/)
  - gcloud CLI with an active project: gcloud config set project <PROJECT_ID>
  - Application Default Credentials: gcloud auth application-default login
  - Secret Manager Admin role on the project

Usage:
  uv run provision_secrets.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from google.api_core import exceptions as gcp_exceptions
from google.cloud import secretmanager

from _helpers import get_active_project

# (secret_name, env_var, description, required)
# "required" means the secret must exist after this script runs. If the secret
# is not yet in GCP, the env var MUST be set. If it already exists, the env var
# is optional (set it to update the value).
SECRET_DEFS: list[tuple[str, str, str, bool]] = [
    ("astra-webhook-secret", "ASTRA_WEBHOOK_SECRET", "HMAC webhook secret", True),
    ("astra-app-id", "ASTRA_APP_ID", "GitHub App ID (integer)", True),
    ("astra-app-private-key", "ASTRA_PEM_FILE", "GitHub App private key (PEM)", True),
    ("astra-anthropic-api-key", "ASTRA_ANTHROPIC_API_KEY", "Anthropic API key for Claude Agent SDK", True),
    ("astra-shortcut-api-token", "ASTRA_SHORTCUT_API_TOKEN", "Shortcut API token for story context", False),
]

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


def secret_exists(
    client: secretmanager.SecretManagerServiceClient,
    project_id: str,
    secret_id: str,
) -> bool:
    """Check if a secret already exists in Secret Manager."""
    secret_path = f"projects/{project_id}/secrets/{secret_id}"
    try:
        client.get_secret(request={"name": secret_path})
        return True
    except gcp_exceptions.NotFound:
        return False


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


def resolve_secret_value(env_var: str, value: str | None) -> bytes:
    """Resolve an env var value to bytes, handling PEM files specially."""
    if env_var == "ASTRA_PEM_FILE":
        assert value is not None
        pem_path = Path(value).expanduser()
        if not pem_path.exists():
            print(f"Error: PEM file not found: {pem_path}")
            sys.exit(1)
        pem_data = pem_path.read_bytes()
        if not pem_data.startswith(b"-----BEGIN"):
            print(f"Warning: {pem_path} doesn't look like a PEM file. Continuing anyway.")
        return pem_data
    assert value is not None
    return value.encode()


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision GCP secrets for Astra")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    # --- Load .env (may be empty or absent if all secrets already exist) ---

    dotenv_path = Path(".env")
    env = load_dotenv(dotenv_path) if dotenv_path.exists() else {}

    # --- Connect to GCP and check which secrets already exist ---

    project_id = get_active_project()

    print(f"\nGCP Project : {project_id}")
    print("Verifying GCP access...")
    client = secretmanager.SecretManagerServiceClient()
    verify_gcp_access(client, project_id)
    print("GCP access verified.")

    print("\nChecking existing secrets...")
    existing = set()
    for secret_id, _, _, _ in SECRET_DEFS:
        if secret_exists(client, project_id, secret_id):
            existing.add(secret_id)
            print(f"  {secret_id}: exists")
        else:
            print(f"  {secret_id}: not found")

    # --- Validate env vars: only required for secrets that don't exist yet ---

    # Validate ASTRA_APP_ID if provided
    app_id_val = env.get("ASTRA_APP_ID")
    if app_id_val:
        try:
            int(app_id_val)
        except ValueError:
            print(f"Error: ASTRA_APP_ID must be an integer, got: {app_id_val}")
            sys.exit(1)

    missing_required: list[str] = []
    for secret_id, env_var, description, required in SECRET_DEFS:
        has_value = bool(env.get(env_var))
        already_exists = secret_id in existing
        if required and not already_exists and not has_value:
            missing_required.append(f"{env_var} (for {secret_id})")

    if missing_required:
        print("\nError: The following secrets don't exist in GCP and have no value in .env:")
        for item in missing_required:
            print(f"  - {item}")
        print("\nEither set them in .env or create the secrets manually.")
        sys.exit(1)

    # --- Build list of secrets to create/update ---

    secrets_to_provision: list[tuple[str, str, bytes]] = []  # (secret_id, description, data)
    skipped: list[tuple[str, str]] = []  # (secret_id, reason)

    for secret_id, env_var, description, required in SECRET_DEFS:
        value = env.get(env_var)
        if value:
            data = resolve_secret_value(env_var, value)
            secrets_to_provision.append((secret_id, description, data))
        elif secret_id in existing:
            skipped.append((secret_id, "already exists, no new value in .env"))
        else:
            skipped.append((secret_id, "not set in .env (optional)"))

    if not secrets_to_provision:
        print("\nAll secrets already exist and no new values provided. Nothing to do.")
        sys.exit(0)

    # --- Confirm before proceeding ---

    print(f"\nThis will create or update the following secrets in project '{project_id}':\n")
    for secret_id, description, _ in secrets_to_provision:
        action = "update" if secret_id in existing else "create"
        print(f"  - {secret_id}: {description} ({action})")
    for secret_id, reason in skipped:
        print(f"  - {secret_id}: skipped ({reason})")

    print()
    if not args.yes:
        confirm = input("Proceed? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            sys.exit(0)

    # --- Provision secrets ---

    print("\nProvisioning secrets...\n")

    results = {}
    for secret_id, _, data in secrets_to_provision:
        status = create_or_update_secret(client, project_id, secret_id, data)
        results[secret_id] = status
        print(f"  {secret_id}: {status}")

    print(f"\nDone. {len(results)} secrets provisioned in project '{project_id}'.")
    print("\nVerify with:")
    print(f"  gcloud secrets list --filter='labels.app=astra' --project={project_id}")


if __name__ == "__main__":
    main()
