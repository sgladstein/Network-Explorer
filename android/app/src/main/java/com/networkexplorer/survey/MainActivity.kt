package com.networkexplorer.survey

import android.Manifest
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.location.LocationManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.text.SpannableStringBuilder
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import com.networkexplorer.survey.core.SignalScale
import com.networkexplorer.survey.core.Stats
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.Collections
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.math.max

/**
 * Walk-around Wi-Fi survey: pick a floor plan, tap where you're standing, press Measure.
 * Each measurement records the link (signal, band, channel, link rate, which eero), nearby
 * access points, latency and optional throughput to the survey server, which stores it and
 * replies with a diagnosis.
 */
class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("survey", MODE_PRIVATE) }
    private val worker = Executors.newSingleThreadExecutor()
    private val ui = Handler(Looper.getMainLooper())
    private lateinit var collector: WifiCollector

    private var server: SurveyServer? = null
    private var plans: List<FloorPlan> = emptyList()
    private var currentPlan: FloorPlan? = null
    private var measuring = false

    private lateinit var planSpinner: Spinner
    private lateinit var floorView: FloorPlanView
    private lateinit var statusView: TextView
    private lateinit var roomEdit: EditText
    private lateinit var speedCheck: CheckBox
    private lateinit var measureButton: Button
    private lateinit var resultView: TextView

    private val dp get() = resources.displayMetrics.density
    private fun px(v: Int) = (v * dp).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        collector = WifiCollector(this)
        collector.onChange = { ui.post { updateStatus() } }
        setContentView(buildUi())

        requestMissingPermissions()
        val url = prefs.getString("server", null)
        if (url.isNullOrBlank()) showServerDialog() else connect(url)
    }

    override fun onStart() {
        super.onStart()
        collector.start()
        ui.post(statusTicker)
    }

    override fun onStop() {
        super.onStop()
        collector.stop()
        ui.removeCallbacks(statusTicker)
    }

    override fun onDestroy() {
        super.onDestroy()
        worker.shutdownNow()
    }

    private val statusTicker = object : Runnable {
        override fun run() {
            updateStatus()
            ui.postDelayed(this, 1500)
        }
    }

    // UI -----------------------------------------------------------------------------------

    private fun buildUi(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(12), px(12), px(12), px(12))
        }

        val header = row()
        header.addView(TextView(this).apply {
            text = "Wi-Fi Survey"
            textSize = 20f
            setTypeface(typeface, Typeface.BOLD)
        }, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        header.addView(Button(this).apply { text = "Server"; setOnClickListener { showServerDialog() } })
        root.addView(header)

        val planRow = row()
        planSpinner = Spinner(this)
        planSpinner.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(p: AdapterView<*>?, v: View?, pos: Int, id: Long) {
                val plan = plans.getOrNull(pos) ?: return
                if (plan.id != currentPlan?.id) loadPlan(plan)
            }
            override fun onNothingSelected(p: AdapterView<*>?) {}
        }
        planRow.addView(planSpinner, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        planRow.addView(Button(this).apply { text = "Add plan"; setOnClickListener { pickFloorPlanImage() } })
        root.addView(planRow)

        floorView = FloorPlanView(this).apply {
            background = GradientDrawable().apply {
                setStroke(px(1), 0x40808080)
                cornerRadius = 6 * dp
            }
            onSpotSelected = { _, _ -> measureButton.isEnabled = !measuring }
        }
        root.addView(floorView, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f).apply {
            topMargin = px(8); bottomMargin = px(8)
        })

        statusView = TextView(this).apply { textSize = 13f; typeface = Typeface.MONOSPACE }
        root.addView(statusView)

        val roomRow = row()
        roomEdit = EditText(this).apply {
            hint = "Room (e.g. Kitchen)"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_WORDS
            setSingleLine()
            setText(prefs.getString("room", ""))
        }
        roomRow.addView(roomEdit, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        speedCheck = CheckBox(this).apply {
            text = "Speed test"
            isChecked = prefs.getBoolean("speed", true)
            setOnCheckedChangeListener { _, c -> prefs.edit().putBoolean("speed", c).apply() }
        }
        roomRow.addView(speedCheck)
        root.addView(roomRow)

        measureButton = Button(this).apply {
            text = "Tap the map where you're standing"
            isEnabled = false
            setOnClickListener { measure() }
        }
        root.addView(measureButton, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        resultView = TextView(this).apply { textSize = 14f; setPadding(0, px(6), 0, 0) }
        val scroll = ScrollView(this).apply { addView(resultView) }
        root.addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, px(170)))

        // Android 15 draws apps edge to edge; keep content clear of the system bars and keyboard.
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            val night = (resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES
            if (!night) {
                val light = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
                window.insetsController?.setSystemBarsAppearance(light, light)
            }
            root.setOnApplyWindowInsetsListener { v, insets ->
                val b = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.ime() or WindowInsets.Type.displayCutout())
                v.setPadding(px(12) + b.left, px(12) + b.top, px(12) + b.right, px(12) + b.bottom)
                insets
            }
        }
        return root
    }

    private fun row() = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_LONG).show()

    private fun updateStatus() {
        val snap = collector.snapshot()
        val sb = StringBuilder()
        if (snap?.rssi == null) {
            sb.append("Not connected to Wi-Fi")
        } else {
            sb.append(snap.ssid ?: "Wi-Fi")
            snap.band?.let { sb.append(" · $it GHz ch ${snap.channel ?: "?"}") }
            sb.append(" · ${snap.rssi} dBm (${SignalScale.grade(snap.rssi)})")
            snap.linkSpeedMbps?.let { sb.append(" · $it Mbps") }
            sb.append('\n').append(snap.bssid?.let { "Access point $it" } ?: "Allow location access to see which eero you're on")
        }
        if (!locationEnabled()) sb.append("\nTurn on Location in system settings so Android reports scan results.")
        if (!hasPermissions()) sb.append("\nLocation permission is off: tap Measure to grant it.")
        statusView.text = sb
    }

    // Permissions ---------------------------------------------------------------------------

    private fun missingPermissions(): List<String> {
        val wanted = mutableListOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) wanted += Manifest.permission.NEARBY_WIFI_DEVICES
        return wanted.filter { checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
    }

    private fun hasPermissions() = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

    private fun requestMissingPermissions() {
        val missing = missingPermissions()
        if (missing.isNotEmpty()) requestPermissions(missing.toTypedArray(), REQ_PERMISSIONS)
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_PERMISSIONS) {
            // Re-register so Android 12+ starts including the BSSID in callbacks.
            collector.stop(); collector.start()
            updateStatus()
        }
    }

    private fun locationEnabled(): Boolean =
        getSystemService(LocationManager::class.java)?.isLocationEnabled ?: true

    // Server and floor plans -----------------------------------------------------------------

    private fun showServerDialog() {
        val input = EditText(this).apply {
            hint = "http://192.168.4.20:8765"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setText(prefs.getString("server", ""))
            setSingleLine()
        }
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(px(20), px(8), px(20), 0)
            addView(TextView(this@MainActivity).apply {
                text = "Run `network-explorer serve` on a computer at home (ideally wired to an eero) and enter the address it prints."
            })
            addView(input)
        }
        AlertDialog.Builder(this)
            .setTitle("Survey server")
            .setView(box)
            .setPositiveButton("Connect") { _, _ ->
                var url = input.text.toString().trim()
                if (url.isNotEmpty() && !url.startsWith("http://") && !url.startsWith("https://")) url = "http://$url"
                if (url.isNotEmpty()) connect(url)
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun connect(url: String) {
        val srv = SurveyServer(url)
        resultView.text = "Connecting to ${srv.base}…"
        worker.execute {
            try {
                val version = srv.health()
                val list = srv.floorPlans()
                ui.post {
                    server = srv
                    prefs.edit().putString("server", srv.base).apply()
                    resultView.text = "Connected to ${srv.base} (server $version)."
                    showPlans(list, null)
                }
            } catch (e: Exception) {
                ui.post { resultView.text = "Couldn't reach ${srv.base}: ${e.message}\nCheck the address, and that the phone is on your home Wi-Fi." }
            }
        }
    }

    private fun refreshPlans(selectId: Int?) {
        val srv = server ?: return
        worker.execute {
            try {
                val list = srv.floorPlans()
                ui.post { showPlans(list, selectId) }
            } catch (e: Exception) {
                ui.post { toast("Couldn't load floor plans: ${e.message}") }
            }
        }
    }

    private fun showPlans(list: List<FloorPlan>, selectId: Int?) {
        plans = list
        planSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, list)
        if (list.isEmpty()) {
            currentPlan = null
            floorView.setFloorPlan(null, "Add a floor plan: a photo of a sketch works")
            return
        }
        val keep = selectId ?: currentPlan?.id ?: prefs.getInt("plan", -1)
        val idx = list.indexOfFirst { it.id == keep }.takeIf { it >= 0 } ?: 0
        currentPlan = null // force reload
        planSpinner.setSelection(idx)
        loadPlan(list[idx])
    }

    private fun loadPlan(plan: FloorPlan) {
        val srv = server ?: return
        currentPlan = plan
        prefs.edit().putInt("plan", plan.id).apply()
        measureButton.isEnabled = false
        measureButton.text = "Tap the map where you're standing"
        worker.execute {
            try {
                val bmp = decodeScaled(srv.floorPlanImage(plan.id), 2048)
                val pts = srv.samples(plan.id)
                ui.post {
                    if (currentPlan?.id != plan.id) return@post
                    floorView.setFloorPlan(bmp)
                    floorView.setPoints(pts)
                }
            } catch (e: Exception) {
                ui.post { toast("Couldn't load ${plan.name}: ${e.message}") }
            }
        }
    }

    private fun pickFloorPlanImage() {
        if (server == null) { showServerDialog(); return }
        val intent = Intent(Intent.ACTION_GET_CONTENT).setType("image/*").addCategory(Intent.CATEGORY_OPENABLE)
        @Suppress("DEPRECATION")
        startActivityForResult(intent, REQ_PICK_IMAGE)
    }

    // The framework Activity result API is deprecated in favour of AndroidX, which this app avoids.
    @Suppress("OVERRIDE_DEPRECATION")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        @Suppress("DEPRECATION")
        super.onActivityResult(requestCode, resultCode, data)
        val uri = data?.data
        if (requestCode == REQ_PICK_IMAGE && resultCode == RESULT_OK && uri != null) askPlanName(uri)
    }

    private fun askPlanName(uri: Uri) {
        val input = EditText(this).apply { hint = "Ground floor"; setSingleLine() }
        AlertDialog.Builder(this)
            .setTitle("Name this floor plan")
            .setView(input)
            .setPositiveButton("Upload") { _, _ -> uploadPlan(uri, input.text.toString().ifBlank { "Floor plan" }) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun uploadPlan(uri: Uri, name: String) {
        val srv = server ?: return
        worker.execute {
            try {
                val raw = contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: throw IOException("Couldn't read the image")
                // Phone photos can be huge; a 2400 px JPEG is plenty for a floor plan.
                val bmp = decodeScaled(raw, 2400) ?: throw IOException("That file isn't an image Android can read")
                val jpeg = ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.JPEG, 88, it) }.toByteArray()
                val plan = srv.uploadFloorPlan(name, jpeg, "image/jpeg")
                ui.post { toast("Added ${plan.name}"); refreshPlans(plan.id) }
            } catch (e: Exception) {
                ui.post { toast("Upload failed: ${e.message}") }
            }
        }
    }

    private fun decodeScaled(bytes: ByteArray, maxDim: Int): Bitmap? {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
        var sample = 1
        while (max(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxDim) sample *= 2
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
    }

    // Measurement ---------------------------------------------------------------------------

    private fun measure() {
        val srv = server ?: run { showServerDialog(); return }
        val plan = currentPlan ?: run { toast("Add or pick a floor plan first"); return }
        val spot = floorView.marker ?: run { toast("Tap the map where you're standing first"); return }
        if (!hasPermissions()) {
            requestMissingPermissions()
            toast("Location permission lets the app see which eero you're on. Measure again once granted.")
            return
        }
        val room = roomEdit.text.toString().trim()
        prefs.edit().putString("room", room).apply()
        val withSpeed = speedCheck.isChecked

        measuring = true
        measureButton.isEnabled = false
        measureButton.text = "Measuring… stay still"
        resultView.text = ""

        worker.execute {
            val rssiReadings = Collections.synchronizedList(mutableListOf<Double>())
            val sampler = Executors.newSingleThreadScheduledExecutor()
            try {
                val network = collector.wifiNetwork ?: throw IOException("Not connected to Wi-Fi")
                sampler.scheduleWithFixedDelay({
                    collector.snapshot()?.rssi?.let { rssiReadings.add(it.toDouble()) }
                }, 0, 500, TimeUnit.MILLISECONDS)

                progress("Scanning nearby networks…")
                val scan = collector.scan()
                progress("Measuring latency…")
                val ping = srv.ping(network)
                var down: Double? = null
                var up: Double? = null
                if (withSpeed) {
                    progress("Testing download…")
                    down = runCatching { srv.download(network) }.getOrNull()
                    progress("Testing upload…")
                    up = runCatching { srv.upload(network, Stats.uploadBytesFor(down)) }.getOrNull()
                }
                sampler.shutdownNow()

                val snap = collector.snapshot() ?: throw IOException("Lost the Wi-Fi connection during the test")
                val rssi = Stats.median(rssiReadings.toList())?.toInt() ?: snap.rssi
                val width = scan.firstOrNull { it.bssid == snap.bssid }?.channelWidthMhz

                val body = JSONObject().apply {
                    put("x", spot.first.toDouble()); put("y", spot.second.toDouble())
                    putOpt("room", room.ifEmpty { null })
                    put("device_model", "${Build.MANUFACTURER} ${Build.MODEL}")
                    putOpt("ssid", snap.ssid); putOpt("bssid", snap.bssid); putOpt("rssi", rssi)
                    putOpt("frequency_mhz", snap.frequencyMhz); putOpt("channel_width_mhz", width)
                    putOpt("link_speed_mbps", snap.linkSpeedMbps)
                    putOpt("tx_link_speed_mbps", snap.txLinkSpeedMbps); putOpt("rx_link_speed_mbps", snap.rxLinkSpeedMbps)
                    putOpt("wifi_standard", snap.wifiStandard)
                    putOpt("latency_ms_median", ping.medianMs); putOpt("latency_jitter_ms", ping.jitterMs)
                    putOpt("packet_loss_pct", ping.lossPct)
                    putOpt("download_mbps", down); putOpt("upload_mbps", up)
                    put("scan", JSONArray().apply {
                        scan.take(100).forEach { e ->
                            put(JSONObject().apply {
                                put("bssid", e.bssid); putOpt("ssid", e.ssid); put("rssi", e.rssi)
                                put("frequency_mhz", e.frequencyMhz); putOpt("channel_width_mhz", e.channelWidthMhz)
                            })
                        }
                    })
                }
                val saved = srv.postSample(plan.id, body)
                val points = runCatching { srv.samples(plan.id) }.getOrNull()
                ui.post {
                    showResult(saved)
                    points?.let { floorView.setPoints(it) }
                    floorView.clearMarker()
                }
            } catch (e: Exception) {
                ui.post { resultView.text = "Measurement failed: ${e.message}" }
            } finally {
                sampler.shutdownNow()
                ui.post {
                    measuring = false
                    measureButton.text = "Tap the next spot"
                    measureButton.isEnabled = floorView.marker != null
                }
            }
        }
    }

    private fun progress(msg: String) = ui.post { measureButton.text = msg }

    private fun showResult(s: JSONObject) {
        val sb = SpannableStringBuilder()
        fun opt(key: String): Double? = if (s.isNull(key)) null else s.optDouble(key).takeIf { !it.isNaN() }
        val parts = mutableListOf<String>()
        s.optString("room").takeIf { it.isNotEmpty() && it != "null" }?.let { parts += it }
        opt("rssi")?.let { parts += "${it.toInt()} dBm (${s.optString("signal_grade")})" }
        if (!s.isNull("band")) parts += "${s.optString("band")} GHz ch ${s.optString("channel")}"
        opt("link_speed_mbps")?.let { parts += "${it.toInt()} Mbps link" }
        sb.append(parts.joinToString(" · ")).append('\n')
        val perf = mutableListOf<String>()
        opt("download_mbps")?.let { perf += "Down ${"%.0f".format(it)} Mbps" }
        opt("upload_mbps")?.let { perf += "Up ${"%.0f".format(it)} Mbps" }
        opt("latency_ms_median")?.let { perf += "Ping ${"%.0f".format(it)} ms" }
        opt("latency_jitter_ms")?.let { perf += "jitter ${"%.0f".format(it)} ms" }
        opt("packet_loss_pct")?.let { perf += "${"%.0f".format(it)}% loss" }
        sb.append(perf.joinToString(" · ")).append("\n")

        val findings = s.optJSONArray("findings") ?: JSONArray()
        for (i in 0 until findings.length()) {
            val f = findings.getJSONObject(i)
            val color = when (f.optString("severity")) {
                "bad" -> 0xFFC0392B.toInt()
                "warn" -> 0xFFB7791F.toInt()
                "ok" -> 0xFF2E8B57.toInt()
                else -> 0xFF2F6F9F.toInt()
            }
            sb.append('\n')
            val start = sb.length
            sb.append(f.optString("title"))
            sb.setSpan(StyleSpan(Typeface.BOLD), start, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            sb.setSpan(ForegroundColorSpan(color), start, sb.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
            sb.append('\n').append(f.optString("detail")).append('\n')
        }
        resultView.text = sb
    }

    companion object {
        private const val REQ_PERMISSIONS = 1
        private const val REQ_PICK_IMAGE = 2
    }
}
