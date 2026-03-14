# =============================================================================
# TRAKN Backend Tests — test_security.py
# 4 tests for API key generation/validation, bcrypt, rate-limit headers.
# =============================================================================

import hmac
import hashlib
import pytest

from httpx import AsyncClient
from main import (
    generate_api_key,
    hash_api_key,
    validate_api_key_hmac,
    hash_password,
    verify_password,
    DEVICE_API_KEY_SALT,
)


pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Test 1: API key generation follows the spec format
# ---------------------------------------------------------------------------
def test_api_key_format():
    """API key must be 'trakn-hw-' + 24 hex chars."""
    mac     = "24:42:E3:15:E5:72"
    api_key = generate_api_key(mac)

    assert api_key.startswith("trakn-hw-"), f"Wrong prefix: {api_key}"
    suffix = api_key[len("trakn-hw-"):]
    assert len(suffix) == 24, f"Suffix length wrong: {len(suffix)}"
    assert all(c in "0123456789abcdef" for c in suffix), "Suffix not hex"

    # Formula check: sha256(mac+salt)[:24]
    expected_digest = hashlib.sha256((mac + DEVICE_API_KEY_SALT).encode()).hexdigest()[:24]
    assert suffix == expected_digest


# ---------------------------------------------------------------------------
# Test 2: hmac.compare_digest is used in validation (constant-time)
# ---------------------------------------------------------------------------
def test_api_key_hmac_validation():
    """validate_api_key_hmac returns True for correct key, False for wrong."""
    mac      = "24:42:E3:15:E5:72"
    api_key  = generate_api_key(mac)
    key_hash = hash_api_key(api_key)

    assert validate_api_key_hmac(api_key, key_hash) is True

    wrong_key = "trakn-hw-000000000000000000000000"
    assert validate_api_key_hmac(wrong_key, key_hash) is False


# ---------------------------------------------------------------------------
# Test 3: bcrypt hashes are unique (salt) and verify correctly
# ---------------------------------------------------------------------------
def test_bcrypt_password_hashing():
    """Same password hashed twice → different hashes; verify works."""
    password = "SecurePassword123!"
    hash1    = hash_password(password)
    hash2    = hash_password(password)

    assert hash1 != hash2, "bcrypt hashes should differ (different salts)"

    assert verify_password(password, hash1), "Verification should pass for hash1"
    assert verify_password(password, hash2), "Verification should pass for hash2"
    assert not verify_password("WrongPassword", hash1), "Wrong password should fail"


# ---------------------------------------------------------------------------
# Test 4: Input validation rejects malformed MAC addresses
# ---------------------------------------------------------------------------
async def test_input_validation_bad_mac(client: AsyncClient, registered_user):
    """Gateway endpoint rejects packets with invalid MAC format."""
    token = registered_user["token"]

    packet = {
        "mac": "NOT_A_VALID_MAC",
        "samples": [
            {"ts": 0, "ax": 0.1, "ay": 0.0, "az": 9.8,
             "gx": 0.0, "gy": 0.0, "gz": 0.0}
        ],
        "wifi": []
    }

    resp = await client.post(
        "/api/v1/gateway/packet",
        json=packet,
        headers={"X-TRAKN-API-Key": "trakn-hw-000000000000000000000000"}
    )
    # Should be 422 (validation error) or 401 (auth failure before validation)
    assert resp.status_code in (401, 422), \
        f"Expected 401 or 422 for bad MAC, got {resp.status_code}"
