"""Tests for eero_dump.py against a local fake of the eero cloud API."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

import eero_dump

TOKEN = "tok-123"
NET = "/2.2/networks/111"


def envelope(data, code=200):
    return {"meta": {"code": code, "server_time": "2026-11-05T00:00:00Z"}, "data": data}


FAKE_GET = {
    "/2.2/account": envelope({"name": "Pat Example", "email": {"value": "pat@example.com", "verified": True},
                              "phone": {"value": "+15550100"},
                              "networks": {"count": 1, "data": [{"url": NET, "name": "Home"}]}}),
    NET: envelope({"name": "Home", "status": "connected", "gateway": "eero", "password": "hunter2",
                   "connection": {"mode": "automatic"},
                   "geo_ip": {"city": "Springfield", "lat": 1.0, "isp": "AT&T"},
                   "wan_ip": "8.8.4.4", "gateway_ip": "192.168.1.254",
                   "guest_network": {"enabled": False, "password": "guestpw"},
                   "resources": {"eeros": f"{NET}/eeros", "devices": f"{NET}/devices"}}),
    f"{NET}/eeros": envelope([
        {"url": "/2.2/eeros/1", "location": "Living room", "model": "eero", "model_number": "J010011",
         "gateway": True, "status": "green", "connected_clients_count": 5, "serial": "GGC123",
         "mac_address": "f8:bb:bf:00:00:01", "wired": True, "mesh_quality_bars": 5},
        {"url": "/2.2/eeros/2", "location": "Office", "model": "eero", "model_number": "J010011",
         "gateway": False, "status": "green", "connected_clients_count": 3,
         "mac_address": "f8:bb:bf:00:00:02", "wired": False, "mesh_quality_bars": 5},
    ]),
    "/2.2/eeros/1": envelope({"url": "/2.2/eeros/1", "ports": {"interfaces": [{"negotiated_speed": "1000"}]}}),
    "/2.2/eeros/2": envelope({"url": "/2.2/eeros/2", "upstream": {"location": "Living room"}}),
    "/2.2/eeros/1/connections": envelope({"wired": []}),
    f"{NET}/devices": envelope([
        {"mac": "aa:bb:cc:11:22:33", "hostname": "Pats-Pixel", "nickname": None, "connected": True, "wireless": True,
         "channel": 149, "interface": {"frequency": "5"}, "source": {"location": "Office"},
         "connectivity": {"signal": "-48 dBm", "rx_bitrate": "866.7 MBit/s"}, "ips": ["192.168.4.20", "2600:1700:1:2::5"]},
    ]),
    f"{NET}/speedtest": envelope([{"down_mbps": 300.5, "up_mbps": 280.1, "date": "2026-11-04T10:00:00Z"}]),
    f"{NET}/network_scan": envelope([]),
    f"{NET}/routing": envelope({}),
    f"{NET}/updates": envelope({}),
    f"{NET}/app_events": envelope([]),
    f"{NET}/channel_utilization": envelope({"utilization": []}),
    f"{NET}/thread": envelope({"thread_network_key": "SHOULD-NOT-BE-FETCHED"}),
}


class FakeEero(BaseHTTPRequestHandler):
    log: list = []

    def log_message(self, *a):
        pass

    def _send(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authed(self):
        return self.headers.get("X-User-Token") == TOKEN and f"s={TOKEN}" in (self.headers.get("Cookie") or "")

    def do_GET(self):
        url = urlsplit(self.path)
        FakeEero.log.append(("GET", url.path, parse_qs(url.query), self.headers.get("User-Agent")))
        if not self._authed():
            return self._send(401, {"meta": {"code": 401, "error": "error.session.invalid"}})
        if url.path in FAKE_GET:
            return self._send(200, FAKE_GET[url.path])
        return self._send(404, {"meta": {"code": 404, "error": "error.not_found"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(length).decode())
        FakeEero.log.append(("POST", self.path, form, self.headers.get("User-Agent")))
        if self.path == "/2.2/login":
            return self._send(200, envelope({"user_token": TOKEN}))
        if self.path == "/2.2/login/verify":
            if not self._authed() or form.get("code") != ["654321"]:
                return self._send(401, {"meta": {"code": 401, "error": "error.verification.invalid"}})
            return self._send(200, envelope({"name": "Pat"}))
        if self.path == "/2.2/logout":
            return self._send(200, envelope({}))
        return self._send(404, {"meta": {"code": 404}})


@pytest.fixture()
def fake_api():
    FakeEero.log = []
    srv = HTTPServer(("127.0.0.1", 0), FakeEero)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def run(fake_api, tmp_path, extra=(), code="654321"):
    answers = iter(["pat@example.com", code])
    rc = eero_dump.main(["--api-base", fake_api, "--delay", "0", "--out", str(tmp_path), *extra],
                        input_fn=lambda prompt: next(answers))
    return rc


def test_full_run_is_read_only_and_redacted(fake_api, tmp_path, capsys):
    assert run(fake_api, tmp_path) == 0
    dump_file = next(tmp_path.glob("eero-dump-*.json"))
    text = dump_file.read_text()
    dump = json.loads(text)

    # Read-only: the only POSTs are sign-in and sign-out, and the Thread key endpoint is never touched.
    posts = [p for m, p, *_ in FakeEero.log if m == "POST"]
    assert posts == ["/2.2/login", "/2.2/login/verify", "/2.2/logout"]
    assert all(p != f"{NET}/thread" for _, p, *_ in FakeEero.log)
    assert all(ua == eero_dump.USER_AGENT for *_, ua in FakeEero.log)

    # Secrets and personal details are gone; diagnostic data stays.
    for secret in ("hunter2", "guestpw", TOKEN, "pat@example.com", "+15550100", "Pat Example", "Springfield", "8.8.4.4",
                   "GGC123", "2600:1700"):
        assert secret not in text, secret
    net = dump["networks"][0]
    assert net["network"]["data"]["gateway_ip"] == "192.168.1.254"
    assert net["network"]["data"]["geo_ip"]["isp"] == "AT&T"
    assert net["devices"]["data"][0]["hostname"] == "Pats-Pixel"
    assert net["eero_details"]["/2.2/eeros/2"]["eero"]["data"]["upstream"]["location"] == "Living room"
    cu = [q for m, p, q, _ in FakeEero.log if p == f"{NET}/channel_utilization"][0]
    assert set(cu) == {"start", "end"}
    # Endpoints that fail are recorded, not fatal.
    assert "error" in net["eero_details"]["/2.2/eeros/2"]["connections"]

    summary = next(tmp_path.glob("eero-summary-*.txt")).read_text()
    assert "Office: model=eero (J010011) gateway=False" in summary
    assert "mesh_quality_bars: 5" in summary and "upstream:" in summary
    assert "Pats-Pixel: 5 GHz ch 149 signal -48 dBm" in summary
    assert "300.5" in summary
    assert "Signed out" in capsys.readouterr().out


def test_anonymize_masks_names_and_macs(fake_api, tmp_path):
    assert run(fake_api, tmp_path, extra=["--anonymize"]) == 0
    text = next(tmp_path.glob("eero-dump-*.json")).read_text()
    assert "Pats-Pixel" not in text
    assert "aa:bb:cc:11:22:33" not in text
    assert "aa:bb:cc:" in text  # manufacturer prefix kept
    assert "Office" in text  # eero room names kept


def test_wrong_code_fails_cleanly(fake_api, tmp_path, capsys):
    assert run(fake_api, tmp_path, code="000000") == 1
    assert "Sign-in failed" in capsys.readouterr().out
    assert not list(tmp_path.glob("eero-dump-*.json"))


def test_client_refuses_writes():
    c = eero_dump.EeroClient("http://127.0.0.1:9", delay=0)
    with pytest.raises(eero_dump.EeroError, match="only reads"):
        c._request("POST", "/2.2/networks/1/reboot", form={})
    with pytest.raises(eero_dump.EeroError, match="only reads"):
        c._request("PUT", "/2.2/networks/1/settings", form={})
