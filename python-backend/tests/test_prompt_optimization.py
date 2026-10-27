"""
Comprehensive tests for PromptOptimizationService.
Covers all 11 transformation rules and edge cases.
"""
from __future__ import annotations

import pytest
from app.ai_agent.prompt_optimization import PromptOptimizationService, OptimizationResult


# ── Helper ────────────────────────────────────────────────────────────────────

def optimize(prompt: str) -> OptimizationResult:
    return PromptOptimizationService().optimize(prompt)


# ── Tests: Empty / whitespace inputs ─────────────────────────────────────────

def test_empty_prompt_returns_unchanged():
    result = optimize("")
    assert result.optimized_prompt == ""
    assert result.strategy == "none"
    assert result.applied == []


def test_whitespace_only_prompt_returns_unchanged():
    result = optimize("   ")
    assert result.optimized_prompt == "   "
    assert result.strategy == "none"


# ── Tests: Rule 1 — External data fetching ───────────────────────────────────

@pytest.mark.parametrize("phrase", [
    "get data from the internet",
    "fetch prices from web",
    "grab info from api",
    "pull content from online",
])
def test_rule1_external_data_fetch_replaced(phrase: str):
    result = optimize(f"I want to {phrase}")
    assert "use hardcoded sample data" in result.optimized_prompt
    assert any("Replaced external data fetching" in a for a in result.applied)


def test_rule1_no_external_fetch_not_triggered():
    result = optimize("Build a CRUD page for products")
    assert "use hardcoded sample data" not in result.optimized_prompt
    assert not any("Replaced external data fetching" in a for a in result.applied)


# ── Tests: Rule 2 — Quantity constraints ─────────────────────────────────────

def test_rule2_adds_quantity_constraint_for_entities():
    result = optimize("Create a feature for managing players")
    assert "ONE entity only" in result.optimized_prompt
    assert any("Added quantity constraints" in a for a in result.applied)


def test_rule2_skipped_when_quantity_word_already_present():
    result = optimize("Create a feature for a single player profile")
    assert not any("Added quantity constraints" in a for a in result.applied)


def test_rule2_skipped_with_only_keyword():
    result = optimize("Show only one user at a time")
    assert not any("Added quantity constraints" in a for a in result.applied)


# ── Tests: Rule 3 — DataSeeder guidance ──────────────────────────────────────

def test_rule3_adds_data_seeder_hint_for_database_keyword():
    result = optimize("Setup the database with initial data for products")
    assert "data_seeder.py" in result.optimized_prompt
    assert "Added DataSeeder location guidance" in result.applied


def test_rule3_skipped_when_data_seeder_already_mentioned():
    result = optimize("Add seed data to data_seeder.py for products")
    assert "Added DataSeeder location guidance" not in result.applied


def test_rule3_triggers_on_seed_keyword():
    result = optimize("seed the database with sample customers")
    # rule3 fires on "seed" and "database"
    assert "Added DataSeeder location guidance" in result.applied


# ── Tests: Rule 4 — Service pattern for CRUD ─────────────────────────────────

def test_rule4_adds_service_pattern_for_crud():
    result = optimize("Create a feature to add and delete products")
    assert "AsyncSession" in result.optimized_prompt
    assert "Added service pattern guidance" in result.applied


def test_rule4_skipped_if_async_session_already_present():
    result = optimize("Use AsyncSession in services to create products")
    assert "Added service pattern guidance" not in result.applied


def test_rule4_triggers_on_update_keyword():
    result = optimize("Build an update form for users")
    assert "AsyncSession" in result.optimized_prompt


# ── Tests: Rule 5 — react-hot-toast guidance ─────────────────────────────────

def test_rule5_adds_toast_guidance_for_notification_keyword():
    result = optimize("Show a notification when the user logs in")
    assert "react-hot-toast" in result.optimized_prompt
    assert "Added framework service guidance" in result.applied


def test_rule5_skipped_if_toast_already_mentioned():
    result = optimize("Use react-hot-toast for alerts on the page")
    assert "Added framework service guidance" not in result.applied


def test_rule5_triggers_on_alert_keyword():
    result = optimize("Show an alert when deletion is complete")
    assert "react-hot-toast" in result.optimized_prompt


# ── Tests: Rule 6 — MVP focus for complex requests ───────────────────────────

def test_rule6_adds_mvp_focus_for_long_prompt():
    long_prompt = " ".join(["feature"] * 120)  # > 500 chars
    result = optimize(long_prompt)
    assert "Start with MVP/core features:" in result.optimized_prompt
    assert any("Added MVP focus" in a for a in result.applied)


def test_rule6_adds_mvp_focus_for_many_and_conjunctions():
    # Rule triggers when count of \and\ > 5 (strictly more than 5)
    prompt = "Build a form and add rows and show data and filter results and export csv and print report and archive old"
    result = optimize(prompt)
    assert "Start with MVP/core features:" in result.optimized_prompt


