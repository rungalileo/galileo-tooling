import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

from astra.github import parse_pr_url
from astra.github.api import add_reaction, get_pr_metadata, post_error_comment, publish_review
from astra.github.clone import clone_pr
from astra.github.fetcher import fetch_pr_data
from astra.shortcut.api import extract_shortcut_urls, get_story
from astra.workflows.review import ContextFile, run_review


log = logging.getLogger(__name__)

GCP_PROJECT = "rungalileo-dev"
GCP_REGION = "us-west1"
JOB_NAME = "astra-job"


def _log_explorer_url(execution: str) -> str:
    """Build a GCP Log Explorer URL for a given job execution."""
    query = (
        f'resource.type = "cloud_run_job" '
        f'resource.labels.job_name = "{JOB_NAME}" '
        f'resource.labels.location = "{GCP_REGION}" '
        f'labels."run.googleapis.com/execution_name" = "{execution}" '
        f"severity>=DEFAULT"
    )
    return (
        f"https://console.cloud.google.com/logs/query"
        f";query={quote(query)}"
        f";storageScope=project"
        f"?project={GCP_PROJECT}"
    )


async def _fetch_shortcut_stories(
    pr_data: dict, output_dir: Path,
) -> dict[str, ContextFile]:
    """Extract Shortcut links from PR description and comments, fetch each story."""
    if not os.environ.get("SHORTCUT_API_TOKEN"):
        log.info("SHORTCUT_API_TOKEN not set, skipping Shortcut story fetch")
        return {}

    # Collect text from PR body and all comments
    texts: list[str] = []
    pr = pr_data.get("pr", {})
    if pr.get("body"):
        texts.append(pr["body"])
    for comment in pr_data.get("comments", []):
        if comment.get("body"):
            texts.append(comment["body"])
    for comment in pr_data.get("review_comments", []):
        if comment.get("body"):
            texts.append(comment["body"])

    # Deduplicate story IDs
    story_ids: set[str] = set()
    for text in texts:
        story_ids.update(extract_shortcut_urls(text))

    if not story_ids:
        log.info("No Shortcut story links found in PR")
        return {}

    log.info("Found %d Shortcut story link(s): %s", len(story_ids), story_ids)

    files: dict[str, ContextFile] = {}
    for story_id in sorted(story_ids):
        try:
            story = await get_story(story_id)
            filename = f"shortcut-sc-{story_id}.json"
            story_path = output_dir / filename
            story_path.write_text(json.dumps(story, indent=2))
            key = f"sc-{story_id}"
            files[key] = ContextFile(
                title=f"Shortcut story sc-{story_id}",
                path=str(story_path),
            )
            log.info("Saved %s to %s", key, story_path)
        except Exception:
            log.warning("Failed to fetch Shortcut story %s", story_id, exc_info=True)

    return files


async def _prepare_context_files(
    owner: str, repo: str, pr_number: int, output_dir: Path, *, metadata: dict,
) -> dict[str, ContextFile]:
    log.info("Fetching PR data")
    raw_paths = await fetch_pr_data(owner, repo, pr_number, output_dir, metadata=metadata)

    context_files: dict[str, ContextFile] = {
        "diff": ContextFile(title="Pull request diff", path=raw_paths["diff"]),
        "metadata": ContextFile(title="Pull request metadata", path=raw_paths["metadata"]),
    }

    # Load the saved PR data to extract Shortcut links
    pr_json_path = Path(raw_paths["metadata"])
    pr_data = json.loads(pr_json_path.read_text())
    shortcut_files = await _fetch_shortcut_stories(pr_data, output_dir)
    context_files.update(shortcut_files)

    context_files["binaries"] = ContextFile(
        title="Available binaries",
        path=str(Path.home() / "available-binaries.md"),
    )
    return context_files


async def _ensure_github_token() -> None:
    """If running via GitHub App, mint an installation token and set GITHUB_TOKEN."""
    installation_id = os.environ.get("ASTRA_INSTALLATION_ID")
    if not installation_id:
        return
    from astra.github.auth import mint_installation_token

    app_id = os.environ["ASTRA_APP_ID"]
    private_key = os.environ["ASTRA_APP_PRIVATE_KEY"]
    token = await mint_installation_token(app_id, private_key, int(installation_id))
    os.environ["GITHUB_TOKEN"] = token
    log.info("Minted installation token for installation %s", installation_id)


