from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

SHORTCUT_API_BASE = "https://api.app.shortcut.com/api/v3"

SHORTCUT_URL_PATTERN = re.compile(
    r"https?://app\.shortcut\.com/[^/]+/story/(\d+)(?:/[^\s)\"'>]*)?"
)


def extract_story_id(story_url_or_id: str) -> int:
    """Extract a numeric story ID from a Shortcut URL or plain ID string."""
    value = story_url_or_id.strip()
    if value.isdigit():
        return int(value)

    parsed = urlparse(value)
    path = parsed.path.rstrip("/")
    match = re.match(r"^/[^/]+/story/(\d+)(?:/[^/]+)?$", path)
    if not match:
        raise ValueError(
            f"Could not extract Shortcut story ID from: {story_url_or_id!r}"
        )
    return int(match.group(1))


def extract_shortcut_urls(text: str) -> set[str]:
    """Find all Shortcut story URLs in a block of text."""
    return set(SHORTCUT_URL_PATTERN.findall(text))


async def get_story(
    story_url_or_id: str,
    api_token: str | None = None,
    *,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Fetch a Shortcut story (with comments) as JSON using the v3 REST API."""
    token = api_token or os.environ.get("SHORTCUT_API_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing Shortcut API token. Set SHORTCUT_API_TOKEN or pass api_token=..."
        )

    story_id = extract_story_id(story_url_or_id)
    headers = {
        "Shortcut-Token": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        # Fetch story
        url = f"{SHORTCUT_API_BASE}/stories/{story_id}"
        log.info("GET %s", url)
        resp = await client.get(url)
        resp.raise_for_status()
        story = resp.json()

        # Fetch comments for the story
        comments_url = f"{SHORTCUT_API_BASE}/stories/{story_id}/comments"
        log.info("GET %s", comments_url)
        comments_resp = await client.get(comments_url)
        comments_resp.raise_for_status()
        story["fetched_comments"] = comments_resp.json()

    return story
