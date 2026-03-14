# TRAKN — Product Requirements Document
**Version:** 1.0  
**Date:** March 2026  
**Author:** Majd (Senior Design Project 2 — Qatar University, Computer Engineering)  
**Status:** Active Development  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Project File Schema](#3-project-file-schema)
4. [Hardware Specification — BW16 Wearable Tag](#4-hardware-specification--bw16-wearable-tag)
5. [Mathematics and Algorithms](#5-mathematics-and-algorithms)
6. [Component 1 — BW16 Firmware (Arduino/C++)](#6-component-1--bw16-firmware-arduinoc)
7. [Component 2 — FastAPI Backend (Python)](#7-component-2--fastapi-backend-python)
8. [Component 3 — Web Mapping Tool](#8-component-3--web-mapping-tool)
9. [Component 4 — Android RTT Mapping App](#9-component-4--android-rtt-mapping-app)
10. [Component 5 — Parent Mobile Application](#10-component-5--parent-mobile-application)
11. [Infrastructure and Deployment](#11-infrastructure-and-deployment)
12. [Security Layer](#12-security-layer)
13. [API Reference](#13-api-reference)
14. [Database Schema](#14-database-schema)
15. [Testing Strategy](#15-testing-strategy)

---

## 1. Executive Summary

**TRAKN** is a real-time indoor child localization system designed for large public venues such as shopping malls, hospitals, airports, and convention centers. A child wears a compact IoT device (the "tag") on their belt. If separated from their parent, the parent opens the TRAKN mobile application to see their child's position plotted in real time on the venue floor map.

### Core Technical Approach

The system fuses two complementary positioning methods:

| Method | Strength | Weakness |
|---|---|---|
| **PDR (IMU-based)** | High update rate (100 Hz), no infrastructure dependency, tracks motion continuously | Drifts over time — error accumulates with each step |
| **Wi-Fi RSSI positioning** | Absolute position reference, drift-free | Noisy, slow (~1–2 Hz), affected by obstacles |

Sensor fusion via a **Kalman filter** combines both: PDR provides continuous high-frequency position updates while Wi-Fi RSSI corrections prevent drift accumulation.

### Accuracy Targets

| Condition | Target Accuracy |
|---|---|
| Open area, ≥4 APs visible | ≤ 2.0 m CEP (50th percentile) |
| Cluttered environment | ≤ 4.0 m CEP |
| Pure PDR (Wi-Fi lost, <30 s) | ≤ 3.0 m cumulative drift |

---

## 2. System Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    TRAKN System                         │
│                                                         │
│  ┌──────────┐      HTTPS POST       ┌────────────────┐  │
│  │  BW16    │ ─────────────────────▶│   FastAPI      │  │
│  │  Tag     │  (venue Wi-Fi)        │   Backend      │  │
│  │          │                       │   (GCP VM)     │  │
│  │ MPU6050  │                       │                │  │
│  │ (IMU)    │                       │  ┌──────────┐  │  │
│  │          │                       │  │ Kalman   │  │  │
│  │ Wi-Fi    │                       │  │ Fusion   │  │  │
│  │ Scanner  │                       │  │ Engine   │  │  │
│  └──────────┘                       │  └──────────┘  │  │
│                                     │  ┌──────────┐  │  │
│  ┌──────────┐      WSS Push         │  │PostgreSQL│  │  │
│  │ Parent   │◀─────────────────────│  │   DB     │  │  │
│  │  App     │                       │  └──────────┘  │  │
│  │(Flutter) │                       └────────────────┘  │
│  └──────────┘                              ▲            │
│                                            │            │
│  ┌──────────┐    Calibration Data          │            │
│  │ Android  │─────────────────────────────┘            │
│  │ RTT App  │  (AP locations + offsets)                 │
│  └──────────┘                                           │
│                                                         │
│  ┌──────────┐    Map + Grid Config                      │
│  │  Web     │─────────────────────────────┘            │
│  │ Mapping  │  (floor plan, grid points,                │
│  │  Tool    │   path loss calibration)                  │
│  └──────────┘                                           │
└─────────────────────────────────────────────────────────┘
```

### Data Flow Summary

1. BW16 tag collects IMU data (100 Hz) + scans Wi-Fi RSSI (~1 Hz)
2. Packets are sent over venue Wi-Fi via HTTPS POST to backend
3. Backend runs sensor fusion (PDR + RSSI Kalman filter)
4. Fused position is stored in PostgreSQL and pushed to parent app via WebSocket
5. Parent app renders position on floor plan map in real time

---

## 3. Project File Schema

```
trakn/
│
├── firmware/                          # BW16 Arduino firmware
│   ├── trakn_tag/
│   │   ├── trakn_tag.ino             # Main firmware entry point
│   │   ├── imu.h / imu.cpp           # MPU6050 driver
│   │   ├── wifi_scanner.h / .cpp     # RSSI scan + packet builder
│   │   ├── wifi_conn.h / .cpp        # Venue Wi-Fi connection + reconnect
│   │   ├── http_client.h / .cpp      # HTTPS POST to backend
│   │   └── config.h                  # SSID, server IP, device MAC, timing
│
├── backend/                           # Python FastAPI backend (single-process)
│   ├── main.py                        # ALL logic in one file (FastAPI app)
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx/
│       └── nginx.conf                 # TLS termination, reverse proxy
│
├── web-mapping-tool/                  # Browser-based venue setup tool
│   ├── index.html
│   ├── app.js                         # Floor plan upload, grid generation,
│   │                                  # path loss calibration, AP radio map
│   ├── style.css
│   └── assets/
│
├── android-rtt-app/                   # Android AP localization tool
│   ├── app/src/main/
│   │   ├── MainActivity.kt
│   │   ├── RttScanner.kt             # One-sided RTT ranging
│   │   ├── MapView.kt                # Floor plan + intersection overlay
│   │   └── ApiClient.kt             # Syncs AP pins to backend
│   └── build.gradle
│
├── parent-app/                        # Flutter cross-platform parent app
│   ├── lib/
│   │   ├── main.dart
│   │   ├── screens/
│   │   │   ├── home_screen.dart
│   │   │   ├── map_screen.dart       # Live floor plan + child marker
│   │   │   └── link_tag_screen.dart # Pair tag MAC → parent account
│   │   ├── services/
│   │   │   ├── websocket_service.dart
│   │   │   └── auth_service.dart
│   │   └── models/
│   │       └── position.dart
│   └── pubspec.yaml
│
├── docs/
│   ├── TRAKN_PRD.md                  # This document
│   ├── DEPLOYMENT.md
│   └── API_REFERENCE.md
│
└── scripts/
    ├── setup_db.sql                   # PostgreSQL schema
    └── generate_grid.py               # Offline grid generation utility
```

---

## 4. Hardware Specification — BW16 Wearable Tag

### 4.1 Microcontroller

| Property | Value |
|---|---|
| Module | Realtek RTL8720DN (BW16) |
| Wi-Fi | Dual-band 2.4 GHz + 5 GHz, 802.11 a/b/g/n |
| BLE | 5.0 |
| Role | Sensor aggregator + data transmitter |
| MAC Address | `24:42:E3:15:E5:72` |
| Network Auth | MAC-registered on venue Wi-Fi (no password needed) |

### 4.2 IMU Sensor

| Property | Value |
|---|---|
| Model | InvenSense MPU6050 |
| Interface | I²C, 400 kHz fast mode, address `0x68` |
| DOF | 6 (3-axis accel + 3-axis gyro) |
| Sampling Rate | 100 Hz (10 ms loop) |
| Accelerometer Range | ±4g → register `ACCEL_CONFIG = 0x08` → 8192 LSB/g |
| Gyroscope Range | ±500°/s → register `GYRO_CONFIG = 0x08` → 65.5 LSB/(°/s) |
| DLPF | 21 Hz → register `CONFIG = 0x04` |
| No magnetometer | MagX/Y/Z fields are zero placeholders |

**Conversion constants (locked — verified in SDP1):**

```
ax_SI = ax_raw × 0.0011978149   (= raw × 9.81 / 8192)   [m/s²]
gz_SI = gz_raw × 0.0002663309   (= raw × π / (180 × 65.5)) [rad/s]
```

### 4.3 Packet Format

The BW16 transmits a JSON packet over HTTPS POST at ~10 Hz (every 100 ms):

```json
{
  "mac": "24:42:E3:15:E5:72",
  "ts": 1712345678901,
  "imu": {
    "ax": 0.034512, "ay": 0.011243, "az": 9.812341,
    "gx": 0.000412, "gy": -0.000234, "gz": 0.002341
  },
  "wifi": [
    { "bssid": "AA:BB:CC:DD:EE:01", "ssid": "VenueWiFi", "rssi": -52, "freq": 5180 },
    { "bssid": "AA:BB:CC:DD:EE:02", "ssid": "VenueWiFi", "rssi": -67, "freq": 2412 },
    { "bssid": "AA:BB:CC:DD:EE:03", "ssid": "VenueWiFi", "rssi": -71, "freq": 5220 },
    { "bssid": "AA:BB:CC:DD:EE:04", "ssid": "VenueWiFi", "rssi": -79, "freq": 2437 }
  ]
}
```

Wi-Fi scan runs in a separate non-blocking cycle. The 4 strongest APs (by RSSI) after Kalman smoothing are included.

---

## 5. Mathematics and Algorithms

### 5.1 PDR — Pedestrian Dead Reckoning

PDR estimates 2D position by integrating detected steps with estimated stride length and heading.

#### 5.1.1 Step Detection

**Acceleration magnitude:**
```
a_mag(t) = √(ax² + ay² + az²)
```

**Exponential Moving Average filter (EMA):**
```
a_filt(t) = a_filt(t-1) + α × (a_mag(t) - a_filt(t-1))
α = 1 - exp(-2π × f_c × dt)    where f_c = 3.2 Hz
```

**Step validity conditions (all must be true):**
```
(1) dt_since_last_step > 0.35 s            (anti-double-count)
(2) a_max_in_window > median(buf) + 2×std(buf)   (adaptive peak threshold)
(3) swing = a_max - a_min > 0.9 × std(buf)       (adaptive swing threshold)
(4) std(buf) > 1.2 m/s²                    (motion — not stationary)
(5) |mean(buf) - 9.8| > 0.4 m/s²           (not gravity-locked)
```

#### 5.1.2 Stride Length Estimation — Weinberg Model

Validated in SDP1 (88 steps, 64 m loop, 3.75% error):

```
L_stride = K_wein × swing^p_wein

K_wein  = 0.47   (calibrated coefficient)
p_wein  = 0.25   (Weinberg exponent)
swing   = a_max - a_min   within detection window
```

Clamped to realistic bounds: `L_stride ∈ [0.25 m, 1.40 m]`

**Optional SVR hybrid (when model trained):**
```
L_stride = 0.5 × L_weinberg + 0.5 × L_svr
```

The SVR uses 20-bin log-histogram features of `a_mag` within the detection window.

#### 5.1.3 Heading Estimation (Gyro Integration)

**Gyro bias calibration (first 2 seconds at rest):**
```
bias_gz = (1/N) × Σ gz(i)    for i = 1..N during calibration window
```

**Heading update:**
```
gz_corrected = gz_raw - bias_gz
gz_filt(t) = gz_filt(t-1) + α × (gz_corrected - gz_filt(t-1))
heading(t) = heading(t-1) + gz_filt(t) × dt
```

#### 5.1.4 2D Position Update (per step)

```
X(t) = X(t-1) + L_stride × cos(heading(t))
Y(t) = Y(t-1) + L_stride × sin(heading(t))
```

---

### 5.2 Wi-Fi RSSI Positioning

#### 5.2.1 Log-Distance Path Loss Model

The fundamental relationship between RSSI and distance:

```
RSSI(d) = RSSI_0 - 10 × n × log10(d / d_0)
```

Where:
- `RSSI_0` = RSSI measured at reference distance `d_0 = 1 m`
- `n` = path loss exponent (environment-dependent)
- `d` = distance from AP to device (meters)

**Inverting for distance:**
```
d = d_0 × 10^((RSSI_0 - RSSI) / (10 × n))
```

**Path loss exponent calibration:**

During AP mapping (Android RTT app), close-range RSSI is captured at known distances. For each AP `i`, `RSSI_0_i` is recorded at 1 m. A per-environment median `n` is estimated from multiple capture points.

Default fallback values by environment type:

| Environment | n |
|---|---|
| Free space (open mall atrium) | 2.0 |
| Mixed indoor (typical mall) | 2.7 |
| Heavy obstruction (walls, shelving) | 3.5 |

**Per-intersection-point RSSI estimation:**

Given AP `i` at coordinates `(xi, yi)` and grid point `j` at `(xj, yj)`:

```
d_ij = √((xj - xi)² + (yj - yi)²)
RSSI_estimated_ij = RSSI_0_i - 10 × n × log10(d_ij)
```

This is computed offline during venue setup and stored in the database as the **radio map**.

#### 5.2.2 RSSI Kalman Filter (per AP, real-time)

Smooths noisy RSSI measurements before positioning:

```
State vector:    x̂_k = [RSSI_k]        (scalar per AP)
Prediction:      x̂_k|k-1 = x̂_k-1
                 P_k|k-1  = P_k-1 + Q      (Q = process noise = 2 dBm²)
Update:          K_k = P_k|k-1 / (P_k|k-1 + R)   (R = measurement noise = 9 dBm²)
                 x̂_k = x̂_k|k-1 + K_k × (z_k - x̂_k|k-1)
                 P_k = (1 - K_k) × P_k|k-1
```

#### 5.2.3 Trilateration (Weighted Least Squares)

Given smoothed distances `d_i` from `N` APs (minimum N=3):

```
minimize: Σ_i  w_i × ((X - xi)² + (Y - yi)² - d_i²)²

w_i = 1 / d_i²    (inverse-distance weighting: nearby APs trusted more)
```

This is solved iteratively (Gauss-Newton or gradient descent).

**Distance from smoothed RSSI:**
```
d_i = d_0 × 10^((RSSI_0_i - RSSI_smoothed_i) / (10 × n))
```

#### 5.2.4 Intersection Point Scoring

The trilateration gives a continuous estimate `(X_tri, Y_tri)`. We then find the best matching grid intersection point using a scoring function:

For each candidate intersection point `j = (xj, yj)`:

```
Score_j = Σ_i  w_i × exp(- (d_measured_ij - d_estimated_ij)² / (2 × σ²))

d_measured_ij  = distance implied by live RSSI from AP i to tag
d_estimated_ij = distance from radio map (AP i to grid point j)
σ              = 3.0 m   (scoring tolerance)
w_i            = 1 / d_measured_ij²
```

The highest-scoring intersection point `j*` is the Wi-Fi position estimate:

```
(X_wifi, Y_wifi) = (x_j*, y_j*)
```

---

### 5.3 Sensor Fusion — Extended Kalman Filter

The fusion combines PDR (continuous, drifting) and Wi-Fi positioning (intermittent, bounded error).

#### 5.3.1 State Vector

```
State: x = [X, Y, heading, v_x, v_y]ᵀ    (5-dimensional)

X, Y      = 2D position (meters)
heading   = orientation angle (radians)
v_x, v_y  = velocity components (m/s)
```

#### 5.3.2 Process Model (IMU Prediction Step)

Triggered every IMU packet (~100 Hz):

```
X(t)       = X(t-1) + v_x × dt
Y(t)       = Y(t-1) + v_y × dt
heading(t) = heading(t-1) + gz_filt × dt
v_x(t)     = v_x(t-1) + ax_filt × dt     (optional — omit if noisy)
v_y(t)     = v_y(t-1) + ay_filt × dt

On step detection:
  v_x = L_stride × cos(heading) / step_period
  v_y = L_stride × sin(heading) / step_period
```

**Process noise covariance Q:**
```
Q = diag([σ_x², σ_y², σ_θ², σ_vx², σ_vy²])
  = diag([0.01, 0.01, 0.005, 0.1, 0.1])
```

#### 5.3.3 Observation Model (Wi-Fi Correction Step)

Triggered when a valid Wi-Fi position is available (~1 Hz):

```
Observation vector: z = [X_wifi, Y_wifi]ᵀ
Observation matrix: H = [1 0 0 0 0;
                          0 1 0 0 0]

Measurement noise: R = diag([σ_wifi_x², σ_wifi_y²])
                     = diag([4.0, 4.0])     (2 m std in each axis, squared)
```

**Kalman update:**
```
Innovation:    y_inn = z - H × x̂
S = H × P × Hᵀ + R
K = P × Hᵀ × S⁻¹           (Kalman gain)
x̂ = x̂ + K × y_inn           (state update)
P = (I - K × H) × P          (covariance update)
```

#### 5.3.4 Adaptive Wi-Fi Trust

When Wi-Fi RSSI variance is high (multipath, crowding), reduce measurement trust:

```
If std(RSSI_samples) > 5 dBm:
    R = diag([9.0, 9.0])    (less trust)
Else:
    R = diag([4.0, 4.0])    (normal trust)
```

---

### 5.4 Bayesian Grid Update (Optional Enhancement)

Inspired by Horn (2021), for environments where a full probability map is maintained:

```
P(location = j | measurements) ∝ P(measurements | location = j) × P(location = j)
```

For each grid cell `j`, update:
```
P_j ← P_j × Π_i  p(RSSI_i | d_ij)

p(RSSI | d) = N(μ(d), σ(d))
μ(d) = RSSI_0 - 10n × log10(d)          (log-distance model mean)
σ(d) = σ_0 + σ_m × (d - d_0) × exp(-β × (d-d_0))   (Horn Eq. 3 adapted)
```

This is computationally heavier than EKF but provides a full probability distribution over positions. Implement as an optional mode in the backend.

---

## 6. Component 1 — BW16 Firmware (Arduino/C++)

### 6.1 Firmware Responsibilities

- Initialize MPU6050 with verified register configuration
- Read IMU at 100 Hz
- Scan Wi-Fi RSSI in non-blocking background cycle (~1 Hz)
- Connect to venue Wi-Fi (MAC-authenticated, no password)
- Transmit JSON packets via HTTPS POST to backend
- Handle reconnection gracefully (buffer IMU during dropout)
- Never stop IMU collection due to network issues

### 6.2 Key Firmware Parameters (`config.h`)

```cpp
// Device Identity
#define DEVICE_MAC      "24:42:E3:15:E5:72"

// Network
#define VENUE_SSID      "VenueWiFi"         // Set per venue
#define SERVER_HOST     "trakn.duckdns.org"
#define SERVER_PORT     443
#define API_ENDPOINT    "/api/v1/gateway/packet"

// IMU Timing
#define IMU_SAMPLE_HZ   100                  // 10 ms loop
#define WIFI_SCAN_HZ    1                    // 1000 ms scan cycle
#define POST_BATCH_SIZE 10                   // Send every 10 IMU packets

// IMU Registers (locked)
#define MPU6050_ADDR    0x68
#define GYRO_CONFIG     0x1B
#define ACCEL_CONFIG    0x1C
#define CONFIG          0x1A
#define PWR_MGMT_1      0x6B

// Conversion constants (locked, verified SDP1)
#define ACCEL_SCALE     0.0011978149f        // raw → m/s²
#define GYRO_SCALE      0.0002663309f        // raw → rad/s

// Security
#define API_KEY         "trakn-hw-<device_token>"  // Per-device API key
```

### 6.3 Firmware Loop Architecture

```
setup():
  1. I²C begin (400 kHz)
  2. Wake MPU6050 (PWR_MGMT_1 = 0x00)
  3. Configure registers (GYRO, ACCEL, DLPF)
  4. Connect to venue Wi-Fi (retry loop with 1 s backoff)
  5. Confirm server reachability (GET /health)

loop() — runs every 10 ms:
  1. Read 14 bytes from MPU6050 (burst I²C read)
  2. Convert raw → SI units
  3. Append to JSON batch buffer
  4. Every 1000 ms: trigger non-blocking Wi-Fi scan
     - Store top 4 BSSIDs by RSSI
  5. Every POST_BATCH_SIZE packets: POST batch to server
  6. On POST failure: buffer locally, retry next cycle
  7. If Wi-Fi disconnected: reconnect in background, keep IMU running
```

### 6.4 Wi-Fi Scan Strategy

The BW16 scans passively for beacon frames. Scan cycle:

```cpp
// Non-blocking: called from main loop, results available next cycle
void triggerWifiScan() {
    WiFi.scanNetworks(async=true);
}

void collectScanResults() {
    int n = WiFi.scanComplete();
    if (n <= 0) return;
    // Sort by RSSI, keep top 4
    // Store: BSSID, SSID, RSSI, frequency
    WiFi.scanDelete();
}
```

Expected scan cycle: 300–600 ms (dual-band, BW16).

---

## 7. Component 2 — FastAPI Backend (Python)

### 7.1 Overview

The entire backend lives in **`main.py`** — a single FastAPI file containing all routes, sensor fusion logic, database models, and WebSocket management. This mirrors the "single file" philosophy of the Arduino firmware for simplicity.

### 7.2 Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| Framework | FastAPI (async) |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 async |
| DB Driver | asyncpg |
| Auth | JWT (python-jose) + API key header |
| TLS | Nginx reverse proxy (Let's Encrypt) |
| Containerization | Docker + Docker Compose |
| WebSocket | FastAPI native (Starlette) |

### 7.3 `main.py` Structure

```python
# ─────────────────────────────────────────────────────────
# TRAKN Backend — main.py
# All sensor fusion, positioning, and API logic in one file.
# ─────────────────────────────────────────────────────────

# SECTION 1 — Imports & Configuration
# SECTION 2 — Database Models (SQLAlchemy)
# SECTION 3 — Pydantic Schemas (request/response validation)
# SECTION 4 — Kalman Filter State (in-memory, per device)
# SECTION 5 — PDR Logic (step detection, stride estimation)
# SECTION 6 — RSSI Positioning Logic (log-distance, trilateration)
# SECTION 7 — Sensor Fusion (EKF)
# SECTION 8 — Intersection Point Scoring
# SECTION 9 — API Routes
# SECTION 10 — WebSocket Manager
# SECTION 11 — Startup / Shutdown Lifecycle
```

### 7.4 In-Memory State (per device)

```python
@dataclass
class DeviceState:
    # EKF state
    x: np.ndarray      # [X, Y, heading, vx, vy]
    P: np.ndarray      # 5×5 covariance matrix

    # PDR
    heading: float
    step_count: int
    last_step_time: float
    buf_t: deque
    buf_a: deque
    gyro_bias: float
    bias_calibrated: bool
    a_mag_filt: float
    gz_filt: float

    # RSSI Kalman (per AP)
    rssi_state: dict   # {bssid: (rssi_estimate, variance)}

    # Timing
    last_ts: float
```

`device_states: dict[str, DeviceState] = {}`  — keyed by MAC address.

### 7.5 Core Fusion Algorithm (pseudocode)

```python
async def process_packet(packet: SensorPacket, db: AsyncSession):
    state = get_or_create_state(packet.mac)
    dt = compute_dt(state, packet.ts)

    # ── Step 1: IMU prediction (100 Hz) ──────────────────
    a_mag = sqrt(ax² + ay² + az²)
    state.a_mag_filt = ema_filter(a_mag, state.a_mag_filt, fc=3.2, dt)
    
    if not state.bias_calibrated:
        accumulate_gyro_bias(gz, state)
    else:
        gz_corrected = gz - state.gyro_bias
        state.gz_filt = ema_filter(gz_corrected, state.gz_filt, fc=3.2, dt)
        state.heading += state.gz_filt * dt

    # EKF prediction step
    F = build_transition_matrix(state.heading, dt)
    state.x = F @ state.x
    state.P = F @ state.P @ F.T + Q

    # ── Step 2: Step detection ────────────────────────────
    if detect_step(state):
        stride = weinberg_stride(swing, K=0.47, p=0.25)
        state.x[0] += stride * cos(state.heading)   # X
        state.x[1] += stride * sin(state.heading)   # Y
        state.step_count += 1

    # ── Step 3: RSSI positioning (when Wi-Fi data present) ─
    if packet.wifi and len(packet.wifi) >= 3:
        # Kalman-smooth each AP RSSI
        for ap in packet.wifi:
            ap.rssi = rssi_kalman_update(state, ap.bssid, ap.rssi)

        # Estimate distances via log-distance model
        distances = {}
        for ap in packet.wifi:
            ap_meta = await get_ap_metadata(db, ap.bssid)
            if ap_meta:
                d = d0 * 10**((ap_meta.rssi_ref - ap.rssi) / (10 * ap_meta.n))
                distances[ap.bssid] = (ap_meta.x, ap_meta.y, d)

        # Trilateration → Wi-Fi position
        if len(distances) >= 3:
            x_wifi, y_wifi = weighted_trilateration(distances)

            # Intersection point scoring
            best_point = score_intersection_points(
                distances, venue_grid_points, sigma=3.0
            )

            # EKF correction step
            z = np.array([best_point.x, best_point.y])
            innovation = z - H @ state.x
            S = H @ state.P @ H.T + R
            K = state.P @ H.T @ np.linalg.inv(S)
            state.x = state.x + K @ innovation
            state.P = (I - K @ H) @ state.P

    # ── Step 4: Persist and push ──────────────────────────
    position = Position(
        device_mac=packet.mac,
        x=state.x[0], y=state.x[1],
        heading=state.heading,
        step_count=state.step_count,
        ts=packet.ts
    )
    await db.add(position)
    await db.commit()
    await websocket_manager.broadcast(packet.mac, position)
```

### 7.6 API Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/gateway/packet` | API Key | Receive sensor packet from tag |
| `GET` | `/health` | None | Health check |
| `POST` | `/api/v1/auth/register` | None | Parent account creation |
| `POST` | `/api/v1/auth/login` | None | Returns JWT |
| `POST` | `/api/v1/devices/link` | JWT | Link tag MAC to parent account |
| `GET` | `/api/v1/devices/{mac}/position` | JWT | Latest position (REST poll) |
| `WSS` | `/ws/position/{device_id}` | JWT (query param) | Real-time position stream |
| `POST` | `/api/v1/venue/floor-plan` | Admin JWT | Upload floor plan |
| `POST` | `/api/v1/venue/grid-points` | Admin JWT | Upload grid intersection points |
| `POST` | `/api/v1/venue/ap` | Admin JWT | Register AP location + metadata |
| `GET` | `/api/v1/venue/ap` | JWT | List all APs for a venue |
| `GET` | `/api/v1/venue/radio-map` | JWT | Get pre-computed radio map |

---

## 8. Component 3 — Web Mapping Tool

### 8.1 Purpose

A browser-based single-page application used by venue staff or the system operator during the **one-time setup phase**. It is not shown to parents.

### 8.2 Features

#### Feature 1 — Floor Plan Upload
- Upload a PNG/SVG/PDF floor plan
- Set scale (e.g., drag two points → enter real-world distance in meters)
- The tool computes pixels-per-meter ratio

#### Feature 2 — Wall Definition
- Click-and-drag to draw walls on the floor plan
- Walls are stored as line segments `{x1, y1, x2, y2}` in venue coordinate space
- Used for: visual display + future path constraint in positioning

#### Feature 3 — Grid Generation
- Generate 0.5 m × 0.5 m grid of intersection points covering the walkable area
- Automatically exclude points that fall under wall segments or shelving
- Each point assigned `{id, x, y}` in venue meters
- Display as cyan dots (matching Horn 2021 approach)
- Export grid as JSON → POST to `/api/v1/venue/grid-points`

#### Feature 4 — Path Loss Calibration
- Upload reference RSSI capture file (from Android RTT app)
- Fit path loss exponent `n` per AP using least-squares regression:
  ```
  RSS_measured = RSSI_0 - 10 × n × log10(d)
  n = argmin Σ (RSSI_measured_k - RSSI_0 + 10n × log10(d_k))²
  ```
- Display fitted curve vs. raw measurements
- Store per-AP: `RSSI_0`, `n`, `frequency_band`

#### Feature 5 — Radio Map Preview
- After APs are localized (from Android app), display:
  - Estimated RSSI at each grid point per AP (color-coded heatmap)
  - Vectors from each AP to each grid point
- Allows operator to visually verify the radio map before going live

### 8.3 Tech Stack
- Vanilla HTML + JavaScript + Canvas API (or Leaflet.js for map rendering)
- No build toolchain required — single `index.html` deployable from any web server
- Communicates with backend via Fetch API

---

## 9. Component 4 — Android RTT Mapping App

### 9.1 Purpose

Used **once per venue setup** by the operator to walk the space and pin the physical locations of Wi-Fi access points onto the floor plan. Utilizes Android's one-sided RTT API (available from Android 12).

### 9.2 Core Features

#### Tab 1 — AP Discovery
- Display all APs detected in the environment via `WifiManager.startScan()`
- For each AP: SSID, BSSID (MAC), RSSI, frequency, estimated one-sided RTT distance
- One-sided RTT implemented via:
  ```kotlin
  RangingRequest.Builder()
      .addNon80211mcCapableAccessPoint(scanResult)
      .build()
  ```
- RTT offset subtraction:
  ```
  d_corrected = d_raw - offset_OUI
  offset_OUI ≈ 2550 m   (typical; calibrate per AP manufacturer OUI)
  ```
  The offset is looked up from a bundled OUI-to-offset table, or manually set.

#### Tab 2 — Map + Pin Placement
- Display floor plan with 0.5 m grid intersection points (loaded from backend)
- Overlay: current distance to selected AP (live, updates every ~500 ms)
- Operator selects an AP from Tab 1, walks toward it, watches distance decrease
- When distance < 1 m (or operator judges proximity sufficient), taps the map at the estimated AP location
- On tap: saves AP metadata `{bssid, ssid, rssi_at_1m, n, x, y, freq}` to backend
  ```
  POST /api/v1/venue/ap
  ```

### 9.3 RTT Offset Calibration

For each new AP model encountered:
1. Stand at a measured distance (e.g., 3 m)
2. Record raw RTT distance
3. offset = raw_distance - 3.0 m
4. Verify at 5 m, 10 m — confirm offset is consistent
5. Store offset in the OUI lookup table

### 9.4 Tech Stack
- Kotlin, Android 12+ (API level 31+)
- Requires: `ACCESS_FINE_LOCATION`, `CHANGE_WIFI_STATE` permissions
- `WifiRttManager` API for ranging
- Renders floor plan via `Canvas` or `MPAndroidChart` overlay
- Retrofit 2 for backend API calls

---

## 10. Component 5 — Parent Mobile Application

### 10.1 Purpose

The consumer-facing application. A parent downloads this app, creates an account, links their child's TRAKN tag (by entering the device ID printed on the tag), and sees their child's real-time location on the venue map.

### 10.2 Tech Stack

- **Flutter** (iOS + Android from one codebase)
- WebSocket client: `web_socket_channel`
- Map rendering: `flutter_map` (Leaflet-based, supports custom floor plan tiles)
- HTTP: `dio`
- Auth: JWT stored in `flutter_secure_storage`

### 10.3 User Flows

#### Flow 1 — Account Creation
```
Open App → "Create Account" → Enter name, email, password
→ POST /api/v1/auth/register → Verify email → Login
```

#### Flow 2 — Link Tag
```
Home Screen → "Add Child" → Enter tag ID (printed on device)
→ POST /api/v1/devices/link {mac, child_name, parent_jwt}
→ Tag now appears in parent's device list
```

#### Flow 3 — View Child Location
```
Home Screen → Tap child card → Map Screen opens
→ WSS /ws/position/{device_id}?token=<jwt>
→ Floor plan loads (from /api/v1/venue/floor-plan)
→ Animated marker shows child's real-time position
→ Updates at ≥4 Hz via WebSocket push
```

#### Flow 4 — Alert / Geofence (V2)
```
(Future) Parent defines a safe zone on the map
If child exits zone → push notification sent via FCM
```

### 10.4 Map Screen UI

- Clean floor plan (no grid, no AP markers, no technical overlay)
- Child represented as an animated pulse marker (color-coded per child)
- Distance from parent's last known location (if parent shares GPS)
- "Find" button — highlights shortest walking path to child
- Battery level indicator for the tag

---

## 11. Infrastructure and Deployment

### 11.1 Server

| Property | Value |
|---|---|
| Provider | Google Cloud Platform |
| VM Type | e2-micro |
| Network Tier | Premium |
| Static IP | `35.238.189.188` |
| OS | Ubuntu 22.04 LTS |
| Firewall | TCP 443 inbound open; port 8000 internal only |

### 11.2 Domains and TLS

| Endpoint | URL |
|---|---|
| REST API | `https://trakn.duckdns.org/api/v1/...` |
| WebSocket | `wss://trakn.duckdns.org/ws/position/{device_id}` |
| Health | `https://trakn.duckdns.org/health` |

TLS: Let's Encrypt via Certbot + DuckDNS for dynamic DNS pointing to `35.238.189.188`.

### 11.3 Docker Compose Layout

```yaml
services:
  nginx:
    image: nginx:alpine
    ports: ["443:443", "80:80"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - certbot certs:/etc/letsencrypt
    depends_on: [api]

  api:
    build: .
    expose: ["8000"]          # Internal only
    environment:
      - DATABASE_URL=postgresql+asyncpg://trakn:password@db:5432/trakndb
      - JWT_SECRET=<strong_random_secret>
      - DEVICE_API_KEY_SALT=<random_salt>
    depends_on: [db]

  db:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
    environment:
      - POSTGRES_DB=trakndb
      - POSTGRES_USER=trakn
      - POSTGRES_PASSWORD=<strong_password>
```

---

## 12. Security Layer

### 12.1 Device Authentication (Tag → Server)

Each BW16 tag has a pre-provisioned **API key** embedded in firmware at flash time:

```
Header: X-TRAKN-API-Key: trakn-hw-<sha256(mac + salt)>
```

The backend validates this key on every `POST /api/v1/gateway/packet`. Unknown MAC addresses are rejected with `403 Forbidden`.

```python
# Validation in main.py
def validate_device_key(mac: str, key: str) -> bool:
    expected = "trakn-hw-" + sha256(mac.encode() + DEVICE_SALT.encode()).hexdigest()[:24]
    return hmac.compare_digest(key, expected)
```

### 12.2 Parent Authentication (App → Server)

- JWT-based auth (HS256, 7-day expiry, refreshable)
- Passwords: bcrypt hashed (cost factor 12), never stored in plain text
- JWT claims: `{sub: user_id, role: "parent", exp: ...}`

### 12.3 WebSocket Authentication

JWT passed as query parameter on connection:
```
wss://trakn.duckdns.org/ws/position/{device_id}?token=<jwt>
```

On connect: validate JWT, verify `device_id` belongs to this parent's account. Reject with `4001 Unauthorized` if not.

### 12.4 Rate Limiting

| Endpoint | Limit |
|---|---|
| `POST /gateway/packet` | 20 req/s per device MAC |
| `POST /auth/login` | 5 req/min per IP |
| `POST /auth/register` | 3 req/min per IP |
| All other endpoints | 60 req/min per JWT |

Implemented via `slowapi` (FastAPI rate limiting middleware).

### 12.5 Transport Security

- All endpoints: HTTPS/WSS only (HTTP redirected to HTTPS at Nginx)
- TLS 1.2 minimum (TLS 1.3 preferred)
- HSTS header: `max-age=31536000; includeSubDomains`
- BW16 firmware: TLS enabled on HTTPS POST (server cert validation disabled by default for embedded constraints — use certificate pinning in production)

### 12.6 Data Isolation

- Each parent account can only query positions for their own linked tags
- Enforced at the API layer: every position query includes `WHERE device_mac IN (parent's linked devices)`
- Admin-only endpoints (`/venue/*`) protected by separate `role: "admin"` JWT claim

### 12.7 Nginx Security Headers

```nginx
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options DENY;
add_header X-XSS-Protection "1; mode=block";
add_header Content-Security-Policy "default-src 'self'";
add_header Strict-Transport-Security "max-age=31536000" always;
```

---

## 13. API Reference

### 13.1 POST `/api/v1/gateway/packet`

**Auth:** `X-TRAKN-API-Key: <device_key>`

**Request body:**
```json
{
  "mac": "24:42:E3:15:E5:72",
  "ts": 1712345678901,
  "imu": {
    "ax": 0.034512, "ay": 0.011243, "az": 9.812341,
    "gx": 0.000412, "gy": -0.000234, "gz": 0.002341
  },
  "wifi": [
    { "bssid": "AA:BB:CC:DD:EE:01", "ssid": "Venue", "rssi": -52, "freq": 5180 }
  ]
}
```

**Response `200`:**
```json
{ "status": "ok", "position": { "x": 12.4, "y": 7.8, "heading": 1.57 } }
```

### 13.2 WebSocket `/ws/position/{device_id}`

**Message pushed by server (≥4 Hz):**
```json
{
  "device_id": "24:42:E3:15:E5:72",
  "x": 12.4,
  "y": 7.8,
  "heading": 1.57,
  "step_count": 143,
  "confidence": 0.87,
  "ts": 1712345679001
}
```

`confidence` is derived from EKF covariance trace: `1 / (1 + trace(P[0:2,0:2]))`

---

## 14. Database Schema

```sql
-- Venues
CREATE TABLE venues (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    floor_plan_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Grid intersection points
CREATE TABLE grid_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id UUID REFERENCES venues(id),
    x FLOAT NOT NULL,    -- meters in venue coordinate space
    y FLOAT NOT NULL,
    is_walkable BOOLEAN DEFAULT TRUE
);
CREATE INDEX ON grid_points(venue_id);

-- Access Points
CREATE TABLE access_points (
    bssid TEXT PRIMARY KEY,
    venue_id UUID REFERENCES venues(id),
    ssid TEXT,
    x FLOAT,             -- mapped location in venue meters
    y FLOAT,
    rssi_ref FLOAT,      -- RSSI_0 at 1 m
    path_loss_n FLOAT,   -- fitted path loss exponent
    freq_mhz INT,
    rtt_offset_m FLOAT,  -- one-sided RTT offset (meters)
    oui TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Radio map (precomputed RSSI estimates per AP per grid point)
CREATE TABLE radio_map (
    ap_bssid TEXT REFERENCES access_points(bssid),
    grid_point_id UUID REFERENCES grid_points(id),
    estimated_rssi FLOAT,
    estimated_distance_m FLOAT,
    PRIMARY KEY (ap_bssid, grid_point_id)
);

-- Users (parents)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Devices (tags)
CREATE TABLE devices (
    mac TEXT PRIMARY KEY,
    venue_id UUID REFERENCES venues(id),
    owner_id UUID REFERENCES users(id),
    child_name TEXT,
    api_key_hash TEXT NOT NULL,
    registered_at TIMESTAMPTZ DEFAULT NOW()
);

-- Position history
CREATE TABLE positions (
    id BIGSERIAL PRIMARY KEY,
    device_mac TEXT REFERENCES devices(mac),
    x FLOAT NOT NULL,
    y FLOAT NOT NULL,
    heading FLOAT,
    step_count INT,
    confidence FLOAT,
    ts TIMESTAMPTZ NOT NULL
);
CREATE INDEX ON positions(device_mac, ts DESC);
-- Retain last 24 hours only (run nightly):
-- DELETE FROM positions WHERE ts < NOW() - INTERVAL '24 hours';
```

---

## 15. Testing Strategy

### 15.1 Firmware Testing
- Bench test: MPU6050 reads at 100 Hz, verify JSON output over USB serial
- Wi-Fi scan test: confirm top-4 BSSID selection in a multi-AP environment
- Reconnection test: unplug router, verify IMU keeps running, data resumes on reconnect

### 15.2 Backend Unit Tests
- `test_step_detection.py` — feed synthetic IMU signals, verify step count
- `test_weinberg.py` — known swing values → expected stride lengths
- `test_kalman_rssi.py` — noisy RSSI sequence → verify smoothing
- `test_trilateration.py` — known AP positions + distances → verify XY recovery
- `test_ekf_fusion.py` — PDR-only drift vs. corrected fusion over 60 s
- `test_auth.py` — API key validation, JWT issue/verify, unauthorized access rejection

### 15.3 Integration Testing
- End-to-end: BW16 → POST → backend → WebSocket → parent app receives position
- Walk test: 64 m rectangular loop (replicate SDP1 test) — verify ≤5% distance error
- Fusion test: walk 30 m with ≥4 APs visible — verify position error ≤4 m at each step

### 15.4 Accuracy Benchmarks

| Test Scenario | Pass Criterion |
|---|---|
| 88-step loop, PDR only | Distance error ≤ 5% (SDP1 baseline) |
| Static position, 4 APs | RSSI position error ≤ 3 m |
| Walking, fusion active | 95th percentile error ≤ 4 m |
| Wi-Fi dropout for 15 s | PDR drift ≤ 2 m |
| Wi-Fi dropout for 30 s | PDR drift ≤ 4 m |

---

*End of TRAKN PRD v1.0*

---

## 16. Automated Testing Specification

This section defines the complete test file layout, test cases per phase, and acceptance criteria for each task in `tasks.json`.

### 16.1 Test Directory Structure

```
backend/
└── tests/
    ├── conftest.py              # Shared fixtures: DB session, device state, synthetic walk data
    ├── fixtures/
    │   ├── sdp1_walk.json       # 88-step SDP1 walk replay data (ax, ay, az, gz per sample)
    │   ├── ap_grid_4ap.json     # 4 APs + 20×20 grid for Wi-Fi tests
    │   └── synthetic_rssi.csv   # Distance-RSSI pairs for path loss fitting
    ├── test_pdr.py              # Phase 4 — PDR engine (6 tests)
    ├── test_wifi.py             # Phase 5 — Wi-Fi positioning (5 tests)
    ├── test_fusion.py           # Phase 6 — Sensor fusion / EKF (4 tests)
    ├── test_auth.py             # Phase 3 — Auth routes (4 tests)
    ├── test_devices.py          # Phase 3 — Device linking (2 tests)
    ├── test_api.py              # Phase 6 — Gateway endpoint (3 tests)
    ├── test_websocket.py        # Phase 3 — WebSocket (2 tests)
    ├── test_device_state.py     # Phase 4 — In-memory state (2 tests)
    └── test_security.py         # Phase 10 — Security layer (4 tests)
```

---

### 16.2 `conftest.py` — Shared Fixtures

```python
# conftest.py
import pytest, json, numpy as np
from httpx import AsyncClient, ASGITransport
from main import app, get_db, DeviceState

TEST_MAC = "24:42:E3:15:E5:72"
TEST_EMAIL = "parent@test.com"
TEST_PASS = "TestPass123!"

@pytest.fixture
def sdp1_walk():
    """Load 88-step SDP1 walk replay data."""
    with open("tests/fixtures/sdp1_walk.json") as f:
        return json.load(f)

@pytest.fixture
def ap_grid():
    """4 APs at known positions with 20x20 grid."""
    with open("tests/fixtures/ap_grid_4ap.json") as f:
        return json.load(f)

@pytest.fixture
def fresh_state():
    """Fresh DeviceState with default initialization."""
    return DeviceState(mac=TEST_MAC)

@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

@pytest.fixture
async def auth_token(client):
    await client.post("/api/v1/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASS})
    r = await client.post("/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASS})
    return r.json()["access_token"]
```

---

### 16.3 `test_pdr.py` — PDR Engine Tests

**Covers tasks:** TASK-24 through TASK-30

```python
# test_pdr.py

def test_ema_filter():
    """EMA converges to target value; alpha formula correct."""
    # Feed constant 10.0 to filter initialized at 0.0
    # After 100 samples at dt=0.01 s, fc=3.2 Hz → must converge to 9.5+
    # Acceptance: final value > 9.5

def test_gyro_bias():
    """Bias calibration accumulates 200 samples, computes mean."""
    # Feed 200 samples of gz=0.05 rad/s
    # After 200th sample: bias_calibrated==True, gyro_bias≈0.05
    # Acceptance: |state.gyro_bias - 0.05| < 0.001

def test_heading_integration():
    """Constant gz integrates to correct heading over time."""
    # Feed gz=0.1 rad/s for 10 s at 100 Hz (post-calibration)
    # Acceptance: |final_heading - 1.0| < 0.1 rad

def test_step_detection():
    """Step counter matches SDP1 ground truth ±5%."""
    # Replay sdp1_walk fixture (88-step walk)
    # Acceptance: 84 ≤ detected_steps ≤ 92
    # Also: flat stationary signal (std < 0.5) → 0 steps detected

def test_weinberg():
    """Weinberg formula and clamp behavior."""
    # K=0.47, p=0.25: weinberg(swing=3.0) ≈ 0.688 m (within 0.5%)
    # Clamp low: weinberg(swing=0.001) == 0.25
    # Clamp high: weinberg(swing=100) == 1.40

def test_full_walk():
    """Full PDR pipeline on SDP1 replay data meets distance target."""
    # Replay all 88-step samples through process_imu_sample()
    # Acceptance: |total_distance - 64| / 64 < 0.05 (5% error)
    # Acceptance: trajectory has 4 corners (check heading range spans 4 quadrants)
```

**Run command:** `pytest tests/test_pdr.py -v`  
**Pass criteria:** 6/6 tests green

---

### 16.4 `test_wifi.py` — Wi-Fi Positioning Tests

**Covers tasks:** TASK-31 through TASK-36

```python
# test_wifi.py

def test_rssi_kalman():
    """RSSI Kalman smoother reduces variance and rejects outliers."""
    # Feed alternating [-50, -70] × 20 → smoothed value in [-62, -58]
    # Feed single outlier -100 into stable -50 stream → output shifts < 5 dBm

def test_log_distance():
    """Log-distance model: exact reference → 1.0 m. Known offset → correct distance."""
    # rssi_to_distance(-50, rssi_ref=-50, n=2.7) == 1.0
    # rssi_to_distance(-60, rssi_ref=-50, n=2.7) ≈ 2.67 (within 1%)
    # Clamp: distance never < 0.5 m or > 100 m

def test_trilateration():
    """Weighted trilateration recovers known position from exact distances."""
    # 4 APs at (0,0), (10,0), (0,10), (10,10)
    # True position (5,5): distances = [7.07, 7.07, 7.07, 7.07]
    # Acceptance: |estimated - (5,5)| < 0.1 m
    # With 10% random distance noise: error < 2 m

def test_intersection_scoring():
    """Correct grid point scores highest."""
    # Place tag at grid point (4.0, 6.0). 4 APs with known radio map.
    # Generate RSSI readings consistent with (4.0, 6.0)
    # Acceptance: score at (4.0, 6.0) ≥ 2× score of any neighboring point

def test_radio_map_build():
    """Radio map populates correct estimated RSSI for all grid points."""
    # Add 1 AP at (5,5) with rssi_ref=-50, n=2.7 to a 10×10 m venue
    # After compute_radio_map(): radio_map has entries for all grid points
    # RSSI at (5,5) ≈ -50. RSSI at (5,12.5) < -50 (farther → weaker)
```

**Run command:** `pytest tests/test_wifi.py -v`  
**Pass criteria:** 5/5 tests green

---

### 16.5 `test_fusion.py` — EKF Sensor Fusion Tests

**Covers tasks:** TASK-37 through TASK-40

```python
# test_fusion.py

def test_ekf_prediction():
    """EKF prediction: covariance grows, position stable with no motion."""
    # No movement input (gz=0, no steps). Run 100 prediction steps.
    # Acceptance: state X,Y drift < 0.01 m. trace(P) increases monotonically.

def test_ekf_correction():
    """Wi-Fi correction pulls state toward measurement."""
    # Initialize state at (0,0). Drift PDR to (3,0).
    # Apply Wi-Fi correction z=(0,0) with R=diag([4,4]).
    # Acceptance: post-correction |X| < 1.5. trace(P) decreases.

def test_adaptive_r():
    """Measurement noise R increases with high RSSI variance."""
    # Stable RSSI stream (std < 2 dBm) → R = diag([4,4])
    # Noisy RSSI stream (std > 5 dBm) → R = diag([9,9])

def test_confidence():
    """Confidence score behaves correctly with fusion state."""
    # Fresh state → confidence < 0.3
    # After 5 Wi-Fi corrections → confidence > 0.7
    # confidence = 1 / (1 + trace(P[0:2, 0:2]))
```

**Run command:** `pytest tests/test_fusion.py -v`  
**Pass criteria:** 4/4 tests green

---

### 16.6 `test_auth.py` — Authentication Tests

**Covers tasks:** TASK-20, TASK-21

```python
# test_auth.py

async def test_register_and_login():
    """Full register → login flow returns valid JWT."""
    # POST /register with new email/password → 201
    # POST /login with same credentials → 200, access_token present
    # Decode JWT: sub == user_id, token_type == "bearer"

async def test_login_wrong_password():
    """Wrong password returns 401."""
    # POST /login with correct email, wrong password → 401

async def test_jwt_required():
    """Protected endpoint rejects missing/invalid JWT."""
    # GET /api/v1/devices with no token → 401
    # GET with malformed token → 401

async def test_bcrypt_storage():
    """Password is hashed, not stored plaintext."""
    # Register user, query DB directly
    # Acceptance: password_hash != original password
    # bcrypt.checkpw(password, stored_hash) == True
```

**Run command:** `pytest tests/test_auth.py -v`  
**Pass criteria:** 4/4 tests green

---

### 16.7 `test_security.py` — Security Layer Tests

**Covers tasks:** TASK-60 through TASK-64

```python
# test_security.py

def test_device_api_key():
    """API key validation: correct → 200, wrong → 403, replay with wrong MAC → 403."""
    # Generate key for MAC "24:42:E3:15:E5:72"
    # POST packet with correct key → 200
    # POST with key[-1] mutated → 403
    # POST with correct key but MAC "AA:BB:CC:DD:EE:FF" in body → 403

async def test_rate_limiting():
    """Gateway rate limit: 20 req/s enforced per MAC."""
    # Send 25 requests in < 1 s from same MAC
    # Acceptance: at least 1 response is 429
    # After 1 s pause: requests succeed again

async def test_data_isolation():
    """Parent cannot access another parent's device position."""
    # Create two parent accounts and link one device each
    # Parent A requests position for Parent B's device → 403
    # Parent A requests own device → 200

async def test_input_validation():
    """Malformed packets rejected with 422."""
    # ax=99999 (outside ±50 range) → 422
    # MAC "not-a-mac" (invalid format) → 422
    # Missing imu field → 422
    # rssi=50 (positive, invalid) → 422
```

**Run command:** `pytest tests/test_security.py -v`  
**Pass criteria:** 4/4 tests green

---

### 16.8 `test_api.py` — Gateway API Tests

**Covers task:** TASK-40

```python
# test_api.py

async def test_gateway_packet_valid():
    """Valid packet ingested, returns position."""
    # POST /api/v1/gateway/packet with correct API key + valid IMU/Wi-Fi data
    # Acceptance: 200, response body contains {status: ok, position: {x, y, heading}}

async def test_gateway_packet_bad_key():
    """Invalid API key rejected."""
    # POST with wrong X-TRAKN-API-Key header → 403

async def test_gateway_packet_no_wifi():
    """Packet without Wi-Fi field still returns PDR-only position."""
    # POST packet with imu data but wifi: [] → 200, position returned (PDR only)
```

**Run command:** `pytest tests/test_api.py -v`  
**Pass criteria:** 3/3 tests green

---

### 16.9 `test_websocket.py` — WebSocket Tests

**Covers task:** TASK-22

```python
# test_websocket.py

async def test_websocket_auth():
    """Valid JWT connects; invalid JWT rejected."""
    # Connect wss://…/ws/position/<mac>?token=<valid_jwt> → 101 Switching Protocols
    # Connect with ?token=bad_token → 4001 Unauthorized close code

async def test_websocket_receives_position():
    """Position pushed after gateway packet processed."""
    # Connect WebSocket for device MAC
    # POST gateway packet for same MAC
    # Acceptance: WebSocket receives position message within 500 ms
    # Message contains: device_id, x, y, heading, confidence, ts
```

**Run command:** `pytest tests/test_websocket.py -v`  
**Pass criteria:** 2/2 tests green

---

### 16.10 Acceptance Criteria Summary Table

| Task ID | Component | Test File | Test Function | Pass Criterion |
|---|---|---|---|---|
| TASK-01 | Scaffolding | shell | `ls` check | All dirs exist |
| TASK-08 | DB Schema | shell | `\dt` count | 7 tables |
| TASK-18 | Backend core | shell | `curl /health` | HTTP 200 |
| TASK-20 | Auth | test_auth.py | test_register_and_login | JWT returned |
| TASK-22 | WebSocket | test_websocket.py | test_websocket_auth | 101 on valid, 4001 on invalid |
| TASK-24 | PDR | test_pdr.py | test_ema_filter | Converges > 9.5 |
| TASK-25 | PDR | test_pdr.py | test_gyro_bias | bias within 0.001 |
| TASK-26 | PDR | test_pdr.py | test_heading_integration | ±0.1 rad accuracy |
| TASK-27 | PDR | test_pdr.py | test_step_detection | 84–92 steps |
| TASK-28 | PDR | test_pdr.py | test_weinberg | ±0.5% accuracy + clamp |
| TASK-30 | PDR | test_pdr.py | test_full_walk | ≤5% distance error |
| TASK-31 | Wi-Fi | test_wifi.py | test_rssi_kalman | <5 dBm outlier shift |
| TASK-32 | Wi-Fi | test_wifi.py | test_log_distance | ±1% accuracy |
| TASK-33 | Wi-Fi | test_wifi.py | test_trilateration | <0.1 m exact, <2 m noisy |
| TASK-34 | Wi-Fi | test_wifi.py | test_intersection_scoring | Correct point ≥2× score |
| TASK-35 | Wi-Fi | test_wifi.py | test_radio_map_build | RSSI decays with distance |
| TASK-37 | Fusion | test_fusion.py | test_ekf_correction | Post-correction < 1.5 m |
| TASK-38 | Fusion | test_fusion.py | test_adaptive_r | R switches correctly |
| TASK-39 | Fusion | test_fusion.py | test_confidence | 0.3 fresh → 0.7 corrected |
| TASK-40 | API | test_api.py | test_gateway_packet_valid | 200 + position |
| TASK-60 | Security | test_security.py | test_device_api_key | 200 / 403 correct |
| TASK-61 | Security | test_security.py | test_rate_limiting | 429 on exceed |
| TASK-62 | Security | test_security.py | test_data_isolation | 403 cross-account |
| TASK-64 | Security | test_security.py | test_input_validation | 422 on bad data |
| TASK-69 | E2E | physical | walk benchmark | ≤4 m 95th percentile |
| TASK-70 | E2E | physical | dropout test | <4 m drift at 30 s |

---

### 16.11 Running the Full Test Suite

```bash
# From backend/ directory:

# Install test deps
pip install pytest pytest-asyncio httpx

# Run all unit tests
pytest tests/ -v --tb=short

# Run by phase
pytest tests/test_pdr.py -v          # Phase 4 — PDR
pytest tests/test_wifi.py -v         # Phase 5 — Wi-Fi
pytest tests/test_fusion.py -v       # Phase 6 — Fusion
pytest tests/test_auth.py -v         # Phase 3 — Auth
pytest tests/test_security.py -v     # Phase 10 — Security

# Run with coverage report
pytest tests/ --cov=main --cov-report=term-missing

# Expected result: 30/30 unit tests passing
```

**Minimum coverage target:** 80% line coverage on `main.py` before deployment.

---

*End of TRAKN PRD v1.0 — Sections 1–16*
