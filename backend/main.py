# =============================================================================
# TRAKN Backend — main.py
# Single-file FastAPI backend for TRAKN indoor child localization system.
# PRD Reference: TRAKN_PRD.md v1.0
# =============================================================================

# SECTION 1 — Imports & Configuration
# SECTION 2 — Database Models (SQLAlchemy)
# SECTION 3 — Pydantic Schemas
# SECTION 4 — In-Memory Device State
# SECTION 5 — PDR Logic
# SECTION 6 — RSSI Positioning Logic
# SECTION 7 — EKF Sensor Fusion
# SECTION 8 — Intersection Point Scoring
# SECTION 9 — API Routes
# SECTION 10 — WebSocket Manager
# SECTION 11 — Startup/Shutdown Lifecycle

# =============================================================================
# SECTION 1 — Imports & Configuration
# =============================================================================

import os
import re
import hmac
import hashlib
import logging
from math import exp, pi, cos, sin, sqrt
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
import asyncio

import numpy as np
from scipy.optimize import minimize

from fastapi import (
    FastAPI, Depends, HTTPException, status,
    WebSocket, WebSocketDisconnect, Request, Header
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pydantic import BaseModel, field_validator, model_validator
from pydantic import constr

from jose import jwt, JWTError

from passlib.context import CryptContext

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import (
    Column, String, Float, Boolean, Integer, BigInteger,
    DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import sqlalchemy as sa

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s"
)
logger = logging.getLogger("trakn")

# ---------------------------------------------------------------------------
# Environment / Secrets
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://trakn:password@db:5432/trakndb"
)
JWT_SECRET: str = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION")
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRY_DAYS: int = 7

DEVICE_API_KEY_SALT: str = os.getenv("DEVICE_API_KEY_SALT", "CHANGE_SALT_IN_PRODUCTION")

# ---------------------------------------------------------------------------
# Rate limiter (slowapi)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

# =============================================================================
# SECTION 2 — Database Models (SQLAlchemy)
# =============================================================================

Base = declarative_base()


class Venue(Base):
    __tablename__ = "venues"

    id             = Column(PG_UUID(as_uuid=True), primary_key=True,
                            server_default=sa.text("gen_random_uuid()"))
    name           = Column(String(255), nullable=False)
    floor_plan_url = Column(Text)
    created_at     = Column(DateTime(timezone=True), server_default=sa.func.now())


class GridPoint(Base):
    __tablename__ = "grid_points"

    id          = Column(PG_UUID(as_uuid=True), primary_key=True,
                         server_default=sa.text("gen_random_uuid()"))
    venue_id    = Column(PG_UUID(as_uuid=True),
                         ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    x           = Column(Float, nullable=False)
    y           = Column(Float, nullable=False)
    is_walkable = Column(Boolean, nullable=False, default=True)


class AccessPoint(Base):
    __tablename__ = "access_points"

    bssid        = Column(String(17), primary_key=True)
    venue_id     = Column(PG_UUID(as_uuid=True),
                          ForeignKey("venues.id", ondelete="CASCADE"), nullable=False)
    ssid         = Column(String(255))
    x            = Column(Float, nullable=False)
    y            = Column(Float, nullable=False)
    rssi_ref     = Column(Float, nullable=False, default=-40.0)
    path_loss_n  = Column(Float, nullable=False, default=2.0)
    freq_mhz     = Column(Integer, nullable=False, default=2412)
    rtt_offset_m = Column(Float, nullable=False, default=0.0)
    oui          = Column(String(8))
    updated_at   = Column(DateTime(timezone=True), server_default=sa.func.now())


class RadioMap(Base):
    __tablename__ = "radio_map"

    ap_bssid              = Column(String(17),
                                   ForeignKey("access_points.bssid", ondelete="CASCADE"),
                                   primary_key=True)
    grid_point_id         = Column(PG_UUID(as_uuid=True),
                                   ForeignKey("grid_points.id", ondelete="CASCADE"),
                                   primary_key=True)
    estimated_rssi        = Column(Float, nullable=False)
    estimated_distance_m  = Column(Float, nullable=False)


class User(Base):
    __tablename__ = "users"

    id            = Column(PG_UUID(as_uuid=True), primary_key=True,
                           server_default=sa.text("gen_random_uuid()"))
    email         = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=sa.func.now())


