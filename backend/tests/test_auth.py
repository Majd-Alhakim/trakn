# =============================================================================
# TRAKN Backend Tests — test_auth.py
# 4 tests for register, login, invalid login, and JWT token validation.
# =============================================================================

import pytest
import pytest_asyncio

from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test 1: Register a new user → 201
# ---------------------------------------------------------------------------
async def test_register_success(client: AsyncClient):
    resp = await client.post("/api/v1/auth/register", json={
        "email":    "newuser@trakn.test",
        "password": "MySecurePass1!"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "user_id" in data
    assert len(data["user_id"]) > 0


# ---------------------------------------------------------------------------
# Test 2: Duplicate registration → 409
# ---------------------------------------------------------------------------
async def test_register_duplicate(client: AsyncClient):
    email = "dup@trakn.test"
    # First registration
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Pass1234!"
    })
    # Second registration with same email
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "Pass1234!"
    })
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Test 3: Login with correct credentials → 200, access_token present
# ---------------------------------------------------------------------------
async def test_login_success(client: AsyncClient, registered_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email":    registered_user["email"],
        "password": registered_user["password"]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 20


# ---------------------------------------------------------------------------
# Test 4: Login with wrong password → 401
# ---------------------------------------------------------------------------
async def test_login_wrong_password(client: AsyncClient, registered_user):
    resp = await client.post("/api/v1/auth/login", json={
        "email":    registered_user["email"],
        "password": "WrongPassword999!"
    })
    assert resp.status_code == 401
    assert "detail" in resp.json()
