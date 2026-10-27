"""
PatternEnforcementService — protects framework files and validates AI-generated code.

Ensures that:
1. Core framework files can NEVER be overwritten by AI-generated code
2. Bounded files (routes, layout, permissions) are merged deterministically
3. All generated code follows architectural rules
4. Common mistakes are auto-fixed before committing
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


# ── Protected files — AI may NEVER overwrite these ───────────────────────────
PROTECTED_FILE_NAMES: frozenset[str] = frozenset([
    # Python backend core
    "database.py",
    "main.py",
    "config.py",
    "security.py",
    "dependencies.py",
    "permissions.py",
    # Python backend infrastructure
    "email.py",
    "storage.py",
    "websocket_manager.py",
    "background_tasks.py",
    # Next.js / frontend root config
    "next.config.ts",
    "jest.config.ts",
    "postcss.config.js",
    "postcss.config.mjs",
    "tailwind.config.js",
    "tailwind.config.ts",
    "middleware.ts",
    "package.json",
    "package-lock.json",
])

# Paths (normalized to forward-slash) that AI can NEVER create/overwrite
PROTECTED_PATH_PREFIXES: tuple[str, ...] = (
    "python-backend/app/core/",
    "python-backend/app/infrastructure/",
    "python-backend/app/main.py",
    "python-backend/alembic/",
    "nextjs-frontend/src/components/",
    "nextjs-frontend/src/contexts/",
    "nextjs-frontend/src/lib/",
    "nextjs-frontend/src/types/",
    "nextjs-frontend/src/__tests__/",
    "nextjs-frontend/public/",
)

# App-router: tenant features live under /app/features/* inside the authenticated shell
NEXTJS_APP_SHELL_PREFIX = "nextjs-frontend/src/app/"
NEXTJS_FEATURE_PREFIX = "nextjs-frontend/src/app/app/features/"
LEGACY_FEATURE_PREFIX = "nextjs-frontend/src/app/features/"

# Paths the AI is ALLOWED to create/update freely
FEATURE_OWNED_PATH_PREFIXES: tuple[str, ...] = (
    "nextjs-frontend/src/app/app/features/",
    "python-backend/app/domain/models/",
    "python-backend/app/services/",
    "python-backend/app/schemas/",
    "python-backend/app/api/",
)

# Bounded update files — AI can update these in a CONTROLLED way only
BOUNDED_CORE_UPDATE_FILES: tuple[str, ...] = (
    "nextjs-frontend/src/components/layout/Sidebar.tsx",
    "python-backend/app/core/permissions.py",
    "python-backend/app/api/router.py",
    "python-backend/app/domain/models/__init__.py",
    "python-backend/app/data_seeder.py",
    "python-backend/app/staging_demo_seeder.py",
)

TENANT_NAV_MARKER = "// AI-generated tenant feature nav items — DO NOT REMOVE THIS COMMENT"
HOST_NAV_MARKER = "// AI-generated host feature nav items — DO NOT REMOVE THIS COMMENT"
LEGACY_NAV_MARKER = "// AI-generated feature nav items — DO NOT REMOVE THIS COMMENT"

# Common ORM relationship attribute names — accessing these in async services without
# selectinload triggers sqlalchemy.exc.MissingGreenlet at runtime.
_ASYNC_RELATIONSHIP_ATTRS = frozenset({
    "attachments", "roles", "items", "children", "files", "tags", "comments",
    "members", "claims", "tokens", "features", "generations", "events",
    "permissions", "users", "projects", "subscriptions", "plans",
})


@dataclass
class AutoFixReport:
    total_files_fixed: int = 0
    file_details: list["FileFixDetail"] = field(default_factory=list)
    fix_type_count: dict[str, int] = field(default_factory=dict)

    def add_fix(self, file_path: str, fix_type: str) -> None:
        self.total_files_fixed += 1
        self.fix_type_count[fix_type] = self.fix_type_count.get(fix_type, 0) + 1
        for detail in self.file_details:
            if detail.file_path == file_path:
                detail.fixes_applied.append(fix_type)
                return
        self.file_details.append(FileFixDetail(file_path=file_path, fixes_applied=[fix_type]))

    def get_summary(self) -> str:
        if self.total_files_fixed == 0:
            return "No auto-fixes applied."
        lines = [f"Auto-fixed {self.total_files_fixed} file(s):"]
        for fix_type, count in sorted(self.fix_type_count.items(), key=lambda x: -x[1]):
            lines.append(f"  - {fix_type}: {count}x")
        return "\n".join(lines)


@dataclass
class BoundedMergeHints:
    feature_slug: str = ""
    api_module: str = ""
    api_prefix: str = ""
    sidebar_label: str = ""
    sidebar_href: str = ""
    permission_class: str = ""
    permissions: dict[str, str] = field(default_factory=dict)
    model_imports: list[tuple[str, str]] = field(default_factory=list)
    seed_function_name: str = ""
    seed_function_body: str = ""


@dataclass
class FileFixDetail:
    file_path: str
    fixes_applied: list[str] = field(default_factory=list)


class PatternEnforcementService:
    """
    Validates and auto-fixes AI-generated code to ensure it follows
    ffinn's architectural rules.

    Key responsibilities:
    1. Strip protected files so they are never overwritten
    2. Validate generated code for architectural violations
    3. Auto-fix common mistakes
    4. Provide the system prompt that guides AI code generation
    5. Supply existing file context so AI can merge properly
    """

    def __init__(self, repo_root: str = "", existing_file_cache: Optional[dict[str, str]] = None):
        self._repo_root = repo_root
        self._existing_file_cache: dict[str, str] = existing_file_cache or {}

    def get_system_prompt(self, target_scope: str = "tenant") -> str:
        return self._build_system_prompt(target_scope)

    def get_retry_system_prompt(self, reason: str = "architecture-violation", target_scope: str = "tenant") -> str:
        if reason == "format-failure":
            header = (
                "⚠️ CRITICAL RETRY — INVALID OUTPUT FORMAT ⚠️\n\n"
                "Your previous response was REJECTED because it could not be parsed into files.\n"
                "You MUST respond with a valid JSON object — no markdown prose, no code blocks outside the JSON.\n\n"
                "REQUIRED OUTPUT FORMAT (repeat from instructions):\n"
                "{\n"
                '  "files": [\n'
                '    {"path": "python-backend/app/domain/models/my_feature.py", "content": "# full content"},\n'
                '    {"path": "nextjs-frontend/src/app/app/features/my-feature/page.tsx", "content": "// full content"}\n'
                "  ]\n"
                "}\n\n"
                "Rules:\n"
                "- Respond with ONLY the JSON object — nothing before or after it\n"
                "- Every `path` must be repo-relative (start with `python-backend/` or `nextjs-frontend/`)\n"
                "- Every `content` must be the COMPLETE file — never truncated, never `...existing code...`\n\n"
            )
        else:
            header = (
                "⚠️ CRITICAL RETRY — ARCHITECTURE VIOLATIONS DETECTED ⚠️\n\n"
                "Your previous generation was REJECTED because it violated ffinn's architectural rules.\n"
                "You MUST fix all violations before the code can be accepted.\n\n"
                "KEY RULES THAT WERE VIOLATED:\n"
                "1. Services MUST use SQLAlchemy AsyncSession via dependency injection — never import DB directly\n"
                "2. Routes MUST use FastAPI Depends() for all injections — never instantiate services directly\n"
                "3. Next.js: Add `'use client'` to interactive feature pages (hooks, events, browser APIs)\n"
                "4. Next.js: Use the shared `api` client from `@/lib/api` — never raw fetch() for backend calls\n"
                "5. Next.js: Use react-hot-toast — NEVER window.alert() or window.confirm()\n"
                "6. SQLAlchemy async: ALL relationship() must use lazy=\"selectin\"; services must use selectinload() — never lazy-load in async code\n"
                "7. Pydantic v2: use model_validate/model_copy — NEVER from_orm or .copy(update=...)\n"
                "8. NEVER overwrite protected files\n\n"
                "REQUIRED OUTPUT FORMAT REMINDER:\n"
                "Respond with ONLY a valid JSON object: "
                '{"files": [{"path": "repo-relative path", "content": "full file content"}]}\n'
                "No markdown, no prose outside the JSON.\n\n"
            )
        return header + self._build_system_prompt(target_scope)

    def _scope_guidance(self, target_scope: str) -> str:
        if target_scope == "host":
            return """
