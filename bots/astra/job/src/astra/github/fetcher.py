import json
import logging
from pathlib import Path

from . import api

log = logging.getLogger(__name__)


async def fetch_pr_data(
    owner: str,
    repo: str,
    pr_number: int,
    output_dir: Path,
    *,
    metadata: dict,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Fetching PR comments")
    comments = await api.get_pr_comments(owner, repo, pr_number)

    log.info("Fetching PR review comments")
    review_comments = await api.get_pr_review_comments(owner, repo, pr_number)

    pr_json_path = output_dir / "pr.json"
    pr_data = {
        "pr": metadata,
        "comments": comments,
        "review_comments": review_comments,
    }
    pr_json_path.write_text(json.dumps(pr_data, indent=2))
    log.info("Saved %s (%d bytes)", pr_json_path, pr_json_path.stat().st_size)

    log.info("Fetching PR diff")
    diff = await api.get_pr_diff(owner, repo, pr_number)

    diff_path = output_dir / "diff.patch"
    diff_path.write_text(diff)
    log.info("Saved %s (%d bytes)", diff_path, diff_path.stat().st_size)

    return {
        "diff": str(diff_path),
        "metadata": str(pr_json_path),
    }
