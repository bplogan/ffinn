"""Pytest configuration for ffinn Python backend tests."""
from __future__ import annotations

import asyncio
import atexit
import os
import shutil
import tempfile
from pathlib import Path
from typing import AsyncGenerator

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Set env vars BEFORE importing the app so config loads correctly
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars")
os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-tests-only32c")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REQUIRE_EMAIL_CONFIRMATION", "false")
os.environ.setdefault("DISABLE_BACKGROUND_SCHEDULER", "true")

# Import models first so Base.metadata is fully populated
import app.domain.models as _models             # noqa: E402, F401
import app.infrastructure.database as _db_module  # noqa: E402
from app.infrastructure.database import Base    # noqa: E402
from app.main import app as fastapi_app          # noqa: E402

# ── Single shared engine for all tests ───────────────────────────────────────
# StaticPool + check_same_thread=False reuses one SQLite connection across every
# test. The database lives in a temp file rather than ":memory:" on purpose: when
# a test's event loop closes, asyncio cancels leftover dependency generators and
# a cancelled session.close() makes SQLAlchemy invalidate that connection. With
# ":memory:" the connection *is* the database, so the next test reconnected to an
# empty database ("no such table"). With a file, a reconnect sees the same data.
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="ffinn-tests-"))
atexit.register(shutil.rmtree, _TEST_DB_DIR, ignore_errors=True)

TEST_ENGINE = create_async_engine(
    f"sqlite+aiosqlite:///{(_TEST_DB_DIR / 'test.db').as_posix()}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
test_session_factory = async_sessionmaker(TEST_ENGINE, expire_on_commit=False)

# Patch the app's own database module so get_session uses TEST_ENGINE.
# This is simpler and more reliable than dependency_overrides because
# get_session() reads AsyncSessionLocal at call time.
_APP_ENGINE = _db_module.engine  # still used by modules that imported it by name
_db_module.engine = TEST_ENGINE
_db_module.AsyncSessionLocal = test_session_factory
_db_module.async_session_factory = test_session_factory


async def _test_close_db() -> None:
    """Keep the shared in-memory engine alive across test client lifecycles."""
    pass


_db_module.close_db = _test_close_db


def _create_tables_sync() -> None:
    """Create all tables synchronously before the first test session starts."""
    async def _run() -> None:
        async with TEST_ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run())
    finally:
        loop.close()


# Run once at import time (module level) — guaranteed before any fixture
_create_tables_sync()


def pytest_sessionfinish(session, exitstatus) -> None:
    """Close pooled connections so the interpreter can exit.

    aiosqlite >= 0.22 runs each connection on a non-daemon worker thread, so a
    connection left open (StaticPool never closes its own) keeps the process
    alive after the last test and CI hangs until the job times out.
    """
    async def _dispose() -> None:
        await TEST_ENGINE.dispose()
        await _APP_ENGINE.dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_dispose())
    finally:
        loop.close()


@pytest_asyncio.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac

