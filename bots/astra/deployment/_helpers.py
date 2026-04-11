"""Shared helpers for Astra deployment scripts."""

from __future__ import annotations

import subprocess
import sys


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
    """Return the full email for a service account."""
    return f"{sa_name}@{project}.iam.gserviceaccount.com"


def sa_member(sa_name: str, project: str) -> str:
    """Return the IAM member string for a service account."""
    return f"serviceAccount:{sa_email(sa_name, project)}"
