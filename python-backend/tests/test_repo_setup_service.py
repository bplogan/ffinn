"""Tests for automated GitHub repository CI/CD setup."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.ai_agent.repo_setup_service import RepositorySetupService
from app.core.security import encrypt_value
from app.domain.models.ai_agent import AIAgentConfiguration


def _make_config(**overrides) -> AIAgentConfiguration:
    enc = encrypt_value("gh-test-token", "test-encryption-key-for-tests-only32c")
    defaults = dict(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        name="Test",
        repository_url="https://github.com/owner/repo",
        source_control_provider="github",
        encrypted_access_token=enc,
        staging_workflow_id=None,
        release_workflow_id=None,
        api_base_url="",
    )
    defaults.update(overrides)
    return AIAgentConfiguration(**defaults)


@pytest.mark.asyncio
async def test_setup_repository_success(db):
    config = _make_config()
    db.add(config)
    await db.commit()

    mock_sc = MagicMock()
    mock_sc.verify_connection = AsyncMock(return_value=True)
    mock_sc.get_default_branch = AsyncMock(return_value="main")
    mock_sc.get_file_content = AsyncMock(return_value=None)
    mock_sc.upsert_file = AsyncMock(return_value=True)
    mock_sc.upsert_actions_secret = AsyncMock(return_value=True)
    mock_sc.upsert_actions_variable = AsyncMock(return_value=True)

    with patch("app.ai_agent.repo_setup_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.repo_setup_service.settings") as mock_settings:
            mock_settings.encryption_key = "test-encryption-key-for-tests-only32c"
            mock_settings.callback_token = "test-callback-token"
            mock_settings.api_base_url = "http://localhost:8000"

            svc = RepositorySetupService(db)
            result = await svc.setup_repository(config, api_base_url="https://api.example.com")

    assert result.success is True
    assert result.callback_token_configured is True
    assert result.api_base_url == "https://api.example.com"
    assert mock_sc.upsert_file.await_count == 2
    mock_sc.upsert_actions_secret.assert_awaited_once()
    mock_sc.upsert_actions_variable.assert_awaited_once()

    await db.refresh(config)
    assert config.staging_workflow_id == "ai-agent-staging.yml"
    assert config.release_workflow_id == "ai-agent-production.yml"


@pytest.mark.asyncio
async def test_setup_repository_keeps_existing_workflows(db):
    config = _make_config()
    db.add(config)
    await db.commit()

    mock_sc = MagicMock()
    mock_sc.verify_connection = AsyncMock(return_value=True)
    mock_sc.get_default_branch = AsyncMock(return_value="main")
    mock_sc.get_file_content = AsyncMock(return_value="name: custom deploy")
    mock_sc.upsert_file = AsyncMock(return_value=True)
    mock_sc.upsert_actions_secret = AsyncMock(return_value=True)
    mock_sc.upsert_actions_variable = AsyncMock(return_value=True)

    with patch("app.ai_agent.repo_setup_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.repo_setup_service.settings") as mock_settings:
            mock_settings.encryption_key = "test-encryption-key-for-tests-only32c"
            mock_settings.callback_token = "test-callback-token"
            mock_settings.api_base_url = "http://localhost:8000"

            result = await RepositorySetupService(db).setup_repository(config)

    assert result.success is True
    mock_sc.upsert_file.assert_not_awaited()
    assert [s.detail for s in result.steps if s.name.startswith("workflow:")] == ["Already present, left unchanged"] * 2


@pytest.mark.asyncio
async def test_setup_repository_fails_when_repo_unreachable(db):
    config = _make_config()
    db.add(config)
    await db.commit()

    mock_sc = MagicMock()
    mock_sc.verify_connection = AsyncMock(return_value=False)

    with patch("app.ai_agent.repo_setup_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.repo_setup_service.settings") as mock_settings:
            mock_settings.encryption_key = "test-encryption-key-for-tests-only32c"
            mock_settings.callback_token = "tok"
            mock_settings.api_base_url = "http://localhost:8000"

            svc = RepositorySetupService(db)
            result = await svc.setup_repository(config)

    assert result.success is False
    assert result.steps[0].name == "verify_repository"
    assert result.steps[0].success is False


@pytest.mark.asyncio
async def test_get_setup_status(db):
    config = _make_config(
        staging_workflow_id="ai-agent-staging.yml",
        release_workflow_id="ai-agent-production.yml",
    )

    mock_sc = MagicMock()
    mock_sc.verify_connection = AsyncMock(return_value=True)
    mock_sc.list_actions_secrets = AsyncMock(return_value=["FFINN_CALLBACK_TOKEN"])
    mock_sc.get_file_content = AsyncMock(return_value="workflow: true")

    with patch("app.ai_agent.repo_setup_service.settings") as mock_settings:
        mock_settings.callback_token = "tok"
        svc = RepositorySetupService(db)
        status = await svc.get_setup_status(config, mock_sc, "main")

    assert status["repository_connected"] is True
    assert status["callback_token_configured"] is True
    assert status["github_callback_secret_set"] is True
    assert all(w["present"] for w in status["workflows"])


# ── API integration ───────────────────────────────────────────────────────────

_VALID_CONFIG = {
    "name": "Setup Test Config",
    "source_control_type": "github",
    "repository_url": "https://github.com/owner/repo",
    "source_control_token": "gh-token-test",
    "ai_provider": "openai",
    "ai_model": "gpt-4o",
    "ai_api_key": "sk-test-key",
}


async def _auth_headers(client: AsyncClient) -> dict:
    from tests.test_ai_agent_api import _get_token
    token = await _get_token(client)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_setup_repository_endpoint_requires_auth(client: AsyncClient):
    resp = await client.post(
        f"/api/aiagent/configurations/{uuid.uuid4()}/setup-repository",
        json={},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_setup_repository_endpoint_mocked(client: AsyncClient):
    headers = await _auth_headers(client)
    create_resp = await client.post("/api/aiagent/configurations", json=_VALID_CONFIG, headers=headers)
    assert create_resp.status_code == 201
    config_id = create_resp.json()["id"]

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.steps = []
    mock_result.manual_steps = []
    mock_result.callback_token_configured = True
    mock_result.api_base_url = "http://localhost:8000"

    with patch(
        "app.ai_agent.repo_setup_service.RepositorySetupService.setup_repository",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        resp = await client.post(
            f"/api/aiagent/configurations/{config_id}/setup-repository",
            json={"api_base_url": "http://localhost:8000"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["callback_token_configured"] is True
