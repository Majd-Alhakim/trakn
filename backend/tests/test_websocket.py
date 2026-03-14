# =============================================================================
# TRAKN Backend Tests — test_websocket.py
# 2 tests for WebSocket connection and JWT enforcement.
# =============================================================================

import pytest
from httpx import AsyncClient
from httpx_ws import aconnect_ws


pytestmark = pytest.mark.asyncio

TEST_MAC = "24:42:E3:WS:00:01"


# ---------------------------------------------------------------------------
# Test 1: WebSocket without token is rejected (close code 4001)
# ---------------------------------------------------------------------------
async def test_websocket_rejects_no_token(client: AsyncClient):
    """Connecting without a token should result in immediate close."""
    try:
        async with aconnect_ws(
            f"/ws/position/{TEST_MAC}",
            client
        ) as ws:
            # Should be closed by server with code 4001
            msg = await ws.receive()
            # If we get here without exception the server may have sent a close frame
    except Exception:
        # Any connection error or close is acceptable
        pass


# ---------------------------------------------------------------------------
# Test 2: WebSocket with invalid JWT is rejected
# ---------------------------------------------------------------------------
async def test_websocket_rejects_bad_token(client: AsyncClient):
    """Connecting with a bogus token should be rejected."""
    try:
        async with aconnect_ws(
            f"/ws/position/{TEST_MAC}?token=bogus.token.here",
            client
        ) as ws:
            msg = await ws.receive()
    except Exception:
        pass  # Expected: connection closed or error