async def _react(owner: str, repo: str, comment_id: int | None, reaction: str) -> None:
    """Add a reaction to the triggering comment, if comment_id is available."""
    if not comment_id:
        return
    try:
        await add_reaction(owner, repo, comment_id, reaction)
    except Exception:
        log.warning("Failed to add %s reaction to comment %d", reaction, comment_id, exc_info=True)


async def cmd_review(args: argparse.Namespace) -> None:
    await _ensure_github_token()
    owner, repo, pr_number = parse_pr_url(args.pr_url)
    comment_id_str = os.environ.get("ASTRA_COMMENT_ID")
    comment_id = int(comment_id_str) if comment_id_str else None
    log.info("PR: %s/%s#%d (comment_id=%s)", owner, repo, pr_number, comment_id)

    try:
        await _run_review(owner, repo, pr_number, comment_id)
    except Exception:
        log.error("Review failed", exc_info=True)
        await _react(owner, repo, comment_id, "confused")
        try:
            execution = os.environ.get("CLOUD_RUN_EXECUTION", "unknown")
            logs_url = _log_explorer_url(execution)
            await post_error_comment(
                owner, repo, pr_number,
                "An unexpected error occurred while running the review. "
                f"Job: [`{execution}`]({logs_url})",
            )
        except Exception:
            log.warning("Failed to post error comment", exc_info=True)
        sys.exit(1)


async def _run_review(
    owner: str, repo: str, pr_number: int, comment_id: int | None,
) -> None:
    timestamp = f"{time.time_ns() // 1_000_000}"
    output_dir = Path(".output") / owner / repo / str(pr_number) / timestamp

    log.info("Fetching PR metadata")
    metadata = await get_pr_metadata(owner, repo, pr_number)
    branch = metadata["head"]["ref"]
    head_repo = metadata["head"].get("repo")
    if not head_repo:
        raise RuntimeError(
            "PR head repo is unavailable (deleted fork?). Cannot clone for review."
        )
    repo_url = head_repo["clone_url"]
    main_branch = metadata["base"]["ref"]
    log.info("Branch: %s, base: %s", branch, main_branch)

    log.info("Cloning PR branch")
    clone_path = await clone_pr(owner, repo, branch, repo_url=repo_url, main_branch=main_branch)

    if (clone_path / "pyproject.toml").exists():
        log.info("Found pyproject.toml, running poetry install")
        try:
            proc = await asyncio.create_subprocess_exec("poetry", "install", cwd=clone_path)
            await proc.communicate()
            if proc.returncode:
                log.warning("poetry install failed (exit %d), continuing without it", proc.returncode)
        except OSError:
            log.warning("poetry install failed, continuing without it")

    context_files = await _prepare_context_files(owner, repo, pr_number, output_dir, metadata=metadata)
    log.info("PR data saved to %s", output_dir)

    log.info("Running review workflow")
    result = await run_review(
        context_files,
        repo_dir=str(clone_path),
    )

    if result.trace:
        trace_path = output_dir / "trace.json"
        trace_path.write_text(json.dumps(result.trace, indent=2, default=str))
        log.info("Agent trace written to %s", trace_path)

    if result.error:
        execution = os.environ.get("CLOUD_RUN_EXECUTION", "unknown")
        logs_url = _log_explorer_url(execution)
        log.error("Workflow completed with error: %s", result.error)
        await _react(owner, repo, comment_id, "confused")
        try:
            await post_error_comment(owner, repo, pr_number, f"{result.error}\n\nJob: [`{execution}`]({logs_url})")
        except Exception:
            log.warning("Failed to post error comment", exc_info=True)
        sys.exit(1)

    if result.review:
        review_path = output_dir / "review.json"
        review_path.write_text(json.dumps(result.review, indent=2))
        log.info("Review written to %s", review_path)
        log.info("Publishing review to GitHub")
        submit_result = await publish_review(
            owner, repo, pr_number,
            commit_sha=metadata["head"]["sha"],
            review=result.review,
            pr_node_id=metadata["node_id"],
            diff_text=Path(context_files["diff"].path).read_text(),
        )
        log.info("Review published to GitHub")
        review_url = submit_result["submitPullRequestReview"]["pullRequestReview"]["url"]
        log.info("Review successfully published at %s", review_url)

    await _react(owner, repo, comment_id, "rocket")
