"use strict";

// Metric definitions: how to turn a value into 0 (bad) .. 1 (good).
const METRICS = {
  rssi: { label: "Signal", unit: "dBm", lo: -85, hi: -50, fmt: (v) => `${Math.round(v)} dBm` },
  download_mbps: { label: "Download", unit: "Mbps", lo: 0, hi: null, fmt: (v) => `${v.toFixed(0)} Mbps` },
  upload_mbps: { label: "Upload", unit: "Mbps", lo: 0, hi: null, fmt: (v) => `${v.toFixed(0)} Mbps` },
  latency_ms_median: { label: "Latency", unit: "ms", lo: 150, hi: 5, fmt: (v) => `${v.toFixed(0)} ms` },
};
// Heat colours: red (poor) -> amber -> green (good). Drawn over the floor plan, so theme-independent.
const STOPS = [[0, [200, 50, 40]], [0.5, [230, 170, 40]], [1, [40, 160, 90]]];

// Short names for grouping the same problem across many spots.
const PROBLEM_NAMES = {
  no_wifi: "No Wi-Fi reading", weak_signal: "Weak signal", marginal_signal: "Marginal signal",
  sticky_client: "Phone holding on to a farther eero", on_2g: "On 2.4 GHz although 5/6 GHz is usable",
  busy_channel: "Crowded channel", packet_loss: "Heavy packet loss", congestion: "Good signal but laggy",
  slow_link: "Low link rate despite strong signal", slow_throughput: "Slow despite a good link",
};

