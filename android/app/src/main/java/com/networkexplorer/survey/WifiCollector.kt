package com.networkexplorer.survey

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.ScanResult
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.SystemClock
import com.networkexplorer.survey.core.WifiMath
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** What the phone knows about its current Wi-Fi connection. */
data class WifiSnapshot(
    val ssid: String?,
    val bssid: String?,
    val rssi: Int?,
    val frequencyMhz: Int?,
    val linkSpeedMbps: Int?,
    val txLinkSpeedMbps: Int?,
    val rxLinkSpeedMbps: Int?,
    val wifiStandard: String?,
) {
    val band: String? get() = WifiMath.band(frequencyMhz)
    val channel: Int? get() = WifiMath.channel(frequencyMhz)
}

data class ScanEntry(
    val bssid: String,
    val ssid: String?,
    val rssi: Int,
    val frequencyMhz: Int,
    val channelWidthMhz: Int?,
)

/**
 * Reads the current Wi-Fi link and nearby access points.
 *
 * On Android 12+ the BSSID only comes through a network callback registered with
 * FLAG_INCLUDE_LOCATION_INFO, so we keep one registered while the app is visible. The
 * same callback hands us the Wi-Fi [Network], which the speed tests bind to so they
 * never fall back to mobile data.
 */
class WifiCollector(private val context: Context) {
    private val wifi: WifiManager = requireNotNull(context.applicationContext.getSystemService(WifiManager::class.java)) { "No Wi-Fi on this device" }
    private val cm: ConnectivityManager = requireNotNull(context.applicationContext.getSystemService(ConnectivityManager::class.java))

    @Volatile private var latestInfo: WifiInfo? = null
    @Volatile var wifiNetwork: Network? = null
        private set
    private var callback: ConnectivityManager.NetworkCallback? = null

    /** Called (on a background thread) whenever the link changes, including RSSI changes. */
    var onChange: (() -> Unit)? = null

    fun start() {
        if (callback != null) return
        val cb = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            object : ConnectivityManager.NetworkCallback(FLAG_INCLUDE_LOCATION_INFO) {
                override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) = update(network, caps)
                override fun onLost(network: Network) = lost(network)
            }
        } else {
            object : ConnectivityManager.NetworkCallback() {
                override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) = update(network, caps)
                override fun onLost(network: Network) = lost(network)
            }
        }
        val request = NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build()
        cm.registerNetworkCallback(request, cb)
        callback = cb
    }

    fun stop() {
        callback?.let { runCatching { cm.unregisterNetworkCallback(it) } }
        callback = null
    }

    private fun update(network: Network, caps: NetworkCapabilities) {
        wifiNetwork = network
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            (caps.transportInfo as? WifiInfo)?.let { latestInfo = it }
        }
        onChange?.invoke()
    }

    private fun lost(network: Network) {
        if (network == wifiNetwork) {
            wifiNetwork = null
            latestInfo = null
        }
        onChange?.invoke()
    }

    @Suppress("DEPRECATION")
    private fun currentInfo(): WifiInfo? {
        // Before Android 12, connectionInfo still carries the BSSID (given location permission)
        // and is refreshed more eagerly than the callback.
        return if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) wifi.connectionInfo else latestInfo ?: wifi.connectionInfo
    }

    fun snapshot(): WifiSnapshot? {
        val info = currentInfo() ?: return null
        if (info.networkId == -1 && info.rssi <= -127) return null
        val rssi = info.rssi.takeIf { it in -126..0 }
        val bssid = info.bssid?.lowercase()?.takeIf { WifiMath.isRealBssid(it) }
        return WifiSnapshot(
            ssid = WifiMath.cleanSsid(info.ssid),
            bssid = bssid,
            rssi = rssi,
            frequencyMhz = info.frequency.takeIf { it > 0 },
            linkSpeedMbps = info.linkSpeed.takeIf { it > 0 },
            txLinkSpeedMbps = info.txLinkSpeedMbps.takeIf { it > 0 },
            rxLinkSpeedMbps = info.rxLinkSpeedMbps.takeIf { it > 0 },
            wifiStandard = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) WifiMath.standardName(info.wifiStandard) else null,
        )
    }

    /**
     * Requests a scan and waits up to [timeoutMs] for results. Android throttles apps to
     * four scans every two minutes; when throttled we fall back to the system's recent
     * cached results (no older than [maxAgeMs]). Call from a background thread.
     */
    @Suppress("DEPRECATION")
    fun scan(timeoutMs: Long = 6000, maxAgeMs: Long = 120_000): List<ScanEntry> {
        val latch = CountDownLatch(1)
        val receiver = object : BroadcastReceiver() {
            override fun onReceive(c: Context, intent: Intent) = latch.countDown()
        }
        val filter = IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION)
        val app = context.applicationContext
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            app.registerReceiver(receiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            app.registerReceiver(receiver, filter)
        }
        try {
            val started = runCatching { wifi.startScan() }.getOrDefault(false)
            if (started) latch.await(timeoutMs, TimeUnit.MILLISECONDS)
        } finally {
            runCatching { app.unregisterReceiver(receiver) }
        }
        val nowUs = SystemClock.elapsedRealtimeNanos() / 1000
        val results: List<ScanResult> = try {
            wifi.scanResults ?: emptyList()
        } catch (e: SecurityException) {
            emptyList()
        }
        return results
            .filter { nowUs - it.timestamp <= maxAgeMs * 1000 }
            .mapNotNull { r ->
                val bssid = r.BSSID?.lowercase()?.takeIf { WifiMath.isRealBssid(it) } ?: return@mapNotNull null
                ScanEntry(bssid, WifiMath.cleanSsid(r.SSID), r.level, r.frequency, WifiMath.channelWidthMhz(r.channelWidth))
            }
            .sortedByDescending { it.rssi }
    }
}
