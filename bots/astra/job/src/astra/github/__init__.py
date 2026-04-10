import re

PR_URL_PATTERN = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


def parse_pr_url(url: str) -> tuple[str, str, int]:
    m = PR_URL_PATTERN.match(url)
    if not m:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    return m.group("owner"), m.group("repo"), int(m.group("number"))
