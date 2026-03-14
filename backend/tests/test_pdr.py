# =============================================================================
# TRAKN Backend Tests — test_pdr.py
# 6 tests for the PDR engine (EMA filter, Weinberg stride, step detection, heading).
# =============================================================================

import math
import pytest
import numpy as np

from main import (
    ema_filter,
    weinberg_stride,
    is_valid_step,
    process_pdr,
    DeviceState,
    ImuSampleSchema,
)


# ---------------------------------------------------------------------------
# Test 1: EMA filter converges towards target
# ---------------------------------------------------------------------------
def test_ema_filter_convergence():
    """EMA filter output converges to the new value over time."""
    prev = 0.0
    target = 10.0
    fc = 3.2
    dt = 0.01

    val = prev
    for _ in range(200):
        val = ema_filter(target, val, fc, dt)

    # After 2 seconds at 100 Hz the filter should be within 1% of target
    assert abs(val - target) < 0.5, f"EMA did not converge: {val}"


# ---------------------------------------------------------------------------
# Test 2: EMA alpha is correct for fc=3.2, dt=0.01
# ---------------------------------------------------------------------------
def test_ema_alpha_formula():
    """alpha = 1 - exp(-2*pi*3.2*0.01) ≈ 0.1835."""
    fc = 3.2; dt = 0.01
    expected_alpha = 1.0 - math.exp(-2.0 * math.pi * fc * dt)
    # Cross-check by running one step manually
    prev = 5.0; new_val = 10.0
    result = ema_filter(new_val, prev, fc, dt)
    manual = prev + expected_alpha * (new_val - prev)
    assert abs(result - manual) < 1e-9, f"EMA formula mismatch: {result} vs {manual}"


# ---------------------------------------------------------------------------
# Test 3: Weinberg stride clamping
# ---------------------------------------------------------------------------
def test_weinberg_stride_clamping():
    """Stride is always clamped to [0.25, 1.40]."""
    # Near-zero swing → clamp to min
    assert weinberg_stride(0.001) == pytest.approx(0.25)
    # Very large swing → clamp to max
    assert weinberg_stride(1000.0) == pytest.approx(1.40)


# ---------------------------------------------------------------------------
# Test 4: Weinberg stride formula at typical swing
# ---------------------------------------------------------------------------
def test_weinberg_stride_formula():
    """L = 0.47 * swing^0.25, typical swing ~5 m/s²."""
    swing    = 5.0
    expected = 0.47 * (swing ** 0.25)
    result   = weinberg_stride(swing)
    assert abs(result - expected) < 1e-6, f"Weinberg formula wrong: {result}"
    assert 0.25 <= result <= 1.40


# ---------------------------------------------------------------------------
# Test 5: Step validity — all conditions must pass simultaneously
# ---------------------------------------------------------------------------
def test_is_valid_step_all_conditions():
    """is_valid_step returns False if any condition fails."""
    # Construct a buffer that would normally pass conditions 2–5:
    import random
    rng = np.random.default_rng(42)
    buf = list(9.8 + rng.normal(0, 2.0, 40))   # std~2, mean~9.8

    a_max = max(buf) + 1.0   # ensure condition 2 passes
    a_min = min(buf)
    dt_ok = 0.5              # condition 1: > 0.35

    # Should pass
    assert is_valid_step(a_max, a_min, buf, dt_ok), "Expected True"

    # Fail condition 1: dt_since_last too short
    assert not is_valid_step(a_max, a_min, buf, 0.1), "Condition 1 should fail"

    # Fail condition 4: artificially low std buffer
    flat_buf = [9.8] * 40
    assert not is_valid_step(a_max, 9.79, flat_buf, dt_ok), "Condition 4 should fail"


# ---------------------------------------------------------------------------
# Test 6: PDR integration — heading advances with gyro input
# ---------------------------------------------------------------------------
def test_pdr_heading_integration():
    """Heading should change when gz is non-zero over many samples."""
    state   = DeviceState()
    state.bias_calibrated = True   # skip calibration phase
    state.last_ts = 0.0

    # Feed 100 samples with gz=0.1 rad/s, dt=0.01 s → heading += 0.001 per step
    samples = []
    for i in range(100):
        s = ImuSampleSchema(
            ts=i * 10,
            ax=0.1, ay=0.0, az=9.8,
            gx=0.0, gy=0.0, gz=0.1
        )
        samples.append(s)

    process_pdr(state, samples)

    # Heading should be roughly 0.1 * (100 * 0.01) = 0.1 rad (with EMA lag)
    assert abs(state.heading) > 0.01, f"Heading did not change: {state.heading}"
    assert state.heading < 0.5,       f"Heading suspiciously large: {state.heading}"
