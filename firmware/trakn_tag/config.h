#ifndef CONFIG_H
#define CONFIG_H

// =============================================================================
// TRAKN Tag — config.h
// All hardware constants for the BW16 wearable tag.
// PRD Reference: TRAKN_PRD.md Section 6.2
// LOCKED — do not change these values.
// =============================================================================

// -----------------------------------------------------------------------------
// MPU6050 I2C Address & Registers
// -----------------------------------------------------------------------------
#define MPU6050_ADDR        0x68

#define REG_PWR_MGMT_1      0x6B
#define REG_GYRO_CONFIG     0x1B
#define REG_ACCEL_CONFIG    0x1C
#define REG_CONFIG          0x1A
#define REG_ACCEL_XOUT_H    0x3B

// Register configuration values
#define GYRO_RANGE_REG      0x08    // ±500 dps
#define ACCEL_RANGE_REG     0x08    // ±4g
#define DLPF_CFG            0x04    // 21 Hz bandwidth

// -----------------------------------------------------------------------------
// Scaling Constants (raw ADC → SI units)
// -----------------------------------------------------------------------------
#define ACCEL_SCALE         0.0011978149f   // raw → m/s²
#define GYRO_SCALE          0.0002663309f   // raw → rad/s

// -----------------------------------------------------------------------------
// Sampling
// -----------------------------------------------------------------------------
#define SAMPLING_RATE_HZ    100
#define SAMPLE_INTERVAL_MS  10      // 1000 / SAMPLING_RATE_HZ

// -----------------------------------------------------------------------------
// Device Identity
// -----------------------------------------------------------------------------
#define DEVICE_MAC          "24:42:E3:15:E5:72"

// -----------------------------------------------------------------------------
// PDR / Weinberg Stride Constants
// -----------------------------------------------------------------------------
#define K_WEIN              0.47f
#define P_WEIN              0.25f
#define STRIDE_MIN          0.25f   // metres
#define STRIDE_MAX          1.40f   // metres

// -----------------------------------------------------------------------------
// WiFi / Network
// -----------------------------------------------------------------------------
#ifndef WIFI_SSID
#define WIFI_SSID           "Alhakim"
#endif

#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD       "sham@2014"
#endif

// API server
#define API_HOST            "trakn.duckdns.org"
#define API_PORT            443
#define API_BASE_PATH       "/api/v1"
#define GATEWAY_ENDPOINT    "/api/v1/gateway/packet"
#define HEALTH_ENDPOINT     "/api/v1/health"

// API key for this device (generated as "trakn-hw-" + sha256(mac+salt)[:24])
#ifndef DEVICE_API_KEY
#define DEVICE_API_KEY      "trakn-hw-REPLACE_WITH_GENERATED_KEY"
#endif

// -----------------------------------------------------------------------------
// Packet Batching
// -----------------------------------------------------------------------------
#define POST_BATCH_SIZE     10      // number of IMU samples per HTTP POST
#define SCAN_INTERVAL_MS    1000    // WiFi scan every 1 second
#define MAX_AP_RESULTS      4       // top N APs by RSSI to report

// -----------------------------------------------------------------------------
// WiFi Reconnect
// -----------------------------------------------------------------------------
#define WIFI_RETRY_DELAY_MS 1000
#define WIFI_MAX_RETRIES    10

#endif // CONFIG_H