class Device(Base):
    __tablename__ = "devices"

    mac           = Column(String(17), primary_key=True)
    venue_id      = Column(PG_UUID(as_uuid=True),
                           ForeignKey("venues.id", ondelete="SET NULL"), nullable=True)
    owner_id      = Column(PG_UUID(as_uuid=True),
                           ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    child_name    = Column(String(255), nullable=False)
    api_key_hash  = Column(String(255), nullable=False)
    registered_at = Column(DateTime(timezone=True), server_default=sa.func.now())


class Position(Base):
    __tablename__ = "positions"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    device_mac = Column(String(17),
                        ForeignKey("devices.mac", ondelete="CASCADE"), nullable=False)
    x          = Column(Float, nullable=False)
    y          = Column(Float, nullable=False)
    heading    = Column(Float, nullable=False, default=0.0)
    step_count = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0.0)
    ts         = Column(DateTime(timezone=True), server_default=sa.func.now())


# =============================================================================
# SECTION 3 — Pydantic Schemas
# =============================================================================

MAC_REGEX = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')


def validate_mac(v: str) -> str:
    if not MAC_REGEX.match(v):
        raise ValueError("Invalid MAC address format")
    return v.upper()


class ImuSampleSchema(BaseModel):
    ts: int            # milliseconds since device boot
    ax: float          # m/s²
    ay: float
    az: float
    gx: float          # rad/s
    gy: float
    gz: float

    @field_validator("ax", "ay", "az")
    @classmethod
    def check_accel(cls, v: float) -> float:
        if not (-50.0 <= v <= 50.0):
            raise ValueError("Accelerometer value out of range [-50, 50]")
        return v

    @field_validator("gx", "gy", "gz")
    @classmethod
    def check_gyro(cls, v: float) -> float:
        if not (-35.0 <= v <= 35.0):
            raise ValueError("Gyro value out of range [-35, 35]")
        return v


class WifiEntrySchema(BaseModel):
    bssid: str
    ssid:  str
    rssi:  int
    freq:  int

    @field_validator("bssid")
    @classmethod
    def check_bssid(cls, v: str) -> str:
        return validate_mac(v)

    @field_validator("rssi")
    @classmethod
    def check_rssi(cls, v: int) -> int:
        if not (-120 <= v <= 0):
            raise ValueError("RSSI out of range [-120, 0]")
        return v


class GatewayPacketSchema(BaseModel):
    mac:     str
    samples: List[ImuSampleSchema]
    wifi:    List[WifiEntrySchema] = []

    @field_validator("mac")
    @classmethod
    def check_mac(cls, v: str) -> str:
        return validate_mac(v)


class RegisterSchema(BaseModel):
    email:    str
    password: str

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginSchema(BaseModel):
    email:    str
    password: str


class LinkDeviceSchema(BaseModel):
    mac:        str
    child_name: str
    venue_id:   Optional[str] = None

    @field_validator("mac")
    @classmethod
    def check_mac(cls, v: str) -> str:
        return validate_mac(v)


class VenueCreateSchema(BaseModel):
    name:          str
    floor_plan_url: Optional[str] = None


class GridPointSchema(BaseModel):
    venue_id:    str
    x:           float
    y:           float
    is_walkable: bool = True


class AccessPointSchema(BaseModel):
    bssid:       str
    venue_id:    str
    ssid:        Optional[str] = None
    x:           float
    y:           float
    rssi_ref:    float = -40.0
    path_loss_n: float = 2.0
    freq_mhz:    int   = 2412
    rtt_offset_m: float = 0.0
    oui:         Optional[str] = None

    @field_validator("bssid")
    @classmethod
    def check_bssid(cls, v: str) -> str:
        return validate_mac(v)


class PositionResponseSchema(BaseModel):
    mac:        str
    x:          float
    y:          float
    heading:    float
    step_count: int
    confidence: float
    ts:         str


# =============================================================================
# SECTION 4 — In-Memory Device State
# =============================================================================

BIAS_COLLECT_SAMPLES: int = 200   # 2 s at 100 Hz
BUF_SIZE: int = 40                 # 0.4 s rolling window


