// =============================================================================
// TRAKN Tag — wifi_scanner.cpp
// Non-blocking WiFi AP scanner implementation.
// =============================================================================

#include "wifi_scanner.h"
#include "config.h"
#include <WiFi.h>

static bool _scanInProgress = false;
static bool _scanReady      = false;

// ---------------------------------------------------------------------------
// wifiScanTrigger
// Initiates an asynchronous scan (WIFI_SCAN_RUNNING is returned immediately).
// ---------------------------------------------------------------------------
void wifiScanTrigger() {
    if (_scanInProgress) return;
    // WiFi.scanNetworks(async=true)
    WiFi.scanNetworks(true);
    _scanInProgress = true;
    _scanReady      = false;
}

// ---------------------------------------------------------------------------
// wifiScanComplete
// Poll the scan engine; returns true once results are available.
// ---------------------------------------------------------------------------
bool wifiScanComplete() {
    if (!_scanInProgress) return false;
    if (_scanReady) return true;

    int16_t n = WiFi.scanComplete();
    if (n == WIFI_SCAN_RUNNING) return false;   // still in progress
    if (n == WIFI_SCAN_FAILED)  {
        _scanInProgress = false;
        return false;
    }
    // n >= 0: results ready
    _scanReady      = true;
    _scanInProgress = false;
    return true;
}

// ---------------------------------------------------------------------------
// wifiCollectResults
// Sort and return the top MAX_SCAN_RESULTS APs by RSSI.
// ---------------------------------------------------------------------------
void wifiCollectResults(WifiEntry results[MAX_SCAN_RESULTS], int& count) {
    count = 0;
    if (!_scanReady) return;

    int16_t total = WiFi.scanComplete();
    if (total <= 0) {
        _scanReady = false;
        WiFi.scanDelete();
        return;
    }

    // Build a list of (rssi, index) pairs and pick top MAX_SCAN_RESULTS.
    // Simple selection sort is fine for small N.
    int16_t indices[MAX_SCAN_RESULTS];
    int     kept = 0;

    for (int16_t i = 0; i < total && kept < MAX_SCAN_RESULTS; i++) {
        indices[kept++] = i;
    }

    // Sort kept entries by RSSI descending (bubble sort — tiny N).
    for (int a = 0; a < kept - 1; a++) {
        for (int b = a + 1; b < kept; b++) {
            if (WiFi.RSSI(indices[b]) > WiFi.RSSI(indices[a])) {
                int16_t tmp  = indices[a];
                indices[a]   = indices[b];
                indices[b]   = tmp;
            }
        }
    }

    // Also check remaining entries to see if any beat the weakest kept entry.
    for (int16_t i = MAX_SCAN_RESULTS; i < total; i++) {
        int32_t r = WiFi.RSSI(i);
        // Find the weakest entry in kept.
        int weakIdx = 0;
        for (int k = 1; k < kept; k++) {
            if (WiFi.RSSI(indices[k]) < WiFi.RSSI(indices[weakIdx])) weakIdx = k;
        }
        if (r > WiFi.RSSI(indices[weakIdx])) {
            indices[weakIdx] = i;
            // Re-sort.
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
        strncpy(results[k].bssid, WiFi.BSSIDstr(idx).c_str(), 17);
        results[k].bssid[17] = '\0';
        strncpy(results[k].ssid, WiFi.SSID(idx).c_str(), 32);
        results[k].ssid[32]  = '\0';
        results[k].rssi = WiFi.RSSI(idx);
        results[k].freq = WiFi.channel(idx) <= 14
                          ? 2407 + WiFi.channel(idx) * 5
                          : 5000 + WiFi.channel(idx) * 5;
    }
    count = kept;

    _scanReady = false;
    WiFi.scanDelete();
}
