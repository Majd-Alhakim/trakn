# =============================================================================
# TRAKN Backend Tests — test_fusion.py
# 4 tests for EKF sensor fusion.
# =============================================================================

import math
import pytest
import numpy as np

from main import (
    DeviceState,
    build_transition_matrix,
    ekf_predict,
    ekf_correct,
    get_confidence,
    Q_EKF,
    H_EKF,
    R_NORMAL,
    R_NOISY,
)


# ---------------------------------------------------------------------------
# Test 1: F matrix has correct position-velocity coupling
# ---------------------------------------------------------------------------
def test_transition_matrix_structure():
    """F[0,3] = dt (X ← vx), F[1,4] = dt (Y ← vy)."""
    dt = 0.1
    F  = build_transition_matrix(0.0, dt)
    assert F.shape == (5, 5)
    assert F[0, 3] == pytest.approx(dt)
    assert F[1, 4] == pytest.approx(dt)
    # Diagonal ones
    for i in range(5):
        assert F[i, i] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Test 2: EKF predict increases covariance
# ---------------------------------------------------------------------------
def test_ekf_predict_increases_covariance():
    """After prediction, trace(P) should increase by trace(Q)."""
    state = DeviceState()
    state.P = np.eye(5) * 1.0
    trace_before = float(np.trace(state.P))

    ekf_predict(state, dt=0.1)

    trace_after = float(np.trace(state.P))
    assert trace_after > trace_before, "Covariance should grow during prediction"


# ---------------------------------------------------------------------------
# Test 3: EKF correct reduces position uncertainty after good measurement
# ---------------------------------------------------------------------------
def test_ekf_correct_reduces_uncertainty():
    """After a correction step, positional uncertainty P[0:2,0:2] decreases."""
    state = DeviceState()
    state.x = np.zeros(5)
    state.P = np.eye(5) * 100.0   # large initial uncertainty

    z = np.array([5.0, 5.0])     # observed position
    trace_before = float(np.trace(state.P[0:2, 0:2]))

    ekf_correct(state, z, rssi_std=1.0)   # R_NORMAL

    trace_after = float(np.trace(state.P[0:2, 0:2]))
    assert trace_after < trace_before, "Covariance should shrink after correction"


# ---------------------------------------------------------------------------
# Test 4: Confidence formula
# ---------------------------------------------------------------------------
def test_get_confidence():
    """confidence = 1 / (1 + trace(P[0:2,0:2])): high P → low confidence."""
    P_low  = np.eye(5) * 0.01
    P_high = np.eye(5) * 100.0

    conf_low_unc  = get_confidence(P_low)
    conf_high_unc = get_confidence(P_high)

    assert 0.0 < conf_low_unc  <= 1.0
    assert 0.0 < conf_high_unc <= 1.0
    assert conf_low_unc > conf_high_unc, "Lower uncertainty → higher confidence"

    # Exact formula check for P=I
    P_eye = np.eye(5)
    expected = 1.0 / (1.0 + 2.0)   # trace of 2×2 identity = 2
    assert get_confidence(P_eye) == pytest.approx(expected, abs=1e-9)
