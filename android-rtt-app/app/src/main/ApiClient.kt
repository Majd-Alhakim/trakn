// =============================================================================
// TRAKN Android RTT App — ApiClient.kt
// Retrofit2 client for TRAKN backend.
// POST /api/v1/venue/ap
// PRD Reference: TRAKN_PRD.md Section 9
// =============================================================================

package org.trakn.rttapp

import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.*
import java.util.concurrent.TimeUnit

// -------------------------------------------------------------------------
// Data transfer objects
// -------------------------------------------------------------------------
data class AccessPointDto(
    val bssid:        String,
    val venue_id:     String,
    val ssid:         String?,
    val x:            Double,
    val y:            Double,
    val rssi_ref:     Double  = -40.0,
    val path_loss_n:  Double  = 2.0,
    val freq_mhz:     Int     = 2412,
    val rtt_offset_m: Double  = 0.0,
    val oui:          String? = null
)

data class LoginDto(val email: String, val password: String)
data class LoginResponse(val access_token: String, val token_type: String)

// -------------------------------------------------------------------------
// Retrofit service interface
// -------------------------------------------------------------------------
interface TraknApiService {

    @POST("venue/ap")
    suspend fun postAP(
        @Header("Authorization") auth: String,
        @Body body: AccessPointDto
    ): Response<Any>

    @POST("auth/login")
    suspend fun login(@Body body: LoginDto): Response<LoginResponse>
}

// -------------------------------------------------------------------------
// ApiClient
// -------------------------------------------------------------------------
class ApiClient(private val context: Context) {

    companion object {
        private const val BASE_URL = "https://trakn.duckdns.org/api/v1/"
        private var _token: String = ""
    }

    private val retrofit: Retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(
            OkHttpClient.Builder()
                .connectTimeout(15, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .addInterceptor(
                    HttpLoggingInterceptor().apply {
                        level = HttpLoggingInterceptor.Level.BASIC
                    }
                )
                .build()
        )
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    private val service: TraknApiService = retrofit.create(TraknApiService::class.java)

    // -------------------------------------------------------------------------
    // login: store JWT token for subsequent calls.
    // -------------------------------------------------------------------------
    suspend fun login(email: String, password: String): Boolean {
        val response = service.login(LoginDto(email, password))
        return if (response.isSuccessful) {
            _token = response.body()?.access_token ?: ""
            true
        } else {
            false
        }
    }

    // -------------------------------------------------------------------------
    // postAP: push a ranged AP to the backend.
    // venueId and AP coordinates must be provided externally.
    // -------------------------------------------------------------------------
    suspend fun postAP(
        apEntry:  RttScanner.ApEntry,
        venueId:  String = "",
        xMetres:  Double = 0.0,
        yMetres:  Double = 0.0
    ): Boolean {
        val token = _token
        if (token.isEmpty()) return false

        val oui = apEntry.bssid.take(8)

        val dto = AccessPointDto(
            bssid        = apEntry.bssid,
            venue_id     = venueId,
            ssid         = apEntry.ssid,
            x            = xMetres,
            y            = yMetres,
            rssi_ref     = -40.0,
            path_loss_n  = 2.0,
            freq_mhz     = apEntry.freqMhz,
            rtt_offset_m = apEntry.distanceM - (apEntry.distanceM),  // placeholder; offset computed in RttScanner
            oui          = oui
        )

        val response = service.postAP("Bearer $token", dto)
        return response.isSuccessful
    }

    // Convenience overload used from ApDiscoveryFragment
    suspend fun postAP(apEntry: RttScanner.ApEntry): Boolean = postAP(apEntry, "", 0.0, 0.0)
}
