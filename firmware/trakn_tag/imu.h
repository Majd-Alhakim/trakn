#ifndef IMU_H
#define IMU_H

// =============================================================================
// TRAKN Tag — imu.h
// MPU6050 driver header.
// PRD Reference: TRAKN_PRD.md Section 6.2
// =============================================================================

#include <stdint.h>

// IMU data in SI units (m/s² and rad/s)
struct IMUData {
    float ax;   // m/s²
    float ay;   // m/s²
    float az;   // m/s²
    float gx;   // rad/s
    float gy;   // rad/s
    float gz;   // rad/s
    bool  valid;
};

// Initialize MPU6050: configure PWR_MGMT_1, GYRO_CONFIG, ACCEL_CONFIG, CONFIG
// Returns true on success (device ACK received).
bool imuInit();

// Read 14 bytes from register 0x3B (ACCEL_XOUT_H through GYRO_ZOUT_L).
// Converts raw values to SI units using ACCEL_SCALE and GYRO_SCALE from config.h.
// Returns IMUData with valid=true on success, valid=false on I2C error.
IMUData imuRead();

#endif // IMU_H
