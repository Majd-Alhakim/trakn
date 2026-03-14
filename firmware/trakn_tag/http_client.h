#ifndef HTTP_CLIENT_H
#define HTTP_CLIENT_H

// =============================================================================
// TRAKN Tag — http_client.h
// HTTPS POST helper for sending IMU/WiFi packets to the TRAKN backend.
// =============================================================================

#include <Arduino.h>

// POST a JSON payload to GATEWAY_ENDPOINT on API_HOST:API_PORT.
// Sets the X-TRAKN-API-Key header to DEVICE_API_KEY.
// TLS certificate validation is disabled (no root CA required on-device).
// Returns true if the server responds with HTTP 200.
bool httpPostPacket(const char* jsonBody);

#endif // HTTP_CLIENT_H
