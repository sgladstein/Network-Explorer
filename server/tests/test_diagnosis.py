from network_explorer.diagnosis import diagnose_sample, summarize


def codes(sample):
    return [f["code"] for f in diagnose_sample(sample)]


BASE = {"ssid": "Home", "bssid": "aa:aa:aa:aa:aa:01", "rssi": -55, "frequency_mhz": 5180,
        "link_speed_mbps": 866, "download_mbps": 400, "latency_ms_median": 8, "latency_jitter_ms": 2,
        "packet_loss_pct": 0}


def test_healthy():
    assert codes(BASE) == ["healthy"]


def test_no_wifi():
    assert codes({**BASE, "rssi": None}) == ["no_wifi"]


def test_weak_and_marginal_signal():
    assert "weak_signal" in codes({**BASE, "rssi": -80, "download_mbps": 20})
    assert "marginal_signal" in codes({**BASE, "rssi": -70})


def test_sticky_client_same_band_only():
    scan = [{"bssid": "aa:aa:aa:aa:aa:02", "ssid": "Home", "rssi": -50, "frequency_mhz": 5745}]
    assert "sticky_client" in codes({**BASE, "rssi": -72, "scan": scan})
    # A stronger BSSID on another band is not a roaming problem.
    scan_2g = [{"bssid": "aa:aa:aa:aa:aa:02", "ssid": "Home", "rssi": -40, "frequency_mhz": 2437}]
    assert "sticky_client" not in codes({**BASE, "rssi": -72, "scan": scan_2g})
    # The phone's own BSSID showing up in the scan doesn't count.
    own = [{"bssid": BASE["bssid"], "ssid": "Home", "rssi": -40, "frequency_mhz": 5180}]
    assert "sticky_client" not in codes({**BASE, "rssi": -72, "scan": own})


def test_on_2g_with_usable_5g():
    s = {**BASE, "frequency_mhz": 2437, "link_speed_mbps": 72,
         "scan": [{"bssid": "aa:aa:aa:aa:aa:02", "ssid": "Home", "rssi": -62, "frequency_mhz": 5180}]}
    assert "on_2g" in codes(s)


def test_congestion_vs_coverage():
    assert "congestion" in codes({**BASE, "latency_jitter_ms": 45})
    assert "congestion" not in codes({**BASE, "rssi": -80, "latency_jitter_ms": 45})
    lossy = diagnose_sample({**BASE, "packet_loss_pct": 20})
    assert lossy[0]["code"] == "packet_loss" and "interference" in lossy[0]["detail"]


def test_slow_throughput_points_past_the_radio():
    assert "slow_throughput" in codes({**BASE, "download_mbps": 60})


def test_busy_channel():
    scan = [{"bssid": f"bb:bb:bb:bb:bb:0{i}", "ssid": f"Neighbour{i}", "rssi": -80, "frequency_mhz": 5180} for i in range(6)]
    assert "busy_channel" in codes({**BASE, "scan": scan})


def test_findings_sorted_by_severity():
    f = diagnose_sample({**BASE, "rssi": -80, "packet_loss_pct": 30})
    sev = [x["severity"] for x in f]
    assert sev == sorted(sev, key=["bad", "warn", "info", "ok"].index)


def test_summary_flags_slow_node_as_backhaul():
    def s(bssid, room, down):
        d = {**BASE, "bssid": bssid, "room": room, "download_mbps": down}
        d["findings"] = diagnose_sample(d)
        return d

    samples = [s("aa:aa:aa:aa:aa:01", "Office", 450), s("aa:aa:aa:aa:aa:01", "Office", 420),
               s("cc:cc:cc:cc:cc:01", "Bedroom", 90), s("cc:cc:cc:cc:cc:01", "Bedroom", 110)]
    out = summarize(samples, {"cc:cc:cc:cc:cc:01": "Bedroom eero"})
    assert [r["room"] for r in out["rooms"]] == ["Bedroom", "Office"]
    assert [f["code"] for f in out["findings"]] == ["backhaul_suspect"]
    assert "Bedroom eero" in out["findings"][0]["title"]
