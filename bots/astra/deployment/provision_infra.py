#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Provision GCP infrastructure for Astra.

Creates:
  - Artifact Registry Docker repository: astra
  - Service accounts: astra-gateway, astra-job
  - IAM bindings for secret access, Cloud Tasks enqueuing, Cloud Run invocation
  - Cloud Tasks queue: astra-task-queue

Prerequisites:
  - uv (https://docs.astral.sh/uv/)
  - gcloud CLI with an active project: gcloud config set project <PROJECT_ID>
  - Application Default Credentials: gcloud auth application-default login
  - Secrets already provisioned via provision_secrets.py

Usage:
  uv run provision_infra.py
"""

from __future__ import annotations

import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION = "us-west1"

REQUIRED_APIS = [
    "iam.googleapis.com",
    "cloudtasks.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
]

ARTIFACT_REGISTRY_REPO = "astra"
ARTIFACT_REGISTRY_FORMAT = "docker"

SERVICE_ACCOUNTS = {
    "astra-gateway": "Astra Gateway",
    "astra-job": "Astra Job Runner",
}

REQUIRED_SECRETS = [
    "astra-webhook-secret",
    "astra-app-id",
    "astra-app-private-key",
    "astra-anthropic-api-key",
]

OPTIONAL_SECRETS = [
    "astra-shortcut-api-token",
]

# (service_account_name, secret_name)
SECRET_IAM_BINDINGS = [
    ("astra-gateway", "astra-webhook-secret"),
    ("astra-gateway", "astra-app-id"),
    ("astra-gateway", "astra-app-private-key"),
    ("astra-job", "astra-app-private-key"),
    ("astra-job", "astra-app-id"),
    ("astra-job", "astra-anthropic-api-key"),
    ("astra-job", "astra-shortcut-api-token"),
]

# (service_account_name, role, scope_description)
PROJECT_IAM_BINDINGS = [
    ("astra-gateway", "roles/cloudtasks.enqueuer", "project"),
]

# (service_account_name, resource_type ["jobs"|"services"], resource_name)
CLOUD_RUN_IAM_BINDINGS = [
    ("astra-gateway", "jobs", "astra-job"),
    ("astra-gateway", "services", "astra-gateway"),
]

TASK_QUEUE = "astra-task-queue"

TASK_QUEUE_CONFIG = {
    "max-dispatches-per-second": "10",
    "max-concurrent-dispatches": "5",
    "max-attempts": "5",
    "min-backoff": "10s",
    "max-backoff": "300s",
    "max-doublings": "3",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def run_gcloud(
    args: list[str], *, check: bool = True, quiet: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a gcloud command, printing it first for transparency."""
    cmd = ["gcloud", *args]
    if not quiet:
        print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def resource_exists(describe_args: list[str]) -> bool:
    """Check if a GCP resource exists by running a describe command."""
    result = run_gcloud(describe_args, check=False, quiet=True)
    return result.returncode == 0


def sa_email(sa_name: str, project: str) -> str:
    return f"{sa_name}@{project}.iam.gserviceaccount.com"


def sa_member(sa_name: str, project: str) -> str:
    return f"serviceAccount:{sa_email(sa_name, project)}"


# ---------------------------------------------------------------------------
# Provisioning functions
# ---------------------------------------------------------------------------


def verify_gcp_access(project: str) -> None:
    """Verify GCP authentication by describing the project."""
    result = run_gcloud(
        ["projects", "describe", project, "--format=value(projectId)"],
        check=False,
        quiet=True,
    )
    if result.returncode != 0:
        print(f"Error: Cannot access project '{project}'.")
        print("Check your credentials: gcloud auth application-default login")
        sys.exit(1)


def verify_secrets_exist(project: str) -> set[str]:
    """Verify that required secrets exist in Secret Manager.

    Returns the set of all secrets that exist (required + optional).
    """
    missing = []
    for secret in REQUIRED_SECRETS:
        if not resource_exists(
            ["secrets", "describe", secret, f"--project={project}"]
        ):
            missing.append(secret)

    if missing:
        print(f"Error: Missing secrets in Secret Manager: {', '.join(missing)}")
        print("Run provision_secrets.py first to create them.")
        sys.exit(1)

    existing = set(REQUIRED_SECRETS)
    for secret in OPTIONAL_SECRETS:
        if resource_exists(
            ["secrets", "describe", secret, f"--project={project}"]
        ):
            existing.add(secret)
        else:
            print(f"  Note: Optional secret '{secret}' not found — skipping IAM binding.")

    return existing


def enable_apis(project: str, results: dict[str, list[tuple[str, str]]]) -> None:
    """Enable required GCP APIs."""
    print("\n[1/7] Enabling APIs...\n")
    for api in REQUIRED_APIS:
        run_gcloud(["services", "enable", api, f"--project={project}"])
        results["APIs"].append((api, "enabled"))


def create_artifact_registry(
    project: str, results: dict[str, list[tuple[str, str]]]
) -> None:
    """Create the Artifact Registry Docker repository if it doesn't exist."""
    print("\n[2/7] Creating Artifact Registry repository...\n")
    if resource_exists([
        "artifacts", "repositories", "describe", ARTIFACT_REGISTRY_REPO,
        f"--location={REGION}", f"--project={project}",
    ]):
        print(f"  {ARTIFACT_REGISTRY_REPO}: already exists")
        results["Artifact Registry"].append((ARTIFACT_REGISTRY_REPO, "already exists"))
    else:
        run_gcloud([
            "artifacts", "repositories", "create", ARTIFACT_REGISTRY_REPO,
            f"--repository-format={ARTIFACT_REGISTRY_FORMAT}",
            f"--location={REGION}",
            f"--project={project}",
        ])
        results["Artifact Registry"].append((ARTIFACT_REGISTRY_REPO, "created"))


def create_service_accounts(
    project: str, results: dict[str, list[tuple[str, str]]]
) -> None:
    """Create service accounts if they don't exist."""
    print("\n[3/7] Creating service accounts...\n")
    created = []
    for sa_name, display_name in SERVICE_ACCOUNTS.items():
        email = sa_email(sa_name, project)
        if resource_exists(
            ["iam", "service-accounts", "describe", email, f"--project={project}"]
        ):
            print(f"  {sa_name}: already exists")
            results["Service accounts"].append((sa_name, "already exists"))
        else:
            run_gcloud([
                "iam", "service-accounts", "create", sa_name,
                f"--display-name={display_name}",
                f"--project={project}",
            ])
            created.append(sa_name)
            results["Service accounts"].append((sa_name, "created"))

    if created:
        print("\n  Waiting for service accounts to propagate...", end="", flush=True)
        for _ in range(6):
            time.sleep(5)
            print(".", end="", flush=True)
        print(" done.")


def bind_project_iam(
    project: str, results: dict[str, list[tuple[str, str]]]
) -> None:
    """Add project-level IAM bindings."""
    print("\n[4/7] Adding project-level IAM bindings...\n")
    for sa_name, role, scope in PROJECT_IAM_BINDINGS:
        member = sa_member(sa_name, project)
        run_gcloud([
            "projects", "add-iam-policy-binding", project,
            f"--member={member}",
            f"--role={role}",
            "--condition=None",
            "--quiet",
        ])
        label = f"{sa_name} -> {role.split('/')[-1]} ({scope})"
        results["IAM bindings"].append((label, "bound"))


def bind_secret_iam(
    project: str,
    results: dict[str, list[tuple[str, str]]],
    existing_secrets: set[str],
) -> None:
    """Add secret-level IAM bindings."""
    print("\n[5/7] Adding secret-level IAM bindings...\n")
    role = "roles/secretmanager.secretAccessor"
    for sa_name, secret in SECRET_IAM_BINDINGS:
        if secret not in existing_secrets:
            label = f"{sa_name} -> secretAccessor ({secret})"
            results["IAM bindings"].append((label, "skipped (secret not provisioned)"))
            print(f"  {label}: skipped (secret not provisioned)")
            continue
        member = sa_member(sa_name, project)
        run_gcloud([
            "secrets", "add-iam-policy-binding", secret,
            f"--member={member}",
            f"--role={role}",
            f"--project={project}",
        ])
        label = f"{sa_name} -> secretAccessor ({secret})"
        results["IAM bindings"].append((label, "bound"))


def bind_cloud_run_iam(
    project: str, results: dict[str, list[tuple[str, str]]]
) -> None:
    """Attempt Cloud Run IAM bindings; defer if resources don't exist yet."""
    print("\n[6/7] Adding Cloud Run IAM bindings (best-effort)...\n")
    role = "roles/run.invoker"
    for sa_name, resource_type, resource_name in CLOUD_RUN_IAM_BINDINGS:
        member = sa_member(sa_name, project)
        args = [
            "run", resource_type, "add-iam-policy-binding", resource_name,
            f"--member={member}",
            f"--role={role}",
            f"--region={REGION}",
            f"--project={project}",
        ]
        result = run_gcloud(args, check=False)
        label = f"{sa_name} -> run.invoker ({resource_type}: {resource_name})"
        if result.returncode == 0:
            results["Cloud Run IAM"].append((label, "bound"))
        else:
            deferred_cmd = f"gcloud {' '.join(args)}"
            results["Cloud Run IAM (deferred)"].append((label, deferred_cmd))
            print(f"  WARNING: {resource_type} '{resource_name}' not found (not yet deployed?).")
            print(f"  Run after deploying:\n    {deferred_cmd}\n")


def create_task_queue(
    project: str, results: dict[str, list[tuple[str, str]]]
) -> None:
    """Create or update the Cloud Tasks queue."""
    print("\n[7/7] Creating Cloud Tasks queue...\n")
    config_args = [f"--{k}={v}" for k, v in TASK_QUEUE_CONFIG.items()]

    if resource_exists([
        "tasks", "queues", "describe", TASK_QUEUE,
        f"--location={REGION}", f"--project={project}",
    ]):
        run_gcloud([
            "tasks", "queues", "update", TASK_QUEUE,
            f"--location={REGION}",
            f"--project={project}",
            *config_args,
        ])
        results["Cloud Tasks queue"].append((TASK_QUEUE, "updated"))
    else:
        run_gcloud([
            "tasks", "queues", "create", TASK_QUEUE,
            f"--location={REGION}",
            f"--project={project}",
            *config_args,
        ])
        results["Cloud Tasks queue"].append((TASK_QUEUE, "created"))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_summary(project: str, results: dict[str, list[tuple[str, str]]]) -> None:
    """Print a grouped results summary."""
    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)

    for section, items in results.items():
        if not items:
            continue
        print(f"\n  {section}:")
        if section == "Cloud Run IAM (deferred)":
            for label, cmd in items:
                print(f"    {label:<55} DEFERRED")
                print(f"      Run after deploying: {cmd}")
        else:
            for name, status in items:
                print(f"    {name:<55} {status}")

    print(f"\nVerify with:")
    print(f"  gcloud artifacts repositories describe {ARTIFACT_REGISTRY_REPO} --location={REGION} --project={project}")
    print(f"  gcloud iam service-accounts list --filter='email:astra-' --project={project}")
    print(f"  gcloud tasks queues describe {TASK_QUEUE} --location={REGION} --project={project}")
    print()


