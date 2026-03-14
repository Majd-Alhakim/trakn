// =============================================================================
// TRAKN Android RTT App — MainActivity.kt
// TabActivity with Tab 1: AP Discovery, Tab 2: Map + Pin
// PRD Reference: TRAKN_PRD.md Section 9
// =============================================================================

package org.trakn.rttapp

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.viewpager2.widget.ViewPager2
import androidx.fragment.app.Fragment
import androidx.fragment.app.FragmentActivity
import androidx.viewpager2.adapter.FragmentStateAdapter
import com.google.android.material.tabs.TabLayout
import com.google.android.material.tabs.TabLayoutMediator
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {

    private lateinit var tabLayout:  TabLayout
    private lateinit var viewPager:  ViewPager2

    companion object {
        private const val PERMISSIONS_REQUEST_CODE = 100
        private val REQUIRED_PERMISSIONS = arrayOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_WIFI_STATE,
            Manifest.permission.CHANGE_WIFI_STATE
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        tabLayout = findViewById(R.id.tab_layout)
        viewPager = findViewById(R.id.view_pager)

        viewPager.adapter = TabAdapter(this)

        TabLayoutMediator(tabLayout, viewPager) { tab, position ->
            tab.text = when (position) {
                0 -> "AP Discovery"
                1 -> "Map & Pin"
                else -> ""
            }
        }.attach()

        requestPermissions()
    }

    private fun requestPermissions() {
        val missing = REQUIRED_PERMISSIONS.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(
                this,
                missing.toTypedArray(),
                PERMISSIONS_REQUEST_CODE
            )
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSIONS_REQUEST_CODE) {
            val allGranted = grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            if (!allGranted) {
                Toast.makeText(
                    this,
                    "Location permission required for Wi-Fi RTT ranging.",
                    Toast.LENGTH_LONG
                ).show()
            }
        }
    }

    private class TabAdapter(activity: FragmentActivity) : FragmentStateAdapter(activity) {
        override fun getItemCount(): Int = 2
        override fun createFragment(position: Int): Fragment = when (position) {
            0 -> ApDiscoveryFragment()
            1 -> MapPinFragment()
            else -> ApDiscoveryFragment()
        }
    }
}

// =============================================================================
// Fragment: AP Discovery (Tab 1)
// =============================================================================
class ApDiscoveryFragment : Fragment() {

    private lateinit var rttScanner: RttScanner
    private lateinit var apiClient:  ApiClient
    private lateinit var listView:   ListView
    private val apEntries = mutableListOf<RttScanner.ApEntry>()

    override fun onCreateView(
        inflater: android.view.LayoutInflater,
        container: android.view.ViewGroup?,
        savedInstanceState: Bundle?
    ): android.view.View {
        val layout = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }

        val btnScan = Button(requireContext()).apply { text = "Scan & Range APs" }
        listView    = ListView(requireContext())
        val btnPush = Button(requireContext()).apply { text = "Push to API" }

        layout.addView(btnScan)
        layout.addView(listView)
        layout.addView(btnPush)

        rttScanner = RttScanner(requireContext())
        apiClient  = ApiClient(requireContext())

        btnScan.setOnClickListener {
            lifecycleScope.launch {
                apEntries.clear()
                val results = rttScanner.rangeAllAPs()
                apEntries.addAll(results)
                val adapter = ArrayAdapter(
                    requireContext(),
                    android.R.layout.simple_list_item_2,
                    android.R.id.text1,
                    results.map { "${it.ssid} (${it.bssid})" }
                )
                listView.adapter = adapter
            }
        }

        btnPush.setOnClickListener {
            lifecycleScope.launch {
                for (ap in apEntries) {
                    apiClient.postAP(ap)
                }
                Toast.makeText(requireContext(), "Pushed ${apEntries.size} APs.", Toast.LENGTH_SHORT).show()
            }
        }

        return layout
    }
}

// =============================================================================
// Fragment: Map + Pin (Tab 2)
// =============================================================================
class MapPinFragment : Fragment() {

    private lateinit var mapView: MapView

    override fun onCreateView(
        inflater: android.view.LayoutInflater,
        container: android.view.ViewGroup?,
        savedInstanceState: Bundle?
    ): android.view.View {
        val layout = LinearLayout(requireContext()).apply {
            orientation = LinearLayout.VERTICAL
        }

        mapView = MapView(requireContext())
        layout.addView(mapView, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0, 1f
        ))

        val btnLoad = Button(requireContext()).apply { text = "Load Floor Plan" }
        layout.addView(btnLoad)

        btnLoad.setOnClickListener {
            mapView.promptLoadFloorPlan()
        }

        return layout
    }
}
