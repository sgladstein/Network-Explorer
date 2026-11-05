package com.networkexplorer.survey

import android.net.Network
import com.networkexplorer.survey.core.Stats
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID

data class FloorPlan(val id: Int, val name: String, val sampleCount: Int) {
    override fun toString() = "$name ($sampleCount)"
}

data class PingResult(val medianMs: Double?, val jitterMs: Double?, val lossPct: Double?)

/**
 * Talks to the Network Explorer survey server. All methods block; call them off the main thread.
 *
 * Measurement requests are opened through the Wi-Fi [Network] when we have one, so a phone
 * with mobile data never quietly runs the test over the cellular link.
 */
class SurveyServer(baseUrl: String) {
    val base: String = baseUrl.trim().trimEnd('/')

    private fun open(path: String, network: Network? = null, timeoutMs: Int = 5000): HttpURLConnection {
        val url = URL(base + path)
        val conn = (network?.openConnection(url) ?: url.openConnection()) as HttpURLConnection
        conn.connectTimeout = timeoutMs
        conn.readTimeout = timeoutMs
        conn.useCaches = false
        return conn
    }

    private fun HttpURLConnection.readBody(): String {
        val code = responseCode
        val stream = if (code in 200..299) inputStream else errorStream
        val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
        if (code !in 200..299) {
            val detail = runCatching { JSONObject(text).optString("detail") }.getOrNull()
            throw IOException("Server returned $code${if (!detail.isNullOrEmpty()) ": $detail" else ""}")
        }
        return text
    }

    fun health(): String {
        val conn = open("/api/health", timeoutMs = 3000)
        try {
            val json = JSONObject(conn.readBody())
            if (json.optString("name") != "network-explorer") throw IOException("That address isn't a Network Explorer server")
            return json.optString("version")
        } finally {
            conn.disconnect()
        }
    }

    fun floorPlans(): List<FloorPlan> {
        val conn = open("/api/floorplans")
        try {
            val arr = JSONArray(conn.readBody())
            return (0 until arr.length()).map {
                val o = arr.getJSONObject(it)
                FloorPlan(o.getInt("id"), o.getString("name"), o.optInt("sample_count"))
            }
        } finally {
            conn.disconnect()
        }
    }

    fun floorPlanImage(id: Int): ByteArray {
        val conn = open("/api/floorplans/$id/image", timeoutMs = 15000)
        try {
            if (conn.responseCode != 200) throw IOException("Couldn't load floor plan image (${conn.responseCode})")
            return conn.inputStream.use { it.readBytes() }
        } finally {
            conn.disconnect()
        }
    }

    fun uploadFloorPlan(name: String, image: ByteArray, mimeType: String): FloorPlan {
        val boundary = "----survey" + UUID.randomUUID().toString().replace("-", "")
        val body = ByteArrayOutputStream()
        fun part(header: String) = body.write(("--$boundary\r\n$header\r\n\r\n").toByteArray())
        part("Content-Disposition: form-data; name=\"name\"")
        body.write(name.toByteArray()); body.write("\r\n".toByteArray())
        part("Content-Disposition: form-data; name=\"image\"; filename=\"floorplan\"\r\nContent-Type: $mimeType")
        body.write(image); body.write("\r\n".toByteArray())
        body.write("--$boundary--\r\n".toByteArray())
        val bytes = body.toByteArray()

        val conn = open("/api/floorplans", timeoutMs = 30000)
        try {
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
            conn.setFixedLengthStreamingMode(bytes.size)
            conn.outputStream.use { it.write(bytes) }
            val o = JSONObject(conn.readBody())
            return FloorPlan(o.getInt("id"), o.getString("name"), 0)
        } finally {
            conn.disconnect()
        }
    }