# ---------------------------------------------------------------------------
# Pre-confirmation summary
# ---------------------------------------------------------------------------


def print_plan(project: str) -> None:
    """Print what the script will do before asking for confirmation."""
    print(f"\nThis will provision the following resources in project '{project}':\n")

    print("  APIs to enable:")
    for api in REQUIRED_APIS:
        print(f"    - {api}")

    print(f"\n  Artifact Registry repository:")
    print(f"    - {ARTIFACT_REGISTRY_REPO} (format: {ARTIFACT_REGISTRY_FORMAT}, location: {REGION})")

    print("\n  Service accounts to create:")
    for sa_name, display_name in SERVICE_ACCOUNTS.items():
        print(f"    - {sa_name} ({display_name})")

    print("\n  IAM bindings:")
    for sa_name, role, scope in PROJECT_IAM_BINDINGS:
        print(f"    - {sa_name} -> {role} ({scope})")
    for sa_name, secret in SECRET_IAM_BINDINGS:
        print(f"    - {sa_name} -> roles/secretmanager.secretAccessor ({secret})")
    for sa_name, resource_type, resource_name in CLOUD_RUN_IAM_BINDINGS:
        print(f"    - {sa_name} -> roles/run.invoker ({resource_type}: {resource_name}) [best-effort]")

    print(f"\n  Cloud Tasks queue:")
    print(f"    - {TASK_QUEUE} (location: {REGION})")
    for k, v in TASK_QUEUE_CONFIG.items():
        print(f"        {k}: {v}")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # --- Preflight checks ---

    project = get_active_project()
    print(f"\nGCP Project: {project}")

    print("Verifying GCP access...")
    verify_gcp_access(project)
    print("GCP access verified.")

    print("Verifying secrets exist...")
    existing_secrets = verify_secrets_exist(project)
    print("Secrets verified.")

    # --- Confirm before proceeding ---

    print_plan(project)

    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # --- Provision resources ---

    results: dict[str, list[tuple[str, str]]] = {
        "APIs": [],
        "Artifact Registry": [],
        "Service accounts": [],
        "IAM bindings": [],
        "Cloud Run IAM": [],
        "Cloud Run IAM (deferred)": [],
        "Cloud Tasks queue": [],
    }

    try:
        enable_apis(project, results)
        create_artifact_registry(project, results)
        create_service_accounts(project, results)
        bind_project_iam(project, results)
        bind_secret_iam(project, results, existing_secrets)
        bind_cloud_run_iam(project, results)
        create_task_queue(project, results)
    except subprocess.CalledProcessError as exc:
        print(f"\nError: gcloud command failed (exit code {exc.returncode}):")
        print(f"  $ gcloud {' '.join(exc.cmd[1:]) if len(exc.cmd) > 1 else exc.cmd}")
        if exc.stderr:
            print(f"  {exc.stderr.strip()}")
        sys.exit(1)

    # --- Summary ---

    print_summary(project, results)
    print("Done.")


if __name__ == "__main__":
    main()
