import pytest

from astra.github import parse_pr_url
from astra.github.api import _extract_comment_id, _parse_diff_lines
from astra.shortcut.api import extract_shortcut_urls, extract_story_id


class TestParsePrUrl:
    def test_standard_url(self):
        assert parse_pr_url("https://github.com/org/repo/pull/42") == (
            "org",
            "repo",
            42,
        )

    def test_http_url(self):
        assert parse_pr_url("http://github.com/org/repo/pull/1") == ("org", "repo", 1)

    def test_invalid_url(self):
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://example.com/not-a-pr")

    def test_missing_number(self):
        with pytest.raises(ValueError):
            parse_pr_url("https://github.com/org/repo/pull/")


class TestExtractCommentId:
    def test_rest_api_url(self):
        url = "https://api.github.com/repos/org/repo/pulls/comments/12345"
        assert _extract_comment_id(url) == 12345

    def test_html_discussion_url(self):
        url = "https://github.com/org/repo/pull/1#discussion_r67890"
        assert _extract_comment_id(url) == 67890

    def test_invalid_url(self):
        with pytest.raises(ValueError, match="Cannot extract comment ID"):
            _extract_comment_id("https://example.com/nothing")


class TestParseDiffLines:
    def test_simple_addition(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,4 @@\n"
            " line1\n"
            " line2\n"
            "+new_line\n"
            " line3\n"
        )
        result = _parse_diff_lines(diff)
        assert "foo.py" in result
        assert 1 in result["foo.py"]
        assert 2 in result["foo.py"]
        assert 3 in result["foo.py"]  # the new line
        assert 4 in result["foo.py"]

    def test_deletion_only(self):
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,3 +1,2 @@\n"
            " line1\n"
            "-removed\n"
            " line3"
        )
        result = _parse_diff_lines(diff)
        assert "foo.py" in result
        # Deleted lines don't appear on the new side
        assert result["foo.py"] == {1, 2}

    def test_new_file(self):
        diff = (
            "diff --git a/new.py b/new.py\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1,2 @@\n"
            "+line1\n"
            "+line2"
        )
        result = _parse_diff_lines(diff)
        assert result["new.py"] == {1, 2}

    def test_multiple_files(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing\n"
            "+added\n"
            "diff --git a/b.py b/b.py\n"
            "@@ -1,1 +1,1 @@\n"
            " unchanged\n"
        )
        result = _parse_diff_lines(diff)
        assert "a.py" in result
        assert "b.py" in result


class TestExtractShortcutUrls:
    def test_single_url(self):
        text = "See https://app.shortcut.com/galileo/story/12345 for details"
        assert extract_shortcut_urls(text) == {"12345"}

    def test_multiple_urls(self):
        text = (
            "Links: https://app.shortcut.com/galileo/story/111 "
            "and https://app.shortcut.com/galileo/story/222/slug"
        )
        assert extract_shortcut_urls(text) == {"111", "222"}

    def test_no_urls(self):
        assert extract_shortcut_urls("no links here") == set()

    def test_deduplication(self):
        text = (
            "https://app.shortcut.com/galileo/story/42 "
            "https://app.shortcut.com/galileo/story/42"
        )
        assert extract_shortcut_urls(text) == {"42"}


class TestExtractStoryId:
    def test_plain_id(self):
        assert extract_story_id("12345") == 12345

    def test_url(self):
        assert extract_story_id("https://app.shortcut.com/galileo/story/678") == 678

    def test_url_with_slug(self):
        assert (
            extract_story_id("https://app.shortcut.com/galileo/story/678/my-story")
            == 678
        )

    def test_invalid(self):
        with pytest.raises(ValueError, match="Could not extract"):
            extract_story_id("not-a-story")