@dataclass
class DeviceState:
    # EKF state vector [X, Y, heading, vx, vy]
    x: np.ndarray = field(
        default_factory=lambda: np.zeros(5, dtype=float)
    )
    # EKF covariance matrix 5×5
    P: np.ndarray = field(
        default_factory=lambda: np.eye(5, dtype=float) * 10.0
    )
    heading:     float = 0.0
    step_count:  int   = 0
    last_step_time: float = 0.0  # wall-clock seconds

    # Rolling accel-magnitude buffer (0.4 s)
    buf_t: deque = field(default_factory=lambda: deque(maxlen=BUF_SIZE))
    buf_a: deque = field(default_factory=lambda: deque(maxlen=BUF_SIZE))

    # Gyro bias (rad/s) — estimated during first 200 samples
    gyro_bias:       float = 0.0
    bias_calibrated: bool  = False
    bias_samples:    list  = field(default_factory=list)

    # EMA-filtered values
    a_mag_filt: float = 9.8
    gz_filt:    float = 0.0

    # Per-AP Kalman RSSI state {bssid: {"rssi_est": float, "P": float}}
    rssi_state: dict = field(default_factory=dict)

    # Last packet timestamp (seconds, derived from device boot millis)
    last_ts: float = 0.0


# Global in-memory store: MAC → DeviceState
_device_states: Dict[str, DeviceState] = {}


def get_device_state(mac: str) -> DeviceState:
    mac = mac.upper()
    if mac not in _device_states:
        _device_states[mac] = DeviceState()
    return _device_states[mac]


# =============================================================================
# SECTION 5 — PDR Logic
# =============================================================================

def ema_filter(new_val: float, prev_val: float, fc: float, dt: float) -> float:
    """Exponential Moving Average filter.
    alpha = 1 - exp(-2*pi*fc*dt)
    """
    if dt <= 0:
        return prev_val
    alpha = 1.0 - exp(-2.0 * pi * fc * dt)
    return prev_val + alpha * (new_val - prev_val)


def weinberg_stride(swing: float) -> float:
    """L_stride = K_wein * swing**p_wein, clamped to [STRIDE_MIN, STRIDE_MAX]."""
    K_WEIN    = 0.47
    P_WEIN    = 0.25
    STRIDE_MIN = 0.25
    STRIDE_MAX = 1.40
    stride = K_WEIN * (swing ** P_WEIN)
    return max(STRIDE_MIN, min(STRIDE_MAX, stride))


def is_valid_step(
    a_max: float,
    a_min: float,
    buf: list,
    dt_since_last: float
) -> bool:
    """Return True if all 5 step-validity conditions are satisfied.

    Conditions:
    1. dt_since_last > 0.35 s
    2. a_max > median(buf) + 2*std(buf)
    3. swing = a_max - a_min > 0.9 * std(buf)
    4. std(buf) > 1.2 m/s²
    5. |mean(buf) - 9.8| > 0.4 m/s²
    """
    if len(buf) < 2:
        return False

    arr    = np.array(buf, dtype=float)
    median = float(np.median(arr))
    std    = float(np.std(arr))
    mean   = float(np.mean(arr))
    swing  = a_max - a_min

    c1 = dt_since_last > 0.35
    c2 = a_max > median + 2.0 * std
    c3 = swing > 0.9 * std
    c4 = std > 1.2
    c5 = abs(mean - 9.8) > 0.4

    return c1 and c2 and c3 and c4 and c5


def process_pdr(state: DeviceState, samples: list) -> None:
    """Run PDR over a batch of IMU samples, updating state in place.

    Args:
        state:   DeviceState (mutated in place)
        samples: list of ImuSampleSchema (ordered by ts ascending)
    """
    EMA_FC_ACCEL = 3.2   # Hz cutoff for accel EMA
    EMA_FC_GYRO  = 3.2   # Hz cutoff for gyro EMA

    for s in samples:
        current_ts = s.ts / 1000.0  # ms → seconds
        dt = current_ts - state.last_ts if state.last_ts > 0 else 0.01
        dt = max(1e-6, min(dt, 0.5))   # clamp unreasonable dt values
        state.last_ts = current_ts

        # --- Gyro bias calibration (first 200 samples) ---
        if not state.bias_calibrated:
            state.bias_samples.append(s.gz)
            if len(state.bias_samples) >= BIAS_COLLECT_SAMPLES:
                state.gyro_bias = float(np.mean(state.bias_samples))
                state.bias_calibrated = True
                logger.info("Gyro bias calibrated: %.6f rad/s", state.gyro_bias)
            # Still process the sample during calibration
            gz_corrected = s.gz - state.gyro_bias
        else:
            gz_corrected = s.gz - state.gyro_bias

        # --- Accel magnitude ---
        a_mag = sqrt(s.ax**2 + s.ay**2 + s.az**2)

        # --- EMA filters ---
        state.a_mag_filt = ema_filter(a_mag, state.a_mag_filt, EMA_FC_ACCEL, dt)
        state.gz_filt    = ema_filter(gz_corrected, state.gz_filt, EMA_FC_GYRO, dt)

        # --- Heading integration ---
        state.heading += state.gz_filt * dt

        # --- Rolling buffer ---
        state.buf_t.append(current_ts)
        state.buf_a.append(state.a_mag_filt)

        # --- Step detection ---
        if len(state.buf_a) >= 4:
            buf_list = list(state.buf_a)
            a_max    = max(buf_list)
            a_min    = min(buf_list)
            dt_since = current_ts - state.last_step_time

            if is_valid_step(a_max, a_min, buf_list, dt_since):
                swing          = a_max - a_min
                stride         = weinberg_stride(swing)
                state.x[0]    += stride * cos(state.heading)
                state.x[1]    += stride * sin(state.heading)
                state.x[2]     = state.heading
                state.step_count += 1
                state.last_step_time = current_ts


