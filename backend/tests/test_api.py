# =============================================================================
# TRAKN Backend Tests — test_api.py
# 3 tests for health endpoint, unauthenticated access, and gateway packet.
# =============================================================================

import pytest
from httpx import AsyncClient
from main import generate_api_key, hash_api_key


pytestmark = pytest.mark.asyncio

TEST_MAC = "24:42:E3:AA:BB:CC"


# ---------------------------------------------------------------------------
# Test 1: GET /health returns 200
# ---------------------------------------------------------------------------
async def test_health_endpoint(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Test 2: Protected endpoint without JWT → 403
# ---------------------------------------------------------------------------
async def test_protected_endpoint_requires_jwt(client: AsyncClient):
    resp = await client.get(f"/api/v1/devices/{TEST_MAC}/position")
    # 403 (no credentials) or 401 (depends on auth scheme)
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Test 3: Gateway packet with wrong/missing API key → 401
# ---------------------------------------------------------------------------
async def test_gateway_rejects_bad_api_key(client: AsyncClient):
    packet = {
        "mac": TEST_MAC,
        "samples": [
            {
                "ts": 0,
                "ax": 0.1, "ay": 0.0, "az": 9.8,
                "gx": 0.0, "gy": 0.0, "gz": 0.0
            }
        ],
        "wifi": []
    }
    # No API key header
    resp = await client.post("/api/v1/gateway/packet", json=packet)
    assert resp.status_code == 401

    # Wrong API key
    resp2 = await client.post(
        "/api/v1/gateway/packet",
        json=packet,
        headers={"X-TRAKN-API-Key": "trakn-hw-0000000000000000000000"}
    )
    assert resp2.status_code == 401
