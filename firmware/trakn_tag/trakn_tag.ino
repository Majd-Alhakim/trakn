// =============================================================================
// TRAKN Tag — trakn_tag.ino
// Main Arduino sketch for the BW16 wearable IMU + WiFi tag.
// PRD Reference: TRAKN_PRD.md Section 6
// =============================================================================

#include <Wire.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <Arduino.h>

#include "config.h"
#include "imu.h"
#include "wifi_conn.h"
#include "wifi_scanner.h"
#include "http_client.h"

// ---------------------------------------------------------------------------
// Batch buffer
// ---------------------------------------------------------------------------
struct ImuSample {
    uint32_t ts_ms;
    float ax, ay, az;
    float gx, gy, gz;
};

static ImuSample    _batch[POST_BATCH_SIZE];
static int          _batchCount = 0;

// WiFi scan results
static WifiEntry    _scanResults[MAX_SCAN_RESULTS];
static int          _scanCount   = 0;
static bool         _scanPending = false;

// Timing
static unsigned long _lastSampleMs = 0;
static unsigned long _lastScanMs   = 0;

// ---------------------------------------------------------------------------
// buildJson
// Assembles the JSON packet string into `buf` (caller provides buffer).
// ---------------------------------------------------------------------------
static void buildJson(char* buf, size_t bufLen) {
    // Start JSON object
    int pos = snprintf(buf, bufLen,
        "{\"mac\":\"%s\",\"samples\":[", DEVICE_MAC);

    for (int i = 0; i < _batchCount && pos < (int)bufLen - 2; i++) {
        ImuSample& s = _batch[i];
        char tmp[256];
        int n = snprintf(tmp, sizeof(tmp),
            "%s{\"ts\":%lu,\"ax\":%.5f,\"ay\":%.5f,\"az\":%.5f,"
            "\"gx\":%.6f,\"gy\":%.6f,\"gz\":%.6f}",
            (i == 0 ? "" : ","),
            (unsigned long)s.ts_ms,
            s.ax, s.ay, s.az, s.gx, s.gy, s.gz);
        if (pos + n < (int)bufLen - 2) {
            memcpy(buf + pos, tmp, n);
            pos += n;
        }
    }

    // Append WiFi scan results
    pos += snprintf(buf + pos, bufLen - pos, "],\"wifi\":[");

    for (int i = 0; i < _scanCount && pos < (int)bufLen - 2; i++) {
        WifiEntry& ap = _scanResults[i];
        char tmp[200];
        int n = snprintf(tmp, sizeof(tmp),
            "%s{\"bssid\":\"%s\",\"ssid\":\"%s\",\"rssi\":%ld,\"freq\":%ld}",
            (i == 0 ? "" : ","),
            ap.bssid, ap.ssid, (long)ap.rssi, (long)ap.freq);
        if (pos + n < (int)bufLen - 2) {
            memcpy(buf + pos, tmp, n);
            pos += n;
        }
    }

    snprintf(buf + pos, bufLen - pos, "]}");
}

// ---------------------------------------------------------------------------
// healthCheck
// GET /health — block until response or timeout.
// ---------------------------------------------------------------------------
static void healthCheck() {
    WiFiClientSecure tlsClient;
    tlsClient.setInsecure();

    HTTPClient http;
    String url = String("https://") + API_HOST + ":" + API_PORT + HEALTH_ENDPOINT;
    if (!http.begin(tlsClient, url)) return;

    int code = http.GET();
    if (code == 200) {
        Serial.println("[TRAKN] Health check OK");
    } else {
        Serial.printf("[TRAKN] Health check failed: %d\n", code);
    }
    http.end();
}

// ---------------------------------------------------------------------------
// setup
// ---------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    delay(100);
    Serial.println("[TRAKN] Booting...");

    // I2C at 400 kHz for MPU6050
    Wire.begin();
    Wire.setClock(400000UL);

    // Initialize MPU6050
    if (!imuInit()) {
        Serial.println("[TRAKN] ERROR: MPU6050 init failed. Halting.");
        while (true) { delay(1000); }
    }
    Serial.println("[TRAKN] MPU6050 initialized.");

    // Connect to WiFi
    Serial.printf("[TRAKN] Connecting to SSID: %s\n", WIFI_SSID);
    if (!wifiConnect(WIFI_SSID, WIFI_PASSWORD)) {
        Serial.println("[TRAKN] WARNING: WiFi connect failed at startup.");
    } else {
        Serial.printf("[TRAKN] WiFi connected. IP: %s\n",
                      WiFi.localIP().toString().c_str());
    }

    // Health check
    if (wifiIsConnected()) {
        healthCheck();
    }

    _lastSampleMs = millis();
    _lastScanMs   = millis();
}

// ---------------------------------------------------------------------------
// loop — runs at ~100 Hz
// ---------------------------------------------------------------------------
void loop() {
    unsigned long now = millis();

    // Maintain 100 Hz sample rate
    if ((now - _lastSampleMs) < SAMPLE_INTERVAL_MS) return;
    _lastSampleMs = now;

    // 1. Read IMU
    IMUData imu = imuRead();
    if (imu.valid) {
        if (_batchCount < POST_BATCH_SIZE) {
            _batch[_batchCount++] = { now, imu.ax, imu.ay, imu.az,
                                           imu.gx, imu.gy, imu.gz };
        }
    }

    // 2. Every SCAN_INTERVAL_MS: trigger a WiFi scan (non-blocking)
    if ((now - _lastScanMs) >= SCAN_INTERVAL_MS) {
        _lastScanMs   = now;
        wifiScanTrigger();
        _scanPending  = true;
    }

    // 3. Collect scan results if a scan has completed
    if (_scanPending && wifiScanComplete()) {
        wifiCollectResults(_scanResults, _scanCount);
        _scanPending = false;
    }

    // 4. POST batch when full
    if (_batchCount >= POST_BATCH_SIZE) {
        static char jsonBuf[4096];
        buildJson(jsonBuf, sizeof(jsonBuf));

        if (wifiIsConnected()) {
            bool ok = httpPostPacket(jsonBuf);
            if (!ok) {
                Serial.println("[TRAKN] POST failed.");
            }
        }
        _batchCount = 0;
        // Clear old scan data after each POST
        _scanCount = 0;
    }

    // 5. Non-blocking reconnect
    wifiReconnectIfNeeded(WIFI_SSID, WIFI_PASSWORD);
}
