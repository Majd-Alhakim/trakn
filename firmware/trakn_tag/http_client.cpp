// =============================================================================
// TRAKN Tag — http_client.cpp
// HTTPS POST helper for Ameba RTL8720DN (BW16).
//
// Ameba has no HTTPClient wrapper — HTTP/1.1 is sent manually over
// WiFiSSLClient (Ameba's TLS socket, analogous to ESP32's WiFiClientSecure).
// Certificate validation is left at the SDK default (no pinning required).
// =============================================================================

#include "http_client.h"
#include "config.h"
#include <WiFiSSLClient.h>

// ---------------------------------------------------------------------------
// httpPostPacket
// ---------------------------------------------------------------------------
bool httpPostPacket(const char* jsonBody) {
    if (!jsonBody || jsonBody[0] == '\0') return false;

    WiFiSSLClient client;
    if (!client.connect(API_HOST, API_PORT)) return false;

    size_t bodyLen = strlen(jsonBody);

    // Build and send the HTTP/1.1 request in one print call.
    client.print(
        String("POST ") + GATEWAY_ENDPOINT + " HTTP/1.1\r\n" +
        "Host: " + API_HOST + "\r\n" +
        "Content-Type: application/json\r\n" +
        "X-TRAKN-API-Key: " + DEVICE_API_KEY + "\r\n" +
        "Content-Length: " + (unsigned long)bodyLen + "\r\n" +
        "Connection: close\r\n" +
        "\r\n" +
        jsonBody
    );

    // Read just the status line to extract the HTTP response code.
    String statusLine = client.readStringUntil('\n');
    client.stop();

    // Status line format: "HTTP/1.1 200 OK"
    int spaceIdx = statusLine.indexOf(' ');
    if (spaceIdx < 0) return false;
    int code = statusLine.substring(spaceIdx + 1, spaceIdx + 4).toInt();

    return (code == 200);
}
