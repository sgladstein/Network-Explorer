package com.networkexplorer.survey.core

import kotlin.math.abs
import kotlin.math.roundToInt

/** Pure helpers with no Android dependencies, so they can be unit-tested on the JVM. */
object Stats {
    fun median(xs: List<Double>): Double? {
        if (xs.isEmpty()) return null
        val s = xs.sorted()
        val mid = s.size / 2
        return if (s.size % 2 == 1) s[mid] else (s[mid - 1] + s[mid]) / 2.0
    }

    /** Mean absolute difference between consecutive round-trip times (the RFC 3550 idea of jitter). */
    fun jitter(rtts: List<Double>): Double? {
        if (rtts.size < 2) return null
        return rtts.zipWithNext { a, b -> abs(b - a) }.average()
    }

    fun lossPct(sent: Int, lost: Int): Double? = if (sent <= 0) null else 100.0 * lost / sent

    fun mbps(bytes: Long, nanos: Long): Double? = if (nanos <= 0 || bytes <= 0) null else bytes * 8.0 / (nanos / 1e9) / 1e6

    /** Upload enough data to last about [seconds] at the measured download speed, within sane bounds. */
    fun uploadBytesFor(downloadMbps: Double?, seconds: Double = 4.0): Int {
        val min = 2_000_000
        val max = 60_000_000
        if (downloadMbps == null) return 8_000_000
        val bytes = downloadMbps * 1e6 / 8 * seconds
        return bytes.coerceIn(min.toDouble(), max.toDouble()).toInt()
    }
}

object WifiMath {
    fun band(freqMhz: Int?): String? = when (freqMhz) {
        null -> null
        in 2400 until 2500 -> "2.4"
        in 5150 until 5925 -> "5"
        in 5925..7125 -> "6"
        else -> null
    }

    fun channel(freqMhz: Int?): Int? {
        if (freqMhz == null) return null
        if (freqMhz == 2484) return 14
        return when (band(freqMhz)) {
            "2.4" -> (freqMhz - 2407) / 5
            "5" -> (freqMhz - 5000) / 5
            "6" -> (freqMhz - 5950) / 5
            else -> null
        }
    }

    /** android.net.wifi.ScanResult.CHANNEL_WIDTH_* constant to MHz. */
    fun channelWidthMhz(code: Int): Int? = when (code) {
        0 -> 20
        1 -> 40
        2 -> 80
        3, 4 -> 160
        5 -> 320
        else -> null
    }

    /** android.net.wifi.ScanResult.WIFI_STANDARD_* constant to a readable name. */
    fun standardName(code: Int): String? = when (code) {
        1 -> "802.11a/b/g"
        4 -> "Wi-Fi 4 (802.11n)"
        5 -> "Wi-Fi 5 (802.11ac)"
        6 -> "Wi-Fi 6 (802.11ax)"
        7 -> "802.11ad"
        8 -> "Wi-Fi 7 (802.11be)"
        else -> null
    }

    /** Android hides the real BSSID behind this value without location permission. */
    fun isRealBssid(bssid: String?): Boolean =
        bssid != null && bssid != "02:00:00:00:00:00" && bssid != "00:00:00:00:00:00"

    fun cleanSsid(ssid: String?): String? {
        if (ssid == null) return null
        val s = ssid.removeSurrounding("\"")
        return if (s.isEmpty() || s == "<unknown ssid>") null else s
    }
}

/** Same grading and colours as the web viewer, so a dot looks the same on the phone and the PC. */
object SignalScale {
    const val EXCELLENT = -60
    const val GOOD = -67
    const val FAIR = -75

    fun grade(rssi: Int?): String = when {
        rssi == null -> "unknown"
        rssi >= EXCELLENT -> "excellent"
        rssi >= GOOD -> "good"
        rssi >= FAIR -> "fair"
        else -> "poor"
    }

    private val stops = listOf(
        0.0 to intArrayOf(200, 50, 40),
        0.5 to intArrayOf(230, 170, 40),
        1.0 to intArrayOf(40, 160, 90),
    )

    /** ARGB colour for an RSSI between -85 dBm (red) and -50 dBm (green); grey when unknown. */
    fun colorFor(rssi: Int?): Int {
        if (rssi == null) return 0xFF8A949E.toInt()
        val t = ((rssi - -85).toDouble() / (-50 - -85)).coerceIn(0.0, 1.0)
        for (i in 1 until stops.size) {
            val (t1, c1) = stops[i]
            val (t0, c0) = stops[i - 1]
            if (t <= t1) {
                val k = (t - t0) / (t1 - t0)
                val r = (c0[0] + (c1[0] - c0[0]) * k).roundToInt()
                val g = (c0[1] + (c1[1] - c0[1]) * k).roundToInt()
                val b = (c0[2] + (c1[2] - c0[2]) * k).roundToInt()
                return (0xFF shl 24) or (r shl 16) or (g shl 8) or b
            }
        }
        return 0xFF28A05A.toInt()
    }
}
