#ifndef WIFI_SCANNER_H
#define WIFI_SCANNER_H

// =============================================================================
// TRAKN Tag — wifi_scanner.h
// Non-blocking WiFi AP scanner — returns top-N results by RSSI.
// =============================================================================

#include <Arduino.h>

// Maximum number of scan results to keep.
#define MAX_SCAN_RESULTS    4

// One scanned AP entry.
struct WifiEntry {
    char    bssid[18];  // "XX:XX:XX:XX:XX:XX\0"
    char    ssid[33];   // up to 32-char SSID + null
    int32_t rssi;       // dBm (negative)
    int32_t freq;       // MHz (e.g. 2412, 5180)
};

// Kick off a background (async) WiFi scan.
// Returns immediately; does not block the main loop.
void wifiScanTrigger();

// Returns true if a scan result is ready to be collected.
bool wifiScanComplete();

// Fill `results` with the top-N APs ordered by RSSI (strongest first).
// `count` is set to the number of valid entries filled (0 .. MAX_SCAN_RESULTS).
// Clears the scan-ready flag so subsequent calls return an empty list
// until the next triggerScan() / collectResults() cycle.
void wifiCollectResults(WifiEntry results[MAX_SCAN_RESULTS], int& count);

#endif // WIFI_SCANNER_H
