"""
Comprehensive tests for source control module.
Covers: GitHubClient URL parsing, factory, API mock-based integration tests,
        CommitResult/PullRequestResult dataclasses.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai_agent.source_control import (
    GitHubClient,
    CommitResult,
    PullRequestResult,
    create_source_control_client,
)


# ═══════════════════════════════════════════════════════════════════════
# GitHubClient._parse_repo_url
# ═══════════════════════════════════════════════════════════════════════

class TestGitHubClientUrlParsing:
    def _client(self, url: str) -> GitHubClient:
        return GitHubClient(token="gh-test-token", repo_url=url)

    def test_https_url_standard(self):
        c = self._client("https://github.com/owner/my-repo")
        assert c._owner == "owner"
        assert c._repo == "my-repo"

    def test_https_url_with_git_suffix(self):
        c = self._client("https://github.com/owner/my-repo.git")
        assert c._owner == "owner"
        assert c._repo == "my-repo"

    def test_ssh_url(self):
        c = self._client("git@github.com:owner/my-repo.git")
        assert c._owner == "owner"
        assert c._repo == "my-repo"

    def test_short_owner_slash_repo(self):
        c = self._client("owner/my-repo")
        assert c._owner == "owner"
        assert c._repo == "my-repo"

    def test_url_with_trailing_slash(self):
        # GitHub URL with trailing slash is not a supported format;
        # the parser raises ValueError for URLs it cannot parse.
        with pytest.raises(ValueError, match="Cannot parse GitHub URL"):
            self._client("https://github.com/owner/my-repo/")

    def test_repo_with_dashes_and_underscores(self):
        c = self._client("https://github.com/my-org/my_awesome-repo")
        assert c._owner == "my-org"
        assert c._repo == "my_awesome-repo"

    def test_invalid_url_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot parse GitHub URL"):
            GitHubClient(token="tok", repo_url="not-a-valid-url-at-all")

    def test_org_name_with_numbers(self):
        c = self._client("https://github.com/org123/repo456")
        assert c._owner == "org123"
        assert c._repo == "repo456"

    def test_headers_set_correctly(self):
        c = self._client("owner/repo")
        assert "Authorization" in c._headers
        assert "token gh-test-token" == c._headers["Authorization"]
        assert "application/vnd.github.v3+json" in c._headers["Accept"]


# ═══════════════════════════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════════════════════════

class TestDataclasses:
    def test_commit_result_success(self):
        r = CommitResult(success=True, commit_sha="abc123")
        assert r.success is True
        assert r.commit_sha == "abc123"
        assert r.error is None

    def test_commit_result_failure(self):
        r = CommitResult(success=False, error="not found")
        assert r.success is False
        assert r.error == "not found"

    def test_pr_result_success(self):
        r = PullRequestResult(success=True, pr_number=42, pr_url="https://github.com/owner/repo/pull/42")
        assert r.success is True
        assert r.pr_number == 42

    def test_pr_result_failure(self):
        r = PullRequestResult(success=False, error="already exists")
        assert r.success is False
        assert r.pr_number is None


# ═══════════════════════════════════════════════════════════════════════
# create_source_control_client factory
# ═══════════════════════════════════════════════════════════════════════

class TestCreateSourceControlClient:
    def test_github_provider_returns_github_client(self):
        client = create_source_control_client("github", "tok", "owner/repo")
        assert isinstance(client, GitHubClient)

    def test_github_case_insensitive(self):
        client = create_source_control_client("GitHub", "tok", "owner/repo")
        assert isinstance(client, GitHubClient)

    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported source control provider"):
            create_source_control_client("gitlab", "tok", "owner/repo")

    def test_unsupported_bitbucket_raises(self):
        with pytest.raises(ValueError, match="Unsupported source control provider"):
            create_source_control_client("bitbucket", "tok", "owner/repo")


# ═══════════════════════════════════════════════════════════════════════
# GitHubClient.get_default_branch — mocked HTTP
# ═══════════════════════════════════════════════════════════════════════

def _make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


class TestGitHubClientAPIOperations:
    def _client(self) -> GitHubClient:
        return GitHubClient(token="gh-tok", repo_url="owner/repo")

    @pytest.mark.asyncio
    async def test_get_default_branch_returns_main(self):
        client = self._client()
        mock_resp = _make_mock_response(200, {"default_branch": "main"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            branch = await client.get_default_branch()

        assert branch == "main"

    @pytest.mark.asyncio
    async def test_get_default_branch_returns_master(self):
        client = self._client()
        mock_resp = _make_mock_response(200, {"default_branch": "master"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            branch = await client.get_default_branch()

        assert branch == "master"

    @pytest.mark.asyncio
    async def test_get_default_branch_falls_back_to_main(self):
        """If the API doesn't return default_branch, fall back to 'main'."""
        client = self._client()
        mock_resp = _make_mock_response(200, {})  # no default_branch key

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            branch = await client.get_default_branch()

        assert branch == "main"

    @pytest.mark.asyncio
    async def test_create_branch_returns_true_on_success(self):
        client = self._client()
        ref_resp = _make_mock_response(200, {"object": {"sha": "deadbeef"}})
        create_resp = _make_mock_response(201, {"ref": "refs/heads/ai-feature/test"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=ref_resp)
            mock_http.post = AsyncMock(return_value=create_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.create_branch("ai-feature/test", "main")

        assert result is True

    @pytest.mark.asyncio
    async def test_create_branch_returns_true_when_already_exists(self):
        """422 (branch already exists) should still return True."""
        client = self._client()
        ref_resp = _make_mock_response(200, {"object": {"sha": "deadbeef"}})
        already_exists_resp = _make_mock_response(422, {})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=ref_resp)
            mock_http.post = AsyncMock(return_value=already_exists_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.create_branch("ai-feature/existing", "main")

        assert result is True

    @pytest.mark.asyncio
    async def test_verify_connection_returns_true_on_200(self):
        client = self._client()
        mock_resp = _make_mock_response(200, {"full_name": "owner/repo"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            ok = await client.verify_connection()

        assert ok is True

    @pytest.mark.asyncio
    async def test_verify_connection_returns_false_on_401(self):
        client = self._client()
        mock_resp = _make_mock_response(401, {"message": "Bad credentials"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            ok = await client.verify_connection()

        assert ok is False

    @pytest.mark.asyncio
    async def test_verify_connection_returns_false_on_exception(self):
        client = self._client()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=Exception("network error"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            ok = await client.verify_connection()

        assert ok is False

    @pytest.mark.asyncio
    async def test_get_file_content_returns_decoded_base64(self):
        import base64
        client = self._client()
        encoded = base64.b64encode(b"# router.py content").decode("utf-8")
        mock_resp = _make_mock_response(200, {"encoding": "base64", "content": encoded})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            content = await client.get_file_content("python-backend/app/api/router.py")

        assert content == "# router.py content"

    @pytest.mark.asyncio
    async def test_get_file_content_returns_none_on_404(self):
        client = self._client()
        mock_resp = _make_mock_response(404, {"message": "Not Found"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            content = await client.get_file_content("nonexistent.py")

        assert content is None

    @pytest.mark.asyncio
    async def test_get_file_content_returns_none_on_exception(self):
        client = self._client()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=Exception("timeout"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            content = await client.get_file_content("any-file.py")

        assert content is None

    @pytest.mark.asyncio
    async def test_create_pr_returns_pr_number(self):
        client = self._client()
        pr_resp = _make_mock_response(
            201,
            {"number": 17, "html_url": "https://github.com/owner/repo/pull/17"},
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=pr_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.create_pull_request(
                title="[AI] blogs feature",
                body="AI generated",
                head="ai-feature/blogs",
                base="main",
                draft=True,
            )

        assert result.success is True
        assert result.pr_number == 17
        assert "pull/17" in result.pr_url

    @pytest.mark.asyncio
    async def test_create_pr_returns_failure_on_error(self):
        client = self._client()

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=Exception("unprocessable entity"))
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.create_pull_request(
                title="fail", body="", head="branch", base="main"
            )

        assert result.success is False
        assert result.error is not None


class TestGitHubMergeAndRevert:
    def _client(self):
        from app.ai_agent.source_control import GitHubClient
        return GitHubClient(token="ghp_test", repo_url="owner/repo")

    @pytest.mark.asyncio
    async def test_merge_pull_request_success(self):
        from app.ai_agent.source_control import MergeResult
        client = self._client()
        pr_resp = _make_mock_response(200, {"merged": False, "draft": False})
        merge_resp = _make_mock_response(200, {"sha": "merge123"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=pr_resp)
            mock_http.put = AsyncMock(return_value=merge_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.merge_pull_request(42)

        assert result.success is True
        assert result.merge_commit_sha == "merge123"

    @pytest.mark.asyncio
    async def test_merge_pull_request_already_merged(self):
        client = self._client()
        pr_resp = _make_mock_response(200, {"merged": True, "merge_commit_sha": "abc"})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=pr_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.merge_pull_request(42)

        assert result.success is True
        assert result.already_merged is True
        assert result.merge_commit_sha == "abc"
