# =============================================================================
# TRAKN Backend Tests — test_wifi.py
# 5 tests for RSSI Kalman filter, path-loss model, trilateration.
# =============================================================================

import math
import pytest
import numpy as np

from main import (
    rssi_kalman_update,
    rssi_to_distance,
    weighted_trilateration,
    score_intersection_points,
)


# ---------------------------------------------------------------------------
# Test 1: RSSI Kalman filter moves toward measurement
# ---------------------------------------------------------------------------
def test_rssi_kalman_converges():
    """After many updates, Kalman estimate converges to the true RSSI."""
    state  = {}
    bssid  = "AA:BB:CC:DD:EE:01"
    target = -60.0

    for _ in range(50):
        est = rssi_kalman_update(state, bssid, target)

    assert abs(est - target) < 2.0, f"Kalman did not converge: {est}"


# ---------------------------------------------------------------------------
# Test 2: RSSI Kalman provides smoothing (rejects outlier spike)
# ---------------------------------------------------------------------------
def test_rssi_kalman_smoothing():
    """A single outlier measurement should not dominate the estimate."""
    state = {}
    bssid = "AA:BB:CC:DD:EE:02"

    # Warm up with stable -50 dBm readings
    for _ in range(20):
        rssi_kalman_update(state, bssid, -50.0)

    # One large outlier
    est_after_spike = rssi_kalman_update(state, bssid, -10.0)

    # Should remain close to -50, not jump all the way to -10
    assert est_after_spike < -40.0, f"Kalman not smoothing spike: {est_after_spike}"


# ---------------------------------------------------------------------------
# Test 3: RSSI to distance model at d0=1m
# ---------------------------------------------------------------------------
def test_rssi_to_distance_at_1m():
    """At rssi == rssi_ref the distance should be exactly 1 m (d0)."""
    rssi_ref = -40.0; n = 2.0
    dist = rssi_to_distance(-40.0, rssi_ref, n)
    assert abs(dist - 1.0) < 0.01, f"Distance at rssi_ref should be 1.0 m: {dist}"


# ---------------------------------------------------------------------------
# Test 4: RSSI to distance clamping
# ---------------------------------------------------------------------------
def test_rssi_to_distance_clamped():
    """Distance must be clamped to [0.5, 100.0]."""
    # Very strong signal → clamp to min
    d_min = rssi_to_distance(0.0, -40.0, 2.0)
    assert d_min == pytest.approx(0.5), f"Should be clamped to 0.5: {d_min}"

    # Very weak signal → clamp to max
    d_max = rssi_to_distance(-200.0, -40.0, 2.0)
    assert d_max == pytest.approx(100.0), f"Should be clamped to 100.0: {d_max}"


# ---------------------------------------------------------------------------
# Test 5: Trilateration finds centre of 4 equidistant APs
# ---------------------------------------------------------------------------
def test_trilateration_centre():
    """4 APs at corners of 20m×20m room, equal distances → centre ≈ (10,10)."""
    # Each AP is sqrt(200) ≈ 14.14 m from (10,10)
    aps = [(0.0, 0.0), (20.0, 0.0), (0.0, 20.0), (20.0, 20.0)]
    d   = math.sqrt(200.0)
    dists = [d, d, d, d]

    result = weighted_trilateration(aps, dists)
    assert result is not None, "Trilateration returned None"

    x, y = result
    assert abs(x - 10.0) < 3.0, f"x off-centre: {x}"
    assert abs(y - 10.0) < 3.0, f"y off-centre: {y}"