## TARGET AUDIENCE: HOST / PLATFORM ADMIN
This feature is for the **platform owner** (host admin), NOT tenant/customer users.

### Frontend
- Feature pages: `nextjs-frontend/src/app/app/admin/{feature-slug}/page.tsx`
- Public URL: `/app/admin/{feature-slug}` (host admin menu only)
- Host admins have no tenant_id — do not assume tenant context in the UI

### Backend
- Platform-wide data may use `tenant_id=None` where appropriate
- Host admins pass `user.is_admin()` checks; still enforce permissions
- Filter by tenant_id only when the feature manages per-tenant records

### Navigation
- Do NOT output Sidebar.tsx — the pipeline adds a link to the **host** menu automatically
"""
        return """
## TARGET AUDIENCE: TENANT / CUSTOMER
This feature is for **organization (tenant) users**, not the platform host admin.

### Frontend
- Feature pages: `nextjs-frontend/src/app/app/features/{feature-slug}/page.tsx`
- Public URL: `/app/features/{feature-slug}` (tenant user menu only)

### Backend
- ALWAYS scope data by `current_user.tenant_id` in services and queries
- Tenant isolation is mandatory — never leak data across tenants

### Navigation
- Do NOT output Sidebar.tsx — the pipeline adds a link to the **tenant** menu automatically
"""

    def _build_system_prompt(self, target_scope: str = "tenant") -> str:
        scope = target_scope if target_scope in ("host", "tenant") else "tenant"
        return (
            "You are an AI code generator for the ffinn Application Framework. "
            "Generate production-quality code following these MANDATORY rules:\n"
            + self._scope_guidance(scope)
            + """