def test_rule6_skipped_if_mvp_already_present():
    result = optimize("Build a simple MVP feature for users")
    assert "Added MVP focus" not in result.applied


# ── Tests: Rule 7 — Clarify absolute scope ───────────────────────────────────

def test_rule7_replaces_everything_keyword():
    result = optimize("Show everything about the user profile")
    assert "core features with sample data" in result.optimized_prompt
    assert any("Clarified scope" in a for a in result.applied)


def test_rule7_replaces_all_the_data():
    result = optimize("Retrieve all the data from the database")
    assert "core features with sample data" in result.optimized_prompt


def test_rule7_replaces_complete_system():
    result = optimize("Build a complete system for order management")
    assert "core features with sample data" in result.optimized_prompt


# ── Tests: Rule 8 — Default CRUD requirement ─────────────────────────────────

def test_rule8_adds_crud_for_page_keyword():
    result = optimize("Create a new page for invoice management")
    assert "add/edit/delete" in result.optimized_prompt
    assert any("Added default CRUD requirement" in a for a in result.applied)


def test_rule8_adds_crud_for_feature_keyword():
    result = optimize("Build a user management feature")
    assert "add/edit/delete" in result.optimized_prompt


def test_rule8_skipped_if_read_only_specified():
    result = optimize("Build a read-only view of order history")
    assert not any("Added default CRUD requirement" in a for a in result.applied)


def test_rule8_skipped_if_crud_already_present():
    result = optimize("Build a feature with full add/edit/delete for products")
    assert not any("Added default CRUD requirement" in a for a in result.applied)


# ── Tests: Rule 9 — Next.js frontend patterns ─────────────────────────────────

def test_rule9_adds_nextjs_patterns_for_ui_keyword():
    result = optimize("Build a dashboard page for analytics")
    assert "'use client'" in result.optimized_prompt
    assert "@/lib/api" in result.optimized_prompt
    assert "Added Next.js pattern requirements" in result.applied


def test_rule9_skipped_if_patterns_already_present():
    result = optimize("Use 'use client' and import api from '@/lib/api' in the page")
    assert "Added Next.js pattern requirements" not in result.applied


def test_rule9_triggers_on_component_keyword():
    result = optimize("Create a table component to display orders")
    assert "@/lib/api" in result.optimized_prompt


# ── Tests: Rule 10 — Tailwind dark mode compliance ───────────────────────────

def test_rule10_adds_dark_mode_hint_for_ui_keywords():
    result = optimize("Build a card list page for users")
    assert "dark:" in result.optimized_prompt
    assert "Added Tailwind dark mode compliance" in result.applied


def test_rule10_skipped_if_dark_already_mentioned():
    result = optimize("Build a card page with dark:bg-gray-800 styling")
    assert "Added Tailwind dark mode compliance" not in result.applied


# ── Tests: Rule 11 — Python backend specifics ────────────────────────────────
# Note: Rule 11 won't fire when rule 9 has already appended Next.js rules text
# containing "api" from `@/lib/api`, since rule 11 checks
# `"router" not in optimized.lower()`. Use prompts that don't trigger rule 9.

def test_rule11_adds_python_backend_hint_for_api_keyword():
    # Prompt with "endpoint" but no CRUD/UI keywords to avoid rule 9
    result = optimize("Define the REST endpoint specification")
    assert "FastAPI" in result.optimized_prompt
    assert "Added Python backend specifics" in result.applied


def test_rule11_adds_for_backend_keyword():
    # Prompt with "backend" but no CRUD/UI keywords to avoid rule 9
    result = optimize("The Python backend handler processes requests")
    assert "FastAPI" in result.optimized_prompt


def test_rule11_skipped_if_fastapi_already_present():
    result = optimize("Use FastAPI router for the orders api")
    assert "Added Python backend specifics" not in result.applied


# ── Tests: OptimizationResult structure ──────────────────────────────────────

def test_result_preserves_original_prompt():
    original = "Create a basic products page"
    result = optimize(original)
    assert result.original_prompt == original


def test_result_strategy_is_rules_for_non_empty_prompt():
    result = optimize("Build a users table")
    assert result.strategy == "rules"


def test_multiple_rules_can_fire_together():
    """A realistic prompt should trigger several rules simultaneously."""
    result = optimize("Build a dashboard page to manage all the user data with api endpoints")
    # Rule 7 (everything), Rule 8 (page/crud), Rule 9 (nextjs), Rule 10 (dark), Rule 11 (api)
    # At least 3 should fire
    assert len(result.applied) >= 3


def test_result_optimized_prompt_is_string():
    result = optimize("Build a products feature")
    assert isinstance(result.optimized_prompt, str)
    assert len(result.optimized_prompt) > 0
