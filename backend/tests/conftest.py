# =============================================================================
# TRAKN Backend Tests — conftest.py
# Shared pytest fixtures for all test modules.
# =============================================================================

import json
import os
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path

from httpx import AsyncClient, ASGITransport

# Make sure the backend package is importable from the tests directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Override DATABASE_URL before importing main to avoid real DB dependency
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-12345")
os.environ.setdefault("DEVICE_API_KEY_SALT", "test-salt-xyz")

from main import app, engine, Base

# ---------------------------------------------------------------------------
# Event loop — use asyncio default
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database setup / teardown
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Create all tables in the in-memory SQLite DB for the test session."""
    # SQLite compatibility: swap asyncpg URL for aiosqlite
    from sqlalchemy.ext.asyncio import create_async_engine as cae
    test_engine = cae("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


# ---------------------------------------------------------------------------
# HTTP test client
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client():
    """Async HTTPX test client wrapping the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Fixture data loaders
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def walk_data():
    """Load the synthetic 88-step walk fixture."""
    with open(FIXTURES_DIR / "sdp1_walk.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def ap_grid_data():
    """Load the 4-AP grid fixture."""
    with open(FIXTURES_DIR / "ap_grid_4ap.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Registered user fixture
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def registered_user(client):
    """Create a test user and return credentials."""
    email    = "testuser@trakn.test"
    password = "Password123!"

    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": password
    })
    assert resp.status_code in (201, 409), f"Register failed: {resp.text}"

    resp = await client.post("/api/v1/auth/login", json={
        "email": email, "password": password
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"

    token = resp.json()["access_token"]
    return {"email": email, "password": password, "token": token}


# ---------------------------------------------------------------------------
# DeviceState factory fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def fresh_device_state():
    """Return a fresh DeviceState instance."""
    from main import DeviceState
    return DeviceState()
