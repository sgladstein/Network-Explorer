import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from network_explorer.app import create_app


def tiny_png() -> bytes:
    raw = b"\x00\xff\xff\xff"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


@pytest.fixture()
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def make_plan(client, name="Ground floor"):
    r = client.post("/api/floorplans", data={"name": name}, files={"image": ("plan.png", tiny_png(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_health_and_ping(client):
    assert client.get("/api/health").json()["name"] == "network-explorer"
    assert client.get("/api/ping").status_code == 204


def test_speedtest(client):
    r = client.get("/api/speedtest/download", params={"bytes": 200_000})
    assert r.status_code == 200 and len(r.content) == 200_000
    assert client.get("/api/speedtest/download", params={"bytes": 10**10}).status_code == 422
    r = client.post("/api/speedtest/upload", content=b"x" * 123_456)
    assert r.json() == {"bytes": 123_456}


def test_floorplan_validation(client):
    r = client.post("/api/floorplans", data={"name": "x"}, files={"image": ("a.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_survey_round_trip(client):
    fid = make_plan(client)
    assert client.get(f"/api/floorplans/{fid}/image").content.startswith(b"\x89PNG")
    sample = {"x": 0.25, "y": 0.5, "room": " Kitchen ", "ssid": '"Home"', "bssid": "AA:AA:AA:AA:AA:01",
              "rssi": -78, "frequency_mhz": 5180, "link_speed_mbps": 130, "download_mbps": 30,
              "latency_ms_median": 20, "latency_jitter_ms": 5, "packet_loss_pct": 0,
              "scan": [{"bssid": "aa:aa:aa:aa:aa:02", "ssid": "Home", "rssi": -60, "frequency_mhz": 5745}]}
    r = client.post(f"/api/floorplans/{fid}/samples", json=sample)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["room"] == "Kitchen" and body["ssid"] == "Home" and body["bssid"] == "aa:aa:aa:aa:aa:01"
    assert body["band"] == "5" and body["channel"] == 36 and body["signal_grade"] == "poor"
    found = {f["code"] for f in body["findings"]}
    assert {"weak_signal", "sticky_client"} <= found

    assert len(client.get(f"/api/floorplans/{fid}/samples").json()) == 1
    assert client.get("/api/floorplans").json()[0]["sample_count"] == 1

    client.put("/api/labels/aa:aa:aa:aa:aa:01", json={"label": "Kitchen eero"})
    summary = client.get(f"/api/floorplans/{fid}/summary").json()
    assert summary["access_points"][0]["label"] == "Kitchen eero"
    assert summary["rooms"][0]["room"] == "Kitchen"

    assert client.delete(f"/api/samples/{body['id']}").status_code == 204
    assert client.get(f"/api/floorplans/{fid}/samples").json() == []
    assert client.delete(f"/api/floorplans/{fid}").status_code == 204
    assert client.get(f"/api/floorplans/{fid}/samples").status_code == 404


def test_sample_validation(client):
    fid = make_plan(client)
    assert client.post(f"/api/floorplans/{fid}/samples", json={"x": 2, "y": 0.5}).status_code == 422
    assert client.post("/api/floorplans/999/samples", json={"x": 0.1, "y": 0.1}).status_code == 404


def test_web_viewer_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "Network Explorer" in r.text