## PYTHON BACKEND RULES

### Architecture (STRICT)
- **Routes** (`app/api/`): HTTP handling ONLY — call services, return DTOs. NO business logic.
- **Services** (`app/services/`): ALL business logic. Receive `AsyncSession` as constructor arg.
- **Models** (`app/domain/models/`): SQLAlchemy 2.0 declarative with `Mapped[]` type annotations.
- **Schemas** (`app/schemas/`): Pydantic v2 DTOs with `alias_generator=to_camel` when returning to frontend.

### SQLAlchemy Patterns
```python
from sqlalchemy.orm import selectinload

result = await db.execute(
    select(MyModel)
    .where(MyModel.tenant_id == tenant_id)
    .options(selectinload(MyModel.related_items))
    .order_by(MyModel.created_at.desc())
)
items = result.scalars().all()
# NEVER use db.query() — it is synchronous
# NEVER access model.related_items without selectinload — causes MissingGreenlet in async
```

### SQLAlchemy Relationships (MANDATORY for async)
Every `relationship()` MUST set `lazy="selectin"` to avoid MissingGreenlet errors:
```python
items: Mapped[list["MyRelated"]] = relationship(
    "MyRelated", back_populates="parent", lazy="selectin"
)
```
When querying parent rows in services, also eager-load:
```python
select(Parent).options(selectinload(Parent.items))
```

### Pydantic v2 (schemas + service DTOs)
```python
dto = MyRead.model_validate(orm_obj).model_copy(update={"extra": value})
# NEVER use from_orm() or .copy(update=...) — removed in Pydantic v2
```

### FastAPI Route Pattern (match existing features)
```python
from typing import Annotated
from fastapi import APIRouter, Depends
from app.core.dependencies import DBSession, get_current_user, CurrentUser
from app.core.exceptions import ForbiddenException

router = APIRouter(prefix="/api/my-feature", tags=["MyFeature"])

def _require_access(user: CurrentUser) -> None:
    if not user.is_admin() and not user.has_permission("MyFeature.View"):
        raise ForbiddenException("MyFeature.View permission required.")

@router.get("")
async def list_items(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: DBSession,
):
    _require_access(current_user)
    return await MyFeatureService(db).list_items(current_user.tenant_id)
```

### Model Definition
```python
class MyEntity(Base):
    __tablename__ = "my_entities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### File Placement
- **New entity**: `python-backend/app/domain/models/my_feature.py`
- **New service**: `python-backend/app/services/my_feature_service.py`
- **New routes**: `python-backend/app/api/my_feature.py` (NOT router.py — pipeline registers automatically)
- **New schemas**: `python-backend/app/schemas/my_feature_schemas.py`

## NEXT.JS FRONTEND RULES

### App Router (MANDATORY)
- Tenant feature pages: `nextjs-frontend/src/app/app/features/{feature-name}/page.tsx`
- Host feature pages: `nextjs-frontend/src/app/app/admin/{feature-name}/page.tsx`
- Follow the TARGET AUDIENCE section above for which path to use
- Add `'use client'` when using hooks, events, or browser APIs

### Canonical Page Pattern (match admin pages like notifications)
```tsx
'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, put, del } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import toast from 'react-hot-toast'

interface MyItem { id: string; name: string }

