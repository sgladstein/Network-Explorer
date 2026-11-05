"""Small Wi-Fi helpers: frequency to band/channel, signal grading."""

from __future__ import annotations


def band_for_frequency(mhz: int | None) -> str | None:
    """Return "2.4", "5" or "6" (GHz) for a channel centre frequency in MHz."""
    if not mhz:
        return None
    if 2400 <= mhz < 2500:
        return "2.4"
    if 5150 <= mhz < 5925:
        return "5"
    if 5925 <= mhz <= 7125:
        return "6"
    return None


def channel_for_frequency(mhz: int | None) -> int | None:
    """Return the IEEE channel number for a 20 MHz channel centre frequency."""
    if not mhz:
        return None
    if mhz == 2484:
        return 14
    band = band_for_frequency(mhz)
    if band == "2.4":
        return (mhz - 2407) // 5
    if band == "5":
        return (mhz - 5000) // 5
    if band == "6":
        return (mhz - 5950) // 5
    return None


# Signal grades. These are the usual rules of thumb for data/voice clients
# (-67 dBm is the common "good enough for video calls" line). They are starting
# points to calibrate against your own house, not standards.
EXCELLENT_DBM = -60
GOOD_DBM = -67
FAIR_DBM = -75


def signal_grade(rssi: int | None) -> str:
    if rssi is None:
        return "unknown"
    if rssi >= EXCELLENT_DBM:
        return "excellent"
    if rssi >= GOOD_DBM:
        return "good"
    if rssi >= FAIR_DBM:
        return "fair"
    return "poor"


def normalize_bssid(bssid: str | None) -> str | None:
    """Lower-case a BSSID and drop Android's "no permission" placeholder."""
    if not bssid:
        return None
    b = bssid.strip().lower()
    if b in ("02:00:00:00:00:00", "00:00:00:00:00:00"):
        return None
    return b


def normalize_ssid(ssid: str | None) -> str | None:
    """Strip the quotes Android puts around SSIDs and its "<unknown ssid>" value."""
    if not ssid:
        return None
    s = ssid.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    if s in ("<unknown ssid>", ""):
        return None
    return s
