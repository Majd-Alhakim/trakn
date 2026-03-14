// =============================================================================
// TRAKN Tag — trakn_tag.ino
// Main Arduino sketch for the BW16 wearable IMU + WiFi tag.
// PRD Reference: TRAKN_PRD.md Section 6
// =============================================================================

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiSSLClient.h>
#include <Wire.h>


#include "config.h"
#include "http_client.h"
#include "imu.h"
#include "wifi_conn.h"
#include "wifi_scanner.h"


// ---------------------------------------------------------------------------
// Batch buffer
// ---------------------------------------------------------------------------
struct ImuSample {
  uint32_t ts_ms;
  float ax, ay, az;
  float gx, gy, gz;
};

static ImuSample _batch[POST_BATCH_SIZE];
static int _batchCount = 0;

// WiFi scan results
static WifiEntry _scanResults[MAX_SCAN_RESULTS];
static int _scanCount = 0;
static bool _scanPending = false;

// Timing
static unsigned long _lastSampleMs = 0;
static unsigned long _lastScanMs = 0;

// ---------------------------------------------------------------------------
// buildJson
// Assembles the JSON packet string into `buf` (caller provides buffer).
// ---------------------------------------------------------------------------
static void buildJson(char *buf, size_t bufLen) {
  // Start JSON object
  int pos = snprintf(buf, bufLen, "{\"mac\":\"%s\",\"samples\":[", DEVICE_MAC);

  for (int i = 0; i < _batchCount && pos < (int)bufLen - 2; i++) {
    ImuSample &s = _batch[i];
    char tmp[256];
    int n = snprintf(tmp, sizeof(tmp),
                     "%s{\"ts\":%lu,\"ax\":%.5f,\"ay\":%.5f,\"az\":%.5f,"
                     "\"gx\":%.6f,\"gy\":%.6f,\"gz\":%.6f}",
                     (i == 0 ? "" : ","), (unsigned long)s.ts_ms, s.ax, s.ay,
                     s.az, s.gx, s.gy, s.gz);
    if (pos + n < (int)bufLen - 2) {
      memcpy(buf + pos, tmp, n);
      pos += n;
    }
  }

  // Append WiFi scan results
  pos += snprintf(buf + pos, bufLen - pos, "],\"wifi\":[");

  for (int i = 0; i < _scanCount && pos < (int)bufLen - 2; i++) {
    WifiEntry &ap = _scanResults[i];
    char tmp[200];
    int n = snprintf(
        tmp, sizeof(tmp),
        "%s{\"bssid\":\"%s\",\"ssid\":\"%s\",\"rssi\":%ld,\"freq\":%ld}",
        (i == 0 ? "" : ","), ap.bssid, ap.ssid, (long)ap.rssi, (long)ap.freq);
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
  WiFiSSLClient client;
  if (!client.connect(API_HOST, API_PORT))
    return;

  client.print(String("GET ") + HEALTH_ENDPOINT + " HTTP/1.1\r\n" +
               "Host: " + API_HOST + "\r\n" + "Connection: close\r\n\r\n");

  String statusLine = client.readStringUntil('\n');
  client.stop();

  int spaceIdx = statusLine.indexOf(' ');
  int code = (spaceIdx >= 0)
                 ? statusLine.substring(spaceIdx + 1, spaceIdx + 4).toInt()
                 : 0;

  if (code == 200) {
    Serial.println("[TRAKN] Health check OK");
  } else {
    Serial.print("[TRAKN] Health check failed: ");
    Serial.println(code);
  }
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
    while (true) {
      delay(1000);
    }
  }
  Serial.println("[TRAKN] MPU6050 initialized.");

  // Connect to WiFi
  Serial.print("[TRAKN] Connecting to SSID: ");
  Serial.println(WIFI_SSID);
  if (!wifiConnect(WIFI_SSID, WIFI_PASSWORD)) {
    Serial.println("[TRAKN] WARNING: WiFi connect failed at startup.");
  } else {
    IPAddress ip = WiFi.localIP();
    char ipStr[16];
    snprintf(ipStr, sizeof(ipStr), "%d.%d.%d.%d", ip[0], ip[1], ip[2], ip[3]);
    Serial.print("[TRAKN] WiFi connected. IP: ");
    Serial.println(ipStr);
  }

  // Health check
  if (wifiIsConnected()) {
    healthCheck();
  }

  _lastSampleMs = millis();
  _lastScanMs = millis();
}

// ---------------------------------------------------------------------------
// loop — runs at ~100 Hz
// ---------------------------------------------------------------------------
void loop() {
  unsigned long now = millis();

  // Maintain 100 Hz sample rate
  if ((now - _lastSampleMs) < SAMPLE_INTERVAL_MS)
    return;
  _lastSampleMs = now;

  // 1. Read IMU
  IMUData imu = imuRead();
  if (imu.valid) {
    if (_batchCount < POST_BATCH_SIZE) {
      _batch[_batchCount++] = {now,    imu.ax, imu.ay, imu.az,
                               imu.gx, imu.gy, imu.gz};
    }
  }

  // 2. Every SCAN_INTERVAL_MS: trigger a WiFi scan (non-blocking)
  if ((now - _lastScanMs) >= SCAN_INTERVAL_MS) {
    _lastScanMs = now;
    wifiScanTrigger();
    _scanPending = true;
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
