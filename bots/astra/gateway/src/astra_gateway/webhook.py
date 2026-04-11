import logging
import os

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from astra_gateway.auth import mint_installation_token, validate_webhook_signature
from astra_gateway.enqueue import enqueue_task

log = logging.getLogger(__name__)

router = APIRouter()

GITHUB_API = "https://api.github.com"
COMMAND_PREFIX = "/astra "
VALID_COMMANDS = {"review"}


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@router.post("/webhook")
async def handle_webhook(request: Request) -> JSONResponse:
    body = await request.body()

    # 1. Validate HMAC signature
    secret = os.environ["ASTRA_WEBHOOK_SECRET"]
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not validate_webhook_signature(body, signature, secret):
        return JSONResponse({"error": "invalid_signature"}, status_code=401)

    # 2. Filter by event type
    event = request.headers.get("X-GitHub-Event", "")
    if event != "issue_comment":
        return JSONResponse({"ignored": f"event={event}"})

    # 3. Filter by action
    payload = await request.json()
    if payload.get("action") != "created":
        return JSONResponse({"ignored": f"action={payload.get('action')}"})

    # 4. Must be a PR comment, not an issue comment
    if "pull_request" not in payload.get("issue", {}):
        return JSONResponse({"ignored": "not_pr"})

    # 5. Parse command
    comment_body = payload["comment"]["body"].strip()
    if not comment_body.startswith(COMMAND_PREFIX):
        return JSONResponse({"ignored": "not_astra_command"})
    parts = comment_body.split(None, 2)
    command = parts[1] if len(parts) >= 2 else None
    if not command:
        return JSONResponse({"ignored": "empty_command"})
    # 6. Extract fields
    repo_owner = payload["repository"]["owner"]["login"]
    repo_name = payload["repository"]["name"]
    pr_number = payload["issue"]["number"]
    comment_id = payload["comment"]["id"]
    installation_id = payload["installation"]["id"]
    requester = payload["comment"]["user"]["login"]

    log.info(
        "Received /astra %s from %s on %s/%s#%d",
        command, requester, repo_owner, repo_name, pr_number,
    )

    # 7. Mint installation token
    app_id = os.environ["ASTRA_APP_ID"]
    private_key = os.environ["ASTRA_APP_PRIVATE_KEY"]
    try:
        token = await mint_installation_token(app_id, private_key, installation_id)
    except Exception:
        log.exception("Failed to mint installation token for installation %s", installation_id)
        return JSONResponse({"error": "failed to mint installation token"})

    try:
        # 8. Validate command
        if command not in VALID_COMMANDS and command != "help":
            valid = ", ".join(sorted(VALID_COMMANDS | {"help"}))
            body = f"Unknown command `{command}`. Valid commands: {valid}."
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=_github_headers(token),
                    json={"body": body},
                )
            return JSONResponse({"ignored": f"unknown_command={command}"})

        if command == "help":
            lines = ["Available commands:"]
            lines.extend(f"- `{cmd}`" for cmd in sorted(VALID_COMMANDS | {"help"}))
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=_github_headers(token),
                    json={"body": "\n".join(lines)},
                )
            return JSONResponse({"ok": True, "command": "help"})

        try:
            async with httpx.AsyncClient() as client:
                # 9. Fetch head SHA
                pr_url = payload["issue"]["pull_request"]["url"]
                resp = await client.get(pr_url, headers=_github_headers(token))
                resp.raise_for_status()
                head_sha = resp.json()["head"]["sha"]

                # 10. Add eyes reaction (non-critical)
                try:
                    reaction_resp = await client.post(
                        f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}/reactions",
                        headers=_github_headers(token),
                        json={"content": "eyes"},
                    )
                    if not reaction_resp.is_success:
                        log.warning(
                            "Failed to add eyes reaction: %d %s",
                            reaction_resp.status_code, reaction_resp.text,
                        )
                except Exception:
                    log.warning("Failed to add eyes reaction", exc_info=True)
        except httpx.HTTPStatusError as exc:
            log.error("Failed to fetch PR head SHA: %s", exc)
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=_github_headers(token),
                    json={"body": f"Failed to process command: could not fetch PR metadata ({exc.response.status_code})."},
                )
                await client.post(
                    f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}/reactions",
                    headers=_github_headers(token),
                    json={"content": "confused"},
                )
            return JSONResponse({"error": "failed to fetch PR head SHA"})

        # 11. Enqueue Cloud Task
        await enqueue_task({
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "installation_id": installation_id,
            "comment_id": comment_id,
            "command": command,
            "requester": requester,
        })

        return JSONResponse({
            "ok": True,
            "command": command,
            "repo": f"{repo_owner}/{repo_name}",
            "pr": pr_number,
            "head_sha": head_sha,
            "requester": requester,
        })
    except Exception:
        log.exception(
            "Unexpected error processing /astra %s on %s/%s#%d",
            command, repo_owner, repo_name, pr_number,
        )
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments",
                    headers=_github_headers(token),
                    json={"body": "Sorry, an unexpected error occurred while processing your command."},
                )
                await client.post(
                    f"{GITHUB_API}/repos/{repo_owner}/{repo_name}/issues/comments/{comment_id}/reactions",
                    headers=_github_headers(token),
                    json={"content": "confused"},
                )
        except Exception:
            log.warning("Failed to post error feedback to PR", exc_info=True)
        return JSONResponse({"error": "unexpected error"})
