"""FastAPI app: survey API for the Android app, speed-test endpoints and a web viewer."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .db import Store
from .diagnosis import diagnose_sample, summarize
from .wifi import band_for_frequency, channel_for_frequency, normalize_bssid, normalize_ssid, signal_grade

STATIC_DIR = Path(__file__).parent / "static"
MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_SPEEDTEST_BYTES = 200 * 1024 * 1024
_CHUNK = os.urandom(64 * 1024)  # random so nothing along the path can compress it

IMAGE_TYPES = {
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
}


def _sniff_image(data: bytes) -> tuple[str, str] | None:
    for magic, kind in IMAGE_TYPES.items():
        if data.startswith(magic):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ("image/webp", ".webp")
    return None


class ScanEntry(BaseModel):
    bssid: str | None = None
    ssid: str | None = None
    rssi: int | None = None
    frequency_mhz: int | None = None
    channel_width_mhz: int | None = None


class SampleIn(BaseModel):
    x: float = Field(ge=0, le=1, description="Horizontal position as a fraction of the floor-plan width")
    y: float = Field(ge=0, le=1, description="Vertical position as a fraction of the floor-plan height")
    room: str | None = Field(default=None, max_length=100)
    device_model: str | None = Field(default=None, max_length=100)
    ssid: str | None = None
    bssid: str | None = None
    rssi: int | None = Field(default=None, ge=-127, le=0)
    frequency_mhz: int | None = None
    channel_width_mhz: int | None = None
    link_speed_mbps: int | None = None
    tx_link_speed_mbps: int | None = None
    rx_link_speed_mbps: int | None = None
    wifi_standard: str | None = None
    latency_ms_median: float | None = None
    latency_jitter_ms: float | None = None
    packet_loss_pct: float | None = Field(default=None, ge=0, le=100)
    download_mbps: float | None = None
    upload_mbps: float | None = None
    scan: list[ScanEntry] = Field(default_factory=list, max_length=200)


class LabelIn(BaseModel):
    label: str | None = Field(default=None, max_length=100)


def _decorate(sample: dict[str, Any]) -> dict[str, Any]:
    freq = sample.get("frequency_mhz")
    sample["band"] = band_for_frequency(freq)
    sample["channel"] = channel_for_frequency(freq)
    sample["signal_grade"] = signal_grade(sample.get("rssi"))
    return sample


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    data_dir = Path(data_dir or os.environ.get("NETWORK_EXPLORER_DATA") or Path.home() / ".network-explorer")
    store = Store(data_dir)
    app = FastAPI(title="Network Explorer", version=__version__)
    app.state.store = store

    def _floorplan_or_404(fid: int) -> dict[str, Any]:
        fp = store.get_floorplan(fid)
        if not fp:
            raise HTTPException(404, "Floor plan not found")
        return fp

    # Health and speed tests -------------------------------------------------------

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"name": "network-explorer", "version": __version__}

    @app.get("/api/ping")
    def ping() -> Response:
        return Response(status_code=204)

    @app.get("/api/speedtest/download")
    def download(bytes: int = Query(default=10_000_000, ge=1, le=MAX_SPEEDTEST_BYTES)) -> StreamingResponse:
        total = bytes

        def gen():
            remaining = total
            while remaining > 0:
                n = min(remaining, len(_CHUNK))
                yield _CHUNK[:n]
                remaining -= n

        return StreamingResponse(
            gen(),
            media_type="application/octet-stream",
            headers={"Content-Length": str(total), "Cache-Control": "no-store"},
        )

    @app.post("/api/speedtest/upload")
    async def upload(request: Request) -> dict[str, int]:
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_SPEEDTEST_BYTES:
                raise HTTPException(413, "Upload too large")
        return {"bytes": received}

    # Floor plans ------------------------------------------------------------------------

    @app.get("/api/floorplans")
    def list_floorplans() -> list[dict[str, Any]]:
        return store.list_floorplans()

    @app.post("/api/floorplans", status_code=201)
    async def create_floorplan(name: str = Form(..., max_length=100), image: UploadFile = File(...)) -> dict[str, Any]:
        data = await image.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(413, "Image larger than 15 MB")
        kind = _sniff_image(data)
        if not kind:
            raise HTTPException(415, "Floor plan must be a PNG, JPEG or WebP image")
        fp = store.add_floorplan(name.strip() or "Floor plan", data, kind[0], kind[1])
        return {k: fp[k] for k in ("id", "name", "created_at")}

    @app.get("/api/floorplans/{fid}/image")
    def floorplan_image(fid: int) -> FileResponse:
        fp = _floorplan_or_404(fid)
        return FileResponse(store.image_path(fp), media_type=fp["content_type"])

    @app.delete("/api/floorplans/{fid}", status_code=204)
    def delete_floorplan(fid: int) -> Response:
        if not store.delete_floorplan(fid):
            raise HTTPException(404, "Floor plan not found")
        return Response(status_code=204)

    # Samples ----------------------------------------------------------------------------

    @app.get("/api/floorplans/{fid}/samples")
    def list_samples(fid: int) -> list[dict[str, Any]]:
        _floorplan_or_404(fid)
        return [_decorate(s) for s in store.list_samples(fid)]

    @app.post("/api/floorplans/{fid}/samples", status_code=201)
    def add_sample(fid: int, body: SampleIn) -> dict[str, Any]:
        _floorplan_or_404(fid)
        data = body.model_dump()
        data["floorplan_id"] = fid
        data["bssid"] = normalize_bssid(data.get("bssid"))
        data["ssid"] = normalize_ssid(data.get("ssid"))
        data["room"] = (data.get("room") or "").strip() or None
        data["findings"] = diagnose_sample(data)
        return _decorate(store.add_sample(data))

    @app.delete("/api/samples/{sid}", status_code=204)
    def delete_sample(sid: int) -> Response:
        if not store.delete_sample(sid):
            raise HTTPException(404, "Sample not found")
        return Response(status_code=204)

    @app.get("/api/floorplans/{fid}/summary")
    def summary(fid: int) -> dict[str, Any]:
        _floorplan_or_404(fid)
        return summarize(store.list_samples(fid), store.labels())

    # Access-point labels ------------------------------------------------------------------

    @app.get("/api/labels")
    def labels() -> dict[str, str]:
        return store.labels()

    @app.put("/api/labels/{bssid}")
    def set_label(bssid: str, body: LabelIn) -> JSONResponse:
        b = normalize_bssid(bssid)
        if not b:
            raise HTTPException(400, "Invalid BSSID")
        store.set_label(b, (body.label or "").strip() or None)
        return JSONResponse(store.labels())

    # Web viewer ------------------------------------------------------------------------------

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
