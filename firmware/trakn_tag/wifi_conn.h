#ifndef WIFI_CONN_H
#define WIFI_CONN_H

// =============================================================================
// TRAKN Tag — wifi_conn.h
// WiFi station connection management.
// =============================================================================

#include <Arduino.h>

// Connect to the specified SSID using the password from config.h.
// Retries with 1-second backoff up to WIFI_MAX_RETRIES times.
// Returns true if connected, false if all retries exhausted.
bool wifiConnect(const char* ssid, const char* password);

// Returns true if the WiFi link is currently up.
bool wifiIsConnected();

// Non-blocking reconnect: if connection is lost, attempts to reconnect once.
// Call from loop(); the reconnect attempt uses a 1s backoff guard so it
// does not flood the radio with association requests on every iteration.
void wifiReconnectIfNeeded(const char* ssid, const char* password);

#endif // WIFI_CONN_H
