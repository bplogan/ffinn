"""Tests for pattern enforcement — the CRUCIAL safety system."""
from __future__ import annotations

import pytest
from app.ai_agent.pattern_enforcement import PatternEnforcementService, PROTECTED_FILE_NAMES


def make_svc():
    return PatternEnforcementService()


def test_strip_protected_files():
    """strip_protected_files modifies the dict in-place and returns count stripped."""
    svc = make_svc()
    files = {
        "python-backend/app/main.py": "content",
        "python-backend/app/core/security.py": "content",
        "python-backend/app/api/router.py": "content",
        "nextjs-frontend/src/app/app/features/blog/page.tsx": "new feature",
    }
    count = svc.strip_protected_files(files)
    assert "python-backend/app/main.py" not in files
    assert "python-backend/app/core/security.py" not in files
    assert "python-backend/app/api/router.py" in files
    assert "nextjs-frontend/src/app/app/features/blog/page.tsx" in files
    assert count == 2


def test_validate_python_no_direct_db_in_routes():
    svc = make_svc()
    files = {
        "app/api/blog.py": (
            "from fastapi import APIRouter\n"
            "from sqlalchemy.orm import Session\n"
            "router = APIRouter()\n"
            "@router.get('/posts')\n"
            "def get_posts(db: Session):\n"
            "    return db.query(Post).all()\n"
        )
    }
    errors = svc.validate_generated_code(files)
    assert any("direct database" in e.lower() or "business logic" in e.lower() for e in errors)


def test_validate_typescript_requires_use_client_with_hooks():
    svc = make_svc()
    files = {
        "nextjs-frontend/src/app/app/features/blog/page.tsx": (
            "import { useState } from 'react'\n"
            "export default function BlogPage() {\n"
            "  const [items, setItems] = useState([])\n"
            "  return <div />\n"
            "}\n"
        )
    }
    errors = svc.validate_generated_code(files)
    assert any("'use client'" in e for e in errors)


def test_validate_typescript_rejects_raw_fetch_in_features():
    svc = make_svc()
    files = {
        "nextjs-frontend/src/app/app/features/blog/page.tsx": (
            "'use client'\n"
            "export default function BlogPage() {\n"
            "  async function load() { await fetch('/api/blog') }\n"
            "  return <div />\n"
            "}\n"
        )
    }
    errors = svc.validate_generated_code(files)
    assert any("@/lib/api" in e for e in errors)


def test_autofix_adds_use_client():
    svc = make_svc()
    files = {
        "nextjs-frontend/src/app/app/features/blog/page.tsx": (
            "import { useState } from 'react'\n"
            "export default function BlogPage() {\n"
            "  const [items, setItems] = useState([])\n"
            "  return <div />\n"
            "}\n"
        )
    }
    report = svc.auto_fix_generated_code(files)
    content = files["nextjs-frontend/src/app/app/features/blog/page.tsx"]
    assert content.startswith("'use client'")
    assert report.total_files_fixed >= 1


def test_validate_typescript_rejects_window_alert():
    svc = make_svc()
    files = {
        "nextjs-frontend/src/app/app/features/blog/page.tsx": (
            "'use client'\n"
            "export default function BlogPage() {\n"
            "  window.alert('hi')\n"
            "  return <div />\n"
            "}\n"
        )
    }
    errors = svc.validate_generated_code(files)
    assert any("react-hot-toast" in e for e in errors)


def test_merge_router_include():
    svc = make_svc()
    existing = (
        "from fastapi import APIRouter\n"
        "api_router = APIRouter()\n"
        "api_router.include_router(auth_router)\n"
        "# AI-generated routers \u2014 DO NOT REMOVE THIS COMMENT\n"
    )
    result = svc.merge_router_include(existing, "blog", "/blog")
    assert "api_router.include_router(blog_router)" in result
    assert "auth_router" in result
    assert "# AI-generated routers \u2014 DO NOT REMOVE THIS COMMENT" in result


def test_merge_sidebar_nav_item():
    svc = make_svc()
    existing = (
        "const FEATURE_NAV: NavItem[] = [\n"
        "// AI-generated tenant feature nav items — DO NOT REMOVE THIS COMMENT\n"
        "]\n"
    )
    result = svc.merge_sidebar_nav_item(existing, "Blog", "/app/features/blog")
    assert "Blog" in result
    assert "/app/features/blog" in result


def test_merge_sidebar_nav_item_host():
    svc = make_svc()
    existing = (
        "const HOST_FEATURE_NAV: NavItem[] = [\n"
        "// AI-generated host feature nav items — DO NOT REMOVE THIS COMMENT\n"
        "]\n"
    )
    result = svc.merge_sidebar_nav_item(
        existing, "Reports", "/app/admin/reports", target_scope="host"
    )
    assert "Reports" in result
    assert "/app/admin/reports" in result


def test_system_prompt_contains_key_instructions():
    svc = make_svc()
    prompt = svc.get_system_prompt()
    assert "protected" in prompt.lower()
    assert "router.py" in prompt.lower() or "router" in prompt.lower()
    assert "nextjs-frontend" in prompt


def test_protected_file_names_not_empty():
    assert len(PROTECTED_FILE_NAMES) > 5


def test_normalize_feature_paths_rewrites_legacy():
    svc = make_svc()
    files = {
        "nextjs-frontend/src/app/features/blog/page.tsx": "content",
        "python-backend/app/api/blog.py": "router",
    }
    count = svc.normalize_feature_paths(files)
    assert count == 1
    assert "nextjs-frontend/src/app/app/features/blog/page.tsx" in files
    assert "nextjs-frontend/src/app/features/blog/page.tsx" not in files


def test_apply_bounded_merges_merges_router_and_sidebar():
    svc = make_svc()
    bounded_cache = {
        "python-backend/app/api/router.py": (
            "from fastapi import APIRouter\n"
            "api_router = APIRouter()\n"
            "# AI-generated routers — DO NOT REMOVE THIS COMMENT\n"
        ),
        "nextjs-frontend/src/components/layout/Sidebar.tsx": (
            "const FEATURE_NAV: NavItem[] = [\n"
            "// AI-generated tenant feature nav items — DO NOT REMOVE THIS COMMENT\n"
            "]\n"
        ),
        "python-backend/app/core/permissions.py": (
            "class Permissions:\n"
            "    # ── AI agent may add new feature permission groups below this line ────────\n"
        ),
        "python-backend/app/domain/models/__init__.py": (
            "# AI-generated model imports — DO NOT REMOVE THIS COMMENT\n"
        ),
    }
    generated = {
        "python-backend/app/api/inventory.py": (
            'router = APIRouter(prefix="/api/inventory")\n'
        ),
        "python-backend/app/domain/models/inventory.py": (
            "class InventoryItem(Base):\n"
            "    pass\n"
        ),
        "python-backend/app/api/router.py": "SHOULD BE STRIPPED",
        "nextjs-frontend/src/app/app/features/inventory/page.tsx": "'use client'\n",
    }
    result = svc.apply_bounded_merges(generated, bounded_cache, "Inventory")
    assert "SHOULD BE STRIPPED" not in result.get("python-backend/app/api/router.py", "")
    assert "inventory_router" in result["python-backend/app/api/router.py"]
    assert "/app/features/inventory" in result["nextjs-frontend/src/components/layout/Sidebar.tsx"]
    assert "InventoryPermissions" in result["python-backend/app/core/permissions.py"]
    assert "from app.domain.models.inventory import InventoryItem" in result[
        "python-backend/app/domain/models/__init__.py"
    ]