# =============================================================================
# SECTION 6 — RSSI Positioning Logic
# =============================================================================

def rssi_kalman_update(rssi_state: dict, bssid: str, rssi_meas: float) -> float:
    """1-D Kalman filter for RSSI smoothing.

    Q = 2.0 (process noise), R = 9.0 (measurement noise).
    Returns filtered RSSI estimate.
    """
    Q = 2.0
    R = 9.0

    if bssid not in rssi_state:
        rssi_state[bssid] = {"rssi_est": rssi_meas, "P": R}

    est   = rssi_state[bssid]["rssi_est"]
    P_est = rssi_state[bssid]["P"]

    # Predict
    P_pred = P_est + Q

    # Update
    K        = P_pred / (P_pred + R)
    est_new  = est + K * (rssi_meas - est)
    P_new    = (1.0 - K) * P_pred

    rssi_state[bssid]["rssi_est"] = est_new
    rssi_state[bssid]["P"]        = P_new

    return est_new


def rssi_to_distance(rssi: float, rssi_ref: float, n: float) -> float:
    """Log-distance path loss model.

    d = d0 * 10**((rssi_ref - rssi) / (10 * n)), d0 = 1.0 m
    Clamped to [0.5, 100.0] metres.
    """
    d0 = 1.0
    exponent = (rssi_ref - rssi) / (10.0 * n)
    d = d0 * (10.0 ** exponent)
    return max(0.5, min(100.0, d))


def weighted_trilateration(
    ap_positions: List[tuple],
    distances:    List[float]
) -> Optional[tuple]:
    """Weighted trilateration via scipy.optimize.minimize.

    Weights are inverse-distance squared (1/d²).
    Returns (x, y) or None if fewer than 3 APs.
    """
    if len(ap_positions) < 3:
        if len(ap_positions) == 2:
            # Simple midpoint weighted by distances
            w0 = 1.0 / max(distances[0]**2, 1e-6)
            w1 = 1.0 / max(distances[1]**2, 1e-6)
            total = w0 + w1
            x = (w0 * ap_positions[0][0] + w1 * ap_positions[1][0]) / total
            y = (w0 * ap_positions[0][1] + w1 * ap_positions[1][1]) / total
            return (x, y)
        return None

    weights = np.array([1.0 / max(d**2, 1e-6) for d in distances])
    aps     = np.array(ap_positions)
    dists   = np.array(distances)

    def objective(pos):
        dx   = aps[:, 0] - pos[0]
        dy   = aps[:, 1] - pos[1]
        pred = np.sqrt(dx**2 + dy**2)
        diff = pred - dists
        return float(np.sum(weights * diff**2))

    # Initial guess: weighted centroid
    x0_init = float(np.sum(weights * aps[:, 0]) / np.sum(weights))
    y0_init = float(np.sum(weights * aps[:, 1]) / np.sum(weights))
    x0 = np.array([x0_init, y0_init])

    result = minimize(objective, x0, method="Nelder-Mead",
                      options={"xatol": 0.01, "fatol": 0.01, "maxiter": 500})
    if result.success or result.fun < 1.0:
        return (float(result.x[0]), float(result.x[1]))
    return None


# =============================================================================
# SECTION 7 — EKF Sensor Fusion
# =============================================================================

# EKF process noise
Q_EKF = np.diag([0.01, 0.01, 0.005, 0.1, 0.1])

# Observation matrix H = [[1,0,0,0,0],[0,1,0,0,0]]
H_EKF = np.array([[1, 0, 0, 0, 0],
                  [0, 1, 0, 0, 0]], dtype=float)

# Measurement noise (normal vs noisy Wi-Fi)
R_NORMAL = np.diag([4.0, 4.0])
R_NOISY  = np.diag([9.0, 9.0])


