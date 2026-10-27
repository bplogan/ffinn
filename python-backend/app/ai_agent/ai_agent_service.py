"""
Main AI Agent orchestration service.
Coordinates: prompt optimization → AI provider → pattern enforcement
             → source control commit → PR creation → CI/CD trigger → progress WebSocket.
"""
from __future__ import annotations

import asyncio
import re
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from app.ai_agent.pattern_enforcement import PatternEnforcementService
from app.ai_agent.prompt_optimization import PromptOptimizationService
from app.ai_agent.providers import create_ai_provider, parse_generated_files
from app.ai_agent.source_control import create_source_control_client, GitHubClient
from app.core.config import settings
from app.core.security import decrypt_value
from app.domain.models.ai_agent import (
    AIAgentConfiguration,
    AIAgentGeneration,
    AIAgentProgressEvent,
    AIAgentQueueItem,
)

log = structlog.get_logger(__name__)

_REPO_ROOT = str(Path(__file__).resolve().parents[3])

# ── Generation status machine ──────────────────────────────────────────────────
class GenerationStatus:
    DRAFT = "Draft"
    QUEUED = "Queued"
    ANALYZING = "Analyzing"
    GENERATING = "Generating"
    VALIDATING = "Validating"
    AUTO_FIXING = "AutoFixing"
    COMMITTING = "Committing"
    CREATING_PR = "CreatingPr"
    BUILDING = "Building"
    STAGING = "Staging"
    READY = "Ready"
    RELEASING = "Releasing"
    RELEASED = "Released"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    REVERTED = "Reverted"


