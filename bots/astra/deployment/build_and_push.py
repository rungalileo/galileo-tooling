#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Build and push Astra Docker images to Google Artifact Registry.

Builds and pushes:
  - astra-gateway  (gateway service)
  - astra-job      (Cloud Run job runner)

Prerequisites:
  - uv (https://docs.astral.sh/uv/)
  - Docker running locally
  - gcloud CLI with an active project: gcloud config set project <PROJECT_ID>
  - Docker authenticated: gcloud auth configure-docker us-west1-docker.pkg.dev

Usage:
  uv run build_and_push.py               # Build and push both images (latest + git hash)
  uv run build_and_push.py --gateway     # Build and push gateway only
  uv run build_and_push.py --job         # Build and push job only
  uv run build_and_push.py --tag v1.2.3  # Use a specific tag (repeatable)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _helpers import get_active_project

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTRY = "us-west1-docker.pkg.dev"
REPO = "astra"

# image name -> build context directory (relative to bots/astra/)
IMAGES: dict[str, str] = {
    "astra-gateway": "gateway",
    "astra-job": "job",
}

ASTRA_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def check_docker() -> None:
    """Verify Docker is available and running."""
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        print("Error: Docker not found. Install it from https://docs.docker.com/get-docker/")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("Error: Docker is not running. Start Docker and try again.")
        sys.exit(1)


def get_git_short_hash() -> str:
    """Get the short git commit hash, or exit."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=ASTRA_ROOT,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: Could not determine git commit hash.")
        sys.exit(1)
    return result.stdout.strip()


def image_ref(project: str, name: str, tag: str) -> str:
    return f"{REGISTRY}/{project}/{REPO}/{name}:{tag}"


def build_image(project: str, name: str, context_dir: str, tags: list[str]) -> None:
    """Build a Docker image with multiple tags."""
    context = ASTRA_ROOT / context_dir
    tag_args = []
    for tag in tags:
        tag_args.extend(["-t", image_ref(project, name, tag)])
    cmd = [
        "docker", "build",
        "--platform", "linux/amd64",
        *tag_args,
        "-f", str(context / "Dockerfile"),
        str(context),
    ]
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def push_image(project: str, name: str, tags: list[str]) -> None:
    """Push all tags for a Docker image to Artifact Registry."""
    for tag in tags:
        ref = image_ref(project, name, tag)
        cmd = ["docker", "push", ref]
        print(f"  $ {' '.join(cmd)}")
        subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Build and push Astra Docker images")
    parser.add_argument("--gateway", action="store_true", help="Build gateway image only")
    parser.add_argument("--job", action="store_true", help="Build job image only")
    parser.add_argument("--tag", action="append", default=None,
                        help="Image tag(s) to apply (repeatable; default: latest + git short hash)")
    args = parser.parse_args()

    # Determine which images to build
    if args.gateway and args.job:
        selected = IMAGES
    elif args.gateway:
        selected = {"astra-gateway": IMAGES["astra-gateway"]}
    elif args.job:
        selected = {"astra-job": IMAGES["astra-job"]}
    else:
        selected = IMAGES

    # Determine tags
    if args.tag:
        tags = args.tag
    else:
        git_hash = get_git_short_hash()
        tags = ["latest", git_hash]

    # Preflight
    project = get_active_project()
    print(f"\nGCP Project: {project}")

    check_docker()
    print("Docker is running.")

    # Plan
    print("\nThis will build and push the following images:\n")
    for name in selected:
        for tag in tags:
            print(f"  - {image_ref(project, name, tag)}")
    print()

    confirm = input("Proceed? [y/N] ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # Build and push
    for name, context_dir in selected.items():
        print(f"\n--- {name} ---\n")

        print("Building...")
        build_image(project, name, context_dir, tags)

        print("\nPushing...")
        push_image(project, name, tags)

        pushed = ", ".join(image_ref(project, name, t) for t in tags)
        print(f"\n  Pushed: {pushed}")

    # Summary
    print("\n" + "=" * 60)
    print("Done. Verify with:")
    print(f"  gcloud artifacts docker images list {REGISTRY}/{project}/{REPO}")
    print()


if __name__ == "__main__":
    main()