    /** Returns the saved points as (x, y, rssi) triples for drawing. */
    fun samples(floorPlanId: Int): List<SamplePoint> {
        val conn = open("/api/floorplans/$floorPlanId/samples", timeoutMs = 10000)
        try {
            val arr = JSONArray(conn.readBody())
            return (0 until arr.length()).map {
                val o = arr.getJSONObject(it)
                SamplePoint(
                    o.getDouble("x").toFloat(), o.getDouble("y").toFloat(),
                    if (o.isNull("rssi")) null else o.getInt("rssi"),
                )
            }
        } finally {
            conn.disconnect()
        }
    }

    fun postSample(floorPlanId: Int, sample: JSONObject): JSONObject {
        val bytes = sample.toString().toByteArray()
        val conn = open("/api/floorplans/$floorPlanId/samples", timeoutMs = 10000)
        try {
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/json")
            conn.setFixedLengthStreamingMode(bytes.size)
            conn.outputStream.use { it.write(bytes) }
            return JSONObject(conn.readBody())
        } finally {
            conn.disconnect()
        }
    }

    // Measurements --------------------------------------------------------------------------

    /** Sequential HTTP round trips to the server. The first one only warms up the connection. */
    fun ping(network: Network?, count: Int = 20, timeoutMs: Int = 1000, gapMs: Long = 80): PingResult {
        val rtts = mutableListOf<Double>()
        var lost = 0
        for (i in 0..count) {
            val start = System.nanoTime()
            val ok = try {
                val conn = open("/api/ping", network, timeoutMs)
                val code = conn.responseCode
                runCatching { conn.inputStream.use { it.readBytes() } }
                code in 200..299
            } catch (e: IOException) {
                false
            }
            val ms = (System.nanoTime() - start) / 1e6
            if (i > 0) {
                if (ok) rtts.add(ms) else lost++
            }
            Thread.sleep(gapMs)
        }
        return PingResult(Stats.median(rtts), Stats.jitter(rtts), Stats.lossPct(count, lost))
    }

    /** Downloads for up to [maxSeconds] and returns Mbps. Timing starts at the first byte. */
    fun download(network: Network?, maxBytes: Long = 150_000_000, maxSeconds: Double = 5.0): Double? {
        val conn = open("/api/speedtest/download?bytes=$maxBytes", network, 10000)
        try {
            conn.inputStream.use { input ->
                val buf = ByteArray(64 * 1024)
                if (input.read(buf) <= 0) return null
                val start = System.nanoTime()
                var total = 0L
                val limit = (maxSeconds * 1e9).toLong()
                while (true) {
                    val n = input.read(buf)
                    if (n < 0) break
                    total += n
                    if (System.nanoTime() - start > limit) break
                }
                return Stats.mbps(total, System.nanoTime() - start)
            }
        } finally {
            conn.disconnect()
        }
    }

    /** Uploads [bytes] (stopping early after [maxSeconds]) and returns Mbps. */
    fun upload(network: Network?, bytes: Int, maxSeconds: Double = 6.0): Double? {
        val conn = open("/api/speedtest/upload", network, 15000)
        val chunk = ByteArray(64 * 1024).also { java.util.Random().nextBytes(it) }
        try {
            conn.requestMethod = "POST"
            conn.doOutput = true
            conn.setRequestProperty("Content-Type", "application/octet-stream")
            conn.setFixedLengthStreamingMode(bytes)
            val start = System.nanoTime()
            val limit = (maxSeconds * 1e9).toLong()
            var sent = 0L
            var finished = false
            try {
                conn.outputStream.use { out ->
                    while (sent < bytes) {
                        val n = minOf(chunk.size.toLong(), bytes - sent).toInt()
                        out.write(chunk, 0, n)
                        sent += n
                        if (System.nanoTime() - start > limit) break
                    }
                }
                if (sent >= bytes) {
                    conn.readBody()
                    finished = true
                }
            } catch (e: IOException) {
                if (sent == 0L) throw e
            }
            val elapsed = System.nanoTime() - start
            return if (finished || sent > 0) Stats.mbps(sent, elapsed) else null
        } finally {
            conn.disconnect()
        }
    }
}
