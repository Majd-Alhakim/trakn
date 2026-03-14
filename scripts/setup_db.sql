-- =============================================================================
-- TRAKN Database Schema — setup_db.sql
-- PostgreSQL 16
-- PRD Reference: TRAKN_PRD.md Section 14
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- Table: venues
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS venues (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    floor_plan_url  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- Table: grid_points
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS grid_points (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id    UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    x           DOUBLE PRECISION NOT NULL,
    y           DOUBLE PRECISION NOT NULL,
    is_walkable BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_grid_points_venue ON grid_points(venue_id);
CREATE INDEX IF NOT EXISTS idx_grid_points_walkable ON grid_points(venue_id, is_walkable);

-- -----------------------------------------------------------------------------
-- Table: access_points
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS access_points (
    bssid           VARCHAR(17) PRIMARY KEY,
    venue_id        UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    ssid            VARCHAR(255),
    x               DOUBLE PRECISION NOT NULL,
    y               DOUBLE PRECISION NOT NULL,
    rssi_ref        DOUBLE PRECISION NOT NULL DEFAULT -40.0,
    path_loss_n     DOUBLE PRECISION NOT NULL DEFAULT 2.0,
    freq_mhz        INTEGER NOT NULL DEFAULT 2412,
    rtt_offset_m    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    oui             VARCHAR(8),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ap_venue ON access_points(venue_id);

-- -----------------------------------------------------------------------------
-- Table: radio_map
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS radio_map (
    ap_bssid            VARCHAR(17) NOT NULL REFERENCES access_points(bssid) ON DELETE CASCADE,
    grid_point_id       UUID NOT NULL REFERENCES grid_points(id) ON DELETE CASCADE,
    estimated_rssi      DOUBLE PRECISION NOT NULL,
    estimated_distance_m DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (ap_bssid, grid_point_id)
);

CREATE INDEX IF NOT EXISTS idx_radio_map_ap ON radio_map(ap_bssid);
CREATE INDEX IF NOT EXISTS idx_radio_map_gp ON radio_map(grid_point_id);

-- -----------------------------------------------------------------------------
-- Table: users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- -----------------------------------------------------------------------------
-- Table: devices
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    mac             VARCHAR(17) PRIMARY KEY,
    venue_id        UUID REFERENCES venues(id) ON DELETE SET NULL,
    owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    child_name      VARCHAR(255) NOT NULL,
    api_key_hash    VARCHAR(255) NOT NULL,
    registered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_devices_owner ON devices(owner_id);
CREATE INDEX IF NOT EXISTS idx_devices_venue ON devices(venue_id);

-- -----------------------------------------------------------------------------
-- Table: positions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id          BIGSERIAL PRIMARY KEY,
    device_mac  VARCHAR(17) NOT NULL REFERENCES devices(mac) ON DELETE CASCADE,
    x           DOUBLE PRECISION NOT NULL,
    y           DOUBLE PRECISION NOT NULL,
    heading     DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    step_count  INTEGER NOT NULL DEFAULT 0,
    confidence  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_device ON positions(device_mac);
CREATE INDEX IF NOT EXISTS idx_positions_ts ON positions(device_mac, ts DESC);

-- -----------------------------------------------------------------------------
-- Trigger: update access_points.updated_at on row update
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ap_updated_at
    BEFORE UPDATE ON access_points
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
