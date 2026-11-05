package com.networkexplorer.survey.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class MeasurementsTest {
    @Test
    fun medianOddEvenEmpty() {
        assertEquals(3.0, Stats.median(listOf(5.0, 1.0, 3.0))!!, 1e-9)
        assertEquals(2.5, Stats.median(listOf(4.0, 1.0, 2.0, 3.0))!!, 1e-9)
        assertNull(Stats.median(emptyList()))
    }

    @Test
    fun jitterIsMeanConsecutiveDifference() {
        assertEquals(5.0, Stats.jitter(listOf(10.0, 20.0, 15.0, 15.0))!!, 1e-9)
        assertNull(Stats.jitter(listOf(10.0)))
    }

    @Test
    fun lossAndThroughput() {
        assertEquals(10.0, Stats.lossPct(20, 2)!!, 1e-9)
        assertNull(Stats.lossPct(0, 0))
        // 12.5 MB in one second is 100 Mbps.
        assertEquals(100.0, Stats.mbps(12_500_000, 1_000_000_000)!!, 1e-9)
        assertNull(Stats.mbps(0, 1))
    }

    @Test
    fun uploadSizeScalesWithDownloadSpeed() {
        assertEquals(8_000_000, Stats.uploadBytesFor(null))
        assertEquals(2_000_000, Stats.uploadBytesFor(1.0))
        assertEquals(50_000_000, Stats.uploadBytesFor(100.0))
        assertEquals(60_000_000, Stats.uploadBytesFor(900.0))
    }

    @Test
    fun channelsMatchServer() {
        assertEquals(1, WifiMath.channel(2412))
        assertEquals(14, WifiMath.channel(2484))
        assertEquals(36, WifiMath.channel(5180))
        assertEquals(149, WifiMath.channel(5745))
        assertEquals(1, WifiMath.channel(5955))
        assertEquals("6", WifiMath.band(5955))
        assertNull(WifiMath.channel(900))
    }

    @Test
    fun bssidAndSsidCleanup() {
        assertFalse(WifiMath.isRealBssid("02:00:00:00:00:00"))
        assertTrue(WifiMath.isRealBssid("aa:bb:cc:dd:ee:ff"))
        assertEquals("Home", WifiMath.cleanSsid("\"Home\""))
        assertNull(WifiMath.cleanSsid("<unknown ssid>"))
    }

    @Test
    fun signalColours() {
        assertEquals("good", SignalScale.grade(-65))
        assertEquals("poor", SignalScale.grade(-80))
        assertEquals(0xFFC83228.toInt(), SignalScale.colorFor(-95))
        assertEquals(0xFF28A05A.toInt(), SignalScale.colorFor(-40))
        assertEquals(0xFF8A949E.toInt(), SignalScale.colorFor(null))
    }
}
