"""
Comprehensive tests for AIAgentService orchestration layer.
All external I/O (AI providers, source control, WebSocket) is mocked.
Database uses the shared in-memory SQLite engine from conftest.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_agent.ai_agent_service import AIAgentService, GenerationStatus
from app.domain.models.ai_agent import AIAgentConfiguration, AIAgentGeneration


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_config(tenant_id: uuid.UUID, user_id: uuid.UUID) -> AIAgentConfiguration:
    return AIAgentConfiguration(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        created_by_id=user_id,
        name="Test Config",
        source_control_type="github",
        repository_url="owner/repo",
        source_control_token_encrypted="enc-token",
        ai_provider="openai",
        ai_model="gpt-4o",
        ai_api_key_encrypted="enc-key",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_service(db: AsyncSession, ws=None) -> AIAgentService:
    return AIAgentService(db=db, websocket_manager=ws)


# ═══════════════════════════════════════════════════════════════════════
# GenerationStatus constants
# ═══════════════════════════════════════════════════════════════════════

class TestGenerationStatus:
    def test_all_status_constants_are_strings(self):
        statuses = [
            GenerationStatus.DRAFT, GenerationStatus.QUEUED, GenerationStatus.ANALYZING,
            GenerationStatus.GENERATING, GenerationStatus.VALIDATING, GenerationStatus.AUTO_FIXING,
            GenerationStatus.COMMITTING, GenerationStatus.CREATING_PR, GenerationStatus.BUILDING,
            GenerationStatus.STAGING, GenerationStatus.READY, GenerationStatus.RELEASING,
            GenerationStatus.RELEASED,
            GenerationStatus.FAILED, GenerationStatus.CANCELLED, GenerationStatus.REVERTED,
        ]
        for s in statuses:
            assert isinstance(s, str)
            assert len(s) > 0

    def test_no_duplicate_status_values(self):
        statuses = [
            GenerationStatus.DRAFT, GenerationStatus.QUEUED, GenerationStatus.ANALYZING,
            GenerationStatus.GENERATING, GenerationStatus.VALIDATING, GenerationStatus.AUTO_FIXING,
            GenerationStatus.COMMITTING, GenerationStatus.CREATING_PR, GenerationStatus.BUILDING,
            GenerationStatus.STAGING, GenerationStatus.READY, GenerationStatus.RELEASING,
            GenerationStatus.RELEASED,
            GenerationStatus.FAILED, GenerationStatus.CANCELLED, GenerationStatus.REVERTED,
        ]
        assert len(statuses) == len(set(statuses))


# ═══════════════════════════════════════════════════════════════════════
# create_generation
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_generation_success(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    generation = await svc.create_generation(
        tenant_id=tenant_id,
        user_id=user_id,
        config_id=config.id,
        prompt="Build a blog feature",
        feature_name="Blog",
    )

    assert generation.id is not None
    assert generation.tenant_id == tenant_id
    assert generation.user_id == user_id
    assert generation.config_id == config.id
    assert generation.status == GenerationStatus.QUEUED
    assert generation.feature_name == "Blog"
    assert generation.user_prompt == "Build a blog feature"


@pytest.mark.asyncio
async def test_create_generation_with_overrides(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    generation = await svc.create_generation(
        tenant_id=tenant_id,
        user_id=user_id,
        config_id=config.id,
        prompt="Build an orders feature",
        feature_name="Orders",
        provider_override="anthropic",
        model_override="claude-3-5-sonnet-20241022",
    )

    assert generation.provider_override == "anthropic"
    assert generation.model_override == "claude-3-5-sonnet-20241022"


@pytest.mark.asyncio
async def test_create_generation_config_not_found_raises(db: AsyncSession):
    svc = _make_service(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.create_generation(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            config_id=uuid.uuid4(),  # non-existent
            prompt="build something",
            feature_name="test",
        )


@pytest.mark.asyncio
async def test_create_generation_inactive_config_raises(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    config.is_active = False
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    with pytest.raises(ValueError, match="not active"):
        await svc.create_generation(
            tenant_id=tenant_id,
            user_id=user_id,
            config_id=config.id,
            prompt="build something",
            feature_name="test",
        )


@pytest.mark.asyncio
async def test_create_generation_wrong_tenant_raises(db: AsyncSession):
    """Config belongs to tenant A — tenant B cannot use it."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_a, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.create_generation(
            tenant_id=tenant_b,
            user_id=user_id,
            config_id=config.id,
            prompt="build something",
            feature_name="test",
        )


