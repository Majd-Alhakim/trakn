// =============================================================================
// TRAKN Tag — imu.cpp
// MPU6050 driver implementation.
// PRD Reference: TRAKN_PRD.md Section 6.2
// =============================================================================

#include "imu.h"
#include "config.h"
#include <Wire.h>

// Write a single byte to an MPU6050 register over I2C.
static bool writeRegister(uint8_t reg, uint8_t value) {
    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(reg);
    Wire.write(value);
    return (Wire.endTransmission() == 0);
}

// ---------------------------------------------------------------------------
// imuInit
// Configure MPU6050 registers as specified in PRD Section 6.2.
// ---------------------------------------------------------------------------
bool imuInit() {
    // Wake the device: clear SLEEP bit in PWR_MGMT_1, use internal 8 MHz oscillator
    if (!writeRegister(REG_PWR_MGMT_1, 0x00)) return false;

    // Digital Low-Pass Filter: DLPF_CFG = 0x04 (21 Hz bandwidth)
    if (!writeRegister(REG_CONFIG, DLPF_CFG)) return false;

    // Gyro full-scale: ±500 dps  (FS_SEL = 1 → bits [4:3] = 0b01 → 0x08)
    if (!writeRegister(REG_GYRO_CONFIG, GYRO_RANGE_REG)) return false;

    // Accel full-scale: ±4 g  (AFS_SEL = 1 → bits [4:3] = 0b01 → 0x08)
    if (!writeRegister(REG_ACCEL_CONFIG, ACCEL_RANGE_REG)) return false;

    return true;
}

// ---------------------------------------------------------------------------
// imuRead
// Burst-read 14 bytes starting at ACCEL_XOUT_H (0x3B).
// Register map (each 2 bytes, big-endian, two's complement):
//   0x3B–0x3C  ACCEL_X
//   0x3D–0x3E  ACCEL_Y
//   0x3F–0x40  ACCEL_Z
//   0x41–0x42  TEMP  (ignored)
//   0x43–0x44  GYRO_X
//   0x45–0x46  GYRO_Y
//   0x47–0x48  GYRO_Z
// ---------------------------------------------------------------------------
IMUData imuRead() {
    IMUData data;
    data.valid = false;

    Wire.beginTransmission(MPU6050_ADDR);
    Wire.write(REG_ACCEL_XOUT_H);
    if (Wire.endTransmission(false) != 0) return data;

    uint8_t n = Wire.requestFrom((uint8_t)MPU6050_ADDR, (uint8_t)14);
    if (n != 14) return data;

    // Read raw 16-bit signed values (big-endian)
    int16_t raw_ax = (int16_t)((Wire.read() << 8) | Wire.read());
    int16_t raw_ay = (int16_t)((Wire.read() << 8) | Wire.read());
    int16_t raw_az = (int16_t)((Wire.read() << 8) | Wire.read());
    Wire.read(); Wire.read();  // temperature MSB + LSB (discard)
    int16_t raw_gx = (int16_t)((Wire.read() << 8) | Wire.read());
    int16_t raw_gy = (int16_t)((Wire.read() << 8) | Wire.read());
    int16_t raw_gz = (int16_t)((Wire.read() << 8) | Wire.read());

    // Scale to SI units using locked constants from config.h
    data.ax = (float)raw_ax * ACCEL_SCALE;
    data.ay = (float)raw_ay * ACCEL_SCALE;
    data.az = (float)raw_az * ACCEL_SCALE;
    data.gx = (float)raw_gx * GYRO_SCALE;
    data.gy = (float)raw_gy * GYRO_SCALE;
    data.gz = (float)raw_gz * GYRO_SCALE;
    data.valid = true;

    return data;
}
