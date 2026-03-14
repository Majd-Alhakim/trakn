// =============================================================================
// TRAKN Tag — http_client.cpp
// HTTPS POST helper implementation.
// Uses WiFiClientSecure with certificate validation disabled.
// =============================================================================

#include "http_client.h"
#include "config.h"
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// ---------------------------------------------------------------------------
// httpPostPacket
// ---------------------------------------------------------------------------
bool httpPostPacket(const char* jsonBody) {
    if (!jsonBody || jsonBody[0] == '\0') return false;

    WiFiClientSecure tlsClient;
    tlsClient.setInsecure();   // Skip certificate validation on embedded device

    HTTPClient http;

    String url = String("https://") + API_HOST + ":" + API_PORT + GATEWAY_ENDPOINT;

    if (!http.begin(tlsClient, url)) return false;

    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-TRAKN-API-Key", DEVICE_API_KEY);

    int httpCode = http.POST(String(jsonBody));
    http.end();

    return (httpCode == 200);
}