class AIAgentService:
    """Orchestrates AI code generation from prompt to deployed PR."""

    def __init__(
        self,
        db: AsyncSession,
        websocket_manager=None,  # optional: inject WebSocket hub
    ):
        self._db = db
        self._ws = websocket_manager
        self._pattern = PatternEnforcementService(repo_root=_REPO_ROOT)
        self._optimizer = PromptOptimizationService()

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    async def create_generation(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        config_id: uuid.UUID,
        prompt: str,
        feature_name: str,
        target_scope: str = "tenant",
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        scheduled_release: Optional[datetime] = None,
    ) -> AIAgentGeneration:
        """Create and enqueue a new generation request."""
        config = await self._get_config(config_id, tenant_id)
        if not config:
            raise ValueError("AI agent configuration not found or not accessible.")
        if not config.is_active:
            raise ValueError("AI agent configuration is not active.")

        generation = AIAgentGeneration(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            config_id=config_id,
            feature_name=feature_name,
            user_prompt=prompt,
            target_scope=target_scope if target_scope in ("host", "tenant") else "tenant",
            status=GenerationStatus.QUEUED,
            provider_override=provider_override,
            model_override=model_override,
            scheduled_release_at=scheduled_release,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self._db.add(generation)

        queue_item = AIAgentQueueItem(
            id=uuid.uuid4(),
            generation_id=generation.id,
            tenant_id=tenant_id,
            queued_at=datetime.now(timezone.utc),
            priority=0,
        )
        self._db.add(queue_item)
        await self._db.commit()
        await self._db.refresh(generation)

        log.info(
            "Generation queued",
            generation_id=str(generation.id),
            feature=feature_name,
            tenant_id=str(tenant_id),
        )
        return generation

    async def process_generation(self, generation_id: uuid.UUID) -> None:
        """Full pipeline: prompt → AI → enforce → commit → PR → CI/CD."""
        generation = await self._get_generation(generation_id)
        if not generation:
            log.error("Generation not found", id=str(generation_id))
            return

        config = await self._get_config(generation.config_id, generation.tenant_id)
        if not config:
            await self._fail(generation, "Configuration not found.")
            return

        try:
            # 1. Analyzing
            await self._set_status(generation, GenerationStatus.ANALYZING)
            await self._emit(generation, "Analyzing your feature request…")

            # 2. Optimize prompt
            optimization = self._optimizer.optimize(generation.user_prompt)
            optimized_prompt = optimization.optimized_prompt
            await self._emit(generation, "Prompt optimized — calling AI provider…")

            # 3. Build system prompt with pattern enforcement rules
            existing_context, context_fetched, bounded_cache = await self._fetch_existing_context(config)
            system_prompt = self._pattern.get_system_prompt(
                getattr(generation, "target_scope", None) or "tenant"
            )

            # 4. Generating
            await self._set_status(generation, GenerationStatus.GENERATING)

            provider_name, ai_key, deployment_name, endpoint = await self._resolve_provider(
                config, generation
            )
            provider = create_ai_provider(
                provider_name=provider_name,
                api_key=ai_key,
                model=deployment_name,
                endpoint=endpoint or None,
            )

            full_prompt = optimized_prompt
            if existing_context:
                full_prompt += f"\n\n## Existing Framework Files (for reference/merging)\n{existing_context}"

            max_retries = 3
            result = None
            retry_reason = "architecture-violation"  # updated before each retry continue
            for attempt in range(1, max_retries + 1):
                await self._emit(generation, f"AI generation attempt {attempt}/{max_retries}…")
                result = await provider.generate_code(
                    system_prompt=(
                        system_prompt
                        if attempt == 1
                        else self._pattern.get_retry_system_prompt(
                            reason=retry_reason,
                            target_scope=getattr(generation, "target_scope", None) or "tenant",
                        )
                    ),
                    user_prompt=full_prompt,
                )
                if not result.success:
                    if attempt == max_retries:
                        await self._fail(generation, f"AI provider failed: {result.error}")
                        return
                    await asyncio.sleep(2 ** attempt)
                    continue

                # 5. Validating
                await self._set_status(generation, GenerationStatus.VALIDATING)
                files = parse_generated_files(result.raw_response)

                # Guard: if the AI returned content but we couldn't parse any files,
                # the response doesn't follow the expected JSON/markdown format.
                # Treat it as a format failure so the retry prompt specifically reminds
                # the AI of the required JSON output structure (not "architecture violations").
                if not files:
                    retry_reason = "format-failure"
                    await self._emit(
                        generation,
                        f"AI response could not be parsed into files (attempt {attempt}/{max_retries}). "
                        "Ensure the response is JSON: {\"files\": [{\"path\": \"...\", \"content\": \"...\"}]}",
                    )
                    if attempt == max_retries:
                        await self._fail(generation, "AI response contained no parseable files after all retries.")
                        return
                    await asyncio.sleep(2 ** attempt)
                    continue

                await self._emit(generation, f"Validating {len(files)} generated files…")

                # Strip protected files (modifies files dict in-place, returns count)
                files_before = set(files.keys())
                self._pattern.strip_protected_files(files)
                removed = files_before - set(files.keys())
                if removed:
                    await self._emit(generation, f"Protected files removed: {', '.join(removed)}")

                # Auto-fix common AI mistakes (modifies files in-place)
                await self._set_status(generation, GenerationStatus.AUTO_FIXING)
                fix_report = self._pattern.auto_fix_generated_code(files)
                if fix_report.total_files_fixed > 0:
                    await self._emit(generation, fix_report.get_summary())

                # Merge bounded core files — pass the context flag so that
                # bounded files are stripped when context fetch failed (unsafe to trust AI)
                merged_files = await self._merge_bounded_files(
                    files, generation.feature_name, bounded_cache, context_fetched,
                    getattr(generation, "target_scope", None) or "tenant",
                )

                # Auto-repair fixable validation issues (lazy loaders, selectinload, Pydantic v2, etc.)
                errors, repair_report = self._pattern.repair_until_valid(merged_files)
                if repair_report.total_files_fixed > 0:
                    await self._emit(
                        generation,
                        f"Auto-repaired validation issues:\n{repair_report.get_summary()}",
                    )

                # Only retry the AI when issues remain after auto-repair
                if errors:
                    retry_reason = "architecture-violation"
                    await self._emit(
                        generation,
                        f"Unfixable validation errors (attempt {attempt}): {'; '.join(errors[:3])}. Retrying AI…",
                    )
                    full_prompt += (
                        f"\n\n## Retry Feedback (Attempt {attempt})\n"
                        + "\n".join(f"- {e}" for e in errors)
                    )
                    if attempt == max_retries:
                        await self._fail(generation, f"Validation failed after {max_retries} attempts: {errors[0]}")
                        return
                    await asyncio.sleep(1)
                    continue

                # Validation passed — update result with finalised files
                result.generated_files = merged_files
                break

            if not result or not result.success:
                return

            # 6. Persist generated files
            await self._update_generation(
                generation,
                generated_files=result.generated_files,
                tokens_used=result.tokens_used,
                estimated_cost=float(result.estimated_cost) if result.estimated_cost else None,
                validation_errors=[],
                status=GenerationStatus.COMMITTING,
            )
            await self._emit(generation, f"Committing {len(result.generated_files)} files…")

            # 7. Source control — commit to feature branch
            sc_token = _decrypt(config.source_control_token_encrypted)
            sc = create_source_control_client(
                provider=config.source_control_type or "github",
                token=sc_token,
                repo_url=config.repository_url,
            )

            _safe = re.sub(r"[^a-z0-9\-]", "-", generation.feature_name.lower())
            _safe = re.sub(r"-{2,}", "-", _safe).strip("-")[:50]
            branch_prefix = (config.default_branch_prefix or "ai-feature/").strip().rstrip("/")
            branch_name = f"{branch_prefix}/{_safe}-{generation.id.hex[:8]}"
            default_branch = await sc.get_default_branch()

            await sc.create_branch(branch_name, from_branch=default_branch)

            # Strip control characters from feature_name to prevent git trailer injection
            _safe_feature = re.sub(r"[\r\n\x00-\x1f\x7f]", "", generation.feature_name).strip()
            commit_msg = (
                f"feat: {_safe_feature}\n\n"
                f"AI-generated feature — generation ID {generation.id}"
            )
            commit_result = await sc.commit_files(branch_name, result.generated_files, commit_msg)
            if not commit_result.success:
                await self._fail(generation, f"Commit failed: {commit_result.error}")
                return

            await self._update_generation(
                generation,
                branch_name=branch_name,
                commit_sha=commit_result.commit_sha,
                status=GenerationStatus.CREATING_PR,
            )

            # 8. Create PR
            await self._emit(generation, "Creating pull request…")
            pr_result = await sc.create_pull_request(
                title=f"[AI] {generation.feature_name}",
                body=self._build_pr_body(generation, result),
                head=branch_name,
                base=default_branch,
                draft=True,
            )
            if pr_result.success:
                post_pr_status = GenerationStatus.BUILDING
                if config.staging_workflow_id:
                    triggered = await self._trigger_staging_workflow(
                        sc, config.staging_workflow_id, branch_name, generation.id, default_branch
                    )
                    if not triggered:
                        await self._emit(
                            generation,
                            "Warning: staging workflow dispatch failed — review PR manually.",
                        )
                        post_pr_status = GenerationStatus.READY
                else:
                    post_pr_status = GenerationStatus.READY

                await self._update_generation(
                    generation,
                    pr_number=pr_result.pr_number,
                    pr_url=pr_result.pr_url,
                    pipeline_url=None,
                    status=post_pr_status,
                )
                if post_pr_status == GenerationStatus.READY:
                    await self._emit(generation, f"PR #{pr_result.pr_number} created — ready for review.")
                else:
                    await self._emit(generation, f"PR #{pr_result.pr_number} created — triggering CI…")
            else:
                await self._update_generation(generation, status=GenerationStatus.READY)
                await self._emit(generation, "Committed — no PR created (check repo permissions).")
                return

            await self._emit(generation, "Generation complete — PR ready for review!")
            log.info(
                "Generation complete",
                generation_id=str(generation.id),
                pr_number=pr_result.pr_number if pr_result.success else None,
                files=len(result.generated_files),
                cost=result.estimated_cost,
            )

        except Exception as exc:
            tb = traceback.format_exc()
            log.error("Unhandled generation error", generation_id=str(generation_id), error=str(exc), tb=tb)
            msg = str(exc)
            if "404" in msg and "api.github.com/repos" in msg:
                repo = config.repository_url if config else "unknown"
                msg = (
                    f"GitHub repository not found ({repo}). "
                    "Check the repository URL on your agent — it may be misspelled, private without access, or deleted."
                )
            await self._fail(generation, f"Unexpected error: {msg}" if "GitHub repository" not in msg else msg)

    async def release_generation(
        self,
        generation_id: uuid.UUID,
        tenant_id: uuid.UUID,
        release_workflow_id: Optional[str] = None,
    ) -> None:
        """Merge the PR to main and trigger the production deployment workflow."""
        generation = await self._get_generation(generation_id)
        if not generation or generation.tenant_id != tenant_id:
            raise ValueError("Generation not found.")
        if generation.status not in (GenerationStatus.READY, GenerationStatus.STAGING):
            raise ValueError(f"Cannot release generation in status {generation.status}.")

        config = await self._get_config(generation.config_id, tenant_id)
        if not config:
            raise ValueError("Configuration not found.")

        if config.require_staging_verification and config.staging_workflow_id:
            if not generation.staging_url and not generation.staging_deployed_at:
                raise ValueError(
                    "Staging verification required — deploy to staging and verify before releasing."
                )

        sc_token = _decrypt(config.source_control_token_encrypted)
        sc = create_source_control_client(
            config.source_control_type or "github", sc_token, config.repository_url
        )
        default_branch = await sc.get_default_branch()

        workflow = release_workflow_id or config.release_workflow_id
        if not workflow:
            raise ValueError("No release workflow configured.")

        merge_sha: Optional[str] = None
        if generation.pr_number:
            await self._emit(generation, f"Merging PR #{generation.pr_number}…")
            merge_result = await sc.merge_pull_request(generation.pr_number)
            if not merge_result.success:
                raise ValueError(f"Failed to merge PR #{generation.pr_number}: {merge_result.error}")
            merge_sha = merge_result.merge_commit_sha
            if merge_result.already_merged:
                await self._emit(generation, f"PR #{generation.pr_number} was already merged.")
            else:
                await self._emit(generation, f"PR #{generation.pr_number} merged to {default_branch}.")

        await self._update_generation(
            generation,
            status=GenerationStatus.RELEASING,
            commit_sha=merge_sha or generation.commit_sha,
        )

        triggered = await sc.trigger_workflow(
            workflow_id=workflow,
            inputs={
                "branch": default_branch,
                "pr_number": str(generation.pr_number or ""),
                "generation_id": str(generation.id),
            },
            ref=default_branch,
        )
        if not triggered:
            await self._update_generation(generation, status=GenerationStatus.READY)
            raise ValueError("Failed to trigger production release workflow.")

        await self._emit(generation, "Production release workflow started…")

    async def deploy_staging_generation(
        self, generation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        """Manually trigger the staging CI/CD workflow for a generation."""
        generation = await self._get_generation(generation_id)
        if not generation or generation.tenant_id != tenant_id:
            raise ValueError("Generation not found.")
        if not generation.branch_name:
            raise ValueError("Generation has no feature branch to deploy.")

        config = await self._get_config(generation.config_id, tenant_id)
        if not config or not config.staging_workflow_id:
            raise ValueError("No staging workflow configured on this agent.")

        sc_token = _decrypt(config.source_control_token_encrypted)
        sc = create_source_control_client(
            config.source_control_type or "github", sc_token, config.repository_url
        )
        default_branch = await sc.get_default_branch()

        triggered = await self._trigger_staging_workflow(
            sc,
            config.staging_workflow_id,
            generation.branch_name,
            generation.id,
            default_branch,
        )
        if not triggered:
            raise ValueError("Failed to trigger staging workflow.")

        await self._update_generation(generation, status=GenerationStatus.BUILDING)
        await self._emit(generation, "Staging deployment triggered…")

    async def revert_generation(
        self, generation_id: uuid.UUID, tenant_id: uuid.UUID, reason: Optional[str] = None
    ) -> None:
        """Revert a generation: close open PRs, delete branch, or open a revert PR if merged."""
        generation = await self._get_generation(generation_id)
        if not generation or generation.tenant_id != tenant_id:
            raise ValueError("Generation not found.")

        config = await self._get_config(generation.config_id, tenant_id)
        sc: Optional[GitHubClient] = None
        if config and config.repository_url and config.source_control_token_encrypted:
            sc_token = _decrypt(config.source_control_token_encrypted)
            sc = create_source_control_client(
                config.source_control_type or "github", sc_token, config.repository_url
            )

        if sc and generation.status == GenerationStatus.RELEASED and generation.pr_number:
            await self._emit(generation, f"Creating revert PR for #{generation.pr_number}…")
            revert_pr = await sc.revert_pull_request(generation.pr_number)
            if revert_pr.success:
                await self._emit(
                    generation,
                    f"Revert PR #{revert_pr.pr_number} created — merge it to roll back production.",
                )
            else:
                await self._emit(generation, f"Could not auto-revert PR: {revert_pr.error}")
        elif sc and generation.pr_number and generation.status != GenerationStatus.RELEASED:
            await sc.close_pull_request(generation.pr_number)

        staging_was_deployed = bool(
            generation.staging_deployed_at
            or generation.staging_url
            or generation.status in (GenerationStatus.STAGING, GenerationStatus.BUILDING)
        )
        if (
            sc
            and config
            and config.staging_workflow_id
            and staging_was_deployed
            and generation.status != GenerationStatus.RELEASED
        ):
            default_branch = await sc.get_default_branch()
            await self._emit(generation, f"Restoring staging from {default_branch}…")
            restored = await self._trigger_staging_workflow(
                sc,
                config.staging_workflow_id,
                default_branch,
                generation.id,
                default_branch,
            )
            if restored:
                await self._emit(generation, "Staging restore workflow started.")
            else:
                await self._emit(
                    generation,
                    "Warning: could not trigger staging restore — reset staging manually.",
                )

        if sc and generation.branch_name:
            await sc.delete_branch(generation.branch_name)

        await self._update_generation(
            generation,
            status=GenerationStatus.REVERTED,
            reverted_at=datetime.now(timezone.utc),
            revert_reason=(reason or "")[:500] or None,
            staging_url=None,
            staging_frontend_url=None,
            staging_deployed_at=None,
        )
        await self._emit(generation, "Generation reverted.")

    async def cancel_generation(
        self, generation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        generation = await self._get_generation(generation_id)
        if not generation or generation.tenant_id != tenant_id:
            raise ValueError("Generation not found.")
        if generation.status in (GenerationStatus.RELEASED, GenerationStatus.REVERTED):
            raise ValueError("Cannot cancel an already released or reverted generation.")
        await self._update_generation(generation, status=GenerationStatus.CANCELLED)

    async def handle_build_callback(
        self,
        generation_id: uuid.UUID,
        success: bool,
        build_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        generation = await self._get_generation(generation_id)
        if not generation:
            return
        if generation.status == GenerationStatus.REVERTED:
            return
        error = (error or "")[:500]
        if success:
            await self._update_generation(
                generation,
                status=GenerationStatus.STAGING,
                pipeline_url=build_url,
                pipeline_status="success",
            )
            await self._emit(generation, "✅ Build passed — staging preview ready.")
        else:
            await self._update_generation(
                generation,
                status=GenerationStatus.READY,
                pipeline_status="failed",
                error_message=error,
            )
            await self._emit(generation, f"❌ Build failed: {error}")

    async def handle_deploy_callback(
        self,
        generation_id: uuid.UUID,
        success: bool,
        staging_url: Optional[str] = None,
        staging_frontend_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        generation = await self._get_generation(generation_id)
        if not generation:
            return
        if generation.status == GenerationStatus.REVERTED:
            return
        error = (error or "")[:500]
        if success:
            await self._update_generation(
                generation,
                status=GenerationStatus.STAGING,
                staging_url=staging_url,
                staging_frontend_url=staging_frontend_url,
                staging_deployed_at=datetime.now(timezone.utc),
                staging_build_status="success",
                error_message=None,
            )
            preview = staging_frontend_url or staging_url
            await self._emit(generation, f"✅ Deployed to staging: {preview}")
        else:
            await self._update_generation(
                generation,
                staging_build_status="failed",
                error_message=(error or "Staging deploy failed")[:500],
            )
            await self._emit(generation, f"❌ Staging deploy failed: {error}")

    async def handle_release_callback(
        self,
        generation_id: uuid.UUID,
        success: bool,
        production_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        generation = await self._get_generation(generation_id)
        if not generation:
            return
        error = (error or "")[:500]
        if success:
            await self._update_generation(
                generation,
                status=GenerationStatus.RELEASED,
                released_at=datetime.now(timezone.utc),
                pipeline_status="success",
                pipeline_url=production_url,
            )
            await self._emit(generation, f"✅ Released to production{f': {production_url}' if production_url else ''}")
        else:
            await self._update_generation(
                generation,
                status=GenerationStatus.READY,
                pipeline_status="failed",
                error_message=error or "Production release failed",
            )
            await self._emit(generation, f"❌ Production release failed: {error}")

    async def handle_pr_validation_callback(
        self,
        generation_id: uuid.UUID,
        approved: bool,
        reviewer_notes: Optional[str] = None,
    ) -> None:
        generation = await self._get_generation(generation_id)
        if not generation:
            return
        reviewer_notes = (reviewer_notes or "")[:500]
        if approved:
            await self._update_generation(
                generation, status=GenerationStatus.READY, code_review_status="Approved"
            )
            await self._emit(generation, "✅ Code review approved — ready to release.")
        else:
            await self._update_generation(
                generation, status=GenerationStatus.READY, code_review_status="ChangesRequested"
            )
            await self._emit(generation, f"❌ Code review failed: {reviewer_notes}")

    async def get_generation(
        self, generation_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Optional[AIAgentGeneration]:
        result = await self._db.execute(
            select(AIAgentGeneration).where(
                AIAgentGeneration.id == generation_id,
                AIAgentGeneration.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_generations(
        self,
        tenant_id: uuid.UUID,
        config_id: Optional[uuid.UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[AIAgentGeneration], int]:
        from sqlalchemy import func

        q = select(AIAgentGeneration).where(AIAgentGeneration.tenant_id == tenant_id)
        if config_id:
            q = q.where(AIAgentGeneration.config_id == config_id)
        count_q = select(func.count()).select_from(q.subquery())
        total = (await self._db.execute(count_q)).scalar() or 0
        items = (
            await self._db.execute(
                q.order_by(AIAgentGeneration.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).scalars().all()
        return list(items), total

    # ─────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _get_config(
        self, config_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Optional[AIAgentConfiguration]:
        result = await self._db.execute(
            select(AIAgentConfiguration).where(
                AIAgentConfiguration.id == config_id,
                AIAgentConfiguration.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def _resolve_provider(self, config: AIAgentConfiguration, generation: AIAgentGeneration):
        """Work out (provider, api_key, model/deployment, endpoint) for one generation.

        Precedence: the generation's provider override, then the provider the agent is
        linked to, then the agent's own legacy copy of the credentials.
        """
        from app.ai_agent.azure_config import (
            azure_agent_deployment_name,
            azure_deployment_name as provider_deployment_name,
            is_azure_provider,
        )
        from app.ai_agent.providers import canonical_provider

        override = (generation.provider_override or "").strip()
        model_override = (generation.model_override or "").strip()
        linked = None
        from_override = False

        if override:
            linked = await self._load_provider_by_ref(config.tenant_id, override)
            if linked is None and canonical_provider(override) != canonical_provider(config.ai_provider):
                raise ValueError(
                    f"No saved provider matches '{override}'. Add it under AI Providers or "
                    "pick one of your saved providers."
                )
            from_override = linked is not None
        if linked is None and not override and getattr(config, "provider_id", None):
            linked = await self._load_provider_by_ref(config.tenant_id, str(config.provider_id))
            if linked is None:
                raise ValueError(
                    "The AI provider this agent was linked to no longer exists. "
                    "Edit the agent and choose another provider."
                )

        if linked is not None:
            name = linked.provider_name
            key = _decrypt(linked.api_key_encrypted)
            endpoint = linked.endpoint or linked.endpoint_url or ""
            if is_azure_provider(name):
                agent_dep = "" if from_override else (config.azure_deployment_name or "").strip()
                model = model_override or agent_dep or provider_deployment_name(linked)
            else:
                agent_model = "" if from_override else (config.ai_model or "").strip()
                model = model_override or agent_model or (linked.model_name or "").strip()
            if not model:
                raise ValueError(
                    f"No model is set for provider '{linked.display_name or name}'. Edit the provider and choose one."
                )
            return name, key, model, endpoint

        # Legacy agent: credentials were copied onto the agent when it was created.
        name = config.ai_provider
        key = _decrypt(config.ai_api_key_encrypted)
        provider_cfg = await self._find_tenant_provider_config(config.tenant_id, name)
        if provider_cfg and not key.strip():
            key = _decrypt(provider_cfg.api_key_encrypted)
        endpoint = config.azure_openai_endpoint
        if provider_cfg and not (endpoint or "").strip():
            endpoint = provider_cfg.endpoint or provider_cfg.endpoint_url
        if is_azure_provider(name):
            model = azure_agent_deployment_name(config, model_override=model_override, provider_cfg=provider_cfg)
            # Persist corrected Azure routing id on the agent when we inferred it.
            if provider_cfg and not (config.azure_deployment_name or "").strip():
                resolved = provider_deployment_name(provider_cfg)
                if resolved:
                    config.azure_deployment_name = resolved
                    if (config.ai_model or "").strip() != resolved:
                        config.ai_model = resolved
                    await self._db.commit()
        else:
            model = model_override or config.ai_model
        return name, key, model, endpoint or ""

    async def _load_provider_by_ref(self, tenant_id, ref: str):
        """Find a saved provider by id, or by provider name, within the tenant. No fallback."""
        from app.ai_agent.providers import canonical_provider
        from app.domain.models.ai_agent import AIProviderConfiguration

        stmt = select(AIProviderConfiguration)
        stmt = stmt.where(
            AIProviderConfiguration.tenant_id == tenant_id
            if tenant_id is not None
            else AIProviderConfiguration.tenant_id.is_(None)
        )
        rows = list((await self._db.execute(stmt.order_by(AIProviderConfiguration.created_at.desc()))).scalars())
        try:
            wanted_id = uuid.UUID(ref)
        except ValueError:
            wanted_id = None
        if wanted_id is not None:
            return next((r for r in rows if r.id == wanted_id), None)
        return next((r for r in rows if canonical_provider(r.provider_name) == canonical_provider(ref)), None)

    async def _find_tenant_provider_config(
        self,
        tenant_id: Optional[uuid.UUID],
        provider_name: str,
    ):
        from app.domain.models.ai_agent import AIProviderConfiguration

        stmt = select(AIProviderConfiguration).order_by(
            AIProviderConfiguration.updated_at.desc()
        )
        if tenant_id is not None:
            stmt = stmt.where(AIProviderConfiguration.tenant_id == tenant_id)
        else:
            stmt = stmt.where(AIProviderConfiguration.tenant_id.is_(None))

        result = await self._db.execute(stmt)
        configs = list(result.scalars().all())
        if not configs:
            return None

        target = (provider_name or "").lower().replace("_", "-")
        for cfg in configs:
            pname = (cfg.provider_name or "").lower().replace("_", "-")
            if pname == target:
                return cfg
        return None

    async def _get_generation(
        self,
        generation_id: uuid.UUID,
        tenant_id: Optional[uuid.UUID] = None,
    ) -> Optional[AIAgentGeneration]:
        stmt = select(AIAgentGeneration).where(AIAgentGeneration.id == generation_id)
        if tenant_id is not None:
            stmt = stmt.where(AIAgentGeneration.tenant_id == tenant_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _set_status(self, generation: AIAgentGeneration, status: str) -> None:
        generation.status = status
        generation.updated_at = datetime.now(timezone.utc)
        await self._db.commit()

    async def _update_generation(self, generation: AIAgentGeneration, **kwargs) -> None:
        for key, val in kwargs.items():
            if hasattr(generation, key):
                setattr(generation, key, val)
        generation.updated_at = datetime.now(timezone.utc)
        await self._db.commit()

    async def _fail(self, generation: AIAgentGeneration, error: str) -> None:
        # Truncate to prevent storing unbounded text (e.g. long AI/HTTP error bodies)
        # and to avoid accidentally persisting sensitive details such as endpoint URLs.
        error = error[:500]
        generation.status = GenerationStatus.FAILED
        generation.error_message = error
        generation.updated_at = datetime.now(timezone.utc)
        await self._db.commit()
        await self._emit(generation, f"Generation failed: {error}")
        log.error("Generation failed", generation_id=str(generation.id), error=error)

    async def _emit(self, generation: AIAgentGeneration, message: str) -> None:
        """Persist a progress event and push to WebSocket if manager available."""
        event = AIAgentProgressEvent(
            id=uuid.uuid4(),
            generation_id=generation.id,
            event_type="progress",
            message=message,
            step=generation.status,
        )
        self._db.add(event)
        try:
            await self._db.commit()
        except Exception:
            pass  # non-fatal

        if self._ws:
            try:
                await self._ws.broadcast_to_tenant(
                    str(generation.tenant_id),
                    {
                        "type": "ai_agent_progress",
                        "generationId": str(generation.id),
                        "status": generation.status,
                        "message": message,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception:
                pass  # websocket errors are non-fatal

    async def _fetch_existing_context(
        self, config: AIAgentConfiguration
    ) -> tuple[str, bool, dict[str, str]]:
        """Load bounded core files from disk and optionally from source control.

        Returns:
            (context_str, remote_ok, bounded_cache): bounded_cache always includes
            files found on the local repo disk; remote_ok is True when GitHub fetch succeeded.
        """
        from app.ai_agent.pattern_enforcement import BOUNDED_CORE_UPDATE_FILES

        bounded_cache = self._pattern.get_existing_file_context(list(BOUNDED_CORE_UPDATE_FILES))
        remote_ok = False

        if config.repository_url and config.source_control_token_encrypted:
            try:
                sc_token = _decrypt(config.source_control_token_encrypted)
                sc = create_source_control_client(
                    config.source_control_type or "github", sc_token, config.repository_url
                )
                for path in BOUNDED_CORE_UPDATE_FILES:
                    content = await sc.get_file_content(path)
                    if content:
                        bounded_cache[path] = content
                self._pattern.supplement_existing_file_cache(bounded_cache)
                remote_ok = True
            except Exception as exc:
                log.warning("Could not fetch existing file context from remote", error=str(exc))

        context_parts = [
            f"### {path}\n```\n{content}\n```"
            for path, content in bounded_cache.items()
        ]
        context_str = "\n\n".join(context_parts) if context_parts else ""
        return context_str, remote_ok, bounded_cache

    async def _merge_bounded_files(
        self,
        files: dict[str, str],
        feature_name: str,
        bounded_cache: dict[str, str],
        context_fetched: bool = True,
        target_scope: str = "tenant",
    ) -> dict[str, str]:
        """Normalize feature paths and deterministically merge bounded framework files."""
        from app.ai_agent.pattern_enforcement import BOUNDED_CORE_UPDATE_FILES

        self._pattern.normalize_feature_paths(files)

        bounded_in_output = [p for p in files if p.replace("\\", "/") in BOUNDED_CORE_UPDATE_FILES]
        for p in bounded_in_output:
            del files[p]

        if not bounded_cache:
            if bounded_in_output:
                log.warning(
                    "No bounded file context available — skipped router/sidebar/permission merges",
                    stripped=bounded_in_output,
                )
            return files

        self._pattern.supplement_existing_file_cache(bounded_cache)
        merged = self._pattern.apply_bounded_merges(
            files, bounded_cache, feature_name, target_scope=target_scope
        )
        log.info(
            "Applied deterministic bounded file merges",
            feature=feature_name,
            bounded_files=[p for p in merged if p.replace("\\", "/") in BOUNDED_CORE_UPDATE_FILES],
        )
        return merged

    @staticmethod
    async def _trigger_staging_workflow(
        sc: GitHubClient,
        workflow_id: str,
        branch_name: str,
        generation_id: uuid.UUID,
        default_branch: str,
    ) -> bool:
        return await sc.trigger_workflow(
            workflow_id=workflow_id,
            inputs={
                "branch": branch_name,
                "generation_id": str(generation_id),
            },
            ref=default_branch,
        )

    def _build_pr_body(self, generation: AIAgentGeneration, result) -> str:
        files_list = "\n".join(f"- `{p}`" for p in sorted(result.generated_files.keys()))
        cost_str = f"${result.estimated_cost:.4f}" if result.estimated_cost else "N/A"
        return f"""## AI-Generated Feature: {generation.feature_name}

**Generation ID:** `{generation.id}`
**Tokens used:** {result.tokens_used or 'N/A'}
**Estimated cost:** {cost_str}

### Generated Files
{files_list}

---
*This PR was automatically generated by [ffinn AI Agent](https://github.com/ffinnframework/ffinn).
Please review carefully before merging — pattern enforcement rules were applied.*
"""


def _decrypt(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return decrypt_value(value, settings.encryption_key)
    except Exception as e:
        log.error(
            "Failed to decrypt stored credential — ENCRYPTION_KEY mismatch or corrupted value",
            error=str(e),
        )
        raise ValueError(
            "Decryption failed. Verify ENCRYPTION_KEY matches the key used when the credential was saved."
        ) from e
