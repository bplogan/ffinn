"""
Extended tests for PatternEnforcementService edge cases.
Supplements the basic test_pattern_enforcement.py file.
Covers: protected path prefixes, auto-fix edge cases, merge helpers,
        permission group merge, data seeder merge, existing file cache,
        retry system prompt, validate_generated_code exhaustive rules.
"""
from __future__ import annotations

import pytest
from app.ai_agent.pattern_enforcement import (
    PatternEnforcementService,
    AutoFixReport,
    FileFixDetail,
    PROTECTED_FILE_NAMES,
    PROTECTED_PATH_PREFIXES,
    FEATURE_OWNED_PATH_PREFIXES,
    BOUNDED_CORE_UPDATE_FILES,
)


def svc() -> PatternEnforcementService:
    return PatternEnforcementService()


# ═══════════════════════════════════════════════════════════════════════
# Protected file constants
# ═══════════════════════════════════════════════════════════════════════

class TestProtectedConstants:
    def test_protected_file_names_contains_core_files(self):
        assert "main.py" in PROTECTED_FILE_NAMES
        assert "config.py" in PROTECTED_FILE_NAMES
        assert "security.py" in PROTECTED_FILE_NAMES
        assert "database.py" in PROTECTED_FILE_NAMES
        assert "dependencies.py" in PROTECTED_FILE_NAMES

    def test_protected_file_names_contains_nextjs_files(self):
        assert "next.config.ts" in PROTECTED_FILE_NAMES
        assert "middleware.ts" in PROTECTED_FILE_NAMES
        assert "package.json" in PROTECTED_FILE_NAMES

    def test_protected_path_prefixes_cover_core(self):
        assert any("app/core/" in p for p in PROTECTED_PATH_PREFIXES)
        assert any("app/infrastructure/" in p for p in PROTECTED_PATH_PREFIXES)

    def test_bounded_core_update_files_contains_router(self):
        assert any("router.py" in p for p in BOUNDED_CORE_UPDATE_FILES)

    def test_feature_owned_paths_contain_api_and_services(self):
        assert any("app/api/" in p for p in FEATURE_OWNED_PATH_PREFIXES)
        assert any("app/services/" in p for p in FEATURE_OWNED_PATH_PREFIXES)


# ═══════════════════════════════════════════════════════════════════════
# strip_protected_files — exhaustive
# ═══════════════════════════════════════════════════════════════════════

class TestStripProtectedFilesExhaustive:
    def test_strips_infrastructure_path(self):
        s = svc()
        files = {"python-backend/app/infrastructure/database.py": "engine = ..."}
        count = s.strip_protected_files(files)
        assert count == 1
        assert not files

    def test_strips_core_path(self):
        s = svc()
        files = {"python-backend/app/core/config.py": "settings = ..."}
        count = s.strip_protected_files(files)
        assert count == 1
        assert not files

    def test_strips_nextjs_app_shell_outside_features(self):
        s = svc()
        files = {"nextjs-frontend/src/app/app/dashboard/page.tsx": "export default function Page() {}"}
        count = s.strip_protected_files(files)
        assert count == 1
        assert not files

    def test_does_not_strip_feature_paths(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": "// blog",
            "python-backend/app/services/blog_service.py": "class BlogService: pass",
            "python-backend/app/domain/models/blog.py": "class Blog(Base): pass",
            "python-backend/app/schemas/blog.py": "class BlogSchema(BaseModel): pass",
        }
        count = s.strip_protected_files(files)
        assert count == 0
        assert len(files) == 4

    def test_does_not_strip_bounded_router_file(self):
        """router.py is a BOUNDED file — not stripped (it's allowed to be updated)."""
        s = svc()
        files = {"python-backend/app/api/router.py": "# router"}
        count = s.strip_protected_files(files)
        assert count == 0
        assert "python-backend/app/api/router.py" in files

    def test_strips_multiple_protected_at_once(self):
        s = svc()
        files = {
            "python-backend/app/core/security.py": "x",
            "python-backend/app/infrastructure/email.py": "x",
            "python-backend/app/main.py": "x",
            "python-backend/app/services/blog_service.py": "x",  # allowed
        }
        count = s.strip_protected_files(files)
        assert count == 3
        assert len(files) == 1

    def test_backslash_paths_normalized(self):
        """Windows-style backslash paths should be normalized and matched."""
        s = svc()
        files = {"python-backend\\app\\core\\config.py": "settings = ..."}
        count = s.strip_protected_files(files)
        assert count == 1

    def test_strip_by_filename_match(self):
        """A file named 'main.py' anywhere in the tree should be stripped."""
        s = svc()
        files = {"some/random/path/main.py": "# main"}
        count = s.strip_protected_files(files)
        assert count == 1

    def test_alembic_versions_stripped_by_broader_prefix(self):
        """alembic/versions paths are stripped because 'python-backend/alembic/'
        appears in PROTECTED_PATH_PREFIXES before the feature-owned versions/ entry.
        This is intentional — AI should never generate migrations autonomously."""
        s = svc()
        files = {"python-backend/alembic/versions/001_create_blog.py": "# migration"}
        count = s.strip_protected_files(files)
        assert count == 1  # stripped — broader alembic/ prefix wins

    def test_strips_nextjs_frontend_path(self):
        """The ffinn admin UI (nextjs-frontend/) is fully protected.
        AI generates code for the *tenant's* app, never for this dashboard."""
        s = svc()
        files = {
            "nextjs-frontend/src/app/page.tsx": "export default function Page() {}",
            "nextjs-frontend/src/components/Widget.tsx": "export const Widget = () => null",
        }
        count = s.strip_protected_files(files)
        assert count == 2
        assert not files

    def test_strips_infrastructure_email_by_filename(self):
        """email.py is in PROTECTED_FILE_NAMES — protected even without the full prefix."""
        s = svc()
        files = {"app/infrastructure/email.py": "# mailer"}
        count = s.strip_protected_files(files)
        assert count == 1

    def test_strips_infrastructure_storage_by_filename(self):
        s = svc()
        files = {"app/infrastructure/storage.py": "# s3"}
        count = s.strip_protected_files(files)
        assert count == 1

    def test_strips_websocket_manager_by_filename(self):
        s = svc()
        files = {"app/infrastructure/websocket_manager.py": "# ws"}
        count = s.strip_protected_files(files)
        assert count == 1

    def test_strips_background_tasks_by_filename(self):
        s = svc()
        files = {"app/infrastructure/background_tasks.py": "# tasks"}
        count = s.strip_protected_files(files)
        assert count == 1