def build_transition_matrix(heading: float, dt: float) -> np.ndarray:
    """Build 5×5 state transition matrix F.

    State: [X, Y, heading, vx, vy]
    X(k+1)       = X(k) + vx(k)*dt
    Y(k+1)       = Y(k) + vy(k)*dt
    heading(k+1) = heading(k)
    vx(k+1)      = vx(k)
    vy(k+1)      = vy(k)
    """
    F = np.eye(5, dtype=float)
    F[0, 3] = dt   # X ← vx
    F[1, 4] = dt   # Y ← vy
    return F


def ekf_predict(state: DeviceState, dt: float) -> None:
    """EKF prediction step (mutates state in place)."""
    F           = build_transition_matrix(state.x[2], dt)
    state.x     = F @ state.x
    state.x[2]  = state.heading   # override heading from PDR
    state.P     = F @ state.P @ F.T + Q_EKF


def ekf_correct(state: DeviceState, z: np.ndarray, rssi_std: float) -> None:
    """EKF correction step given Wi-Fi position measurement z = [X, Y].

    Uses R_NOISY when rssi_std > 5, R_NORMAL otherwise.
    Mutates state in place.
    """
    R = R_NOISY if rssi_std > 5.0 else R_NORMAL

    innovation = z - H_EKF @ state.x
    S          = H_EKF @ state.P @ H_EKF.T + R
    K          = state.P @ H_EKF.T @ np.linalg.inv(S)

    state.x = state.x + K @ innovation
    I        = np.eye(5, dtype=float)
    state.P  = (I - K @ H_EKF) @ state.P


def get_confidence(P: np.ndarray) -> float:
    """confidence = 1 / (1 + trace(P[0:2, 0:2]))."""
    return 1.0 / (1.0 + float(np.trace(P[0:2, 0:2])))


# =============================================================================
# SECTION 8 — Intersection Point Scoring
# =============================================================================

def score_intersection_points(
    candidate_points: List[tuple],
    ap_positions:     List[tuple],
    d_measured:       List[float]
) -> Optional[tuple]:
    """Score candidate intersection points and return the best one.

    Score_j = Σ_i w_i * exp(-(d_meas_ij - d_est_ij)² / (2 * sigma²))
    where sigma = 3.0, w_i = 1 / d_meas²

    Returns best (x, y) or None.
    """
    if not candidate_points or not ap_positions:
        return None

    SIGMA = 3.0
    sigma2_x2 = 2.0 * SIGMA**2

    best_score = -1.0
    best_point = None

    for (cx, cy) in candidate_points:
        score = 0.0
        for i, (ax, ay) in enumerate(ap_positions):
            d_meas = max(d_measured[i], 1e-6)
            d_est  = sqrt((cx - ax)**2 + (cy - ay)**2)
            w_i    = 1.0 / (d_meas**2)
            score += w_i * exp(-((d_meas - d_est)**2) / sigma2_x2)
        if score > best_score:
            best_score = score
            best_point = (cx, cy)

    return best_point


# =============================================================================
# SECTION 9 — API Routes
# =============================================================================

# ---------------------------------------------------------------------------
# Database session factory
# ---------------------------------------------------------------------------
engine        = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire  = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Returns user_id (sub) or raises HTTPException 401."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def generate_api_key(mac: str) -> str:
    """Generate device API key: 'trakn-hw-' + sha256(mac+salt).hexdigest()[:24]."""
    digest = hashlib.sha256((mac + DEVICE_API_KEY_SALT).encode()).hexdigest()
    return "trakn-hw-" + digest[:24]


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def validate_api_key_hmac(provided: str, stored_hash: str) -> bool:
    """Constant-time comparison of API key against stored hash."""
    provided_hash = hash_api_key(provided)
    return hmac.compare_digest(provided_hash, stored_hash)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TRAKN Backend",
    description="Indoor child localization system API",
    version="1.0.0"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Dependency: current user (JWT)