# ═══════════════════════════════════════════════════════════════════════
# cancel_generation
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cancel_queued_generation(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    generation = await svc.create_generation(
        tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, prompt="x", feature_name="X",
    )
    assert generation.status == GenerationStatus.QUEUED

    await svc.cancel_generation(generation.id, tenant_id)
    await db.refresh(generation)
    assert generation.status == GenerationStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_released_generation_raises(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="X", user_prompt="x",
        status=GenerationStatus.RELEASED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    with pytest.raises(ValueError, match="Cannot cancel"):
        await svc.cancel_generation(gen.id, tenant_id)


@pytest.mark.asyncio
async def test_cancel_nonexistent_generation_raises(db: AsyncSession):
    svc = _make_service(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.cancel_generation(uuid.uuid4(), uuid.uuid4())


@pytest.mark.asyncio
async def test_cancel_wrong_tenant_raises(db: AsyncSession):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_a, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_a, user_id=user_id,
        config_id=config.id, feature_name="X", user_prompt="x",
        status=GenerationStatus.QUEUED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.cancel_generation(gen.id, tenant_b)


# ═══════════════════════════════════════════════════════════════════════
# revert_generation
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_revert_ready_generation(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.READY,
        pr_number=3, branch_name="ai-feature/blog-abc",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    mock_sc = AsyncMock()
    mock_sc.close_pull_request = AsyncMock(return_value=True)
    mock_sc.delete_branch = AsyncMock(return_value=True)

    svc = _make_service(db)
    with patch("app.ai_agent.ai_agent_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.ai_agent_service._decrypt", return_value="token"):
            await svc.revert_generation(gen.id, tenant_id)
    await db.refresh(gen)
    assert gen.status == GenerationStatus.REVERTED
    assert gen.reverted_at is not None
    mock_sc.close_pull_request.assert_awaited_once_with(3)
    mock_sc.delete_branch.assert_awaited_once_with("ai-feature/blog-abc")


@pytest.mark.asyncio
async def test_revert_staging_generation_restores_staging(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    config.staging_workflow_id = "ai-agent-staging.yml"
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.STAGING,
        pr_number=5, branch_name="ai-agent/blog-abc",
        staging_url="https://staging.example.com",
        staging_deployed_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    mock_sc = AsyncMock()
    mock_sc.close_pull_request = AsyncMock(return_value=True)
    mock_sc.delete_branch = AsyncMock(return_value=True)
    mock_sc.get_default_branch = AsyncMock(return_value="main")
    mock_sc.trigger_workflow = AsyncMock(return_value=True)

    svc = _make_service(db)
    with patch("app.ai_agent.ai_agent_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.ai_agent_service._decrypt", return_value="token"):
            await svc.revert_generation(gen.id, tenant_id)

    await db.refresh(gen)
    assert gen.status == GenerationStatus.REVERTED
    assert gen.staging_url is None
    assert gen.staging_deployed_at is None
    mock_sc.close_pull_request.assert_awaited_once_with(5)
    mock_sc.trigger_workflow.assert_awaited_once()
    assert mock_sc.trigger_workflow.await_args.kwargs["inputs"]["branch"] == "main"
    mock_sc.delete_branch.assert_awaited_once_with("ai-agent/blog-abc")


@pytest.mark.asyncio
async def test_deploy_callback_ignored_after_revert(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.REVERTED,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    await svc.handle_deploy_callback(gen.id, success=True, staging_url="https://staging.example.com")
    await db.refresh(gen)
    assert gen.status == GenerationStatus.REVERTED
    assert gen.staging_url is None


@pytest.mark.asyncio
async def test_revert_wrong_tenant_raises(db: AsyncSession):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_a, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_a, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.READY,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    with pytest.raises(ValueError, match="not found"):
        await svc.revert_generation(gen.id, tenant_b)


# ═══════════════════════════════════════════════════════════════════════
# release_generation / deploy_staging / release callback
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_release_generation_merges_pr_and_sets_releasing(db: AsyncSession):
    from app.ai_agent.source_control import MergeResult

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    config.release_workflow_id = "ai-agent-production.yml"
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.READY, pr_number=7, branch_name="ai-feature/blog-abc",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    mock_sc = AsyncMock()
    mock_sc.get_default_branch = AsyncMock(return_value="main")
    mock_sc.merge_pull_request = AsyncMock(
        return_value=MergeResult(success=True, merge_commit_sha="deadbeef")
    )
    mock_sc.trigger_workflow = AsyncMock(return_value=True)

    svc = _make_service(db)
    with patch("app.ai_agent.ai_agent_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.ai_agent_service._decrypt", return_value="token"):
            await svc.release_generation(gen.id, tenant_id)

    await db.refresh(gen)
    assert gen.status == GenerationStatus.RELEASING
    assert gen.commit_sha == "deadbeef"
    mock_sc.merge_pull_request.assert_awaited_once_with(7)
    mock_sc.trigger_workflow.assert_awaited_once()


@pytest.mark.asyncio
async def test_release_blocks_when_staging_verification_required(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    config.release_workflow_id = "ai-agent-production.yml"
    config.staging_workflow_id = "ai-agent-staging.yml"
    config.require_staging_verification = True
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.READY,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    with pytest.raises(ValueError, match="Staging verification required"):
        await svc.release_generation(gen.id, tenant_id)


@pytest.mark.asyncio
async def test_handle_release_callback_success(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.RELEASING,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    await svc.handle_release_callback(gen.id, success=True, production_url="https://api.example.com")
    await db.refresh(gen)
    assert gen.status == GenerationStatus.RELEASED
    assert gen.released_at is not None


@pytest.mark.asyncio
async def test_deploy_staging_triggers_workflow(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    config.staging_workflow_id = "ai-agent-staging.yml"
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.READY, branch_name="ai-feature/blog-abc",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    mock_sc = AsyncMock()
    mock_sc.get_default_branch = AsyncMock(return_value="main")
    mock_sc.trigger_workflow = AsyncMock(return_value=True)

    svc = _make_service(db)
    with patch("app.ai_agent.ai_agent_service.create_source_control_client", return_value=mock_sc):
        with patch("app.ai_agent.ai_agent_service._decrypt", return_value="token"):
            await svc.deploy_staging_generation(gen.id, tenant_id)

    await db.refresh(gen)
    assert gen.status == GenerationStatus.BUILDING
    mock_sc.trigger_workflow.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════════════
# handle_build_callback
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_handle_build_callback_success(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.BUILDING,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    await svc.handle_build_callback(gen.id, success=True, build_url="https://ci.example.com/builds/1")
    await db.refresh(gen)
    assert gen.status == GenerationStatus.STAGING
    assert gen.pipeline_status == "success"


@pytest.mark.asyncio
async def test_handle_build_callback_failure(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.BUILDING,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    await svc.handle_build_callback(gen.id, success=False, error="Tests failed")
    await db.refresh(gen)
    assert gen.status == GenerationStatus.READY
    assert gen.pipeline_status == "failed"
    assert gen.error_message == "Tests failed"


@pytest.mark.asyncio
async def test_handle_build_callback_nonexistent_silently_ignores(db: AsyncSession):
    """Callback for a non-existent generation should not raise."""
    svc = _make_service(db)
    await svc.handle_build_callback(uuid.uuid4(), success=True)  # no exception


# ═══════════════════════════════════════════════════════════════════════
# handle_pr_validation_callback
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_pr_validation_approved(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.BUILDING,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    await svc.handle_pr_validation_callback(gen.id, approved=True)
    await db.refresh(gen)
    assert gen.status == GenerationStatus.READY
    assert gen.code_review_status == "Approved"


@pytest.mark.asyncio
async def test_pr_validation_rejected(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)

    gen = AIAgentGeneration(
        id=uuid.uuid4(), tenant_id=tenant_id, user_id=user_id,
        config_id=config.id, feature_name="Blog", user_prompt="x",
        status=GenerationStatus.BUILDING,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(gen)
    await db.commit()

    svc = _make_service(db)
    await svc.handle_pr_validation_callback(gen.id, approved=False, reviewer_notes="Fix naming")
    await db.refresh(gen)
    assert gen.code_review_status == "ChangesRequested"


# ═══════════════════════════════════════════════════════════════════════
# list_generations / get_generation
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_generations_returns_only_tenant_items(db: AsyncSession):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()

    config_a = _make_config(tenant_a, user_id)
    config_b = _make_config(tenant_b, user_id)
    db.add(config_a)
    db.add(config_b)
    await db.commit()

    svc_a = _make_service(db)
    svc_b = _make_service(db)

    await svc_a.create_generation(tenant_a, user_id, config_a.id, "p1", "F1")
    await svc_a.create_generation(tenant_a, user_id, config_a.id, "p2", "F2")
    await svc_b.create_generation(tenant_b, user_id, config_b.id, "p3", "F3")

    items_a, total_a = await svc_a.list_generations(tenant_a)
    assert total_a == 2
    assert all(g.tenant_id == tenant_a for g in items_a)

    items_b, total_b = await svc_b.list_generations(tenant_b)
    assert total_b == 1


@pytest.mark.asyncio
async def test_list_generations_filter_by_config_id(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config1 = _make_config(tenant_id, user_id)
    config2 = _make_config(tenant_id, user_id)
    db.add(config1)
    db.add(config2)
    await db.commit()

    svc = _make_service(db)
    await svc.create_generation(tenant_id, user_id, config1.id, "p1", "F1")
    await svc.create_generation(tenant_id, user_id, config2.id, "p2", "F2")
    await svc.create_generation(tenant_id, user_id, config1.id, "p3", "F3")

    items, total = await svc.list_generations(tenant_id, config_id=config1.id)
    assert total == 2
    assert all(g.config_id == config1.id for g in items)


@pytest.mark.asyncio
async def test_list_generations_pagination(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    for i in range(5):
        await svc.create_generation(tenant_id, user_id, config.id, f"prompt {i}", f"Feature{i}")

    page1, total = await svc.list_generations(tenant_id, page=1, page_size=3)
    assert len(page1) == 3
    assert total == 5

    page2, _ = await svc.list_generations(tenant_id, page=2, page_size=3)
    assert len(page2) == 2


@pytest.mark.asyncio
async def test_get_generation_returns_correct_item(db: AsyncSession):
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(tenant_id, user_id, config.id, "myPrompt", "MyFeature")
    fetched = await svc.get_generation(gen.id, tenant_id)

    assert fetched is not None
    assert fetched.id == gen.id
    assert fetched.feature_name == "MyFeature"


@pytest.mark.asyncio
async def test_get_generation_wrong_tenant_returns_none(db: AsyncSession):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_a, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(tenant_a, user_id, config.id, "p", "F")
    result = await svc.get_generation(gen.id, tenant_b)
    assert result is None


# ═══════════════════════════════════════════════════════════════════════
# WebSocket emission — non-fatal
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_ws_error_does_not_fail_service(db: AsyncSession):
    """WebSocket broadcast failures must be silently swallowed."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    broken_ws = AsyncMock()
    broken_ws.broadcast_to_tenant = AsyncMock(side_effect=Exception("ws connection dropped"))

    svc = _make_service(db, ws=broken_ws)
    gen = await svc.create_generation(tenant_id, user_id, config.id, "p", "F")
    # cancel triggers _emit which calls the broken WS — must not raise
    await svc.cancel_generation(gen.id, tenant_id)


# ═══════════════════════════════════════════════════════════════════════
# process_generation — mocked AI provider pipeline
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_process_generation_with_mocked_pipeline(db: AsyncSession):
    """Full happy-path of process_generation using complete mocks."""
    import json as _json
    from app.ai_agent.providers import AIGenerationResult

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(tenant_id, user_id, config.id, "Build a blog", "Blog")

    good_json = _json.dumps({
        "files": [
            {"path": "python-backend/app/api/blog.py", "content": "router = APIRouter()"},
            {"path": "python-backend/app/services/blog_service.py", "content": "class BlogService: pass"},
        ]
    })
    mock_result = AIGenerationResult(
        success=True,
        generated_files={"python-backend/app/api/blog.py": "router = APIRouter()"},
        raw_response=good_json,
        tokens_used=1000,
        estimated_cost=0.005,
    )

    mock_provider = AsyncMock()
    mock_provider.generate_code = AsyncMock(return_value=mock_result)

    mock_sc = AsyncMock()
    mock_sc.get_default_branch = AsyncMock(return_value="main")
    mock_sc.create_branch = AsyncMock(return_value=True)
    from app.ai_agent.source_control import CommitResult, PullRequestResult
    mock_sc.commit_files = AsyncMock(return_value=CommitResult(success=True, commit_sha="abc123"))
    mock_sc.create_pull_request = AsyncMock(
        return_value=PullRequestResult(success=True, pr_number=5, pr_url="https://github.com/owner/repo/pull/5")
    )
    mock_sc.get_file_content = AsyncMock(return_value=None)
    mock_sc.trigger_workflow = AsyncMock(return_value=True)

    with (
        patch("app.ai_agent.ai_agent_service.create_ai_provider", return_value=mock_provider),
        patch("app.ai_agent.ai_agent_service.create_source_control_client", return_value=mock_sc),
        patch("app.ai_agent.ai_agent_service._decrypt", return_value="decrypted-value"),
    ):
        await svc.process_generation(gen.id)

    await db.refresh(gen)
    # Should end in BUILDING (CI triggered) or READY (no workflow configured)
    assert gen.status in (GenerationStatus.BUILDING, GenerationStatus.READY, GenerationStatus.CREATING_PR)
    assert gen.branch_name is not None
    assert gen.commit_sha == "abc123"


@pytest.mark.asyncio
async def test_process_generation_ai_failure_marks_failed(db: AsyncSession):
    """If the AI provider fails all retries, generation should be FAILED."""
    from app.ai_agent.providers import AIGenerationResult

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(tenant_id, user_id, config.id, "Build a blog", "Blog")

    mock_result = AIGenerationResult(success=False, error="Rate limit exceeded")
    mock_provider = AsyncMock()
    mock_provider.generate_code = AsyncMock(return_value=mock_result)

    mock_sc = AsyncMock()
    mock_sc.get_file_content = AsyncMock(return_value=None)

    with (
        patch("app.ai_agent.ai_agent_service.create_ai_provider", return_value=mock_provider),
        patch("app.ai_agent.ai_agent_service.create_source_control_client", return_value=mock_sc),
        patch("app.ai_agent.ai_agent_service._decrypt", return_value="decrypted-value"),
        patch("asyncio.sleep", new_callable=AsyncMock),  # speed up retries
    ):
        await svc.process_generation(gen.id)

    await db.refresh(gen)
    assert gen.status == GenerationStatus.FAILED
    assert "Rate limit exceeded" in (gen.error_message or "")


@pytest.mark.asyncio
async def test_process_generation_unknown_id_silently_exits(db: AsyncSession):
    """process_generation with a non-existent ID should return gracefully."""
    svc = _make_service(db)
    await svc.process_generation(uuid.uuid4())  # should not raise


# ═══════════════════════════════════════════════════════════════════════
# _resolve_provider — linked providers, overrides, legacy agents
# ═══════════════════════════════════════════════════════════════════════

def _make_provider(tenant_id, name="openai", model="gpt-4o", endpoint=None, key="enc-prov"):
    from app.domain.models.ai_agent import AIProviderConfiguration
    return AIProviderConfiguration(
        id=uuid.uuid4(), tenant_id=tenant_id, provider_name=name, display_name=name.title(),
        api_key_encrypted=key, model_name=model, endpoint=endpoint, is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_resolve_linked_provider_reads_current_provider_key(db: AsyncSession):
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    prov = _make_provider(tenant_id)
    config = _make_config(tenant_id, user_id)
    config.provider_id = prov.id
    config.ai_api_key_encrypted = ""
    config.ai_model = ""
    db.add_all([prov, config])
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(tenant_id, user_id, config.id, "x", "X")
    with patch("app.ai_agent.ai_agent_service._decrypt", side_effect=lambda v: f"dec:{v}"):
        name, key, model, endpoint = await svc._resolve_provider(config, gen)
    assert (name, key, model) == ("openai", "dec:enc-prov", "gpt-4o")

    # Rotating the key on the provider is picked up without touching the agent.
    prov.api_key_encrypted = "enc-rotated"
    await db.commit()
    with patch("app.ai_agent.ai_agent_service._decrypt", side_effect=lambda v: f"dec:{v}"):
        _, key, _, _ = await svc._resolve_provider(config, gen)
    assert key == "dec:enc-rotated"


@pytest.mark.asyncio
async def test_resolve_provider_override_uses_that_providers_own_key(db: AsyncSession):
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    openai_p = _make_provider(tenant_id, "openai", "gpt-4o", key="enc-openai")
    claude_p = _make_provider(tenant_id, "anthropic", "claude-sonnet-5-5", key="enc-claude")
    config = _make_config(tenant_id, user_id)
    config.provider_id = openai_p.id
    db.add_all([openai_p, claude_p, config])
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(
        tenant_id, user_id, config.id, "x", "X", provider_override=str(claude_p.id), model_override=None,
    )
    with patch("app.ai_agent.ai_agent_service._decrypt", side_effect=lambda v: f"dec:{v}"):
        name, key, model, _ = await svc._resolve_provider(config, gen)
    assert (name, key, model) == ("anthropic", "dec:enc-claude", "claude-sonnet-5-5")


@pytest.mark.asyncio
async def test_resolve_provider_override_without_saved_provider_fails_clearly(db: AsyncSession):
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(
        tenant_id, user_id, config.id, "x", "X", provider_override="anthropic",
    )
    with patch("app.ai_agent.ai_agent_service._decrypt", side_effect=lambda v: f"dec:{v}"):
        with pytest.raises(ValueError, match="No saved provider matches"):
            await svc._resolve_provider(config, gen)


@pytest.mark.asyncio
async def test_resolve_legacy_agent_keeps_working_and_passes_endpoint(db: AsyncSession):
    tenant_id, user_id = uuid.uuid4(), uuid.uuid4()
    config = _make_config(tenant_id, user_id)
    config.ai_provider = "ollama"
    config.ai_model = "llama3.2"
    config.azure_openai_endpoint = "http://gpu-box:11434"
    db.add(config)
    await db.commit()

    svc = _make_service(db)
    gen = await svc.create_generation(tenant_id, user_id, config.id, "x", "X")
    with patch("app.ai_agent.ai_agent_service._decrypt", side_effect=lambda v: f"dec:{v}"):
        name, _, model, endpoint = await svc._resolve_provider(config, gen)
    assert (name, model, endpoint) == ("ollama", "llama3.2", "http://gpu-box:11434")
