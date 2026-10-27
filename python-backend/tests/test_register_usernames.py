"""Registration without a chosen username must not clash on the email's local part."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.core.exceptions import ConflictException
from app.domain.models.identity import IdentityUser
from app.services.auth_service import AuthService


async def _user_name(db, email: str) -> str:
    row = await db.execute(select(IdentityUser.user_name).where(IdentityUser.email == email))
    return row.scalar_one()


@pytest.mark.asyncio
async def test_same_local_part_on_different_domains_gets_numbered(db):
    base = f"sam{uuid.uuid4().hex[:8]}"
    svc = AuthService(db)
    for domain in ("one.example", "two.example", "three.example"):
        await svc.register(email=f"{base}@{domain}", password="TestPass123!")

    assert await _user_name(db, f"{base}@one.example") == base
    assert await _user_name(db, f"{base}@two.example") == f"{base}2"
    assert await _user_name(db, f"{base}@three.example") == f"{base}3"


@pytest.mark.asyncio
async def test_duplicate_email_still_rejected(db):
    email = f"dup{uuid.uuid4().hex[:8]}@example.com"
    svc = AuthService(db)
    await svc.register(email=email, password="TestPass123!")
    with pytest.raises(ConflictException, match="email"):
        await svc.register(email=email, password="TestPass123!")


@pytest.mark.asyncio
async def test_chosen_username_that_is_taken_is_rejected(db):
    name = f"pick{uuid.uuid4().hex[:8]}"
    svc = AuthService(db)
    await svc.register(email=f"{name}@a.example", password="TestPass123!", username=name)
    with pytest.raises(ConflictException, match="username"):
        await svc.register(email=f"other{name}@b.example", password="TestPass123!", username=name)