const state = { plans: [], planId: null, samples: [], summary: null, labels: {}, metric: "rssi", ap: "", selected: null, image: null };
const $ = (id) => document.getElementById(id);
const canvas = $("map");
const ctx = canvas.getContext("2d");

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `${res.status}`;
    try { msg = (await res.json()).detail || msg; } catch (_) { /* not JSON */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function lerpColor(t) {
  t = Math.max(0, Math.min(1, t));
  for (let i = 1; i < STOPS.length; i++) {
    const [t1, c1] = STOPS[i];
    const [t0, c0] = STOPS[i - 1];
    if (t <= t1) {
      const k = (t - t0) / (t1 - t0);
      return c0.map((v, j) => Math.round(v + (c1[j] - v) * k));
    }
  }
  return STOPS[STOPS.length - 1][1];
}

function metricRange(metric, samples) {
  const m = METRICS[metric];
  let hi = m.hi;
  if (hi === null) {
    const vals = samples.map((s) => s[metric]).filter((v) => v != null);
    hi = Math.max(100, ...vals);
  }
  return { lo: m.lo, hi };
}

function score(metric, v, range) {
  return (v - range.lo) / (range.hi - range.lo);
}

function visibleSamples() {
  return state.samples.filter((s) => (!state.ap || s.bssid === state.ap) && s[state.metric] != null);
}

// Rendering ---------------------------------------------------------------------------

function draw() {
  const img = state.image;
  if (!img) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

  const pts = visibleSamples();
  const range = metricRange(state.metric, state.samples);
  if (pts.length) drawHeat(pts, range);

  const r = Math.max(6, canvas.width / 110);
  for (const s of state.samples) {
    const x = s.x * canvas.width, y = s.y * canvas.height;
    const v = s[state.metric];
    const inFilter = !state.ap || s.bssid === state.ap;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    if (v != null && inFilter) {
      const [cr, cg, cb] = lerpColor(score(state.metric, v, range));
      ctx.fillStyle = `rgb(${cr},${cg},${cb})`;
    } else {
      ctx.fillStyle = "rgba(120,130,140,0.6)";
    }
    ctx.fill();
    ctx.lineWidth = s.id === state.selected ? r * 0.6 : r * 0.3;
    ctx.strokeStyle = s.id === state.selected ? "#000" : "rgba(255,255,255,0.95)";
    ctx.stroke();
  }
  renderLegend(range);
}

// Inverse-distance-weighted interpolation on a coarse grid, faded out away from
// measured spots so the map doesn't pretend to know rooms nobody measured.
function drawHeat(pts, range) {
  const aspect = canvas.height / canvas.width;
  const gw = 140, gh = Math.max(1, Math.round(gw * aspect));
  const off = document.createElement("canvas");
  off.width = gw; off.height = gh;
  const octx = off.getContext("2d");
  const data = octx.createImageData(gw, gh);
  const reach = 0.14; // fraction of the plan width a measurement "covers"
  for (let gy = 0; gy < gh; gy++) {
    for (let gx = 0; gx < gw; gx++) {
      const px = (gx + 0.5) / gw, py = ((gy + 0.5) / gh) * aspect;
      let wsum = 0, vsum = 0, dmin = Infinity;
      for (const s of pts) {
        const dx = px - s.x, dy = py - s.y * aspect;
        const d2 = dx * dx + dy * dy;
        dmin = Math.min(dmin, d2);
        const w = 1 / (d2 + 1e-5);
        wsum += w;
        vsum += w * score(state.metric, s[state.metric], range);
      }
      const d = Math.sqrt(dmin);
      const fade = Math.max(0, Math.min(1, 1 - (d - reach * 0.5) / reach));
      const [r, g, b] = lerpColor(vsum / wsum);
      const i = (gy * gw + gx) * 4;
      data.data[i] = r; data.data[i + 1] = g; data.data[i + 2] = b;
      data.data[i + 3] = Math.round(150 * fade);
    }
  }
  octx.putImageData(data, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(off, 0, 0, canvas.width, canvas.height);
}

function renderLegend(range) {
  const m = METRICS[state.metric];
  const grad = STOPS.map(([t, c]) => `rgb(${c.join(",")}) ${t * 100}%`).join(", ");
  const lo = m.fmt(range.lo), hi = m.fmt(range.hi);
  const n = visibleSamples().length;
  $("legend").innerHTML =
    `<span>${esc(lo)}</span><span class="legend-bar" style="background:linear-gradient(90deg, ${grad})"></span>` +
    `<span>${esc(hi)}</span><span>· ${n} spot${n === 1 ? "" : "s"} with ${esc(m.label.toLowerCase())} data</span>`;
}

function sevPill(sev) {
  const names = { bad: "Problem", warn: "Warning", info: "Note", ok: "Good" };
  return `<span class="pill sev-${sev}">${names[sev] || sev}</span>`;
}

function findingItems(list) {
  return list.map((f) =>
    `<li class="finding sev-${esc(f.severity)}"><div><div class="finding-title">${esc(f.title)}</div>` +
    `<div class="finding-detail">${esc(f.detail)}</div></div></li>`).join("");
}

function apName(bssid) {
  return state.labels[bssid] || bssid || "—";
}

function renderDetail() {
  const s = state.samples.find((x) => x.id === state.selected);
  $("detail-panel").hidden = !s;
  if (!s) return;
  const when = new Date(s.created_at * 1000).toLocaleString();
  const row = (k, v) => (v == null || v === "" ? "" : `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`);
  $("detail").innerHTML =
    `<dl class="kv">` +
    row("Room", s.room) + row("Taken", when) + row("Phone", s.device_model) +
    row("Access point", apName(s.bssid)) + row("BSSID", s.bssid) +
    row("Band / channel", s.band ? `${s.band} GHz · ch ${s.channel ?? "?"}${s.channel_width_mhz ? ` · ${s.channel_width_mhz} MHz` : ""}` : null) +
    row("Signal", s.rssi != null ? `${s.rssi} dBm (${s.signal_grade})` : null) +
    row("Link rate", s.link_speed_mbps != null ? `${s.link_speed_mbps} Mbps (tx ${s.tx_link_speed_mbps ?? "?"} / rx ${s.rx_link_speed_mbps ?? "?"})` : null) +
    row("Wi-Fi standard", s.wifi_standard) +
    row("Download", s.download_mbps != null ? `${s.download_mbps.toFixed(1)} Mbps` : null) +
    row("Upload", s.upload_mbps != null ? `${s.upload_mbps.toFixed(1)} Mbps` : null) +
    row("Latency", s.latency_ms_median != null ? `${s.latency_ms_median.toFixed(1)} ms (jitter ${s.latency_jitter_ms?.toFixed(1) ?? "?"} ms)` : null) +
    row("Packet loss", s.packet_loss_pct != null ? `${s.packet_loss_pct.toFixed(0)}%` : null) +
    row("Networks seen", s.scan?.length ? `${s.scan.length}` : null) +
    `</dl><ul class="findings">${findingItems(s.findings || [])}</ul>`;
}

function renderSummary() {
  const sum = state.summary;
  if (!sum) return;
  // Survey-wide findings first, then the worst per-spot problems by frequency.
  const counts = {};
  for (const s of state.samples) {
    for (const f of s.findings || []) {
      if (f.severity === "ok") continue;
      const c = counts[f.code] || (counts[f.code] = { f, n: 0, rooms: new Set() });
      c.n++; c.rooms.add(s.room || "(unnamed)");
    }
  }
  const order = { bad: 0, warn: 1, info: 2 };
  const perSpot = Object.values(counts).sort((a, b) => order[a.f.severity] - order[b.f.severity] || b.n - a.n).map((c) => ({
    severity: c.f.severity,
    title: `${PROBLEM_NAMES[c.f.code] || c.f.title} — ${c.n} spot${c.n === 1 ? "" : "s"}`,
    detail: `${[...c.rooms].join(", ")}. ${c.n > 1 ? "Example: " : ""}${c.f.title}. ${c.f.detail}`,
  }));
  const all = [...sum.findings, ...perSpot];
  $("survey-findings").innerHTML = all.length
    ? findingItems(all)
    : `<li class="finding sev-ok"><div><div class="finding-title">${state.samples.length ? "No problems found" : "No measurements yet"}</div>` +
      `<div class="finding-detail">${state.samples.length ? "Every measured spot looks healthy." : "Take measurements with the Android app; they appear here as you go."}</div></div></li>`;

  const num = (v, d = 0) => (v == null ? "—" : v.toFixed(d));
  $("rooms-table").innerHTML =
    `<thead><tr><th>Room</th><th>Spots</th><th>Signal</th><th>Down</th><th>Ping</th><th></th></tr></thead><tbody>` +
    (sum.rooms.map((r) =>
      `<tr><td>${esc(r.room)}</td><td class="num">${r.samples}</td><td class="num">${num(r.rssi_median)}</td>` +
      `<td class="num">${num(r.download_median)}</td><td class="num">${num(r.latency_median)}</td><td>${sevPill(r.worst_severity)}</td></tr>`).join("") ||
      `<tr><td colspan="6" class="hint">No rooms yet.</td></tr>`) + `</tbody>`;

  $("ap-table").innerHTML =
    `<thead><tr><th>Name</th><th>BSSID</th><th>Band</th><th>Spots</th><th>Signal</th></tr></thead><tbody>` +
    (sum.access_points.map((a) =>
      `<tr><td><input data-bssid="${esc(a.bssid)}" value="${esc(a.label || "")}" placeholder="e.g. Office eero" aria-label="Name for ${esc(a.bssid)}"></td>` +
      `<td class="num">${esc(a.bssid)}</td><td class="num">${a.band ? esc(a.band) + " GHz" : "—"}${a.channel ? " ch " + a.channel : ""}</td>` +
      `<td class="num">${a.samples}</td><td class="num">${num(a.rssi_median)}</td></tr>`).join("") ||
      `<tr><td colspan="5" class="hint">No access points seen yet.</td></tr>`) + `</tbody>`;

  const sel = $("ap-filter");
  const current = state.ap;
  sel.innerHTML = `<option value="">All</option>` + sum.access_points.map((a) =>
    `<option value="${esc(a.bssid)}">${esc(a.label || a.bssid)}${a.band ? ` (${esc(a.band)} GHz)` : ""}</option>`).join("");
  sel.value = sum.access_points.some((a) => a.bssid === current) ? current : "";
  state.ap = sel.value;
}

function renderEmpty() {
  const empty = $("map-empty");
  if (!state.plans.length) {
    empty.hidden = false;
    empty.innerHTML = `<p>Add a floor plan to start: a photo of a sketch or an exported plan works. ` +
      `Then open the Android app, pick the plan, tap where you're standing and press Measure.</p>`;
  } else {
    empty.hidden = true;
  }
}

// Data loading ------------------------------------------------------------------------------

async function loadPlans(selectId) {
  state.plans = await api("/api/floorplans");
  const sel = $("floorplan-select");
  sel.innerHTML = state.plans.map((p) => `<option value="${p.id}">${esc(p.name)} (${p.sample_count})</option>`).join("");
  const keep = selectId ?? state.planId;
  state.planId = state.plans.some((p) => p.id === keep) ? keep : state.plans[0]?.id ?? null;
  if (state.planId != null) sel.value = String(state.planId);
  renderEmpty();
  if (state.planId != null) await loadPlan(true);
}

async function loadPlan(reloadImage) {
  if (state.planId == null) return;
  const id = state.planId;
  const [samples, summary, labels] = await Promise.all([
    api(`/api/floorplans/${id}/samples`), api(`/api/floorplans/${id}/summary`), api("/api/labels"),
  ]);
  state.samples = samples; state.summary = summary; state.labels = labels;
  if (reloadImage || !state.image) {
    state.image = await new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = `/api/floorplans/${id}/image`;
    });
    const scale = Math.min(1, 1600 / Math.max(state.image.naturalWidth, state.image.naturalHeight));
    canvas.width = Math.round(state.image.naturalWidth * scale);
    canvas.height = Math.round(state.image.naturalHeight * scale);
  }
  renderSummary();
  renderDetail();
  draw();
}

