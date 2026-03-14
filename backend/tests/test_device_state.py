# =============================================================================
# TRAKN Backend Tests — test_device_state.py
# 2 tests for DeviceState initialization and gyro bias calibration.
# =============================================================================

import pytest
import numpy as np

from main import (
    DeviceState,
    get_device_state,
    process_pdr,
    ImuSampleSchema,
    BIAS_COLLECT_SAMPLES,
    _device_states,
)


# ---------------------------------------------------------------------------
# Test 1: Fresh DeviceState has correct initial values
# ---------------------------------------------------------------------------
def test_device_state_initial_values():
    state = DeviceState()
    assert state.x.shape == (5,)
    assert np.all(state.x == 0.0)
    assert state.P.shape == (5, 5)
    assert state.step_count == 0
    assert state.heading == 0.0
    assert not state.bias_calibrated
    assert len(state.bias_samples) == 0
    assert len(state.buf_a) == 0
    assert isinstance(state.rssi_state, dict)


# ---------------------------------------------------------------------------
# Test 2: Gyro bias is estimated after BIAS_COLLECT_SAMPLES samples
# ---------------------------------------------------------------------------
def test_gyro_bias_calibration():
    """After 200 samples, bias_calibrated=True and gyro_bias ≈ mean gz."""
    state = DeviceState()
    state.last_ts = 0.0

    known_gz = 0.05   # constant gyro reading during still phase

    samples = []
    for i in range(BIAS_COLLECT_SAMPLES):
        samples.append(ImuSampleSchema(
            ts=i * 10,
            ax=0.0, ay=0.0, az=9.8,
            gx=0.0, gy=0.0, gz=known_gz
        ))

    process_pdr(state, samples)

    assert state.bias_calibrated, "Bias should be calibrated after 200 samples"
    assert abs(state.gyro_bias - known_gz) < 0.01, \
        f"Estimated bias {state.gyro_bias} differs from true {known_gz}"