# ---------------------------------------------------------------------------
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    user_id = decode_access_token(credentials.credentials)
    result  = await db.execute(
        sa.select(User).where(User.id == sa.text(f"'{user_id}'::uuid"))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Dependency: device ownership check
# ---------------------------------------------------------------------------
async def verify_device_ownership(
    mac:          str,
    current_user: User,
    db:           AsyncSession
) -> Device:
    result = await db.execute(
        sa.select(Device).where(Device.mac == mac.upper())
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if str(device.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Not your device")
    return device


# ---------------------------------------------------------------------------
# GET /api/v1/health
# Proxied by Nginx at /api/v1/* — /health alone is blocked at the reverse proxy.
# ---------------------------------------------------------------------------
@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/v1/auth/register
# Rate limit: 3/min per IP
# ---------------------------------------------------------------------------
@app.post("/api/v1/auth/register", status_code=201)
@limiter.limit("3/minute")
async def register(
    request: Request,
    body:    RegisterSchema,
    db:      AsyncSession = Depends(get_db)
):
    # Check duplicate email
    result = await db.execute(sa.select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password)
    )
    db.add(user)
    await db.flush()
    return {"user_id": str(user.id)}


# ---------------------------------------------------------------------------
# POST /api/v1/auth/login
# Rate limit: 5/min per IP
# ---------------------------------------------------------------------------
@app.post("/api/v1/auth/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body:    LoginSchema,
    db:      AsyncSession = Depends(get_db)
):
    result = await db.execute(sa.select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# POST /api/v1/devices/link
# JWT required
# ---------------------------------------------------------------------------
@app.post("/api/v1/devices/link")
async def link_device(
    body:         LinkDeviceSchema,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    mac = body.mac.upper()

    # Check if device already linked
    result = await db.execute(sa.select(Device).where(Device.mac == mac))
    existing = result.scalar_one_or_none()
    if existing:
        if str(existing.owner_id) != str(current_user.id):
            raise HTTPException(status_code=409, detail="Device already linked to another user")
        return {"mac": mac, "child_name": existing.child_name}

    api_key      = generate_api_key(mac)
    api_key_hash = hash_api_key(api_key)

    device = Device(
        mac=mac,
        owner_id=current_user.id,
        child_name=body.child_name,
        api_key_hash=api_key_hash,
        venue_id=body.venue_id if body.venue_id else None
    )
    db.add(device)
    await db.flush()
    return {"mac": mac, "child_name": body.child_name, "api_key": api_key}


# ---------------------------------------------------------------------------
# GET /api/v1/devices/{mac}/position
# JWT + ownership check
# ---------------------------------------------------------------------------
@app.get("/api/v1/devices/{mac}/position", response_model=PositionResponseSchema)
async def get_position(
    mac:          str,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    await verify_device_ownership(mac, current_user, db)

    # Get latest position from DB
    result = await db.execute(
        sa.select(Position)
        .where(Position.device_mac == mac.upper())
        .order_by(Position.ts.desc())
        .limit(1)
    )
    pos = result.scalar_one_or_none()

    if pos:
        return PositionResponseSchema(
            mac=mac.upper(),
            x=pos.x, y=pos.y,
            heading=pos.heading,
            step_count=pos.step_count,
            confidence=pos.confidence,
            ts=pos.ts.isoformat()
        )

    # Fall back to in-memory state
    state = get_device_state(mac)
    return PositionResponseSchema(
        mac=mac.upper(),
        x=float(state.x[0]), y=float(state.x[1]),
        heading=state.heading,
        step_count=state.step_count,
        confidence=get_confidence(state.P),
        ts=datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# POST /api/v1/gateway/packet
# Rate limit: 20/s per MAC (using X-TRAKN-API-Key as key)
# API key auth via X-TRAKN-API-Key header
# ---------------------------------------------------------------------------
async def _get_device_by_api_key(
    x_trakn_api_key: str,
    db: AsyncSession
) -> Device:
    """Validate X-TRAKN-API-Key header and return matching Device."""
    if not x_trakn_api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_api_key(x_trakn_api_key)

    result = await db.execute(
        sa.select(Device).where(Device.api_key_hash == key_hash)
    )
    device = result.scalar_one_or_none()

    if not device:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Constant-time validation as extra guard
    if not validate_api_key_hmac(x_trakn_api_key, device.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return device


@app.post("/api/v1/gateway/packet")
@limiter.limit("20/second")
async def gateway_packet(
    request:         Request,
    body:            GatewayPacketSchema,
    x_trakn_api_key: str = Header(alias="X-TRAKN-API-Key", default=""),
    db:              AsyncSession = Depends(get_db)
):
    device = await _get_device_by_api_key(x_trakn_api_key, db)

    # Verify MAC matches the API key's device
    if device.mac.upper() != body.mac.upper():
        raise HTTPException(status_code=403, detail="MAC mismatch for API key")

    mac   = body.mac.upper()
    state = get_device_state(mac)

    # Sort samples by timestamp ascending
    samples = sorted(body.samples, key=lambda s: s.ts)

    # --- PDR step ---
    if samples:
        dt_batch = (samples[-1].ts - samples[0].ts) / 1000.0 if len(samples) > 1 else 0.01
        process_pdr(state, samples)

        # EKF prediction (use median dt within batch)
        dt_predict = max(0.001, dt_batch / max(len(samples), 1))
        for _ in samples:
            ekf_predict(state, dt_predict)
        state.x[2] = state.heading

    # --- Wi-Fi positioning ---
    wifi_position = None
    rssi_std      = 0.0

    if body.wifi:
        # Load known APs from DB
        bssids = [w.bssid.upper() for w in body.wifi]
        result = await db.execute(
            sa.select(AccessPoint).where(AccessPoint.bssid.in_(bssids))
        )
        known_aps: List[AccessPoint] = list(result.scalars().all())

        ap_by_bssid = {ap.bssid.upper(): ap for ap in known_aps}

        ap_positions_list: List[tuple]  = []
        distances_list:    List[float]  = []
        rssi_values:       List[float]  = []

        for w in body.wifi:
            bssid = w.bssid.upper()
            if bssid not in ap_by_bssid:
                continue
            ap = ap_by_bssid[bssid]

            # Kalman-filter the RSSI
            rssi_filt = rssi_kalman_update(state.rssi_state, bssid, float(w.rssi))
            rssi_values.append(rssi_filt)

            dist = rssi_to_distance(rssi_filt, ap.rssi_ref, ap.path_loss_n)
            ap_positions_list.append((ap.x, ap.y))
            distances_list.append(dist)

        if rssi_values:
            rssi_std = float(np.std(rssi_values))

        if len(ap_positions_list) >= 2:
            wifi_position = weighted_trilateration(ap_positions_list, distances_list)

    # --- EKF correction ---
    if wifi_position is not None:
        z = np.array([wifi_position[0], wifi_position[1]], dtype=float)
        ekf_correct(state, z, rssi_std)

    confidence = get_confidence(state.P)

    # --- Persist position to DB ---
    pos_row = Position(
        device_mac=mac,
        x=float(state.x[0]),
        y=float(state.x[1]),
        heading=float(state.x[2]),
        step_count=state.step_count,
        confidence=confidence
    )
    db.add(pos_row)
    await db.flush()

    # --- Broadcast via WebSocket ---
    position_payload = {
        "mac":        mac,
        "x":          float(state.x[0]),
        "y":          float(state.x[1]),
        "heading":    float(state.x[2]),
        "step_count": state.step_count,
        "confidence": confidence,
        "ts":         datetime.now(timezone.utc).isoformat()
    }
    await ws_manager.broadcast(mac, position_payload)

    return {
        "status":   "ok",
        "position": position_payload
    }


# ---------------------------------------------------------------------------
# Venue endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/venue/floor-plan", status_code=201)
async def create_venue(
    body:         VenueCreateSchema,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    venue = Venue(name=body.name, floor_plan_url=body.floor_plan_url)
    db.add(venue)
    await db.flush()
    return {"venue_id": str(venue.id), "name": venue.name}


@app.post("/api/v1/venue/grid-points", status_code=201)
async def create_grid_points(
    body:         List[GridPointSchema],
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    created = []
    for gp in body:
        row = GridPoint(
            venue_id=gp.venue_id,
            x=gp.x,
            y=gp.y,
            is_walkable=gp.is_walkable
        )
        db.add(row)
        created.append(row)
    await db.flush()
    return {"created": len(created)}


@app.post("/api/v1/venue/ap", status_code=201)
async def create_ap(
    body:         AccessPointSchema,
    current_user: User         = Depends(get_current_user),
    db:           AsyncSession = Depends(get_db)
):
    # Upsert: insert or update on bssid PK
    result = await db.execute(
        sa.select(AccessPoint).where(AccessPoint.bssid == body.bssid)
    )
    ap = result.scalar_one_or_none()
    if ap:
        ap.venue_id    = body.venue_id
        ap.ssid        = body.ssid
        ap.x           = body.x
        ap.y           = body.y
        ap.rssi_ref    = body.rssi_ref
        ap.path_loss_n = body.path_loss_n
        ap.freq_mhz    = body.freq_mhz
        ap.rtt_offset_m = body.rtt_offset_m
        ap.oui         = body.oui
    else:
        ap = AccessPoint(
            bssid=body.bssid,
            venue_id=body.venue_id,
            ssid=body.ssid,
            x=body.x,
            y=body.y,
            rssi_ref=body.rssi_ref,
            path_loss_n=body.path_loss_n,
            freq_mhz=body.freq_mhz,
            rtt_offset_m=body.rtt_offset_m,
            oui=body.oui
        )
        db.add(ap)
    await db.flush()
    return {"bssid": body.bssid}


@app.get("/api/v1/venue/ap")
async def list_aps(
    venue_id:     Optional[str] = None,
    current_user: User          = Depends(get_current_user),
    db:           AsyncSession  = Depends(get_db)
):
    query = sa.select(AccessPoint)
    if venue_id:
        query = query.where(AccessPoint.venue_id == sa.text(f"'{venue_id}'::uuid"))
    result = await db.execute(query)
    aps    = result.scalars().all()
    return [
        {
            "bssid": ap.bssid, "venue_id": str(ap.venue_id),
            "ssid": ap.ssid, "x": ap.x, "y": ap.y,
            "rssi_ref": ap.rssi_ref, "path_loss_n": ap.path_loss_n,
            "freq_mhz": ap.freq_mhz, "rtt_offset_m": ap.rtt_offset_m,
            "oui": ap.oui
        }
        for ap in aps
    ]


@app.get("/api/v1/venue/radio-map")
async def get_radio_map(
    venue_id:     Optional[str] = None,
    current_user: User          = Depends(get_current_user),
    db:           AsyncSession  = Depends(get_db)
):
    query = sa.select(RadioMap)
    result = await db.execute(query)
    rows   = result.scalars().all()
    return [
        {
            "ap_bssid": r.ap_bssid,
            "grid_point_id": str(r.grid_point_id),
            "estimated_rssi": r.estimated_rssi,
            "estimated_distance_m": r.estimated_distance_m
        }
        for r in rows
    ]


# =============================================================================
# SECTION 10 — WebSocket Manager
# =============================================================================

class WebSocketManager:
    """Manages WebSocket connections per device MAC."""

    def __init__(self):
        # mac → list of websockets
        self._connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, mac: str, websocket: WebSocket):
        await websocket.accept()
        if mac not in self._connections:
            self._connections[mac] = []
        self._connections[mac].append(websocket)
        logger.info("WS connected: mac=%s total=%d", mac, len(self._connections[mac]))

    def disconnect(self, mac: str, websocket: WebSocket):
        if mac in self._connections:
            self._connections[mac] = [
                ws for ws in self._connections[mac] if ws is not websocket
            ]
            if not self._connections[mac]:
                del self._connections[mac]

    async def broadcast(self, mac: str, data: dict):
        if mac not in self._connections:
            return
        dead = []
        for ws in self._connections[mac]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(mac, ws)


ws_manager = WebSocketManager()


@app.websocket("/ws/position/{device_id}")
async def websocket_position(
    device_id: str,
    websocket: WebSocket,
    token:     str = "",
    db:        AsyncSession = Depends(get_db)
):
    # Validate JWT
    if not token:
        await websocket.close(code=4001)
        return

    try:
        user_id = decode_access_token(token)
    except HTTPException:
        await websocket.close(code=4001)
        return

    # Validate user
    result = await db.execute(
        sa.select(User).where(User.id == sa.text(f"'{user_id}'::uuid"))
    )
    user = result.scalar_one_or_none()
    if not user:
        await websocket.close(code=4001)
        return

    # Validate device ownership
    mac = device_id.upper()
    result = await db.execute(sa.select(Device).where(Device.mac == mac))
    device = result.scalar_one_or_none()
    if not device or str(device.owner_id) != str(user.id):
        await websocket.close(code=4003)
        return

    await ws_manager.connect(mac, websocket)
    try:
        while True:
            # Keep alive — client can send pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(mac, websocket)
    except Exception as e:
        logger.error("WebSocket error for %s: %s", mac, e)
        ws_manager.disconnect(mac, websocket)


# =============================================================================
# SECTION 11 — Startup/Shutdown Lifecycle
# =============================================================================

@app.on_event("startup")
async def startup():
    logger.info("TRAKN backend starting up...")
    # Test DB connection
    try:
        async with engine.begin() as conn:
            await conn.execute(sa.text("SELECT 1"))
        logger.info("Database connection OK.")
    except Exception as e:
        logger.error("Database connection failed: %s", e)


@app.on_event("shutdown")
async def shutdown():
    logger.info("TRAKN backend shutting down...")
    await engine.dispose()
    logger.info("Database connections closed.")