// Events ---------------------------------------------------------------------------------------

document.querySelectorAll(".seg-btn").forEach((b) => b.addEventListener("click", () => {
  state.metric = b.dataset.metric;
  document.querySelectorAll(".seg-btn").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
  draw();
}));

$("ap-filter").addEventListener("change", (e) => { state.ap = e.target.value; draw(); });

$("floorplan-select").addEventListener("change", (e) => {
  state.planId = Number(e.target.value); state.selected = null; state.ap = "";
  loadPlan(true);
});

canvas.addEventListener("click", (e) => {
  const rect = canvas.getBoundingClientRect();
  const x = (e.clientX - rect.left) / rect.width, y = (e.clientY - rect.top) / rect.height;
  let best = null, bestD = Infinity;
  for (const s of state.samples) {
    const dx = (s.x - x) * rect.width, dy = (s.y - y) * rect.height;
    const d = Math.hypot(dx, dy);
    if (d < bestD) { bestD = d; best = s; }
  }
  state.selected = best && bestD < 20 ? best.id : null;
  renderDetail(); draw();
});

$("delete-sample").addEventListener("click", async () => {
  const btn = $("delete-sample");
  if (btn.dataset.confirm !== "1") { btn.dataset.confirm = "1"; btn.textContent = "Confirm delete"; return; }
  btn.dataset.confirm = ""; btn.textContent = "Delete";
  if (state.selected == null) return;
  await api(`/api/samples/${state.selected}`, { method: "DELETE" });
  state.selected = null;
  await loadPlans();
});

