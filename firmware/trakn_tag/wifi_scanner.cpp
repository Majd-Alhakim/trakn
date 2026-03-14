// =============================================================================
// TRAKN Tag — wifi_scanner.cpp
// WiFi AP scanner implementation for Ameba RTL8720DN (BW16).
//
// Ameba's WiFiClass only supports synchronous scanning:
//   - scanNetworks()    → blocks until done, returns AP count
//   - SSID(i)           → char* (not String)
//   - BSSID(i)          → uint8_t* (6 bytes, not a string)
//   - RSSI(i)           → int32_t
// There is no async scan, scanComplete(), scanDelete(), BSSIDstr(),
// or channel() on this SDK.
// =============================================================================

#include "wifi_scanner.h"
#include "config.h"
#include <WiFi.h>

static bool    _scanReady = false;
static int16_t _scanTotal = 0;

// ---------------------------------------------------------------------------
// wifiScanTrigger
// Runs a synchronous scan and caches the result count.
// Blocks for a few hundred ms — call only from the main loop when acceptable.
// ---------------------------------------------------------------------------
void wifiScanTrigger() {
    _scanReady = false;
    _scanTotal = WiFi.scanNetworks();   // synchronous; returns AP count or -1
    if (_scanTotal < 0) _scanTotal = 0;
    _scanReady = true;
}

// ---------------------------------------------------------------------------
// wifiScanComplete
// Returns true when scan results are available.
// ---------------------------------------------------------------------------
bool wifiScanComplete() {
    return _scanReady;
}

// ---------------------------------------------------------------------------
// wifiCollectResults
// Copies the top MAX_SCAN_RESULTS APs (by RSSI) into results[].
// ---------------------------------------------------------------------------
void wifiCollectResults(WifiEntry results[MAX_SCAN_RESULTS], int& count) {
    count = 0;
    if (!_scanReady || _scanTotal <= 0) {
        _scanReady = false;
        return;
    }

    int16_t total = _scanTotal;

    // Build index array for sorting; cap at MAX_SCAN_RESULTS first pass.
    int16_t indices[MAX_SCAN_RESULTS];
    int kept = 0;
    for (int16_t i = 0; i < total && kept < MAX_SCAN_RESULTS; i++) {
        indices[kept++] = i;
    }

    // Bubble-sort kept entries descending by RSSI.
    for (int a = 0; a < kept - 1; a++) {
        for (int b = a + 1; b < kept; b++) {
            if (WiFi.RSSI(indices[b]) > WiFi.RSSI(indices[a])) {
                int16_t tmp = indices[a];
                indices[a]  = indices[b];
                indices[b]  = tmp;
            }
        }
    }

    // Check remaining entries against the weakest kept.
    for (int16_t i = MAX_SCAN_RESULTS; i < total; i++) {
        int32_t r = WiFi.RSSI(i);
        int weakIdx = 0;
        for (int k = 1; k < kept; k++) {
            if (WiFi.RSSI(indices[k]) < WiFi.RSSI(indices[weakIdx])) weakIdx = k;
        }
        if (r > WiFi.RSSI(indices[weakIdx])) {
            indices[weakIdx] = i;
            for (int a = 0; a < kept - 1; a++) {
                for (int b = a + 1; b < kept; b++) {
                    if (WiFi.RSSI(indices[b]) > WiFi.RSSI(indices[a])) {
                        int16_t tmp = indices[a];
                        indices[a]  = indices[b];
                        indices[b]  = tmp;
                    }
                }
            }
        }
    }

    for (int k = 0; k < kept; k++) {
        int16_t idx = indices[k];

        // SSID — Ameba returns char*, not String
        strncpy(results[k].ssid, WiFi.SSID(idx), 32);
        results[k].ssid[32] = '\0';

        // BSSID — Ameba returns uint8_t[6]; format manually
        uint8_t* mac = WiFi.BSSID(idx);
        snprintf(results[k].bssid, 18, "%02X:%02X:%02X:%02X:%02X:%02X",
                 mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);

        results[k].rssi = WiFi.RSSI(idx);

        // Ameba does not expose channel; set freq to 0.
        results[k].freq = 0;
    }
    count = kept;

    _scanReady = false;
    _scanTotal = 0;
}
