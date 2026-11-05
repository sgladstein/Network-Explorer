#!/usr/bin/env python3
"""Read-only snapshot of your eero network, for working out which fields eero exposes.

What it does
  1. Signs in to eero's cloud with your email and the one-time code eero sends you.
  2. Reads (GET only) your network, eero units, connected devices, speed-test
     history, channel utilisation, neighbouring-network scan, routing and recent events.
  3. Removes secrets (Wi-Fi and guest passwords, Thread network key, tokens),
     public IP addresses, and your account's email, phone and name.
  4. Saves everything to eero-dump-<time>.json and a readable eero-summary-<time>.txt.
  5. Signs out, so the session it used stops working. Nothing is stored for later.

It never changes a setting: the only non-GET requests are the sign-in, code check,
session refresh and sign-out calls (see POST_ALLOWED below).

Needs Python 3.9+ and nothing else. Run:   py eero_dump.py
Add --anonymize to also replace device names and MAC addresses with stand-ins.

The endpoints, headers and sign-in flow mirror the open-source eero-api library
(https://github.com/fulviofreitas/eero-api), which talks to the same undocumented
API the eero app uses.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

API_BASE = "https://api-user.e2ro.com"
# eero decides which fields to return from the app version in the User-Agent; the
# eero-api library sends this current-app string to get the full set.
USER_AGENT = "eero-ios/2026.8.1 (iPhone; iOS 18.5)"
POST_ALLOWED = {"/2.2/login", "/2.2/login/verify", "/2.2/login/refresh", "/2.2/logout"}
TOOL_VERSION = 1


class EeroError(Exception):
    def __init__(self, message: str, status: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


class EeroClient:
    """Minimal eero cloud client. GET for data; POST only for the sign-in calls."""

    def __init__(self, base: str = API_BASE, delay: float = 0.4, timeout: float = 30):
        self.base = base.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.token: str | None = None
        self.requests: list[tuple[str, str]] = []  # (method, path) log, for the read-only check

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            raise EeroError(f"Refusing unexpected path {path!r}")
        return self.base + path

    def _request(self, method: str, path: str, *, form: dict[str, str] | None = None,
                 params: dict[str, str] | None = None, _retried: bool = False) -> dict[str, Any]:
        bare = path.split("?", 1)[0]
        if method != "GET" and bare not in POST_ALLOWED:
            raise EeroError(f"Refusing to send {method} {bare}: this tool only reads")
        url = self._url(path)
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT, "X-Accept-Language": "en-US"}
        if self.token:
            headers["X-User-Token"] = self.token
            headers["Cookie"] = f"s={self.token}"
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        time.sleep(self.delay)  # stay far below eero's ~100 requests/minute limit
        self.requests.append((method, bare))
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status, body = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        except urllib.error.URLError as e:
            raise EeroError(f"Couldn't reach eero ({e.reason})") from e

        try:
            envelope = json.loads(body or b"{}")
        except ValueError:
            raise EeroError(f"{method} {bare}: HTTP {status}, response wasn't JSON", status) from None
        meta = envelope.get("meta") if isinstance(envelope, dict) else None
        err = meta.get("error") if isinstance(meta, dict) else None
        if status >= 400 or err:
            if err == "error.session.refresh" and not _retried and bare != "/2.2/login/refresh":
                self._request("POST", "/2.2/login/refresh", form={})
                return self._request(method, path, form=form, params=params, _retried=True)
            raise EeroError(f"{method} {bare}: HTTP {status} {err or ''}".strip(), status, err)
        return envelope

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        return self._request("GET", path, params=params)

    def login(self, email: str) -> None:
        env = self._request("POST", "/2.2/login", form={"login": email})
        token = (env.get("data") or {}).get("user_token")
        if not token:
            raise EeroError("eero didn't start a sign-in for that email")
        self.token = token

    def verify(self, code: str) -> None:
        self._request("POST", "/2.2/login/verify", form={"code": code})

    def logout(self) -> None:
        if not self.token:
            return
        try:
            self._request("POST", "/2.2/logout", form={"Cookie": f"s={self.token}"})
        except EeroError:
            pass  # an already-expired session is fine
        self.token = None


# Collection ---------------------------------------------------------------------------------

def _data(env: Any) -> Any:
    return env.get("data") if isinstance(env, dict) else None


def _networks_from_account(account: Any) -> list[dict[str, Any]]:
    data = _data(account)
    nets = data.get("networks") if isinstance(data, dict) else None
    if isinstance(nets, dict):
        nets = nets.get("data")
    return [n for n in nets if isinstance(n, dict)] if isinstance(nets, list) else []


def _api_path(value: Any) -> str | None:
    """Accept only host-relative API paths such as /2.2/networks/123."""
    if isinstance(value, str) and re.fullmatch(r"/2\.[0-9]/[A-Za-z0-9_/\-]+", value):
        return value
    return None


def collect(client: EeroClient, log: Callable[[str], None] = print, now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.timezone.utc)

    def safe(label: str, fn: Callable[[], Any]) -> Any:
        try:
            result = fn()
            log(f"  read {label}")
            return result
        except EeroError as e:
            log(f"  skipped {label}: {e}")
            return {"error": str(e), "status": e.status, "code": e.code}

    out: dict[str, Any] = {
        "tool": "network-explorer eero_dump",
        "tool_version": TOOL_VERSION,
        "collected_at": now.isoformat(),
        "user_agent": USER_AGENT,
        "networks": [],
    }
    log("Reading account")
    account = safe("account", lambda: client.get("/2.2/account"))
    out["account"] = account
    nets = _networks_from_account(account)
    if not nets:
        listing = safe("networks", lambda: client.get("/2.2/networks"))
        d = _data(listing)
        nets = d if isinstance(d, list) else (d.get("networks") or d.get("data") or []) if isinstance(d, dict) else []

    start = (now - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    for summary in nets:
        net_path = _api_path(summary.get("url")) or (f"/2.2/networks/{summary['id']}" if summary.get("id") else None)
        if not net_path:
            continue
        log(f"Reading network {summary.get('name') or net_path}")
        entry: dict[str, Any] = {"url": net_path}
        entry["network"] = safe("network", lambda: client.get(net_path))
        nd = _data(entry["network"])
        resources = nd.get("resources") if isinstance(nd, dict) and isinstance(nd.get("resources"), dict) else {}

        def sub(name: str) -> str:
            return _api_path(resources.get(name)) or f"{net_path}/{name}"

        entry["eeros"] = safe("eero units", lambda: client.get(sub("eeros")))
        entry["devices"] = safe("devices", lambda: client.get(sub("devices")))
        entry["speedtest"] = safe("speed-test history", lambda: client.get(sub("speedtest")))
        entry["channel_utilization"] = safe(
            "channel utilisation (last 24 h)",
            lambda: client.get(f"{net_path}/channel_utilization", {"start": start, "end": end}))
        entry["network_scan"] = safe("neighbouring networks", lambda: client.get(f"{net_path}/network_scan"))
        entry["diagnostics"] = safe("diagnostics", lambda: client.get(sub("diagnostics")))
        entry["routing"] = safe("routing", lambda: client.get(f"{net_path}/routing"))
        entry["updates"] = safe("updates", lambda: client.get(sub("updates")))
        entry["app_events"] = safe("recent events", lambda: client.get(f"{net_path}/app_events", {"page_size": "100"}))

        entry["eero_details"] = {}
        eeros = _data(entry["eeros"])
        for e in eeros if isinstance(eeros, list) else []:
            path = _api_path(e.get("url")) if isinstance(e, dict) else None
            if not path:
                continue
            name = e.get("location") or path
            entry["eero_details"][path] = {
                "eero": safe(f"eero '{name}'", lambda: client.get(path)),
                "connections": safe(f"eero '{name}' connections", lambda: client.get(f"{path}/connections")),
            }
        out["networks"].append(entry)
    return out


# Redaction -----------------------------------------------------------------------------------

SECRET_KEY = re.compile(r"(password|passphrase|psk|secret|token|cookie|credential|network_key|private_key|api_key|^key$|serial)", re.I)
ACCOUNT_PERSONAL_KEY = re.compile(r"^(email|phone|phone_number|name|first_name|last_name|value)$", re.I)
LOCATION_KEY = re.compile(r"^(lat|lon|lng|latitude|longitude|postal_code|zip|zip_code|street|address|city)$", re.I)
NAME_KEY = re.compile(r"^(hostname|nickname|display_name|name|device_name)$", re.I)
MAC_RE = re.compile(r"\b([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})[:-]([0-9A-Fa-f]{2})\b")


def _mask_public_ip(s: str) -> str:
    try:
        ip = ipaddress.ip_address(s.split("/")[0].split("%")[0])
    except ValueError:
        return s
    if ip.is_global:
        return "[public-ipv6]" if ip.version == 6 else "[public-ip]"
    return s


def _pseudo_mac(m: re.Match[str]) -> str:
    oui = ":".join(g.lower() for g in m.groups()[:3])  # keep the manufacturer prefix
    h = hashlib.sha256(":".join(m.groups()).lower().encode()).hexdigest()
    return f"{oui}:{h[0:2]}:{h[2:4]}:{h[4:6]}"


def redact(obj: Any, *, anonymize: bool = False, in_account: bool = False, _key: str = "") -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            ks = str(k)
            if SECRET_KEY.search(ks) and isinstance(v, (str, int, float)) and not isinstance(v, bool):
                out[k] = "[redacted]" if v != "" else v
            elif in_account and ACCOUNT_PERSONAL_KEY.match(ks) and not isinstance(v, (dict, list)):
                out[k] = "[redacted]"
            elif LOCATION_KEY.match(ks) and not isinstance(v, (dict, list)):
                out[k] = "[redacted]"
            elif anonymize and NAME_KEY.match(ks) and isinstance(v, str) and v:
                out[k] = "device-" + hashlib.sha256(v.encode()).hexdigest()[:6]
            else:
                out[k] = redact(v, anonymize=anonymize, in_account=in_account or ks == "account", _key=ks)
        return out
    if isinstance(obj, list):
        return [redact(v, anonymize=anonymize, in_account=in_account, _key=_key) for v in obj]
    if isinstance(obj, str):
        s = _mask_public_ip(obj)
        if anonymize:
            s = MAC_RE.sub(_pseudo_mac, s)
        return s
    return obj


# Summary -------------------------------------------------------------------------------------

LINK_HINT = re.compile(r"(backhaul|mesh|upstream|uplink|wired|wireless|connection|connected|bars|quality|signal|link|parent|hop|ports|speed|rate)", re.I)


def _short(v: Any, limit: int = 160) -> str:
    s = json.dumps(v, ensure_ascii=True) if not isinstance(v, str) else v
    return s if len(s) <= limit else s[: limit - 3] + "..."


def summarize(dump: dict[str, Any]) -> str:
    lines = [f"eero snapshot taken {dump.get('collected_at')}", ""]
    for net in dump.get("networks", []):
        nd = _data(net.get("network")) or {}
        lines.append(f"Network: {nd.get('name', '?')}  status={nd.get('status', '?')}  "
                     f"gateway={nd.get('gateway', '?')}  connection_mode={nd.get('connection', {}).get('mode', '?') if isinstance(nd.get('connection'), dict) else '?'}")
        eeros = _data(net.get("eeros"))
        devices = _data(net.get("devices"))
        by_node: dict[str, list[dict[str, Any]]] = {}
        for d in devices if isinstance(devices, list) else []:
            if not isinstance(d, dict) or not d.get("connected"):
                continue
            loc = (d.get("source") or {}).get("location") if isinstance(d.get("source"), dict) else None
            by_node.setdefault(loc or "?", []).append(d)

        lines.append("")
        lines.append("eero units")
        for e in eeros if isinstance(eeros, list) else []:
            if not isinstance(e, dict):
                continue
            loc = e.get("location") or "?"
            lines.append(f"- {loc}: model={e.get('model')} ({e.get('model_number')}) gateway={e.get('gateway')} "
                         f"status={e.get('status')} clients={e.get('connected_clients_count')} os={e.get('os_version')}")
            detail = _data((net.get("eero_details", {}).get(e.get("url")) or {}).get("eero")) or {}
            merged = {**e, **detail} if isinstance(detail, dict) else e
            for k in sorted(merged):
                if LINK_HINT.search(k) and k not in ("connected_clients_count",):
                    lines.append(f"    {k}: {_short(merged[k])}")
            conns = _data((net.get("eero_details", {}).get(e.get("url")) or {}).get("connections"))
            if conns:
                lines.append(f"    connections: {_short(conns, 400)}")
            clients = by_node.get(loc, [])
            wireless = [c for c in clients if c.get("wireless")]
            if wireless:
                lines.append(f"    wireless clients on this unit: {len(wireless)}")
                for c in wireless[:15]:
                    conn = c.get("connectivity") or {}
                    rx = (conn.get("rx_bitrate") or conn.get("rx_rate_info") or "")
                    tx = (conn.get("tx_bitrate") or conn.get("tx_rate_info") or "")
                    lines.append(f"      {c.get('nickname') or c.get('hostname') or c.get('mac')}: "
                                 f"{(c.get('interface') or {}).get('frequency', '?')} GHz ch {c.get('channel')} "
                                 f"signal {conn.get('signal')} rx {_short(rx, 60)} tx {_short(tx, 60)}")
        lines.append("")
        st = _data(net.get("speedtest"))
        if isinstance(st, list) and st:
            lines.append(f"Latest eero speed test: {_short(st[0], 300)}")
        elif isinstance(st, dict) and st:
            lines.append(f"Latest eero speed test: {_short(st, 300)}")
        failed = [k for k, v in net.items() if isinstance(v, dict) and "error" in v]
        if failed:
            lines.append(f"Not available: {', '.join(failed)}")
        lines.append("")
    return "\n".join(lines)


# Command line --------------------------------------------------------------------------------

def main(argv: list[str] | None = None, input_fn: Callable[[str], str] = input) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    p = argparse.ArgumentParser(description="Read-only snapshot of your eero network.")
    p.add_argument("--anonymize", action="store_true", help="also replace device names and MAC addresses")
    p.add_argument("--out", default=".", help="folder for the output files (default: current folder)")
    p.add_argument("--api-base", default=API_BASE, help=argparse.SUPPRESS)  # for tests
    p.add_argument("--delay", type=float, default=0.4, help=argparse.SUPPRESS)
    args = p.parse_args(argv)

    print("eero read-only snapshot\n"
          "Use the email you sign in to the eero app with. (Accounts that sign in with Amazon\n"
          "can't use this; invite an email-based admin in the eero app instead.)\n")
    email = input_fn("eero account email: ").strip()
    client = EeroClient(args.api_base, delay=args.delay)
    try:
        client.login(email)
        code = input_fn("Code eero just emailed you: ").strip()
        client.verify(code)
    except EeroError as e:
        print(f"\nSign-in failed: {e}")
        return 1

    try:
        raw = collect(client)
    finally:
        client.logout()
        print("Signed out; the session used by this tool no longer works.")

    clean = redact(raw, anonymize=args.anonymize)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    import os
    os.makedirs(args.out, exist_ok=True)
    json_path = os.path.join(args.out, f"eero-dump-{stamp}.json")
    txt_path = os.path.join(args.out, f"eero-summary-{stamp}.txt")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    summary = summarize(clean)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(summary)

    non_get = sorted({f"{m} {p}" for m, p in client.requests if m != "GET"})
    print("\n" + summary)
    print(f"Saved:\n  {json_path}\n  {txt_path}")
    print(f"Requests made: {len(client.requests)} ({', '.join(non_get)} for sign-in/out; everything else GET).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
