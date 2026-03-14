// =============================================================================
// TRAKN Tag — wifi_conn.cpp
// WiFi station connection management.
// =============================================================================

#include "wifi_conn.h"
#include "config.h"
#include <WiFi.h>

// Timestamp of the last reconnect attempt (millis).
static unsigned long _lastReconnectAttempt = 0;

// ---------------------------------------------------------------------------
// wifiConnect
// Blocks until connected or WIFI_MAX_RETRIES exhausted.
// ---------------------------------------------------------------------------
bool wifiConnect(const char* ssid, const char* password) {
    // Ameba WiFiClass::begin() takes char* (not const char*)
    WiFi.begin(const_cast<char*>(ssid), password);

    for (int attempt = 0; attempt < WIFI_MAX_RETRIES; attempt++) {
        if (WiFi.status() == WL_CONNECTED) {
            return true;
        }
        delay(WIFI_RETRY_DELAY_MS);
    }
    return (WiFi.status() == WL_CONNECTED);
}

// ---------------------------------------------------------------------------
// wifiIsConnected
// ---------------------------------------------------------------------------
bool wifiIsConnected() {
    return (WiFi.status() == WL_CONNECTED);
}

// ---------------------------------------------------------------------------
// wifiReconnectIfNeeded
// Non-blocking: only attempts once per WIFI_RETRY_DELAY_MS interval.
// ---------------------------------------------------------------------------
void wifiReconnectIfNeeded(const char* ssid, const char* password) {
    if (wifiIsConnected()) return;

    unsigned long now = millis();
    if ((now - _lastReconnectAttempt) < (unsigned long)WIFI_RETRY_DELAY_MS) return;

    _lastReconnectAttempt = now;
    WiFi.disconnect();
    WiFi.begin(const_cast<char*>(ssid), password);
}