# ═══════════════════════════════════════════════════════════════════════
# validate_generated_code — Python rules
# ═══════════════════════════════════════════════════════════════════════

class TestValidatePythonRules:
    def test_route_direct_engine_import_is_error(self):
        s = svc()
        files = {
            "python-backend/app/api/blog.py": (
                "from app.infrastructure.database import engine\n"
                "@router.get('/')\nasync def get(): ..."
            )
        }
        errors = s.validate_generated_code(files)
        assert any("engine" in e.lower() or "session" in e.lower() for e in errors)

    def test_route_creates_session_directly_is_error(self):
        s = svc()
        files = {
            "python-backend/app/api/blog.py": "session = AsyncSessionLocal()\n"
        }
        errors = s.validate_generated_code(files)
        assert any("session" in e.lower() for e in errors)

    def test_route_with_db_query_is_error(self):
        s = svc()
        files = {
            "python-backend/app/api/blog.py": (
                "def get_all(db):\n"
                "    return db.query(Blog).all()\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("query" in e.lower() or "business logic" in e.lower() or "database" in e.lower() for e in errors)

    def test_service_importing_fastapi_response_is_error(self):
        s = svc()
        files = {
            "python-backend/app/services/blog_service.py": "from fastapi.responses import JSONResponse\n"
        }
        errors = s.validate_generated_code(files)
        assert any("fastapi" in e.lower() or "response" in e.lower() for e in errors)

    def test_model_using_column_without_mapped_is_error(self):
        s = svc()
        files = {
            "python-backend/app/domain/models/blog.py": (
                "class Blog(Base):\n"
                "    id = Column(Integer, primary_key=True)\n"
                "    name = Column(String)\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("mapped" in e.lower() or "column" in e.lower() for e in errors)

    def test_clean_service_file_has_no_errors(self):
        s = svc()
        files = {
            "python-backend/app/services/blog_service.py": (
                "from sqlalchemy.ext.asyncio import AsyncSession\n"
                "from sqlalchemy import select\n"
                "class BlogService:\n"
                "    def __init__(self, db: AsyncSession):\n"
                "        self._db = db\n"
                "    async def get_all(self):\n"
                "        result = await self._db.execute(select(Blog))\n"
                "        return result.scalars().all()\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert errors == []

    def test_clean_model_file_has_no_errors(self):
        s = svc()
        files = {
            "python-backend/app/domain/models/blog.py": (
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class Blog(Base):\n"
                "    __tablename__ = 'blogs'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
                "    title: Mapped[str] = mapped_column(String(256))\n"
                "    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert errors == []

    def test_max_10_errors_reported(self):
        """validate_generated_code stops at 10 errors to avoid huge output."""
        s = svc()
        files = {}
        for i in range(20):
            files[f"python-backend/app/api/route{i}.py"] = "db.query(M).all()\n"
        errors = s.validate_generated_code(files)
        assert len(errors) <= 10

    def test_model_relationship_without_lazy_selectin_is_error(self):
        s = svc()
        files = {
            "python-backend/app/domain/models/projects.py": (
                "class Project(Base):\n"
                "    attachments = relationship('ProjectFile', back_populates='project')\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("lazy" in e.lower() and "selectin" in e.lower() for e in errors)

    def test_model_relationship_with_lazy_select_is_error(self):
        s = svc()
        files = {
            "python-backend/app/domain/models/blog.py": (
                "class Blog(Base):\n"
                "    comments = relationship('Comment', lazy='select')\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("selectin" in e.lower() for e in errors)

    def test_service_accessing_relationship_without_selectinload_is_error(self):
        s = svc()
        files = {
            "python-backend/app/services/projects_service.py": (
                "from sqlalchemy.ext.asyncio import AsyncSession\n"
                "from sqlalchemy import select\n"
                "class ProjectsService:\n"
                "    def __init__(self, db: AsyncSession):\n"
                "        self.db = db\n"
                "    async def list_projects(self, tenant_id):\n"
                "        rows = (await self.db.execute(select(Project).where(Project.tenant_id == tenant_id))).scalars().all()\n"
                "        for p in rows:\n"
                "            for pf in p.attachments:\n"
                "                pass\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("selectinload" in e.lower() for e in errors)

    def test_service_with_selectinload_passes_relationship_validation(self):
        s = svc()
        files = {
            "python-backend/app/services/projects_service.py": (
                "from sqlalchemy.ext.asyncio import AsyncSession\n"
                "from sqlalchemy import select\n"
                "from sqlalchemy.orm import selectinload\n"
                "class ProjectsService:\n"
                "    async def list_projects(self, tenant_id):\n"
                "        stmt = select(Project).options(selectinload(Project.attachments))\n"
                "        rows = (await self.db.execute(stmt)).scalars().all()\n"
                "        for p in rows:\n"
                "            for pf in p.attachments:\n"
                "                pass\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert not any("selectinload" in e.lower() for e in errors)

    def test_service_from_orm_is_error(self):
        s = svc()
        files = {
            "python-backend/app/services/blog_service.py": (
                "return ProjectRead.from_orm(p).copy(update={'attachments': []})\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("from_orm" in e for e in errors)
        assert any("model_copy" in e or "copy(update" in e for e in errors)


class TestAutoFixPythonAsyncRules:
    def test_auto_fix_adds_lazy_selectin_to_relationship(self):
        s = svc()
        content = (
            "attachments = relationship(\n"
            '    "ProjectFile", back_populates="project", cascade="all, delete-orphan"\n'
            ")\n"
        )
        fixed, fixes = s._auto_fix_python("python-backend/app/domain/models/projects.py", content)
        assert 'lazy="selectin"' in fixed
        assert any("selectin" in f.lower() for f in fixes)

    def test_auto_fix_replaces_from_orm_and_copy(self):
        s = svc()
        content = "dto = ProjectRead.from_orm(p).copy(update={'x': 1})\n"
        fixed, fixes = s._auto_fix_python("python-backend/app/services/projects_service.py", content)
        assert "model_validate" in fixed
        assert "model_copy" in fixed
        assert len(fixes) == 2

    def test_auto_fix_adds_selectinload_to_service(self):
        s = svc()
        content = (
            "from sqlalchemy.ext.asyncio import AsyncSession\n"
            "from sqlalchemy import select\n"
            "class ProjectsService:\n"
            "    async def list_projects(self, tenant_id):\n"
            "        rows = (await self.db.execute(\n"
            "            select(Project).where(Project.tenant_id == tenant_id)\n"
            "        )).scalars().all()\n"
            "        for p in rows:\n"
            "            for pf in p.attachments:\n"
            "                pass\n"
        )
        fixed, fixes = s._auto_fix_python("python-backend/app/services/projects_service.py", content)
        assert "selectinload" in fixed
        assert "select(Project).options(selectinload(Project.attachments))" in fixed
        assert any("selectinload" in f.lower() for f in fixes)

    def test_repair_until_valid_fixes_projects_style_bug_without_ai_retry(self):
        s = svc()
        files = {
            "python-backend/app/domain/models/projects.py": (
                "class Project(Base):\n"
                "    attachments = relationship('ProjectFile', back_populates='project')\n"
            ),
            "python-backend/app/services/projects_service.py": (
                "from sqlalchemy.ext.asyncio import AsyncSession\n"
                "from sqlalchemy import select\n"
                "class ProjectsService:\n"
                "    def __init__(self, db: AsyncSession):\n"
                "        self.db = db\n"
                "    async def list_projects(self, tenant_id):\n"
                "        rows = (await self.db.execute(select(Project).where(Project.tenant_id == tenant_id))).scalars().all()\n"
                "        out = []\n"
                "        for p in rows:\n"
                "            for pf in p.attachments:\n"
                "                out.append(ProjectRead.from_orm(p).copy(update={'attachments': []}))\n"
                "        return out\n"
            ),
        }
        errors, report = s.repair_until_valid(files)
        assert errors == []
        assert report.total_files_fixed > 0
        assert 'lazy="selectin"' in files["python-backend/app/domain/models/projects.py"]
        assert "selectinload(Project.attachments)" in files["python-backend/app/services/projects_service.py"]
        assert "model_validate" in files["python-backend/app/services/projects_service.py"]

    def test_repair_until_valid_stops_when_unfixable_errors_remain(self):
        s = svc()
        files = {
            "python-backend/app/api/blog.py": "from app.infrastructure.database import engine\n",
        }
        errors, report = s.repair_until_valid(files)
        assert errors
        assert any("engine" in e for e in errors)
        assert report.total_files_fixed == 0


# ═══════════════════════════════════════════════════════════════════════
# validate_generated_code — TypeScript rules
# ═══════════════════════════════════════════════════════════════════════

class TestValidateTypeScriptRules:
    def test_window_confirm_is_error(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "'use client'\n"
                "if (window.confirm('Are you sure?')) { deleteItem(); }\n"
                "export default function BlogPage() { return null }\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("confirmation dialog" in e for e in errors)

    def test_window_alert_is_error(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "'use client'\n"
                "export default function BlogPage() { window.alert('done'); return null }\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("react-hot-toast" in e for e in errors)

    def test_raw_fetch_in_feature_is_error(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "'use client'\n"
                "export default function BlogPage() { fetch('/api/blog'); return null }\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("@/lib/api" in e for e in errors)

    def test_missing_use_client_with_hooks_is_error(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "import { useState } from 'react'\n"
                "export default function BlogPage() { const [x] = useState(0); return null }\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("'use client'" in e for e in errors)

    def test_clean_nextjs_feature_has_no_errors(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "'use client'\n"
                "import { useQuery } from '@tanstack/react-query'\n"
                "import { get } from '@/lib/api'\n"
                "export default function BlogPage() {\n"
                "  useQuery({ queryKey: ['blog'], queryFn: () => get('/api/blog') })\n"
                "  return null\n"
                "}\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert errors == []


@pytest.mark.skip(reason="HTML/angular validation removed — Next.js uses TSX only")
class TestValidateHTMLRules:
    def test_ngfor_is_error(self):
        s = svc()
        files = {
            "angular/src/app/features/blog/blog.component.html": (
                "<li *ngFor='let item of items'>{{item}}</li>\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("@for" in e for e in errors)

    def test_both_ngif_ngfor_reported(self):
        s = svc()
        files = {
            "angular/src/app/features/blog/blog.component.html": (
                "<div *ngIf='loaded'>\n<li *ngFor='let i of items'>{{i}}</li>\n</div>\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("@if" in e for e in errors)
        assert any("@for" in e for e in errors)

    def test_clean_html_with_modern_control_flow_no_errors(self):
        s = svc()
        files = {
            "angular/src/app/features/blog/blog.component.html": (
                "@if (isLoaded()) {\n"
                "  @for (item of items(); track item.id) {\n"
                "    <li>{{ item.title }}</li>\n"
                "  }\n"
                "}\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════
# auto_fix_generated_code — TypeScript
# ═══════════════════════════════════════════════════════════════════════

class TestAutoFixTypeScript:
    def test_adds_use_client_when_hooks_present(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "import { useState } from 'react'\n"
                "export default function BlogPage() { const [x] = useState(0); return null }\n"
            )
        }
        report = s.auto_fix_generated_code(files)
        assert files["nextjs-frontend/src/app/app/features/blog/page.tsx"].startswith("'use client'")
        assert report.total_files_fixed >= 1

    def test_normalizes_legacy_feature_paths(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/features/blog/page.tsx": (
                "import { useState } from 'react'\n"
                "export default function BlogPage() { return null }\n"
            )
        }
        report = s.auto_fix_generated_code(files)
        assert "nextjs-frontend/src/app/app/features/blog/page.tsx" in files
        assert any("legacy" in k.lower() or "paths" in k.lower() for k in report.fix_type_count)

    def test_no_fixes_applied_returns_zero_count(self):
        s = svc()
        files = {
            "nextjs-frontend/src/app/app/features/blog/page.tsx": (
                "'use client'\n"
                "export default function BlogPage() { return null }\n"
            )
        }
        report = s.auto_fix_generated_code(files)
        assert report.total_files_fixed == 0


@pytest.mark.skip(reason="HTML/angular auto-fix removed — Next.js uses TSX only")
class TestAutoFixHTML:
    def test_ngif_reported_without_modifying_content(self):
        """*ngIf is diagnosed and reported but content is returned unchanged.
        A naïve regex would produce unclosed @if blocks — we intentionally don't do that."""
        s = svc()
        original = "<div *ngIf='isLoaded'>content</div>\n"
        files = {
            "angular/src/app/features/blog/blog.component.html": original
        }
        report = s.auto_fix_generated_code(files)
        # Report registers the detection
        assert report.total_files_fixed >= 1
        assert any("*ngIf" in key for key in report.fix_type_count)
        # But HTML content is unchanged — no broken @if{ without closing }
        assert files["angular/src/app/features/blog/blog.component.html"] == original

    def test_ngfor_reported_without_modifying_content(self):
        """*ngFor is diagnosed but content is returned unchanged."""
        s = svc()
        original = "<li *ngFor='let item of items; trackBy: trackById'>{{item}}</li>\n"
        files = {
            "angular/src/app/features/blog/blog.component.html": original
        }
        report = s.auto_fix_generated_code(files)
        assert report.total_files_fixed >= 1
        assert any("*ngFor" in key for key in report.fix_type_count)
        assert files["angular/src/app/features/blog/blog.component.html"] == original

    def test_ngif_gets_partial_fix(self):
        """Legacy test alias — verifies the report is populated."""
        s = svc()
        files = {
            "angular/src/app/features/blog/blog.component.html": (
                "<div *ngIf='isLoaded'>content</div>\n"
            )
        }
        report = s.auto_fix_generated_code(files)
        assert report.total_files_fixed >= 1

    def test_ngfor_flagged(self):
        """Legacy test alias — verifies the report is populated."""
        s = svc()
        files = {
            "angular/src/app/features/blog/blog.component.html": (
                "<li *ngFor='let item of items; trackBy: trackById'>{{item}}</li>\n"
            )
        }
        report = s.auto_fix_generated_code(files)
        assert report.total_files_fixed >= 1


# ═══════════════════════════════════════════════════════════════════════
# AutoFixReport dataclass
# ═══════════════════════════════════════════════════════════════════════

class TestAutoFixReport:
    def test_add_fix_increments_count(self):
        report = AutoFixReport()
        report.add_fix("file.ts", "rxjs/operators → rxjs")
        assert report.total_files_fixed == 1
        assert report.fix_type_count["rxjs/operators → rxjs"] == 1

    def test_add_fix_same_file_counts_once(self):
        report = AutoFixReport()
        report.add_fix("file.ts", "fix-a")
        report.add_fix("file.ts", "fix-b")
        # total_files_fixed increments each add_fix call
        assert report.total_files_fixed == 2

    def test_get_summary_no_fixes(self):
        report = AutoFixReport()
        summary = report.get_summary()
        assert "No auto-fixes" in summary

    def test_get_summary_with_fixes(self):
        report = AutoFixReport()
        report.add_fix("file.ts", "rxjs/operators → rxjs")
        report.add_fix("file.ts", "rxjs/operators → rxjs")
        summary = report.get_summary()
        assert "2" in summary
        assert "rxjs/operators → rxjs" in summary


# ═══════════════════════════════════════════════════════════════════════
# merge_router_include
# ═══════════════════════════════════════════════════════════════════════

class TestMergeRouterInclude:
    def test_inserts_import_and_include_below_marker(self):
        s = svc()
        existing = (
            "from fastapi import APIRouter\n"
            "api_router = APIRouter()\n"
            "# AI-generated routers \u2014 DO NOT REMOVE THIS COMMENT\n"
        )
        result = s.merge_router_include(existing, "products", "/products")
        assert "from app.api.products import router as products_router" in result
        assert 'api_router.include_router(products_router)' in result

    def test_does_not_duplicate_existing_router(self):
        s = svc()
        existing = (
            "from app.api.blog import router as blog_router\n"
            "api_router.include_router(blog_router)\n"
            "# AI-generated routers \u2014 DO NOT REMOVE THIS COMMENT\n"
        )
        result = s.merge_router_include(existing, "blog", "/blog")
        # Should not add a second blog_router import
        assert result.count("from app.api.blog import router as blog_router") == 1

    def test_falls_back_to_append_when_no_marker(self):
        s = svc()
        existing = "api_router = APIRouter()\n"
        result = s.merge_router_include(existing, "orders", "/orders")
        assert "orders_router" in result

    def test_preserves_existing_content_after_insertion(self):
        s = svc()
        existing = (
            "api_router = APIRouter()\n"
            "api_router.include_router(auth_router)\n"
            "# AI-generated routers \u2014 DO NOT REMOVE THIS COMMENT\n"
        )
        result = s.merge_router_include(existing, "invoices", "/invoices")
        assert "auth_router" in result
        assert "invoices_router" in result


# ═══════════════════════════════════════════════════════════════════════
# merge_permission_group
# ═══════════════════════════════════════════════════════════════════════

class TestMergePermissionGroup:
    _EXISTING = (
        "class Permissions:\n"
        "    class Users:\n"
        "        List = 'permissions.users.list'\n"
        "    # \u2500\u2500 AI agent may add new feature permission groups below this line \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
    )

    def test_adds_new_permission_class(self):
        s = svc()
        result = s.merge_permission_group(
            self._EXISTING, "Blog",
            {"List": "permissions.blog.list", "Create": "permissions.blog.create"}
        )
        assert "class Blog:" in result
        assert "permissions.blog.list" in result
        assert "permissions.blog.create" in result

    def test_does_not_duplicate_existing_class(self):
        s = svc()
        existing_with_blog = self._EXISTING + "    class Blog:\n        List = 'x'\n"
        result = s.merge_permission_group(
            existing_with_blog, "Blog", {"List": "permissions.blog.list"}
        )
        assert result.count("class Blog:") == 1

    def test_preserves_existing_permissions(self):
        s = svc()
        result = s.merge_permission_group(
            self._EXISTING, "Orders",
            {"List": "permissions.orders.list"}
        )
        assert "class Users:" in result
        assert "class Orders:" in result


# ═══════════════════════════════════════════════════════════════════════
# merge_data_seeder
# ═══════════════════════════════════════════════════════════════════════

class TestMergeDataSeeder:
    _EXISTING = (
        "class DataSeeder:\n"
        "    async def seed(self):\n"
        "        # AI-generated seed methods \u2014 DO NOT REMOVE THIS COMMENT\n"
        "        await self.seed_users()\n"
    )

    def test_adds_new_seed_function(self):
        new_func = "    async def seed_products(self):\n        pass\n"
        s = svc()
        result = s.merge_data_seeder(self._EXISTING, new_func, "seed_products")
        assert "seed_products" in result

    def test_does_not_duplicate_existing_function(self):
        existing = self._EXISTING + "    async def seed_products(self):\n        pass\n"
        new_func = "    async def seed_products(self):\n        pass\n"
        s = svc()
        result = s.merge_data_seeder(existing, new_func, "seed_products")
        assert result.count("async def seed_products") == 1

    def test_calls_new_seed_from_marker(self):
        new_func = "    async def seed_invoices(self):\n        pass\n"
        s = svc()
        result = s.merge_data_seeder(self._EXISTING, new_func, "seed_invoices")
        assert "await self.seed_invoices()" in result

    def test_seed_calls_marker_in_module_level_seeder(self):
        existing = (
            "async def seed() -> None:\n"
            "    async with async_session_factory() as db:\n"
            "        await seed_roles(db)\n"
            "        # AI-generated seed calls — DO NOT REMOVE THIS COMMENT\n"
        )
        new_func = "async def seed_products_data(db):\n    pass\n"
        s = svc()
        result = s.merge_data_seeder(existing, new_func, "seed_products_data")
        assert "await seed_products_data(db)" in result
        assert "async def seed_products_data" in result


class TestMergeStagingDemoSeeder:
    _EXISTING = (
        "async def seed_staging_demo(db: AsyncSession) -> list[dict[str, str]]:\n"
        "    tenant = await ensure_staging_tenant(db)\n"
        "    # AI-generated staging demo seed calls — DO NOT REMOVE THIS COMMENT\n"
        "    await seed_projects_demo_data(db, tenant.id)\n"
    )

    def test_adds_staging_demo_seed_call(self):
        new_func = "async def seed_widgets_demo_data(db, tenant_id):\n    pass\n"
        s = svc()
        result = s.merge_staging_demo_seeder(self._EXISTING, new_func, "seed_widgets_demo_data")
        assert "await seed_widgets_demo_data(db, tenant.id)" in result
        assert "async def seed_widgets_demo_data" in result

    def test_does_not_duplicate_existing_function(self):
        existing = self._EXISTING + "\nasync def seed_widgets_demo_data(db, tenant_id):\n    pass\n"
        new_func = "async def seed_widgets_demo_data(db, tenant_id):\n    pass\n"
        s = svc()
        result = s.merge_staging_demo_seeder(existing, new_func, "seed_widgets_demo_data")
        assert result.count("async def seed_widgets_demo_data") == 1


# ═══════════════════════════════════════════════════════════════════════
# get_existing_file_context — disk cache
# ═══════════════════════════════════════════════════════════════════════

class TestGetExistingFileContext:
    def test_returns_cached_content(self):
        cache = {"python-backend/app/api/router.py": "# cached router"}
        s = PatternEnforcementService(existing_file_cache=cache)
        ctx = s.get_existing_file_context(["python-backend/app/api/router.py"])
        assert ctx["python-backend/app/api/router.py"] == "# cached router"

    def test_returns_empty_for_missing_files(self):
        s = PatternEnforcementService()
        ctx = s.get_existing_file_context(["nonexistent/path/file.py"])
        assert ctx == {}

    def test_supplement_cache_adds_entries(self):
        s = PatternEnforcementService()
        s.supplement_existing_file_cache({"app/api/router.py": "# router"})
        ctx = s.get_existing_file_context(["app/api/router.py"])
        assert ctx["app/api/router.py"] == "# router"

    def test_supplement_cache_does_not_overwrite_existing(self):
        cache = {"app/api/router.py": "# original"}
        s = PatternEnforcementService(existing_file_cache=cache)
        s.supplement_existing_file_cache({"app/api/router.py": "# new version"})
        ctx = s.get_existing_file_context(["app/api/router.py"])
        # Original should be preserved
        assert ctx["app/api/router.py"] == "# original"


# ═══════════════════════════════════════════════════════════════════════
# Retry system prompt
# ═══════════════════════════════════════════════════════════════════════

class TestRetrySystemPrompt:
    def test_retry_prompt_contains_violation_warning(self):
        s = svc()
        retry = s.get_retry_system_prompt()
        assert "RETRY" in retry.upper() or "VIOLATED" in retry.upper()

    def test_retry_prompt_contains_key_rules(self):
        s = svc()
        retry = s.get_retry_system_prompt()
        assert "AsyncSession" in retry or "DBSession" in retry
        assert "'use client'" in retry
        assert "@/lib/api" in retry

    def test_retry_prompt_is_longer_than_normal_prompt(self):
        s = svc()
        assert len(s.get_retry_system_prompt()) >= len(s.get_system_prompt())


# ═══════════════════════════════════════════════════════════════════════
# System prompt — output format & completeness
# ═══════════════════════════════════════════════════════════════════════

class TestSystemPromptOutputFormat:
    def test_system_prompt_contains_json_word(self):
        """OpenAI json_object mode requires the word 'json' to appear in the messages."""
        s = svc()
        prompt = s.get_system_prompt()
        assert "json" in prompt.lower()

    def test_system_prompt_specifies_files_array_format(self):
        """The AI must know to return {\"files\": [{\"path\": ..., \"content\": ...}]}."""
        s = svc()
        prompt = s.get_system_prompt()
        assert '"files"' in prompt
        assert '"path"' in prompt
        assert '"content"' in prompt

    def test_system_prompt_specifies_repo_relative_paths(self):
        s = svc()
        prompt = s.get_system_prompt()
        assert "python-backend/" in prompt
        assert "nextjs-frontend/" in prompt

    def test_system_prompt_says_never_truncate_content(self):
        """AI must not emit '# ... existing code ...' partial files."""
        s = svc()
        prompt = s.get_system_prompt()
        assert "truncated" in prompt.lower() or "never" in prompt.lower()

    def test_system_prompt_prohibits_migration_generation(self):
        """AI should not autonomously create Alembic migrations."""
        s = svc()
        prompt = s.get_system_prompt()
        assert "migration" in prompt.lower() or "alembic" in prompt.lower()


# ═══════════════════════════════════════════════════════════════════════
# Constants integrity
# ═══════════════════════════════════════════════════════════════════════

class TestConstantsIntegrity:
    def test_feature_owned_paths_does_not_contain_alembic_versions(self):
        """alembic/versions/ must NOT appear in FEATURE_OWNED_PATH_PREFIXES.
        It was previously listed there but is unreachable because the broader
        'python-backend/alembic/' prefix in PROTECTED_PATH_PREFIXES blocks it first.
        Its presence was misleading documentation implying migrations are AI-owned."""
        has_alembic_versions = any("alembic/versions" in p for p in FEATURE_OWNED_PATH_PREFIXES)
        assert not has_alembic_versions, (
            "alembic/versions/ must not be in FEATURE_OWNED_PATH_PREFIXES — "
            "it is unreachable (alembic/ is protected) and misleads readers."
        )

    def test_alembic_still_in_protected_prefixes(self):
        """Removing the dead entry from FEATURE_OWNED must not accidentally remove the
        PROTECTED entry — migrations must still be blocked."""
        assert any("alembic/" in p for p in PROTECTED_PATH_PREFIXES)


# ═══════════════════════════════════════════════════════════════════════
# Tenant-ID validation (multi-tenancy requirement)
# ═══════════════════════════════════════════════════════════════════════

class TestTenantIdValidation:
    def test_domain_model_without_tenant_id_is_error(self):
        """Any domain model with __tablename__ and Mapped[] syntax MUST declare tenant_id."""
        s = svc()
        files = {
            "python-backend/app/domain/models/post.py": (
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "class Post(Base):\n"
                "    __tablename__ = 'posts'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
                "    title: Mapped[str] = mapped_column(String(256))\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert any("tenant_id" in e for e in errors), (
            f"Expected tenant_id validation error but got: {errors}"
        )

    def test_domain_model_with_tenant_id_passes(self):
        s = svc()
        files = {
            "python-backend/app/domain/models/post.py": (
                "import uuid\n"
                "from typing import Optional\n"
                "from sqlalchemy.orm import Mapped, mapped_column\n"
                "from sqlalchemy.dialects.postgresql import UUID\n"
                "class Post(Base):\n"
                "    __tablename__ = 'posts'\n"
                "    id: Mapped[int] = mapped_column(primary_key=True)\n"
                "    title: Mapped[str] = mapped_column(String(256))\n"
                "    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)\n"
            )
        }
        errors = s.validate_generated_code(files)
        assert not any("tenant_id" in e for e in errors)

    def test_init_file_skips_tenant_id_check(self):
        """models/__init__.py is an import-only file — no tablename check applies."""
        s = svc()
        files = {
            "python-backend/app/domain/models/__init__.py": (
                "from .post import Post\n"
                "from .user import User\n"
            )
        }
        errors = s.validate_generated_code(files)
        # __init__.py has no __tablename__ or Mapped[] — no error
        assert not any("tenant_id" in e for e in errors)

    def test_model_using_column_syntax_skips_tenant_id_check(self):
        """Old Column() syntax trips the Mapped[] check first; tenant_id check is
        secondary and only fires for Mapped[] models (modern SQLAlchemy 2.0 style)."""
        s = svc()
        files = {
            "python-backend/app/domain/models/legacy.py": (
                "class Legacy(Base):\n"
                "    __tablename__ = 'legacy'\n"
                "    id = Column(Integer, primary_key=True)\n"
            )
        }
        errors = s.validate_generated_code(files)
        # Should get the MAPPED[] error but NOT a tenant_id error
        assert any("Mapped" in e or "mapped" in e.lower() for e in errors)
        assert not any("tenant_id" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════
# Retry prompt — reason parameter
# ═══════════════════════════════════════════════════════════════════════

class TestRetryPromptReason:
    def test_default_reason_is_architecture_violation(self):
        s = svc()
        retry = s.get_retry_system_prompt()  # no reason arg
        assert "ARCHITECTURE VIOLATIONS" in retry.upper() or "VIOLATION" in retry.upper()

    def test_format_failure_reason_shows_format_header(self):
        s = svc()
        retry = s.get_retry_system_prompt(reason="format-failure")
        assert "FORMAT" in retry.upper()
        assert "ARCHITECTURE VIOLATIONS" not in retry.upper()

    def test_format_failure_retry_includes_json_schema_reminder(self):
        s = svc()
        retry = s.get_retry_system_prompt(reason="format-failure")
        assert '"files"' in retry
        assert '"path"' in retry
        assert '"content"' in retry

    def test_architecture_violation_retry_includes_key_rules(self):
        s = svc()
        retry = s.get_retry_system_prompt(reason="architecture-violation")
        assert "'use client'" in retry
        assert "@/lib/api" in retry
        assert "react-hot-toast" in retry

    def test_both_reasons_include_full_system_prompt(self):
        """Both retry types must include the full system prompt so the AI has all context."""
        s = svc()
        base = s.get_system_prompt()
        for reason in ("format-failure", "architecture-violation"):
            retry = s.get_retry_system_prompt(reason=reason)
            assert base in retry, f"Retry prompt for {reason} must include full system prompt"


# ═══════════════════════════════════════════════════════════════════════
# _merge_bounded_files — deterministic merges
# ═══════════════════════════════════════════════════════════════════════

class TestMergeBoundedFilesContextGuard:
    _ROUTER = (
        "from fastapi import APIRouter\n"
        "api_router = APIRouter()\n"
        "# AI-generated routers — DO NOT REMOVE THIS COMMENT\n"
    )
    _SIDEBAR = (
        "const FEATURE_NAV: NavItem[] = [\n"
        "// AI-generated tenant feature nav items — DO NOT REMOVE THIS COMMENT\n"
        "]\n"
    )
    _PERMS = (
        "class Permissions:\n"
        "    # ── AI agent may add new feature permission groups below this line ────────\n"
    )
    _MODELS_INIT = "# AI-generated model imports — DO NOT REMOVE THIS COMMENT\n"

    @pytest.mark.asyncio
    async def test_strips_ai_bounded_output_without_cache(self):
        """AI must not commit full rewrites of bounded files; without cache, merges are skipped."""
        from unittest.mock import AsyncMock
        from app.ai_agent.ai_agent_service import AIAgentService

        service = AIAgentService(db=AsyncMock())
        files = {
            "python-backend/app/api/router.py": "include_router(blog_router)",
            "python-backend/app/services/blog_service.py": "class BlogService: ...",
        }
        merged = await service._merge_bounded_files(
            files, "Blog", bounded_cache={}, context_fetched=False
        )

        assert "python-backend/app/api/router.py" not in merged
        assert "python-backend/app/services/blog_service.py" in merged

    @pytest.mark.asyncio
    async def test_applies_deterministic_merge_with_cache(self):
        from unittest.mock import AsyncMock
        from app.ai_agent.ai_agent_service import AIAgentService

        service = AIAgentService(db=AsyncMock())
        bounded_cache = {
            "python-backend/app/api/router.py": self._ROUTER,
            "nextjs-frontend/src/components/layout/Sidebar.tsx": self._SIDEBAR,
            "python-backend/app/core/permissions.py": self._PERMS,
            "python-backend/app/domain/models/__init__.py": self._MODELS_INIT,
        }
        files = {
            "python-backend/app/api/router.py": "SHOULD NOT COMMIT",
            "python-backend/app/api/blog.py": 'router = APIRouter(prefix="/api/blog")\n',
            "python-backend/app/services/blog_service.py": "class BlogService: ...",
        }
        merged = await service._merge_bounded_files(
            files, "Blog", bounded_cache=bounded_cache, context_fetched=True
        )

        assert "SHOULD NOT COMMIT" not in merged.get("python-backend/app/api/router.py", "")
        assert "blog_router" in merged["python-backend/app/api/router.py"]
        assert "python-backend/app/services/blog_service.py" in merged

    @pytest.mark.asyncio
    async def test_no_bounded_files_returns_unchanged(self):
        from unittest.mock import AsyncMock
        from app.ai_agent.ai_agent_service import AIAgentService

        service = AIAgentService(db=AsyncMock())
        files = {
            "python-backend/app/services/blog_service.py": "class BlogService: ...",
            "python-backend/app/schemas/blog.py": "class BlogCreate(BaseModel): ...",
        }
        merged = await service._merge_bounded_files(
            files, "Blog", bounded_cache={}, context_fetched=False
        )
        assert merged == files
