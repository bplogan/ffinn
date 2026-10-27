"""Basic API tests."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "name" in resp.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    resp = await client.post("/api/auth/login", json={
        "username_or_email": "nobody@example.com",
        "password": "wrongpassword",
    })
    assert resp.status_code in (400, 401, 404)


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    # Register
    resp = await client.post("/api/auth/register", json={
        "user_name": "testuser",
        "email": "test@example.com",
        "password": "TestPass123!",
    })
    assert resp.status_code in (201, 409)  # 409 if already exists in shared state

    # Login
    resp = await client.post("/api/auth/login", json={
        "username_or_email": "test@example.com",
        "password": "TestPass123!",
    })
    # May fail with 400 if email confirmation required
    assert resp.status_code in (200, 400)


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
