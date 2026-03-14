# =============================================================================
# TRAKN Backend Tests — test_devices.py
# 2 tests for device linking and ownership enforcement.
# =============================================================================

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio

TEST_MAC = "24:42:E3:15:E5:72"


# ---------------------------------------------------------------------------
# Test 1: Link a device successfully
# ---------------------------------------------------------------------------
async def test_link_device(client: AsyncClient, registered_user):
    token = registered_user["token"]
    resp  = await client.post(
        "/api/v1/devices/link",
        json={"mac": TEST_MAC, "child_name": "Layla"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mac"] == TEST_MAC
    assert data["child_name"] == "Layla"
    # api_key returned on first link
    assert "api_key" in data
    assert data["api_key"].startswith("trakn-hw-")


# ---------------------------------------------------------------------------
# Test 2: Another user cannot access the linked device's position
# ---------------------------------------------------------------------------
async def test_device_ownership_enforced(client: AsyncClient, registered_user):
    # Register a second user
    await client.post("/api/v1/auth/register", json={
        "email": "other@trakn.test", "password": "OtherPass1!"
    })
    resp2 = await client.post("/api/v1/auth/login", json={
        "email": "other@trakn.test", "password": "OtherPass1!"
    })
    other_token = resp2.json()["access_token"]

    # Link device as first user (idempotent)
    token1 = registered_user["token"]
    await client.post(
        "/api/v1/devices/link",
        json={"mac": TEST_MAC, "child_name": "Layla"},
        headers={"Authorization": f"Bearer {token1}"}
    )

    # Second user tries to get position → 403
    resp = await client.get(
        f"/api/v1/devices/{TEST_MAC}/position",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert resp.status_code == 403
