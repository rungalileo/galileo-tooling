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
    proc = await asyncio.create_subprocess_exec(
        "git", "config", "--global",
        f"url.https://x-access-token:{token}@github.com/.insteadOf",
        "https://github.com/",
    )
    await proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"git config failed with exit code {proc.returncode}")


async def clone_pr_branch(
    repo_url: str,
    branch: str,
    dest: Path,
    main_branch: str = "main",
) -> Path:
    """Clone a PR branch with an optimized strategy for code review.

    Uses --single-branch, --filter=blob:none, and --no-tags to minimize
    download size while keeping full commit history for merge-base and
    log operations against the main branch.
    """
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


async def clone_pr(
    owner: str,
    repo: str,
    branch: str,
    *,
    repo_url: str | None = None,
    main_branch: str = "main",
) -> Path:
    """Clone a PR branch into ~/projects/{repo}."""
    await configure_git_auth()
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    if repo_url is None:
        repo_url = f"https://github.com/{owner}/{repo}.git"

    dest = PROJECTS_DIR / repo

    if dest.exists():
        log.info("Destination %s already exists, checking out branch %s", dest, branch)
        proc = await asyncio.create_subprocess_exec(
            "git", "fetch", "--filter=blob:none", "origin", branch,
            cwd=dest,
        )
        await proc.communicate()
        if proc.returncode:
            raise RuntimeError(f"git fetch failed with exit code {proc.returncode}")
        proc = await asyncio.create_subprocess_exec(
            "git", "checkout", branch,
            cwd=dest,
        )
        await proc.communicate()
        if proc.returncode:
            raise RuntimeError(f"git checkout failed with exit code {proc.returncode}")
        return dest

    return await clone_pr_branch(repo_url, branch, dest, main_branch=main_branch)
