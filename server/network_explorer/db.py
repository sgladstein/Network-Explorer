"""SQLite storage for floor plans, survey samples and access-point labels."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS floorplans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    image_file TEXT NOT NULL,
    content_type TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    floorplan_id INTEGER NOT NULL REFERENCES floorplans(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    room TEXT,
    created_at REAL NOT NULL,
    device_model TEXT,
    ssid TEXT,
    bssid TEXT,
    rssi INTEGER,
    frequency_mhz INTEGER,
    channel_width_mhz INTEGER,
    link_speed_mbps INTEGER,
    tx_link_speed_mbps INTEGER,
    rx_link_speed_mbps INTEGER,
    wifi_standard TEXT,
    latency_ms_median REAL,
    latency_jitter_ms REAL,
    packet_loss_pct REAL,
    download_mbps REAL,
    upload_mbps REAL,
    scan_json TEXT,
    findings_json TEXT
);
CREATE INDEX IF NOT EXISTS samples_floorplan ON samples(floorplan_id);
CREATE TABLE IF NOT EXISTS ap_labels (
    bssid TEXT PRIMARY KEY,
    label TEXT NOT NULL
);
"""

SAMPLE_COLUMNS = [
    "floorplan_id", "x", "y", "room", "created_at", "device_model", "ssid", "bssid", "rssi",
    "frequency_mhz", "channel_width_mhz", "link_speed_mbps", "tx_link_speed_mbps",
    "rx_link_speed_mbps", "wifi_standard", "latency_ms_median", "latency_jitter_ms",
    "packet_loss_pct", "download_mbps", "upload_mbps", "scan_json", "findings_json",
]


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.image_dir = self.data_dir / "floorplans"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.data_dir / "survey.db", check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        self._db.close()

    # Floor plans -------------------------------------------------------------

    def add_floorplan(self, name: str, image: bytes, content_type: str, ext: str) -> dict[str, Any]:
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO floorplans (name, image_file, content_type, created_at) VALUES (?, '', ?, ?)",
                (name, content_type, time.time()),
            )
            fid = cur.lastrowid
            filename = f"{fid}{ext}"
            (self.image_dir / filename).write_bytes(image)
            self._db.execute("UPDATE floorplans SET image_file = ? WHERE id = ?", (filename, fid))
            self._db.commit()
        return self.get_floorplan(fid)  # type: ignore[return-value]

    def list_floorplans(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT f.id, f.name, f.created_at, COUNT(s.id) AS sample_count "
            "FROM floorplans f LEFT JOIN samples s ON s.floorplan_id = f.id GROUP BY f.id ORDER BY f.id"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_floorplan(self, fid: int) -> dict[str, Any] | None:
        r = self._db.execute(
            "SELECT id, name, image_file, content_type, created_at FROM floorplans WHERE id = ?", (fid,)
        ).fetchone()
        return dict(r) if r else None

    def delete_floorplan(self, fid: int) -> bool:
        fp = self.get_floorplan(fid)
        if not fp:
            return False
        with self._lock:
            self._db.execute("DELETE FROM samples WHERE floorplan_id = ?", (fid,))
            self._db.execute("DELETE FROM floorplans WHERE id = ?", (fid,))
            self._db.commit()
        (self.image_dir / fp["image_file"]).unlink(missing_ok=True)
        return True

    def image_path(self, fp: dict[str, Any]) -> Path:
        return self.image_dir / fp["image_file"]

    # Samples -------------------------------------------------------------------

    def add_sample(self, data: dict[str, Any]) -> dict[str, Any]:
        row = dict(data)
        row["created_at"] = time.time()
        row["scan_json"] = json.dumps(row.pop("scan", None) or [])
        row["findings_json"] = json.dumps(row.pop("findings", None) or [])
        values = [row.get(c) for c in SAMPLE_COLUMNS]
        with self._lock:
            cur = self._db.execute(
                f"INSERT INTO samples ({', '.join(SAMPLE_COLUMNS)}) VALUES ({', '.join('?' * len(SAMPLE_COLUMNS))})",
                values,
            )
            self._db.commit()
        return self.get_sample(cur.lastrowid)  # type: ignore[arg-type,return-value]

    @staticmethod
    def _sample_row(r: sqlite3.Row) -> dict[str, Any]:
        d = dict(r)
        d["scan"] = json.loads(d.pop("scan_json") or "[]")
        d["findings"] = json.loads(d.pop("findings_json") or "[]")
        return d

    def get_sample(self, sid: int) -> dict[str, Any] | None:
        r = self._db.execute("SELECT * FROM samples WHERE id = ?", (sid,)).fetchone()
        return self._sample_row(r) if r else None

    def list_samples(self, fid: int) -> list[dict[str, Any]]:
        rows = self._db.execute("SELECT * FROM samples WHERE floorplan_id = ? ORDER BY id", (fid,)).fetchall()
        return [self._sample_row(r) for r in rows]

    def delete_sample(self, sid: int) -> bool:
        with self._lock:
            cur = self._db.execute("DELETE FROM samples WHERE id = ?", (sid,))
            self._db.commit()
        return cur.rowcount > 0

    # Access-point labels ----------------------------------------------------------

    def labels(self) -> dict[str, str]:
        return {r["bssid"]: r["label"] for r in self._db.execute("SELECT bssid, label FROM ap_labels")}

    def set_label(self, bssid: str, label: str | None) -> None:
        with self._lock:
            if label:
                self._db.execute(
                    "INSERT INTO ap_labels (bssid, label) VALUES (?, ?) "
                    "ON CONFLICT(bssid) DO UPDATE SET label = excluded.label",
                    (bssid, label),
                )
            else:
                self._db.execute("DELETE FROM ap_labels WHERE bssid = ?", (bssid,))
            self._db.commit()