export default function MyFeaturePage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery<MyItem[]>({
    queryKey: ['my-feature'],
    queryFn: () => get<MyItem[]>('/api/my-feature'),
  })
  // ...
}
```

### API Calls
- Use named helpers from `@/lib/api`: `get`, `post`, `put`, `del` — NEVER raw `fetch()`
- Do NOT modify `src/lib/api.ts` or `src/types/` — define interfaces inline in the feature page

### UI & Styling
- Tailwind with light AND dark pairs: `bg-white dark:bg-gray-800`
- Use `react-hot-toast` — NEVER `window.alert` or `window.confirm`
- Use `@/components/ui/` (PageHeader, Button, Input, Modal, Badge, ConfirmDialog)
- Use `lucide-react` icons

### Navigation
- Do NOT output Sidebar.tsx — the pipeline adds nav links automatically based on TARGET AUDIENCE

## PROTECTED FILES (NEVER include in output)
- `python-backend/app/core/*` (except permissions are merged by pipeline)
- `python-backend/app/infrastructure/*`, `main.py`, `alembic/*`
- `nextjs-frontend/src/app/app/*` EXCEPT your feature folder under `features/` (tenant) or `admin/` (host)
- `nextjs-frontend/src/app/auth/*`, marketing pages
- `nextjs-frontend/src/lib/*`, `src/types/*`, `src/components/*`

## BOUNDED FILES (NEVER include — pipeline merges automatically)
- `python-backend/app/api/router.py`
- `python-backend/app/core/permissions.py`
- `nextjs-frontend/src/components/layout/Sidebar.tsx`
- `python-backend/app/domain/models/__init__.py`

## MIGRATION FILES
Do NOT generate Alembic migrations — describe schema in model files only.

## REQUIRED OUTPUT FORMAT
Respond with ONLY valid JSON:
```json
{
  "files": [
    {"path": "python-backend/app/domain/models/my_feature.py", "content": "..."},
    {"path": "python-backend/app/services/my_feature_service.py", "content": "..."},
    {"path": "python-backend/app/schemas/my_feature_schemas.py", "content": "..."},
    {"path": "python-backend/app/api/my_feature.py", "content": "..."},
    {"path": "nextjs-frontend/src/app/app/features/my-feature/page.tsx", "content": "'use client'\\n..."}
  ]
}
```
- Paths are repo-relative (`python-backend/` or `nextjs-frontend/`)
- Content must be complete files — never truncated
"""
        )

    def strip_protected_files(self, generated_files: dict[str, str]) -> int:
        """Remove protected files from generated output. Returns count stripped."""
        import posixpath
        stripped = 0
        to_remove = []
        for path in generated_files:
            normalized = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
            file_name = normalized.split("/")[-1]

            if file_name in PROTECTED_FILE_NAMES:
                log.warning("Stripping protected file (name match)", path=path)
                to_remove.append(path)
                stripped += 1
                continue

            if (
                normalized.startswith(NEXTJS_APP_SHELL_PREFIX)
                and not normalized.startswith(NEXTJS_FEATURE_PREFIX)
                and not normalized.startswith(LEGACY_FEATURE_PREFIX)
                and normalized not in BOUNDED_CORE_UPDATE_FILES
            ):
                log.warning("Stripping protected Next.js app shell file", path=path)
                to_remove.append(path)
                stripped += 1
                continue

            for prefix in PROTECTED_PATH_PREFIXES:
                if normalized.startswith(prefix) and normalized not in BOUNDED_CORE_UPDATE_FILES:
                    log.warning("Stripping protected file (path prefix)", path=path, prefix=prefix)
                    to_remove.append(path)
                    stripped += 1
                    break

        for path in to_remove:
            del generated_files[path]

        return stripped

    def validate_generated_code(
        self, generated_files: dict[str, str]
    ) -> list[str]:
        errors: list[str] = []

        for path, content in generated_files.items():
            normalized = path.replace("\\", "/")
            file_name = normalized.split("/")[-1]
            ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""

            if ext == "py":
                errors.extend(self._validate_python_file(normalized, content))
            elif ext in ("ts", "tsx"):
                errors.extend(self._validate_typescript_file(normalized, content))

            if len(errors) >= 10:
                break

        return errors

    def _validate_python_file(self, path: str, content: str) -> list[str]:
        errors: list[str] = []
        is_route = "/api/" in path and "router.py" not in path

        if is_route:
            if "from app.infrastructure.database import engine" in content:
                errors.append(f"{path}: Routes must not import engine directly — use DBSession dependency")
            if "AsyncSessionLocal()" in content:
                errors.append(f"{path}: Routes must not create sessions directly — use DBSession dependency")
            if re.search(r'\.query\s*\(', content):
                errors.append(f"{path}: Direct database query in route — move business logic to a service")

        if "/services/" in path:
            if "from fastapi.responses" in content:
                errors.append(f"{path}: Services must not import FastAPI response types")

        if "/domain/models/" in path and "class " in content:
            if "Column(" in content and "Mapped[" not in content:
                errors.append(f"{path}: Use SQLAlchemy 2.0 Mapped[] syntax, not Column()")
            if "relationship(" in content:
                errors.extend(self._validate_model_relationships(path, content))

        if "/services/" in path:
            errors.extend(self._validate_async_service_relationships(path, content))
            if ".from_orm(" in content:
                errors.append(
                    f"{path}: Use Pydantic v2 model_validate() instead of deprecated from_orm()"
                )
            if ".copy(update=" in content:
                errors.append(
                    f"{path}: Use Pydantic v2 model_copy(update=...) instead of copy(update=...)"
                )

        file_name = path.rsplit("/", 1)[-1]
        if (
            "/domain/models/" in path
            and file_name not in ("__init__.py",)
            and "__tablename__" in content
            and "Mapped[" in content
            and "tenant_id" not in content
        ):
            errors.append(
                f"{path}: Domain model is missing `tenant_id` — all entities must be tenant-scoped. "
                "Add: `tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)`"
            )

        return errors

    @staticmethod
    def _iter_relationship_calls(content: str) -> list[str]:
        """Return each relationship(...) call expression in content."""
        calls: list[str] = []
        needle = "relationship("
        start = 0
        while True:
            idx = content.find(needle, start)
            if idx == -1:
                break
            depth = 0
            j = idx + len("relationship")
            while j < len(content):
                ch = content[j]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        calls.append(content[idx:j + 1])
                        start = j + 1
                        break
                j += 1
            else:
                break
        return calls

    def _validate_model_relationships(self, path: str, content: str) -> list[str]:
        errors: list[str] = []
        for call in self._iter_relationship_calls(content):
            if 'lazy="selectin"' in call or "lazy='selectin'" in call:
                continue
            if re.search(r'lazy\s*=\s*["\'](?:select|joined|subquery|dynamic)["\']', call):
                errors.append(
                    f"{path}: relationship() must use lazy=\"selectin\" in async SQLAlchemy — "
                    f"found incompatible lazy loader"
                )
            else:
                errors.append(
                    f"{path}: relationship() must set lazy=\"selectin\" — "
                    f"default lazy loading causes MissingGreenlet in async services"
                )
        return errors

    def _validate_async_service_relationships(self, path: str, content: str) -> list[str]:
        errors: list[str] = []
        if "AsyncSession" not in content and "async def" not in content:
            return errors

        accesses_relationship = False
        for attr in _ASYNC_RELATIONSHIP_ATTRS:
            if re.search(rf"\.\s*{re.escape(attr)}\b", content):
                accesses_relationship = True
                break
        if not accesses_relationship and re.search(r"for\s+\w+\s+in\s+\w+\.\w+", content):
            accesses_relationship = True

        if accesses_relationship and "selectinload" not in content:
            errors.append(
                f"{path}: Async service accesses ORM relationships — "
                f"add .options(selectinload(...)) on select() queries to avoid MissingGreenlet"
            )
        return errors

    def _validate_typescript_file(self, path: str, content: str) -> list[str]:
        errors: list[str] = []
        is_feature = "/app/features/" in path or "/app/app/features/" in path

        if "window.confirm" in content:
            errors.append(f"{path}: Use a confirmation dialog component instead of window.confirm()")
        if "window.alert" in content:
            errors.append(f"{path}: Use react-hot-toast instead of window.alert()")

        if is_feature:
            uses_hooks = bool(re.search(r'\buse(State|Effect|Callback|Memo|Ref|Context)\b', content))
            has_client = "'use client'" in content or '"use client"' in content
            if uses_hooks and not has_client:
                errors.append(f"{path}: Add 'use client' directive — this file uses React hooks")

            if re.search(r'\bfetch\s*\(', content) and "@/lib/api" not in content:
                errors.append(f"{path}: Use helpers from `@/lib/api` (get/post/put/del) instead of raw fetch()")

        return errors

    def normalize_feature_paths(self, generated_files: dict[str, str]) -> int:
        """Rewrite legacy src/app/features/ paths to src/app/app/features/."""
        moved = 0
        for old_path in list(generated_files.keys()):
            norm = old_path.replace("\\", "/")
            if norm.startswith(LEGACY_FEATURE_PREFIX):
                new_path = NEXTJS_FEATURE_PREFIX + norm[len(LEGACY_FEATURE_PREFIX):]
                generated_files[new_path] = generated_files.pop(old_path)
                moved += 1
        return moved

    def auto_fix_generated_code(self, generated_files: dict[str, str]) -> AutoFixReport:
        report = AutoFixReport()
        if self.normalize_feature_paths(generated_files):
            report.add_fix("(paths)", "Rewrote legacy feature paths to app/app/features")

        for path, content in list(generated_files.items()):
            original = content
            file_name = path.replace("\\", "/").split("/")[-1]
            ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""

            if ext in ("ts", "tsx"):
                content, fixes = self._auto_fix_typescript(path, content)
                for fix in fixes:
                    report.add_fix(path, fix)
            elif ext == "py":
                content, fixes = self._auto_fix_python(path, content)
                for fix in fixes:
                    report.add_fix(path, fix)

            if content != original:
                generated_files[path] = content

        return report

    def repair_until_valid(
        self, generated_files: dict[str, str], max_passes: int = 5
    ) -> tuple[list[str], AutoFixReport]:
        """Auto-fix and re-validate in a loop before falling back to an AI retry."""
        combined = AutoFixReport()
        errors: list[str] = []

        for _ in range(max_passes):
            fix_report = self.auto_fix_generated_code(generated_files)
            self._merge_fix_reports(combined, fix_report)
            errors = self.validate_generated_code(generated_files)
            if not errors:
                return [], combined
            if fix_report.total_files_fixed == 0:
                break

        return errors, combined

    @staticmethod
    def _merge_fix_reports(target: AutoFixReport, source: AutoFixReport) -> None:
        for detail in source.file_details:
            for fix in detail.fixes_applied:
                target.add_fix(detail.file_path, fix)

    def _auto_fix_typescript(self, path: str, content: str) -> tuple[str, list[str]]:
        fixes: list[str] = []

        if "/features/" in path or "/app/features/" in path:
            uses_hooks = bool(re.search(r'\buse(State|Effect|Callback|Memo|Ref|Context)\b', content))
            has_client = "'use client'" in content or '"use client"' in content
            if uses_hooks and not has_client:
                content = "'use client'\n" + content
                fixes.append("Added 'use client' directive")

        return content, fixes

    def _auto_fix_python(self, path: str, content: str) -> tuple[str, list[str]]:
        fixes: list[str] = []

        if "/domain/models/" in path and "relationship(" in content:
            content, rel_fixes = self._auto_fix_relationship_lazy(content)
            fixes.extend(rel_fixes)

        if ".from_orm(" in content:
            content = content.replace(".from_orm(", ".model_validate(")
            fixes.append("Replaced Pydantic from_orm with model_validate")
        if ".copy(update=" in content:
            content = content.replace(".copy(update=", ".model_copy(update=")
            fixes.append("Replaced Pydantic copy with model_copy")

        if "/services/" in path:
            content, load_fixes = self._auto_fix_service_selectinload(content)
            fixes.extend(load_fixes)

        return content, fixes

    def _auto_fix_service_selectinload(self, content: str) -> tuple[str, list[str]]:
        """Inject selectinload() on select() when a service touches ORM relationships."""
        fixes: list[str] = []
        if "selectinload" in content:
            return content, fixes

        accessed: set[str] = set()
        for attr in _ASYNC_RELATIONSHIP_ATTRS:
            if re.search(rf"\.\s*{re.escape(attr)}\b", content):
                accessed.add(attr)
        if not accessed and re.search(r"for\s+\w+\s+in\s+\w+\.\w+", content):
            # Generic relationship iteration — cannot infer attrs; skip
            return content, fixes
        if not accessed:
            return content, fixes

        models = sorted(set(re.findall(r"select\s*\(\s*(\w+)\s*\)", content)))
        if not models:
            return content, fixes

        content, imported = self._ensure_selectinload_import(content)
        if imported:
            fixes.append("Added selectinload import")

        for model in models:
            opts = ", ".join(f"selectinload({model}.{attr})" for attr in sorted(accessed))
            pattern = rf"select\s*\(\s*{re.escape(model)}\s*\)(?!\s*\.options\s*\()"
            new_content, count = re.subn(pattern, f"select({model}).options({opts})", content)
            if count:
                content = new_content
                fixes.append(f"Added selectinload for {model} ({', '.join(sorted(accessed))})")

        return content, fixes

    @staticmethod
    def _ensure_selectinload_import(content: str) -> tuple[str, bool]:
        if re.search(r"from sqlalchemy\.orm import[^\n]*\bselectinload\b", content):
            return content, False

        orm_import = re.search(r"from sqlalchemy\.orm import (.+)", content)
        if orm_import:
            names = orm_import.group(1).strip()
            if "selectinload" in names:
                return content, False
            updated = content.replace(
                orm_import.group(0),
                f"from sqlalchemy.orm import {names}, selectinload",
                1,
            )
            return updated, True

        sa_import = re.search(r"from sqlalchemy import .+\n", content)
        if sa_import:
            insert_at = sa_import.end()
            return content[:insert_at] + "from sqlalchemy.orm import selectinload\n" + content[insert_at:], True

        return "from sqlalchemy.orm import selectinload\n" + content, True

    @classmethod
    def _auto_fix_relationship_lazy(cls, content: str) -> tuple[str, list[str]]:
        fixes: list[str] = []
        out: list[str] = []
        cursor = 0
        needle = "relationship("

        while cursor < len(content):
            idx = content.find(needle, cursor)
            if idx == -1:
                out.append(content[cursor:])
                break

            out.append(content[cursor:idx])
            depth = 0
            j = idx + len("relationship")
            while j < len(content):
                ch = content[j]
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        call = content[idx:j + 1]
                        if 'lazy="selectin"' in call or "lazy='selectin'" in call:
                            out.append(call)
                        elif re.search(r'lazy\s*=\s*["\'](?:select|joined|subquery|dynamic)["\']', call):
                            call = re.sub(
                                r'lazy\s*=\s*["\'](?:select|joined|subquery|dynamic)["\']',
                                'lazy="selectin"',
                                call,
                            )
                            fixes.append('Changed relationship lazy loader to "selectin"')
                            out.append(call)
                        elif "lazy=" not in call:
                            inner = call[:-1].rstrip()
                            if inner.endswith("("):
                                call = inner + 'lazy="selectin")'
                            else:
                                call = inner + ', lazy="selectin")'
                            fixes.append('Added lazy="selectin" to relationship()')
                            out.append(call)
                        else:
                            out.append(call)
                        cursor = j + 1
                        break
                j += 1
            else:
                out.append(content[idx:])
                break

        return "".join(out), fixes

    def get_existing_file_context(self, file_paths: Optional[list[str]] = None) -> dict[str, str]:
        context: dict[str, str] = {}

        targets = file_paths or list(BOUNDED_CORE_UPDATE_FILES)
        for file_path in targets:
            if file_path in self._existing_file_cache:
                context[file_path] = self._existing_file_cache[file_path]
                continue

            import os
            disk_path = os.path.join(self._repo_root, file_path) if self._repo_root else file_path
            if os.path.isfile(disk_path):
                try:
                    with open(disk_path, encoding="utf-8") as f:
                        content = f.read()
                    context[file_path] = content
                    self._existing_file_cache[file_path] = content
                except OSError:
                    pass

        return context

    def supplement_existing_file_cache(self, supplemental_files: dict[str, str]) -> None:
        for path, content in supplemental_files.items():
            if path not in self._existing_file_cache:
                self._existing_file_cache[path] = content

    def merge_router_include(self, existing_router_content: str, new_module: str, new_prefix: str = "") -> str:
        line = f"from app.api.{new_module} import router as {new_module}_router\n"
        include = f"api_router.include_router({new_module}_router)\n"

        if f"from app.api.{new_module}" in existing_router_content:
            log.info("Router include already exists, skipping", module=new_module)
            return existing_router_content

        marker = "# AI-generated routers — DO NOT REMOVE THIS COMMENT"
        if marker in existing_router_content:
            return existing_router_content.replace(
                marker, f"{marker}\n{line}{include}"
            )
        return existing_router_content + f"\n{line}{include}"

    def merge_sidebar_nav_item(
        self,
        existing_sidebar_content: str,
        label: str,
        href: str,
        icon: str = "LayoutDashboard",
        target_scope: str = "tenant",
    ) -> str:
        """Add a nav item to tenant or host feature nav in Sidebar.tsx without duplicating."""
        entry = f"  {{ label: '{label}', href: '{href}', icon: <{icon} size={{18}} /> }},"
        if href in existing_sidebar_content:
            log.info("Sidebar nav item already exists", href=href)
            return existing_sidebar_content

        scope = target_scope if target_scope in ("host", "tenant") else "tenant"
        marker = HOST_NAV_MARKER if scope == "host" else TENANT_NAV_MARKER
        if marker in existing_sidebar_content:
            return existing_sidebar_content.replace(marker, f"{marker}\n{entry}")
        if scope == "tenant" and LEGACY_NAV_MARKER in existing_sidebar_content:
            return existing_sidebar_content.replace(LEGACY_NAV_MARKER, f"{LEGACY_NAV_MARKER}\n{entry}")
        return existing_sidebar_content

    def merge_permission_group(self, existing_perms_content: str, new_class_name: str, permissions: dict[str, str]) -> str:
        if f"class {new_class_name}:" in existing_perms_content:
            log.info("Permission class already exists", class_name=new_class_name)
            return existing_perms_content

        marker = "# ── AI agent may add new feature permission groups below this line ────────"
        new_class_lines = [f"\n    class {new_class_name}:"]
        for perm_name, perm_value in permissions.items():
            new_class_lines.append(f'        {perm_name} = "{perm_value}"')

        new_class = "\n".join(new_class_lines)

        if marker in existing_perms_content:
            return existing_perms_content.replace(marker, f"{marker}{new_class}\n")
        return existing_perms_content + new_class + "\n"

    def merge_data_seeder(self, existing_seeder_content: str, new_seed_function: str, function_name: str) -> str:
        if f"async def {function_name}(" in existing_seeder_content:
            log.info("Seed function already exists", function_name=function_name)
            return existing_seeder_content

        marker = "        # AI-generated seed calls — DO NOT REMOVE THIS COMMENT"
        if marker in existing_seeder_content:
            call_line = f"        await {function_name}(db)"
            if call_line in existing_seeder_content:
                return existing_seeder_content + f"\n\n{new_seed_function}"
            return existing_seeder_content.replace(
                marker,
                f"{marker}\n{call_line}",
            ) + f"\n\n{new_seed_function}"

        methods_marker = "# AI-generated seed methods — DO NOT REMOVE THIS COMMENT"
        if methods_marker in existing_seeder_content:
            call = f"        await self.{function_name}()"
            updated = existing_seeder_content
            if call not in existing_seeder_content:
                updated = existing_seeder_content.replace(
                    methods_marker,
                    f"{methods_marker}\n{call}",
                )
            return updated + f"\n\n{new_seed_function}"

        return existing_seeder_content + f"\n\n{new_seed_function}"

    def merge_staging_demo_seeder(
        self,
        existing_seeder_content: str,
        new_seed_function: str,
        function_name: str,
    ) -> str:
        """Merge tenant-scoped demo seed into staging_demo_seeder (runs after deploy)."""
        if f"async def {function_name}(" in existing_seeder_content:
            log.info("Staging demo seed function already exists", function_name=function_name)
            return existing_seeder_content

        marker = "    # AI-generated staging demo seed calls — DO NOT REMOVE THIS COMMENT"
        call_line = f"    await {function_name}(db, tenant.id)"
        if marker in existing_seeder_content:
            if call_line in existing_seeder_content:
                return existing_seeder_content + f"\n\n{new_seed_function}"
            return existing_seeder_content.replace(
                marker,
                f"{marker}\n{call_line}",
            ) + f"\n\n{new_seed_function}"

        return existing_seeder_content + f"\n\n{new_seed_function}"

    def merge_model_import(self, existing_init_content: str, model_module: str, model_class: str) -> str:
        import_line = f"from app.domain.models.{model_module} import {model_class}"
        if import_line in existing_init_content or f"import {model_class}" in existing_init_content:
            return existing_init_content

        marker = "# AI-generated model imports — DO NOT REMOVE THIS COMMENT"
        if marker in existing_init_content:
            return existing_init_content.replace(marker, f"{marker}\n{import_line}")
        return existing_init_content + f"\n{import_line}\n"

    @staticmethod
    def _feature_slug(feature_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", feature_name.lower()).strip("-")
        return slug or "feature"

    @staticmethod
    def _to_pascal(name: str) -> str:
        return "".join(part.capitalize() for part in re.split(r"[^a-zA-Z0-9]+", name) if part)

    def extract_merge_hints(
        self,
        generated_files: dict[str, str],
        feature_name: str,
        target_scope: str = "tenant",
    ) -> BoundedMergeHints:
        slug = self._feature_slug(feature_name)
        pascal = self._to_pascal(feature_name)
        api_module = f"{slug.replace('-', '_')}"
        api_prefix = f"/api/{slug.replace('-', '_')}"
        scope = target_scope if target_scope in ("host", "tenant") else "tenant"
        sidebar_href = f"/app/admin/{slug}" if scope == "host" else f"/app/features/{slug}"
        perm_class = f"{pascal}Permissions"
        perm_prefix = slug.replace("-", "_").upper()

        hints = BoundedMergeHints(
            feature_slug=slug,
            api_module=api_module,
            api_prefix=api_prefix,
            sidebar_label=pascal,
            sidebar_href=sidebar_href,
            permission_class=perm_class,
            permissions={
                "VIEW": f"{perm_prefix}.VIEW",
                "CREATE": f"{perm_prefix}.CREATE",
                "EDIT": f"{perm_prefix}.EDIT",
                "DELETE": f"{perm_prefix}.DELETE",
            },
            model_imports=[],
            seed_function_name=f"seed_{api_module}_data",
            seed_function_body="",
        )

        for path, content in generated_files.items():
            norm = path.replace("\\", "/")
            if norm.startswith(f"python-backend/app/domain/models/{api_module}"):
                class_match = re.search(r"^class\s+(\w+)\s*\(", content, re.MULTILINE)
                if class_match:
                    hints.model_imports.append((api_module, class_match.group(1)))
            if norm == f"python-backend/app/api/{api_module}.py":
                prefix_match = re.search(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']+)["\']', content)
                if prefix_match:
                    hints.api_prefix = prefix_match.group(1)
            if "async def seed_" in content and norm.startswith("python-backend/"):
                fn_match = re.search(r"async def (seed_\w+)\s*\(", content)
                if fn_match:
                    hints.seed_function_name = fn_match.group(1)
                    hints.seed_function_body = content

        return hints

    def apply_bounded_merges(
        self,
        generated_files: dict[str, str],
        bounded_cache: dict[str, str],
        feature_name: str,
        target_scope: str = "tenant",
    ) -> dict[str, str]:
        """Strip AI bounded-file output and merge into canonical files deterministically."""
        hints = self.extract_merge_hints(generated_files, feature_name, target_scope=target_scope)

        for bounded_path in list(generated_files.keys()):
            norm = bounded_path.replace("\\", "/")
            if norm in BOUNDED_CORE_UPDATE_FILES:
                del generated_files[bounded_path]

        merged_bounded: dict[str, str] = {}

        router_path = "python-backend/app/api/router.py"
        router_src = bounded_cache.get(router_path, "")
        if router_src:
            merged_bounded[router_path] = self.merge_router_include(
                router_src, hints.api_module, hints.api_prefix
            )

        sidebar_path = "nextjs-frontend/src/components/layout/Sidebar.tsx"
        sidebar_src = bounded_cache.get(sidebar_path, "")
        if sidebar_src:
            merged_bounded[sidebar_path] = self.merge_sidebar_nav_item(
                sidebar_src,
                hints.sidebar_label,
                hints.sidebar_href,
                target_scope=target_scope,
            )

        perms_path = "python-backend/app/core/permissions.py"
        perms_src = bounded_cache.get(perms_path, "")
        if perms_src:
            merged_bounded[perms_path] = self.merge_permission_group(
                perms_src, hints.permission_class, hints.permissions
            )

        models_init_path = "python-backend/app/domain/models/__init__.py"
        models_init_src = bounded_cache.get(models_init_path, "")
        if models_init_src:
            updated = models_init_src
            for module, class_name in hints.model_imports:
                updated = self.merge_model_import(updated, module, class_name)
            merged_bounded[models_init_path] = updated

        seeder_path = "python-backend/app/data_seeder.py"
        seeder_src = bounded_cache.get(seeder_path, "")
        if seeder_src and hints.seed_function_body and target_scope == "host":
            merged_bounded[seeder_path] = self.merge_data_seeder(
                seeder_src, hints.seed_function_body, hints.seed_function_name
            )

        staging_seeder_path = "python-backend/app/staging_demo_seeder.py"
        staging_seeder_src = bounded_cache.get(staging_seeder_path, "")
        if staging_seeder_src and hints.seed_function_body and target_scope == "tenant":
            merged_bounded[staging_seeder_path] = self.merge_staging_demo_seeder(
                staging_seeder_src, hints.seed_function_body, hints.seed_function_name
            )

        generated_files.update(merged_bounded)
        return generated_files
