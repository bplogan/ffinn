"""
Source control integration — GitHub (primary), extensible to Git-lab, Azure DevOps.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

log = structlog.get_logger(__name__)


@dataclass
class CommitResult:
    success: bool
    commit_sha: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PullRequestResult:
    success: bool
    pr_number: Optional[int] = None
    pr_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class MergeResult:
    success: bool
    merge_commit_sha: Optional[str] = None
    already_merged: bool = False
    error: Optional[str] = None


class GitHubClient:
    """GitHub REST API client for source control operations."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, repo_url: str):
        self._token = token
        self._owner, self._repo = self._parse_repo_url(repo_url)
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _parse_repo_url(self, url: str) -> tuple[str, str]:
        """Parse owner/repo from GitHub URL.

        Hard-rejects non-github.com hosts to prevent token leakage to
        attacker-controlled hosts via the encrypted source-control token.
        """
        from urllib.parse import urlparse
        clean = url.strip()
        if "://" in clean:
            parsed = urlparse(clean)
            host = (parsed.hostname or "").lower()
            if host not in ("github.com", "www.github.com", "api.github.com"):
                raise ValueError(
                    "Only github.com repository URLs are supported."
                )
        # https://github.com/owner/repo or owner/repo
        patterns = [
            r"github\.com[:/]([^/]+)/([^/\s.]+?)(?:\.git)?$",
            r"^([^/:\s]+)/([^/\s]+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, clean)
            if match:
                repo = match.group(2)
                if repo.endswith(".git"):
                    repo = repo[:-4]
                return match.group(1), repo
        raise ValueError(f"Cannot parse GitHub URL: {url}")

    async def get_default_branch(self) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self.BASE_URL}/repos/{self._owner}/{self._repo}",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json().get("default_branch", "main")

    async def create_branch(self, branch_name: str, from_branch: str) -> bool:
        """Create a new branch from an existing branch."""
        async with httpx.AsyncClient(timeout=30) as client:
            # Get SHA of the source branch
            ref_resp = await client.get(
                f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/ref/heads/{from_branch}",
                headers=self._headers,
            )
            ref_resp.raise_for_status()
            sha = ref_resp.json()["object"]["sha"]

            # Create the new branch
            create_resp = await client.post(
                f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/refs",
                headers=self._headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": sha},
            )
            if create_resp.status_code == 422:
                # Branch already exists
                log.warning("Branch already exists", branch=branch_name)
                return True
            create_resp.raise_for_status()
            return True

    async def commit_files(
        self,
        branch: str,
        files: dict[str, str],
        commit_message: str,
    ) -> CommitResult:
        """Commit multiple files to a branch in a single commit."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Get branch head SHA
                ref_resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/ref/heads/{branch}",
                    headers=self._headers,
                )
                ref_resp.raise_for_status()
                head_sha = ref_resp.json()["object"]["sha"]

                # Get base tree SHA
                commit_resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/commits/{head_sha}",
                    headers=self._headers,
                )
                commit_resp.raise_for_status()
                base_tree_sha = commit_resp.json()["tree"]["sha"]

                # Build new tree
                import posixpath
                tree_items = []
                for path, content in files.items():
                    # Normalise path: collapse any ../ traversal sequences then
                    # strip a leading / so the path is always repo-relative.
                    clean_path = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
                    if ".." in clean_path:
                        log.warning("Skipping path with traversal after normalisation", path=path)
                        continue
                    tree_items.append({
                        "path": clean_path,
                        "mode": "100644",
                        "type": "blob",
                        "content": content,
                    })

                tree_resp = await client.post(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/trees",
                    headers=self._headers,
                    json={"base_tree": base_tree_sha, "tree": tree_items},
                )
                tree_resp.raise_for_status()
                new_tree_sha = tree_resp.json()["sha"]

                # Create commit
                commit_create_resp = await client.post(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/commits",
                    headers=self._headers,
                    json={
                        "message": commit_message,
                        "tree": new_tree_sha,
                        "parents": [head_sha],
                    },
                )
                commit_create_resp.raise_for_status()
                new_commit_sha = commit_create_resp.json()["sha"]

                # Update branch reference
                update_resp = await client.patch(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/refs/heads/{branch}",
                    headers=self._headers,
                    json={"sha": new_commit_sha},
                )
                update_resp.raise_for_status()

                return CommitResult(success=True, commit_sha=new_commit_sha)

        except Exception as e:
            log.error("GitHub commit failed", error=str(e))
            return CommitResult(success=False, error=str(e))

    async def mark_pull_request_ready(self, pr_number: int) -> bool:
        """Convert a draft PR to ready-for-review."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.patch(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls/{pr_number}",
                    headers=self._headers,
                    json={"draft": False},
                )
                return resp.status_code == 200
        except Exception as e:
            log.warning("Mark PR ready failed", pr=pr_number, error=str(e))
            return False

    async def merge_pull_request(
        self,
        pr_number: int,
        merge_method: str = "squash",
    ) -> MergeResult:
        """Merge an open pull request. Returns merge commit SHA when successful."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                pr_resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls/{pr_number}",
                    headers=self._headers,
                )
                if pr_resp.status_code != 200:
                    return MergeResult(success=False, error=f"PR #{pr_number} not found")
                pr_data = pr_resp.json()
                if pr_data.get("merged"):
                    sha = pr_data.get("merge_commit_sha")
                    return MergeResult(success=True, merge_commit_sha=sha, already_merged=True)
                if pr_data.get("draft"):
                    await self.mark_pull_request_ready(pr_number)

                merge_resp = await client.put(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls/{pr_number}/merge",
                    headers=self._headers,
                    json={"merge_method": merge_method},
                )
                if merge_resp.status_code == 405:
                    # Already merged (race) — re-fetch
                    pr_resp2 = await client.get(
                        f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls/{pr_number}",
                        headers=self._headers,
                    )
                    if pr_resp2.status_code == 200 and pr_resp2.json().get("merged"):
                        return MergeResult(
                            success=True,
                            merge_commit_sha=pr_resp2.json().get("merge_commit_sha"),
                            already_merged=True,
                        )
                merge_resp.raise_for_status()
                data = merge_resp.json()
                return MergeResult(success=True, merge_commit_sha=data.get("sha"))
        except Exception as e:
            log.error("Merge PR failed", pr=pr_number, error=str(e))
            return MergeResult(success=False, error=str(e))

    async def close_pull_request(self, pr_number: int) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.patch(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls/{pr_number}",
                    headers=self._headers,
                    json={"state": "closed"},
                )
                return resp.status_code == 200
        except Exception as e:
            log.warning("Close PR failed", pr=pr_number, error=str(e))
            return False

    async def revert_pull_request(self, pr_number: int) -> PullRequestResult:
        """Open a revert PR for a merged pull request."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls/{pr_number}/revert",
                    headers=self._headers,
                    json={},
                )
                if resp.status_code not in (200, 201):
                    return PullRequestResult(success=False, error=resp.text[:500])
                data = resp.json()
                return PullRequestResult(
                    success=True,
                    pr_number=data.get("number"),
                    pr_url=data.get("html_url"),
                )
        except Exception as e:
            log.error("Revert PR failed", pr=pr_number, error=str(e))
            return PullRequestResult(success=False, error=str(e))

    async def delete_branch(self, branch_name: str) -> bool:
        ref = branch_name.replace("refs/heads/", "")
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.delete(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/git/refs/heads/{ref}",
                    headers=self._headers,
                )
                return resp.status_code in (204, 404)
        except Exception as e:
            log.warning("Delete branch failed", branch=branch_name, error=str(e))
            return False

    async def create_pull_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        draft: bool = False,
    ) -> PullRequestResult:
        """Create a pull request."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/pulls",
                    headers=self._headers,
                    json={"title": title, "body": body, "head": head, "base": base, "draft": draft},
                )
                resp.raise_for_status()
                data = resp.json()
                return PullRequestResult(
                    success=True, pr_number=data["number"], pr_url=data["html_url"]
                )
        except Exception as e:
            log.error("Create PR failed", error=str(e))
            return PullRequestResult(success=False, error=str(e))

    async def trigger_workflow(
        self,
        workflow_id: str,
        inputs: dict,
        ref: str = "main",
    ) -> bool:
        """Trigger a GitHub Actions workflow dispatch."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/workflows/{workflow_id}/dispatches",
                    headers=self._headers,
                    json={"ref": ref, "inputs": inputs},
                )
                return resp.status_code == 204
        except Exception as e:
            log.error("Trigger workflow failed", workflow=workflow_id, error=str(e))
            return False

    async def get_file_content(self, path: str, ref: str = "main") -> Optional[str]:
        """Get file content from the repo."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/contents/{path}",
                    headers=self._headers,
                    params={"ref": ref},
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
                if data.get("encoding") == "base64":
                    return base64.b64decode(data["content"]).decode("utf-8")
                return data.get("content")
        except Exception:
            return None

    async def upsert_file(
        self,
        path: str,
        content: str,
        branch: str,
        message: str,
    ) -> bool:
        """Create or update a file on a branch via the Contents API."""
        import posixpath
        clean_path = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                sha: Optional[str] = None
                get_resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/contents/{clean_path}",
                    headers=self._headers,
                    params={"ref": branch},
                )
                if get_resp.status_code == 200:
                    sha = get_resp.json().get("sha")

                body: dict = {
                    "message": message,
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": branch,
                }
                if sha:
                    body["sha"] = sha

                put_resp = await client.put(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/contents/{clean_path}",
                    headers=self._headers,
                    json=body,
                )
                put_resp.raise_for_status()
                return True
        except Exception as e:
            log.error("Upsert file failed", path=path, error=str(e))
            return False

    async def get_actions_public_key(self) -> Optional[tuple[str, str]]:
        """Return (key_id, public_key_base64) for encrypting Actions secrets."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/secrets/public-key",
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("key_id"), data.get("key")
        except Exception as e:
            log.error("Get actions public key failed", error=str(e))
            return None

    @staticmethod
    def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
        from nacl import encoding, public

        pk = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder)
        sealed = public.SealedBox(pk).encrypt(secret_value.encode("utf-8"))
        return base64.b64encode(sealed).decode("utf-8")

    async def upsert_actions_secret(self, name: str, value: str) -> bool:
        key_info = await self.get_actions_public_key()
        if not key_info:
            return False
        key_id, public_key = key_info
        try:
            encrypted = self.encrypt_secret(public_key, value)
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.put(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/secrets/{name}",
                    headers=self._headers,
                    json={"encrypted_value": encrypted, "key_id": key_id},
                )
                return resp.status_code in (201, 204)
        except Exception as e:
            log.error("Upsert actions secret failed", name=name, error=str(e))
            return False

    async def upsert_actions_variable(self, name: str, value: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                get_resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/variables/{name}",
                    headers=self._headers,
                )
                if get_resp.status_code == 200:
                    patch_resp = await client.patch(
                        f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/variables/{name}",
                        headers=self._headers,
                        json={"name": name, "value": value},
                    )
                    return patch_resp.status_code == 204
                post_resp = await client.post(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/variables",
                    headers=self._headers,
                    json={"name": name, "value": value},
                )
                return post_resp.status_code == 201
        except Exception as e:
            log.error("Upsert actions variable failed", name=name, error=str(e))
            return False

    async def list_actions_secrets(self) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}/actions/secrets",
                    headers=self._headers,
                    params={"per_page": 100},
                )
                resp.raise_for_status()
                return [s["name"] for s in resp.json().get("secrets", [])]
        except Exception:
            return []

    async def verify_connection(self) -> bool:
        """Test if the token and repo are accessible."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/repos/{self._owner}/{self._repo}",
                    headers=self._headers,
                )
                return resp.status_code == 200
        except Exception:
            return False


def create_source_control_client(
    provider: str,
    token: str,
    repo_url: str,
) -> GitHubClient:
    """Factory for source control clients. Currently supports GitHub."""
    if provider.lower() in ("github",):
        return GitHubClient(token=token, repo_url=repo_url)
    # Future: GitLab, Azure DevOps
    raise ValueError(f"Unsupported source control provider: {provider}")
