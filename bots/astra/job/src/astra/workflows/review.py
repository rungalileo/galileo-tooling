import logging
from dataclasses import asdict, dataclass

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    ToolUseBlock,
    query,
)

from astra.skills.loader import load_skill

log = logging.getLogger(__name__)


@dataclass
class ContextFile:
    title: str
    path: str


_SEVERITY_ENUM = ["critical", "major", "minor", "nit"]
_CATEGORY_ENUM = [
    "bug",
    "security",
    "design",
    "performance",
    "testing",
    "documentation",
    "question",
    "other",
]

_COMMENT_PROPERTIES = {
    "severity": {"type": "string", "enum": _SEVERITY_ENUM},
    "category": {"type": "string", "enum": _CATEGORY_ENUM},
    "comment": {"type": "string"},
}

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["approve", "request_changes", "needs_discussion"],
        },
        "verdict_reason": {
            "type": "string",
            "description": "One-line rationale for the verdict.",
        },
        "pr_comments": {
            "type": "array",
            "description": "Comments about the pull request as a whole.",
            "items": {
                "type": "object",
                "properties": _COMMENT_PROPERTIES,
                "required": ["severity", "category", "comment"],
            },
        },
        "file_comments": {
            "type": "array",
            "description": "Comments about a specific file, not tied to a line.",
            "items": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repo root.",
                    },
                    **_COMMENT_PROPERTIES,
                },
                "required": ["path", "severity", "category", "comment"],
            },
        },
        "line_comments": {
            "type": "array",
            "description": "Comments on specific lines of a file.",
            "items": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repo root.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line number of the relevant range.",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line number (same as start_line for single-line comments).",
                    },
                    **_COMMENT_PROPERTIES,
                    "suggestion": {
                        "type": "string",
                        "description": "Suggested replacement code, if applicable.",
                    },
                },
                "required": [
                    "path",
                    "start_line",
                    "end_line",
                    "severity",
                    "category",
                    "comment",
                ],
            },
        },
        "comment_responses": {
            "type": "array",
            "description": "Responses to existing unresolved review comments.",
            "items": {
                "type": "object",
                "properties": {
                    "comment_url": {
                        "type": "string",
                        "description": "URL of the existing review comment.",
                    },
                    "response": {"type": "string"},
                },
                "required": ["comment_url", "response"],
            },
        },
        "follow_ups": {
            "type": "array",
            "description": "Non-blocking improvement opportunities outside the PR's scope.",
            "items": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to the repo root.",
                    },
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                    "description": {"type": "string"},
                },
                "required": ["path", "start_line", "end_line", "description"],
            },
        },
    },
    "required": [
        "verdict",
        "verdict_reason",
        "pr_comments",
        "file_comments",
        "line_comments",
        "comment_responses",
        "follow_ups",
    ],
}

ERROR_SUBTYPES = {
    "error_max_turns": "Agent hit the maximum turn limit ({turns} turns, ${cost:.4f})",
    "error_max_budget_usd": "Agent hit the budget limit ({turns} turns, ${cost:.4f})",
    "error_during_execution": "Agent encountered an execution error ({turns} turns, ${cost:.4f})",
    "error_max_structured_output_retries": "Agent failed to produce valid structured output ({turns} turns, ${cost:.4f})",
}


@dataclass
class WorkflowResult:
    review: dict | None = None
    error: str | None = None
    trace: list[dict] | None = None


async def run_review(
    context_files: dict[str, ContextFile],
    *,
    repo_dir: str | None = None,
) -> WorkflowResult:
    system_prompt = load_skill("review")

    user_prompt = "Review this pull request.\n\n"
    user_prompt += "You must read all these context files\n\n"
    for cf in context_files.values():
        user_prompt += f"- {cf.title}: {cf.path}\n"
    user_prompt += "\n"
    if repo_dir:
        user_prompt += f"Repository clone: {repo_dir}\n"

    log.info("Starting review agent")

    trace: list[dict] = []
    error: str | None = None
    turn = 0

    try:
        async for message in query(
            prompt=user_prompt,
            options=ClaudeAgentOptions(
                system_prompt=system_prompt,
                allowed_tools=[
                    "Read",
                    "Edit",
                    "Write",
                    "Bash",
                    "Glob",
                    "Grep",
                    "Agent",
                ],
                permission_mode="bypassPermissions",
                cwd=repo_dir,
                effort="high",
                output_format={"type": "json_schema", "schema": REVIEW_SCHEMA},
                max_turns=200,
                model="claude-opus-4-6",
                fallback_model="claude-sonnet-4-6",
                max_budget_usd=5.00,
            ),
        ):
            trace.append(
                {
                    "type": type(message).__name__,
                    **asdict(message),
                }
            )

            if isinstance(message, AssistantMessage):
                turn += 1
                tools = [b.name for b in message.content if isinstance(b, ToolUseBlock)]
                if tools:
                    log.info("Turn %d: %s", turn, ", ".join(tools))
                else:
                    log.info("Turn %d: response", turn)

            if isinstance(message, ResultMessage):
                turns = message.num_turns
                cost = message.total_cost_usd or 0

                if message.subtype == "success" and message.structured_output:
                    log.info("Done: %d turns, $%.4f", turns, cost)
                    return WorkflowResult(review=message.structured_output, trace=trace)

                error_template = ERROR_SUBTYPES.get(
                    message.subtype,
                    "Agent failed with unexpected status: {subtype} ({turns} turns, ${cost:.4f})",
                )
                error = error_template.format(
                    subtype=message.subtype, turns=turns, cost=cost
                )
                log.error(error)

    except Exception as exc:
        error = f"Agent raised an exception: {exc}"
        log.exception(error)

    return WorkflowResult(review=None, error=error, trace=trace)