$("ap-table").addEventListener("change", async (e) => {
  const input = e.target.closest("input[data-bssid]");
  if (!input) return;
  state.labels = await api(`/api/labels/${encodeURIComponent(input.dataset.bssid)}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label: input.value }),
  });
  await loadPlan(false);
});

$("new-plan-btn").addEventListener("click", () => { $("upload-form").hidden = false; $("upload-name").focus(); });
$("upload-cancel").addEventListener("click", () => { $("upload-form").hidden = true; });
$("upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData();
  fd.append("name", $("upload-name").value);
  fd.append("image", $("upload-file").files[0]);
  $("upload-error").hidden = true;
  try {
    const fp = await api("/api/floorplans", { method: "POST", body: fd });
    $("upload-form").hidden = true; $("upload-form").reset();
    await loadPlans(fp.id);
  } catch (err) {
    $("upload-error").textContent = `Upload failed: ${err.message}`;
    $("upload-error").hidden = false;
  }
});

// Refresh while a survey is in progress so new spots from the phone appear.
setInterval(() => { if (!document.hidden && state.planId != null) loadPlan(false).catch(() => {}); }, 8000);

loadPlans().catch((err) => {
  $("map-empty").hidden = false;
  $("map-empty").innerHTML = `<p>Couldn't reach the survey server: ${esc(err.message)}</p>`;
});
