# Network Explorer

Tools for understanding and improving a home eero mesh network: why some rooms have poor Wi-Fi, and how to make the network more secure.

The background research is in [`reports/Eero mesh network tooling options.md`](reports/Eero%20mesh%20network%20tooling%20options.md), with the supporting notes in [`research_notes/`](research_notes/).

## What's here

| Part | What it does |
|---|---|
| [`android/`](android/) | **Wi-Fi Survey**, an Android app. Walk around the house, tap where you're standing on the floor plan and press **Measure**. It records signal strength, band, channel, link rate, which eero you're connected to, nearby access points, latency, packet loss and (optionally) download/upload speed. |
| [`server/`](server/) | **Survey server** (Python/FastAPI). Run it on a computer at home. It stores measurements, explains each spot in plain language, and serves a heatmap viewer in the browser. |

```
 Phone (Android app) ──Wi-Fi──► eero mesh ──► Computer running the survey server
   signal, eero BSSID,            │               stores samples, diagnoses them,
   scan, ping, speed test ────────┘               serves the heatmap at http://<ip>:8765/
```

The speed tests run between the phone and the survey server, so they measure your Wi-Fi and the mesh rather than your internet connection. For meaningful numbers, **connect the server computer to an eero with an Ethernet cable**.

## Quick start

### 1. Run the survey server

Python 3.11 or newer:

```bash
cd server
python -m venv .venv && source .venv/bin/activate
pip install -e .
network-explorer serve
```

It prints the address to use, for example:

```
  In the Android app, set the server to:  http://192.168.4.37:8765
  Heatmaps and reports in a browser:      http://192.168.4.37:8765/
```

Data is kept in `~/.network-explorer` (change with `--data-dir`). The server has no login, so keep it on your home network and don't port-forward it.

### 2. Install the Android app

Every push to GitHub builds the app. Open the repository's **Actions** tab, pick the latest **CI** run and download the **wifi-survey-debug-apk** artifact. Unzip it to get `app-debug.apk`, copy it to your phone and open it; Android will ask you to allow installs from that source. To build it yourself instead, see [`android/README.md`](android/README.md).

Requires Android 10 or newer.

### 3. Survey the house

1. Open **Wi-Fi Survey**, tap **Server** and enter the address the server printed.
2. Allow **location** access when asked. Android only tells apps which access point (eero) you're on, and what other networks are nearby, with location permission and Location turned on.
3. Tap **Add plan** and pick a floor-plan image: a photo of a hand-drawn sketch works fine. You can also upload plans from the browser.
4. In each room: type the room name, tap your position on the plan, hold the phone the way you normally would and press **Measure**. A full measurement takes about 15–20 seconds; untick **Speed test** for quicker (about 8-second) signal and latency readings.
5. Aim for 3–5 spots per room, plus the places where Wi-Fi is bad.
6. Open `http://<server-ip>:8765/` on a computer to see the heatmap, per-room table and the **What's wrong** list. In the **Access points** table, give each BSSID the name of its eero (the eero app shows which eero each device is connected to).

## How problems are diagnosed

Each spot is checked against rules from the research report; thresholds are rules of thumb you can tune in `server/network_explorer/diagnosis.py`.

| What the data shows | Likely cause |
|---|---|
| Signal below −75 dBm (or −67 dBm for video calls) | Coverage: too far from an eero, or too many walls |
| Another eero on the same band is 8+ dB stronger than the one the phone uses | Phone not roaming (sticky client) |
| On 2.4 GHz while a 5/6 GHz signal of −70 dBm or better is available | Band steering |
| Strong signal but packet loss, jitter or slow pings | Congestion or interference |
| Strong signal and good link rate, but throughput far below it | Something past the radio link: usually the eero's backhaul |
| Spots near one eero are much slower than spots near another, even at strong signal | That eero's link back to the main eero is weak (wireless backhaul) |
| 5+ neighbouring networks on your channel | Crowded channel |

## Development

```bash
cd server && pip install -e ".[dev]" && pytest          # server tests
cd android && ./gradlew testDebugUnitTest assembleDebug # app tests + APK (needs the Android SDK)
```

CI (`.github/workflows/ci.yml`) runs both on every push and publishes the APK as a build artifact.

## Roadmap

Following the research report: next steps are pulling node and client data from the eero cloud API (to name access points automatically and see eero's own view of each client), LAN device discovery, and a security audit.
