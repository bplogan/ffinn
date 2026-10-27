"""
Prompt optimization service — pre-processes user prompts to improve AI generation quality.
Mirrors the .NET PromptOptimizationService.cs behavior.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass
class OptimizationResult:
    original_prompt: str
    optimized_prompt: str
    applied: list[str] = field(default_factory=list)
    strategy: str = "rules"


class PromptOptimizationService:
    """
    Applies rule-based transformations to user prompts before sending to the AI.
    Goal: improve generation quality and reduce architectural violations on first attempt.
    """

    def optimize(self, prompt: str) -> OptimizationResult:
        if not prompt or not prompt.strip():
            return OptimizationResult(prompt, prompt, [], "none")

        optimized = prompt
        applied: list[str] = []

        # 1. Disambiguate external data fetching
        if re.search(r'(get|grab|fetch|pull).{0,80}?(from|off).{0,80}?(internet|web|api|online)', optimized, re.IGNORECASE):
            optimized = re.sub(
                r'(get|grab|fetch|pull).{0,80}?(from|off).{0,80}?(internet|web|api|online)',
                'use hardcoded sample data',
                optimized, flags=re.IGNORECASE,
            )
            applied.append("Replaced external data fetching with sample data")

        # 2. Add quantity constraints for seed data
        if not re.search(r'\b(one|single|only|just)\b', optimized, re.IGNORECASE):
            if re.search(r'\b(player|user|customer|product|item)s?\b', optimized, re.IGNORECASE):
                optimized += "\n\nFor initial seed data: Include sample data for ONE entity only."
                applied.append("Added quantity constraints for seed data")

        # 3. Add data seeder guidance
        if re.search(r'\b(database|seed|initial.*data|sample.*data)\b', optimized, re.IGNORECASE):
            if "data_seeder" not in optimized.lower():
                optimized += "\n\nTechnical: Add seed data to python-backend/app/data_seeder.py"
                applied.append("Added DataSeeder location guidance")

        # 4. Add repository/service pattern for CRUD
        if re.search(r'\b(crud|create|add|edit|update|delete|remove)\b', optimized, re.IGNORECASE):
            if "AsyncSession" not in optimized and "service" not in optimized.lower():
                optimized += "\n\nArchitecture: Use AsyncSession in services (app/services/), not in routes directly."
                applied.append("Added service pattern guidance")

        # 5. Add toast guidance for notifications
        if re.search(r'\b(notification|message|alert|toast)\b', optimized, re.IGNORECASE):
            if "react-hot-toast" not in optimized:
                optimized += "\n\nUI: Use react-hot-toast for notifications and a confirmation dialog for destructive actions."
                applied.append("Added framework service guidance")

        # 6. Add MVP focus for complex requests — check ORIGINAL length, not post-optimization
        if len(prompt) > 500 or len(re.findall(r'\band\b', prompt, re.IGNORECASE)) > 5:
            if not re.search(r'\b(mvp|minimum|simple|basic)\b', optimized, re.IGNORECASE):
                optimized = "Start with MVP/core features:\n\n" + optimized
                applied.append("Added MVP focus for complex request")

        # 7. Clarify absolute scope claims
        if re.search(r'\b(everything|all\s+(?:the\s+)?data|complete\s+system)\b', optimized, re.IGNORECASE):
            optimized = re.sub(
                r'\b(everything|all\s+(?:the\s+)?data|complete\s+system)\b',
                'core features with sample data',
                optimized, flags=re.IGNORECASE,
            )
            applied.append("Clarified scope from 'everything' to 'core features'")

        # 8. Default CRUD for feature pages
        if re.search(r'\b(page|feature|dashboard|app|module|screen|view)\b', optimized, re.IGNORECASE):
            if not re.search(r'\b(read[- ]?only|view[- ]?only|display[- ]?only|no\s+edit|no\s+crud)\b', optimized, re.IGNORECASE):
                if not re.search(r'\b(crud|add/edit/delete|create.{0,80}update.{0,80}delete)\b', optimized, re.IGNORECASE):
                    optimized += "\n\nCRUD: Include full add/edit/delete functionality with forms, validation, and confirmation dialogs."
                    applied.append("Added default CRUD requirement for feature page")

        # 9. Next.js frontend pattern reinforcement
        if re.search(r'\b(page|feature|dashboard|app|module|screen|view|component|ui|frontend|list|table|form)\b', optimized, re.IGNORECASE):
            if "'use client'" not in optimized and "@/lib/api" not in optimized:
                optimized += (
                    "\n\nNext.js rules: Feature pages go under nextjs-frontend/src/app/app/features/{slug}/ "
                    "(URL /app/features/{slug} inside the authenticated shell). "
                    "Add 'use client' when using hooks or events. "
                    "Use get/post from `@/lib/api` with @tanstack/react-query for data fetching. "
                    "Use react-hot-toast for notifications — NEVER window.alert() or window.confirm(). "
                    "Do NOT output router.py, Sidebar.tsx, permissions.py, or models/__init__.py — the pipeline merges those."
                )
                applied.append("Added Next.js pattern requirements")

        # 10. Tailwind dark mode compliance
        if re.search(r'\b(page|feature|dashboard|app|component|ui|frontend|screen|view|list|table|form|card)\b', optimized, re.IGNORECASE):
            if not re.search(r'\bdark:', optimized, re.IGNORECASE):
                optimized += (
                    "\n\nStyling: This app uses Tailwind darkMode:'class'. "
                    "EVERY bg/text/border class MUST have its dark: pair. "
                    "Examples: 'bg-white dark:bg-gray-800', 'text-gray-900 dark:text-white', "
                    "'border-gray-200 dark:border-gray-700'."
                )
                applied.append("Added Tailwind dark mode compliance")

        # 11. Python backend specifics
        if re.search(r'\b(api|endpoint|route|backend|server)\b', optimized, re.IGNORECASE):
            if "FastAPI" not in optimized and "router" not in optimized.lower():
                optimized += (
                    "\n\nPython backend: Use FastAPI APIRouter, Pydantic v2 schemas, "
                    "SQLAlchemy 2.0 async with Mapped[] syntax. "
                    "Route files in app/api/, services in app/services/, models in app/domain/models/."
                )
                applied.append("Added Python backend specifics")

        return OptimizationResult(
            original_prompt=prompt,
            optimized_prompt=optimized,
            applied=applied,
            strategy="rules",
        )
