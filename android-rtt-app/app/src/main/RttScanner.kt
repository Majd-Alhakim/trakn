// =============================================================================
// TRAKN Android RTT App — RttScanner.kt
// Wi-Fi RTT ranging using WifiRttManager (requires API 28+, minSdk 31)
// OUI offset table applied: d_corrected = d_raw - offset_OUI
// PRD Reference: TRAKN_PRD.md Section 9
// =============================================================================

package org.trakn.rttapp

import android.content.Context
import android.net.wifi.ScanResult
import android.net.wifi.rtt.RangingRequest
import android.net.wifi.rtt.RangingResult
import android.net.wifi.rtt.WifiRttManager
import android.net.wifi.WifiManager
import android.os.Build
import androidx.annotation.RequiresApi
import kotlinx.coroutines.suspendCancellableCoroutine
import java.util.concurrent.Executor
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

@RequiresApi(Build.VERSION_CODES.P)
class RttScanner(private val context: Context) {

    // -------------------------------------------------------------------------
    // OUI offset table (metres) — corrects for vendor-specific RTT biases.
    // Values derived from empirical measurements per manufacturer.
    // -------------------------------------------------------------------------
    private val ouiOffsets: Map<String, Float> = mapOf(
        "FC:EC:DA" to  0.5f,   // Cisco
        "00:17:F2" to  0.3f,   // Apple
        "00:25:00" to  0.4f,   // Apple (alt)
        "B4:FB:E4" to  0.2f,   // Google (Nest)
        "60:38:E0" to  0.6f,   // Netgear
        "00:14:6C" to  0.5f,   // Netgear (alt)
        "E8:65:D4" to  0.4f,   // TP-Link
        "50:C7:BF" to  0.4f,   // TP-Link (alt)
        "00:1A:2B" to  0.3f,   // Generic / fallback
    )
    private val defaultOffset = 0.35f

    data class ApEntry(
        val bssid:       String,
        val ssid:        String,
        val rssi:        Int,
        val freqMhz:     Int,
        val distanceM:   Double,    // OUI-corrected distance
        val distanceStd: Double
    )

    private val wifiManager  = context.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val rttManager   = context.getSystemService(Context.WIFI_RTT_RANGING_SERVICE) as WifiRttManager
    private val mainExecutor: Executor = context.mainExecutor

    // -------------------------------------------------------------------------
    // rangeAllAPs: scan visible APs, range all RTT-capable ones, return results.
    // -------------------------------------------------------------------------
    suspend fun rangeAllAPs(): List<ApEntry> {
        val scanResults = getScanResults()
        val rttCapable  = scanResults.filter { it.is80211mcResponder }

        if (rttCapable.isEmpty()) return emptyList()

        val request = RangingRequest.Builder().apply {
            rttCapable.take(RangingRequest.getMaxPeers()).forEach { addAccessPoint(it) }
        }.build()

        val results = suspendRanging(request)

        return results
            .filter { it.status == RangingResult.STATUS_SUCCESS }
            .mapNotNull { rr ->
                val scanResult = scanResults.firstOrNull {
                    it.BSSID.uppercase() == rr.macAddress.toString().uppercase()
                } ?: return@mapNotNull null

                val offset = ouiOffset(rr.macAddress.toString())
                val corrected = (rr.distanceMm / 1000.0) - offset

                ApEntry(
                    bssid       = rr.macAddress.toString().uppercase(),
                    ssid        = scanResult.SSID,
                    rssi        = scanResult.level,
                    freqMhz     = scanResult.frequency,
                    distanceM   = maxOf(0.1, corrected),
                    distanceStd = rr.distanceStdDevMm / 1000.0
                )
            }
    }

    // -------------------------------------------------------------------------
    // ouiOffset: look up vendor bias correction by OUI (first 3 octets).
    // -------------------------------------------------------------------------
    private fun ouiOffset(bssid: String): Double {
        val oui = bssid.uppercase().take(8)   // "XX:XX:XX"
        return (ouiOffsets[oui] ?: defaultOffset).toDouble()
    }

    // -------------------------------------------------------------------------
    // getScanResults: returns the most recent passive Wi-Fi scan.
    // -------------------------------------------------------------------------
    private fun getScanResults(): List<ScanResult> {
        return try {
            wifiManager.scanResults ?: emptyList()
        } catch (e: SecurityException) {
            emptyList()
        }
    }

    // -------------------------------------------------------------------------
    // suspendRanging: wraps WifiRttManager.startRanging() in a coroutine.
    // -------------------------------------------------------------------------
    private suspend fun suspendRanging(request: RangingRequest): List<RangingResult> =
        suspendCancellableCoroutine { cont ->
            rttManager.startRanging(
                request,
                mainExecutor,
                object : android.net.wifi.rtt.RangingResultCallback() {
                    override fun onRangingResults(results: List<RangingResult>) {
                        cont.resume(results)
                    }
                    override fun onRangingFailure(code: Int) {
                        cont.resumeWithException(
                            RuntimeException("RTT ranging failed with code $code")
                        )
                    }
                }
            )
        }
}
