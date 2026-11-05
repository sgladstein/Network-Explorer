"""Turn raw Wi-Fi measurements into plain-language findings.

The rules follow the cause-separation table from the research report:

* weak RSSI                                  -> coverage / placement
* good RSSI but loss, jitter or slow pings   -> congestion or interference
* good RSSI, good link rate, slow throughput -> eero backhaul (or the server's own link)
* a same-band BSSID 8+ dB stronger than the
  one the phone is using                     -> sticky client / roaming
* on 2.4 GHz while 5/6 GHz is usable         -> band steering

All thresholds are rules of thumb meant to be calibrated against your house.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable

from .wifi import FAIR_DBM, GOOD_DBM, band_for_frequency, channel_for_frequency, normalize_bssid, normalize_ssid

STICKY_MARGIN_DB = 8
USABLE_UPPER_BAND_DBM = -70
BUSY_CHANNEL_NEIGHBOURS = 5
HIGH_LATENCY_MS = 50
HIGH_JITTER_MS = 30
LOSS_WARN_PCT = 2
LOSS_BAD_PCT = 10
SLOW_LINK_MBPS = 100
BACKHAUL_RATIO = 0.5  # node's good-signal throughput vs the best node's

SEVERITY_ORDER = {"bad": 0, "warn": 1, "info": 2, "ok": 3}


def finding(code: str, severity: str, title: str, detail: str) -> dict[str, str]:
    return {"code": code, "severity": severity, "title": title, "detail": detail}


def _scan_entries(sample: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for e in sample.get("scan") or []:
        bssid = normalize_bssid(e.get("bssid"))
        rssi = e.get("rssi")
        if bssid is None or rssi is None:
            continue
        freq = e.get("frequency_mhz")
        out.append(
            {
                "bssid": bssid,
                "ssid": normalize_ssid(e.get("ssid")),
                "rssi": int(rssi),
                "frequency_mhz": freq,
                "band": band_for_frequency(freq),
                "channel": channel_for_frequency(freq),
            }
        )
    return out


def diagnose_sample(sample: dict[str, Any]) -> list[dict[str, str]]:
    """Return findings for one measurement, most severe first."""
    findings: list[dict[str, str]] = []
    rssi = sample.get("rssi")
    freq = sample.get("frequency_mhz")
    band = band_for_frequency(freq)
    channel = channel_for_frequency(freq)
    bssid = normalize_bssid(sample.get("bssid"))
    ssid = normalize_ssid(sample.get("ssid"))
    link = sample.get("link_speed_mbps")
    down = sample.get("download_mbps")
    loss = sample.get("packet_loss_pct")
    jitter = sample.get("latency_jitter_ms")
    lat = sample.get("latency_ms_median")
    scan = _scan_entries(sample)

    if rssi is None:
        findings.append(finding("no_wifi", "bad", "No Wi-Fi reading",
                                "The phone was not connected to Wi-Fi (or the app lacked location permission) when this was taken."))
        return findings

    good_signal = rssi >= GOOD_DBM

    # 1. Coverage
    if rssi < FAIR_DBM:
        findings.append(finding("weak_signal", "bad", f"Weak signal ({rssi} dBm)",
                                "This spot is at the edge of coverage. Expect drops and slow speeds. "
                                "Move the nearest eero closer (halfway between the main eero and this spot works best), "
                                "or add an eero here with a wired connection if you can."))
    elif rssi < GOOD_DBM:
        findings.append(finding("marginal_signal", "warn", f"Marginal signal ({rssi} dBm)",
                                "Fine for browsing, but video calls and streaming can stutter. "
                                "Walls, floors and appliances between this spot and the eero are the usual cause."))

    # 2. Roaming: a much stronger BSSID on the same network and band
    if ssid and scan:
        same_net = [e for e in scan if e["ssid"] == ssid and e["bssid"] != bssid]
        same_band = [e for e in same_net if e["band"] == band]
        if same_band:
            best = max(same_band, key=lambda e: e["rssi"])
            if best["rssi"] - rssi >= STICKY_MARGIN_DB:
                findings.append(finding("sticky_client", "warn",
                                        f"Phone is holding on to a farther eero ({best['rssi'] - rssi} dB weaker)",
                                        f"Another access point on '{ssid}' ({best['bssid']}, {best['rssi']} dBm) is much stronger here. "
                                        "The phone hasn't roamed to it. Toggling Wi-Fi off/on usually moves it; "
                                        "if this happens a lot, check that Client Steering is on in the eero app."))
        # 3. Band steering
        if band == "2.4":
            upper = [e for e in same_net if e["band"] in ("5", "6") and e["rssi"] >= USABLE_UPPER_BAND_DBM]
            if upper:
                best = max(upper, key=lambda e: e["rssi"])
                findings.append(finding("on_2g", "warn", "Using 2.4 GHz although 5/6 GHz is available",
                                        f"A {best['band']} GHz signal at {best['rssi']} dBm is usable here and is usually much faster. "
                                        "2.4 GHz reaches further but is slower and more crowded."))

        # 4. Neighbour networks on the same channel
        if channel is not None:
            neighbours = {e["bssid"] for e in scan if e["channel"] == channel and e["ssid"] != ssid}
            if len(neighbours) >= BUSY_CHANNEL_NEIGHBOURS:
                findings.append(finding("busy_channel", "info",
                                        f"{len(neighbours)} neighbouring networks on channel {channel}",
                                        "Neighbours sharing the channel take airtime. eero picks channels automatically; "
                                        "it re-evaluates them, and a reboot of the eero network forces a fresh choice."))

    # 5. Reliability with a good signal points at interference or congestion
    if loss is not None and loss >= LOSS_BAD_PCT:
        findings.append(finding("packet_loss", "bad", f"Heavy packet loss ({loss:.0f}%)",
                                "Many test packets never came back. "
                                + ("The signal is strong, so this points at interference or an overloaded eero." if good_signal
                                   else "With this weak signal, coverage is the likely cause.")))
    elif good_signal and ((loss is not None and loss >= LOSS_WARN_PCT)
                          or (jitter is not None and jitter >= HIGH_JITTER_MS)
                          or (lat is not None and lat >= HIGH_LATENCY_MS)):
        parts = []
        if lat is not None and lat >= HIGH_LATENCY_MS:
            parts.append(f"median latency {lat:.0f} ms")
        if jitter is not None and jitter >= HIGH_JITTER_MS:
            parts.append(f"jitter {jitter:.0f} ms")
        if loss is not None and loss >= LOSS_WARN_PCT:
            parts.append(f"{loss:.0f}% loss")
        findings.append(finding("congestion", "warn", "Good signal but laggy (" + ", ".join(parts) + ")",
                                "The radio link is strong, so the delay comes from busy airtime: other devices, "
                                "neighbouring networks, or non-Wi-Fi interference such as microwaves."))

    # 6. Link rate: low PHY rate on a strong 5/6 GHz signal
    if good_signal and band in ("5", "6") and link is not None and link < SLOW_LINK_MBPS:
        findings.append(finding("slow_link", "info", f"Low link rate ({link} Mbps) despite a strong signal",
                                "Usually interference, or a phone that negotiates conservatively. "
                                "Compare with other spots served by the same eero."))

    # 7. Throughput far below what the link should carry
    if good_signal and link and down is not None and down < 0.25 * link and down < 200:
        findings.append(finding("slow_throughput", "warn",
                                f"Throughput ({down:.0f} Mbps) far below the link rate ({link} Mbps)",
                                "The phone-to-eero hop is fine, so the bottleneck is further along: the eero's own "
                                "connection back to the main eero (wireless backhaul), congestion, or the survey "
                                "server's link (it should be wired to an eero)."))

    if not findings:
        findings.append(finding("healthy", "ok", "Looks healthy", "Strong signal and responsive connection here."))

    findings.sort(key=lambda f: SEVERITY_ORDER[f["severity"]])
    return findings


def _median(values: Iterable[float | int | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return float(median(vals)) if vals else None


def summarize(samples: list[dict[str, Any]], labels: dict[str, str] | None = None) -> dict[str, Any]:
    """Aggregate a floor plan's samples by room and by access point (BSSID)."""
    labels = labels or {}

    rooms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    aps: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in samples:
        rooms[s.get("room") or "(unnamed)"].append(s)
        b = normalize_bssid(s.get("bssid"))
        if b:
            aps[b].append(s)

    room_rows = []
    for name, ss in sorted(rooms.items()):
        codes: dict[str, int] = defaultdict(int)
        for s in ss:
            for f in s.get("findings") or []:
                codes[f["code"]] += 1
        worst = min((SEVERITY_ORDER[f["severity"]] for s in ss for f in s.get("findings") or []), default=3)
        room_rows.append({
            "room": name,
            "samples": len(ss),
            "rssi_median": _median(s.get("rssi") for s in ss),
            "download_median": _median(s.get("download_mbps") for s in ss),
            "upload_median": _median(s.get("upload_mbps") for s in ss),
            "latency_median": _median(s.get("latency_ms_median") for s in ss),
            "worst_severity": next(k for k, v in SEVERITY_ORDER.items() if v == worst),
            "finding_counts": dict(codes),
            "bssids": sorted({normalize_bssid(s.get("bssid")) for s in ss} - {None}),
        })

    ap_rows = []
    for b, ss in aps.items():
        good = [s for s in ss if s.get("rssi") is not None and s["rssi"] >= GOOD_DBM]
        ap_rows.append({
            "bssid": b,
            "label": labels.get(b),
            "band": band_for_frequency(ss[-1].get("frequency_mhz")),
            "channel": channel_for_frequency(ss[-1].get("frequency_mhz")),
            "samples": len(ss),
            "rssi_median": _median(s.get("rssi") for s in ss),
            "good_signal_download_median": _median(s.get("download_mbps") for s in good),
            "rooms": sorted({s.get("room") or "(unnamed)" for s in ss}),
        })
    ap_rows.sort(key=lambda r: (r["label"] or "~", r["bssid"]))

    # Backhaul check: compare throughput at good-signal spots across access points
    # on the same band. A node that is slow even when the phone is right next to
    # it is probably on a weak wireless backhaul.
    survey_findings = []
    by_band: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
    for r in ap_rows:
        if r["good_signal_download_median"] is not None:
            by_band[r["band"]].append(r)
    for band, rows in by_band.items():
        if len(rows) < 2:
            continue
        best = max(rows, key=lambda r: r["good_signal_download_median"])
        for r in rows:
            if r is best:
                continue
            if r["good_signal_download_median"] < BACKHAUL_RATIO * best["good_signal_download_median"]:
                name = r["label"] or r["bssid"]
                best_name = best["label"] or best["bssid"]
                survey_findings.append(finding(
                    "backhaul_suspect", "warn",
                    f"{name} is slow even at strong signal",
                    f"Spots with a strong signal from {name} get {r['good_signal_download_median']:.0f} Mbps, versus "
                    f"{best['good_signal_download_median']:.0f} Mbps near {best_name} on the same band. "
                    "That points at this eero's link back to the main eero. Check in the eero app whether it is "
                    "wired or wireless; an Ethernet (or MoCA) connection, or moving it closer to the main eero, usually fixes this."))

    return {"rooms": room_rows, "access_points": ap_rows, "findings": survey_findings}
