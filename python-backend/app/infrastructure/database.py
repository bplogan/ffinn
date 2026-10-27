"""
SQLAlchemy async engine and session factory.
"""
from __future__ import annotations

from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

log = structlog.get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────
_url = settings.database_url
_is_sqlite = _url.startswith("sqlite")

_engine_kwargs: dict = {"echo": settings.database_echo or settings.debug}
if not _is_sqlite:
    # SQLite (StaticPool) doesn't support these arguments
    _engine_kwargs.update(
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

engine = create_async_engine(_url, **_engine_kwargs)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)
# Alias used by background_tasks and data_seeder
async_session_factory = AsyncSessionLocal


# ── Base model ────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# ── Lifecycle ─────────────────────────────────────────────────────────────────
async def init_db() -> None:
    """Verify database connectivity on startup."""
    if _is_sqlite:
        # For SQLite (local dev / tests), create all tables from ORM metadata
        # (Alembic migrations use PostgreSQL-specific DDL that SQLite can't run)
        import app.domain.models as _models  # noqa: F401 — ensure all models are registered
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("SQLite schema created via create_all")
        return
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        log.info("Database connection established", url=settings.database_url.split("@")[-1])
    except Exception as e:
        log.error("Database connection failed", error=str(e))
        raise


async def close_db() -> None:
    await engine.dispose()
    log.info("Database connection closed")


# ── Dependency ────────────────────────────────────────────────────────────────
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
