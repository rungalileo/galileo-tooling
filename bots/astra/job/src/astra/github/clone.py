import asyncio
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

PROJECTS_DIR = Path.home() / "projects"


async def configure_git_auth() -> None:
    """Configure git to use GITHUB_TOKEN for all github.com HTTPS URLs."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return
    # Persists the token in ~/.gitconfig — acceptable because this runs in an ephemeral container.
    proc = await asyncio.create_subprocess_exec(
        "git", "config", "--global",
        f"url.https://x-access-token:{token}@github.com/.insteadOf",
        "https://github.com/",
    )
    await proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"git config failed with exit code {proc.returncode}")


async def clone_pr(
    owner: str,
    repo: str,
    branch: str,
    *,
    repo_url: str | None = None,
    main_branch: str = "main",
) -> Path:
    """Clone a PR branch into ~/projects/{repo}.

    Each agent run is expected to start from a fresh container with no
    existing clone. If the destination already exists, we raise rather
    than try to reconcile state — it indicates an unexpected environment.

    Uses --single-branch, --filter=blob:none, and --no-tags to minimize
    download size while keeping full commit history for merge-base and
    log operations against the main branch.
    """
    await configure_git_auth()
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    if repo_url is None:
        repo_url = f"https://github.com/{owner}/{repo}.git"

    dest = PROJECTS_DIR / repo
    if dest.exists():
        raise RuntimeError(
            f"Clone destination {dest} already exists; expected a fresh environment"
        )

    log.info("Cloning %s (branch: %s) into %s", repo_url, branch, dest)
    proc = await asyncio.create_subprocess_exec(
        "git", "clone",
        "--branch", branch,
        "--single-branch",
        "--filter=blob:none",
        "--no-tags",
        repo_url,
        str(dest),
    )
    await proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"git clone failed with exit code {proc.returncode}")

    log.info("Fetching %s for comparison", main_branch)
    proc = await asyncio.create_subprocess_exec(
        "git", "fetch",
        "--filter=blob:none",
        "origin",
        f"{main_branch}:refs/remotes/origin/{main_branch}",
        cwd=dest,
    )
    await proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"git fetch failed with exit code {proc.returncode}")

    log.info("Clone complete: %s", dest)
    return dest
