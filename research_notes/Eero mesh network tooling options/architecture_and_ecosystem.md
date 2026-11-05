# Architecture and Ecosystem for an eero "Network Explorer" Tool (as of Nov 2026)

Scope: overall system design and the ecosystem of comparable projects. eero API internals, Wi-Fi diagnosis methods, LAN discovery tools and security tooling are covered by other researchers. GitHub star counts and last-push dates come from `gh search repos`, run 2026-11-05.

## Comparable existing projects/products and gaps for eero users

### Takeaway
A small set of eero-specific dashboards appeared in 2025-2026: Dashboard_EERO, eeroVista and several new API clients. They already do eero-cloud polling into SQLite, with Prometheus export, health scores, signal history and alerts, so a new project should fork or borrow from them rather than rebuild that layer. None of them combines eero cloud data with active LAN discovery, floor-plan Wi-Fi surveys and an LLM/MCP interface. That combination is the real gap.

### Cited Findings

**eero-specific projects**
- **Dashboard_EERO** (EnricoFlammini): a self-hosted dashboard and management suite for eero. MIT license, 74 stars, pushed 2026-10-31.
  - Features: real-time traffic, per-device usage, Wi-Fi signal history, speed-test history with bufferbloat grades, and a "Network Health Score" built on four diagnostic pillars. Management covers DHCP reservations with collision detection, port forwarding, guest QR codes and a "Gaming Focus Mode". It handles multiple networks, syncs DNS to AdGuard Home, Pi-hole v6 and Technitium, and sends alerts to Telegram, Discord, Pushover and webhooks. It has local roles (Admin/Operator/Viewer).
  - Stack: Python 3.12, FastAPI, Uvicorn, Pydantic v2, httpx, and async SQLite (aiosqlite, WAL mode, `metrics.db`). The frontend is vanilla HTML with Tailwind, Alpine.js and Chart.js, all self-hosted with no CDN.
  - Integrations: Prometheus `/metrics` with 15+ metrics, a 13-panel Grafana dashboard JSON, and MQTT with Home Assistant auto-discovery.
  - Deployment: multi-arch Docker images (amd64/arm64) on `python:3.12-alpine`, plus a Synology DSM template. Versions v1.4.0 through v1.6.2 are visible.
  - Source: [GitHub](https://github.com/EnricoFlammini/Dashboard_EERO)
- **eeroVista** (Yeraze): read-only eero monitoring. 28 stars, pushed 2026-09-21.
  - Features: a 0-100 health score, device list with signal and bandwidth, mesh topology view, and reports on ISP outages, signal trends, roaming detection, node load balancing and device-activity heatmaps. It detects node restarts from uptime resets and sends Apprise alerts.
  - Polling: devices every 30 s and network stats every 60 s.
  - Retention by default: raw data 7 days, hourly aggregates 30 days, daily aggregates 365 days.
  - Stack: Python 3.11+, FastAPI, SQLAlchemy, APScheduler, SQLite, and Jinja2 with Chart.js and Bootstrap. It uses the `eero-client` package.
  - Integrations: Prometheus `/metrics` and Zabbix low-level discovery.
  - Limitation: accounts linked to an Amazon login are not supported directly; the workaround is a separate email/password admin account.
  - Source: [GitHub](https://github.com/Yeraze/eeroVista)
- **schmittx/home-assistant-eero**: the main Home Assistant (HA) custom integration. 221 stars, 39 open issues, 13 open PRs, no releases, last push 2025-09-20. That suggests it is slowing down; flag it as possibly under-maintained.
  - Features: guest network, eero Plus and Labs toggles, pause access per profile or client, content filters, device trackers, sensors, firmware update entities, and network QR images.
  - Requires HA 2025.2+ and installs through HACS as a custom repository.
  - Source: [GitHub](https://github.com/schmittx/home-assistant-eero)
- **jrlucier/eero_tracker**: an older HA device tracker. Last push 2021-05-08. **Unmaintained**; forum users report sign-in errors. Sources: [GitHub](https://github.com/jrlucier/eero_tracker), [HA Community](https://community.home-assistant.io/t/eero-support/21153?page=5)
- **343max/eero-client**: the original Python client, 196 stars, last push 2024-02-08. **Stale.** Source: [GitHub](https://github.com/343max/eero-client)
- **New clients from 2026** (all from `gh search`):
  - fulviofreitas/eero-api (Python): 14 stars, pushed 2026-11-04
  - fulviofreitas/rusteero (Rust): pushed 2026-10-31
  - arvarik/eero-go (Go): pushed 2026-04-23
  - Xaoimoon/ha-eero (a new French-language HA integration): pushed 2026-11-04
  - Sources: [eero-api](https://github.com/fulviofreitas/eero-api), [rusteero](https://github.com/fulviofreitas/rusteero), [eero-go](https://github.com/arvarik/eero-go), [ha-eero](https://github.com/Xaoimoon/ha-eero)
- **fulviofreitas/eero-mcp**: a "read-only MCP server for eero mesh Wi-Fi networks, built on rusteero (unofficial)". 0 stars, pushed 2026-11-03. It is very new and unproven, but it is the only eero MCP server found. Source: [GitHub](https://github.com/fulviofreitas/eero-mcp)
- Other older eero tools: yepher/eeroMonitor (last push 2018, **unmaintained**) and ssnover/knockknock (eero to MQTT presence daemon, last push 2023). Sources: [eeroMonitor](https://github.com/yepher/eeroMonitor), [knockknock](https://github.com/ssnover/knockknock)

**Generic LAN discovery and visibility tools**
- **NetAlertX**: about 7.4k stars, pushed 2026-11-01. It continuously scans for new devices and state changes and sends alerts to 80+ services through Apprise.
  - Discovery plugins: arp-scan, Pi-hole DB and DHCP imports, generic DHCP leases, UniFi controller import and SNMP router import. There is a plugin system for custom scanners.
  - Integrations: Home Assistant, API and webhooks, and Prometheus export. It runs as Docker, an HA add-on or an Unraid app.
  - There is **no eero plugin**. An eero importer plugin would be a natural contribution.
  - Sources: [GitHub](https://github.com/jokob-sk/NetAlertX), [gh search](https://github.com/netalertx/NetAlertX)
- **WatchYourLAN** (aceberg): 7.6k stars, last push 2025-09-10. It may be slowing down. Source: [GitHub](https://github.com/aceberg/WatchYourLAN)
- **Scanopy**: 5.9k stars, pushed 2026-11-04. A self-hosted network mapper that generates L2, L3, workload and application diagrams on a schedule.
  - It uses scanning daemons on Linux, macOS, Windows or Docker, with integrations for Docker, Proxmox, UniFi, SNMP, SSH and gNMI, and recognizes 410+ service types.
  - Exports: SVG, Mermaid and live embeds. Docker Compose deployment on port 60072.
  - License: AGPL-3.0 Community Edition, plus a commercial tier.
  - A third-party scanopy-mcp-server exists (3 stars).
  - Sources: [GitHub](https://github.com/scanopy/scanopy), [gh search](https://github.com/maxparez/scanopy-mcp-server)
- **ntopng**: 8.3k stars, actively pushed 2026-11-04. Its Grafana datasource plugin is stale (last push 2019). Sources: [ntopng](https://github.com/ntop/ntopng), [datasource](https://github.com/ntop/ntopng-grafana-datasource)
- **Kismet**: 2.3k stars, pushed 2026-11-03. Wireless monitor-mode capture. Source: [GitHub](https://github.com/kismetwireless/kismet)

**Wi-Fi survey and heatmap tools**
- **hnykda/wifi-heatmapper**: MIT, 277 stars, pushed 2026-11-01.
  - A laptop walk-around survey: click your position on a floor plan (an uploaded image or phone photo of a sketch). "Signal only" mode takes about 2 s per spot; "signal and speed" mode adds iperf3 against a wired host.
  - Platforms: macOS 13.5+, Windows 10/11, and Linux (.deb, AppImage or Docker). Built with Next.js and Tauri, with a native macOS Wi-Fi helper.
  - Surveys are stored as plain JSON. It has an **optional MCP server so AI agents can read surveys and guide measurements**.
  - Source: [GitHub](https://github.com/hnykda/wifi-heatmapper)
- **jantman/python-wifi-survey-heatmap**: AGPL-3.0, about 500 stars, last push 2025-08-28.
  - Linux-only: the kernel must manage the Wi-Fi hardware directly. Docker install is recommended.
  - Click on a floor plan to record signal and iperf bandwidth, then render the heatmap.
  - Self-described "rough beta" with an inactive badge, so **treat it as low-maintenance**.
  - Sources: [GitHub](https://www.github.com/jantman/python-wifi-survey-heatmap), [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fjantman%2Fpython-wifi-survey-heatmap)
- **benmwebb/wifi-heatmap**: Qt GUI, GPL-3.0. **Effectively unmaintained.** Source: [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Fbenmwebb%2Fwifi-heatmap)

**Commercial products**
- **Fing**: device discovery ("who is on my Wi-Fi"), speed tests and LAN scan, free with in-app purchases. Coverage heatmaps come from a separate app, WiFi Map Explorer. Sources: [App Store](https://apps.apple.com/us/app/-/id430921107), [netxl review](https://www.netxl.com/blog/networking/wifi-network-analyzer-fing/)
- **WiFiman (Ubiquiti)**: Wi-Fi 6 analyzer, signal meter, speed test, network and port scanner. A reviewer notes it lacks ping and traceroute. Deeper surveys use the "WiFiman Wizard" spectrum-analyzer hardware. Source: [netxl review](https://www.netxl.com/blog/networking/wifi-network-analyzer-fing/)
- **Firewalla**: inline security box.
  - With eero, Firewalla recommends **Bridge Mode**: Firewalla sits between the modem and the gateway eero. Simple Mode is legacy and no longer recommended. Sources: [Firewalla bridge mode](https://help.firewalla.com/hc/en-us/articles/24044720058259-Firewalla-Bridge-Mode-Introduction-Newsletter-Feb-22-2023), [Firewalla compatibility](https://help.firewalla.com/hc/en-us/articles/4411167832851)
  - Bridge mode on the eero itself disables advanced security, ad blocking, content filters and hotspot backup. Source: [eero support](https://eero.com/support/articles/what-is-bridge-mode)
- **WLAN Pi**: the project's org repos are active, for example wlanpi-profiler (Wi-Fi client capability analyzer, pushed 2026-11-01). Some older WLAN Pi repos are abandoned (profiler-legacy is marked "ABANDONED"). The wlanpi.com site could not be fetched from this environment. Source: [gh search](https://github.com/WLAN-Pi/wlanpi-profiler)

### Inferences
- The eero-cloud collector layer is a solved problem. Dashboard_EERO is the most complete eero-specific base to fork or study: MIT license, FastAPI with SQLite, Prometheus, MQTT and Grafana, multi-arch Docker. eeroVista's retention and rollup design (raw 7 d, hourly 30 d, daily 365 d) is a good template.
- Gaps for eero users that no single project fills:
  - eero client data (node, band, signal) merged with active LAN discovery (ARP/mDNS/nmap).
  - Spatial Wi-Fi surveys linked to which eero node a client roams to.
  - Historical "why is room X slow" analysis.
  - A natural-language troubleshooting layer.
- Integration-first options:
  - Feed eero data into NetAlertX through a new plugin.
  - Import wifi-heatmapper JSON surveys.
  - Expose everything through MCP.
- Commercial tools such as WiFiman and UniFi assume vendor hardware. Fing gives discovery but not eero-node-aware analytics.

### Gaps
- I did not verify commit cadence, issue responsiveness or code quality for Dashboard_EERO, eeroVista or eero-mcp beyond their READMEs and last-push dates.
- I found no reliable source on Firewalla's own device-map features with eero.
- I did not research the UniFi network map or Grafana community dashboards in depth.
- The r/eero and r/homelab discussions were not reachable for sentiment on these tools.

## Deployment hardware (Pi, mini PC, NAS, Mac, Wi-Fi adapters, ESP32)

### Takeaway
Raspberry Pi pricing has risen sharply in 2025-2026 because of DRAM costs, which weakens its cost advantage over x86 mini PCs. Any Linux Docker host with arm64 or amd64 can run the comparable projects. Monitor-mode capture needs a Linux box with a supported USB adapter. macOS restricts Wi-Fi metadata, which makes an always-on Mac a poor headless Wi-Fi sensor.

### Cited Findings
- **Raspberry Pi price history**:
  - Raspberry Pi raised prices in Oct 2025, Dec 2025, Feb 2026, Apr 2026 and Oct 2026, citing LPDDR4 DRAM costs up about sevenfold since 2025. Source: [Tom's Hardware](https://www.tomshardware.com/raspberry-pi/component-shortages-drive-raspberry-pi-prices-up-by-up-to-23-percent-escalating-lpddr4-lpddr5-costs-trigger-the-third-price-hike-of-the-year), [The Register](https://www.theregister.com/2026/02/02/raspberry_pi_ram_shortage_price_hike/), [Gigazine](https://www.gigazine.net/gsc_news/en/20260402-raspberry-pi-price-increases)
  - The Pi 5 2GB is now $77.50. Source: [Phoronix](https://www.phoronix.com/news/Raspberry-Pi-5-2GB-Price-77.50)
  - The 16GB reached $205 in Feb 2026, against a $120 launch price. Source: [Tom's Hardware](https://www.tomshardware.com/raspberry-pi/raspberry-pi-5-price-increases-drastically-as-ai-shortage-bites-16gb-version-now-usd205-second-price-increase-in-three-months-over-70-percent-more-expensive-than-original-msrp)
  - **Sources conflict on Oct 2026 prices for the 4/8/16GB models**: one reports 8GB at $130 and 16GB at $220; another reports 4GB at $110, 8GB at $180 and 16GB at $305. Check the official pricing page. Source: [OMG! Ubuntu](https://www.omgubuntu.co.uk/2026/10/raspberry-pi-2gb-costs-how-much-now/amp), [Phoronix](https://www.phoronix.com/news/Raspberry-Pi-5-2GB-Price-77.50)
- **Comparable projects run on modest hardware**: Dashboard_EERO publishes linux/amd64 and linux/arm64 images and a Synology DSM 7.2+ template, so a Pi, mini PC or NAS all work. Source: [Dashboard_EERO](https://github.com/EnricoFlammini/Dashboard_EERO)
- **USB Wi-Fi adapters for Linux**: morrownr/USB-WiFi is the main community reference, updated through 2026. It maintains a "Plug and Play" list of adapters with in-kernel drivers and a separate Monitor_Mode guide, and covers mt7921/mt7922 (Wi-Fi 6) and mt7925 (Wi-Fi 7) chipsets. The fetched landing page did not list specific adapter models. Source: [GitHub](https://github.com/morrownr/USB-WiFi)
- **Surveys need direct kernel control of the Wi-Fi hardware**: python-wifi-survey-heatmap works only where the Linux kernel manages the Wi-Fi hardware directly, which rules out VMs and some containers. Source: [jantman](https://www.github.com/jantman/python-wifi-survey-heatmap)
- **macOS restrictions**:
  - `airport` was removed in macOS 14.4. `wdutil` needs sudo and redacts SSID and BSSID.
  - CoreWLAN returns SSID and BSSID only to apps with Location Services authorization and a stable Developer ID signature.
  - Location authorization is per user session, so a system launchd daemon does not work. The workaround is a signed app bundle launched with `open -W`.
  - Sources: [DEV Community](https://dev.to/jaisonerick/reading-wi-fi-data-from-go-on-macos-after-apple-removed-airport-19g), [Apple Forums](https://developer.apple.com/forums/thread/732431), [Jamf](https://community.jamf.com/t5/jamf-pro/collecting-active-ssid-with-macos-sonoma-14-4-and-later/m-p/311680)

### Inferences
- Recommended host: a small always-on Linux box running Docker. With Pi 4GB and 8GB prices in the $110-$180 range, an x86 N100 mini PC is likely cost-competitive and easier to run (x86 images, more RAM, NVMe). A NAS host works if the project needs no raw Wi-Fi access.
- Keep the Wi-Fi sensing role separate from the server role. A Linux laptop or Pi with a supported MediaTek USB adapter can scan and capture. The server only collects data.
- ESP32 boards as cheap fixed RSSI or latency sensors in each room are plausible. Low cost and Wi-Fi scanning ability are general knowledge, but I found no 2026 source for this note.

### Gaps
- I found no sourced 2026 prices or power-draw figures for N100 mini PCs, Alfa adapters (for example AWUS036AXML) or ESP32 boards.
- I did not confirm MT7921AU monitor-mode reliability on the Pi 5. morrownr's Monitor_Mode page was not fetched.
- I found no published ESP32 home-mesh sensor projects; this needs a dedicated search.
- wlanpi.com was unreachable, so WLAN Pi hardware (R4/M4/Go) prices and features are unverified.

## Software stack options (language, storage, UI, deployment)

### Takeaway
The eero ecosystem has converged on Python and FastAPI, SQLite with time-based rollups, Prometheus `/metrics`, and a light server-rendered or Alpine.js frontend, all in Docker Compose. Go and Rust eero clients now exist as well. For a hobbyist build, Python with FastAPI and SQLite (or DuckDB for analytics) gives the most reusable code, with Grafana as an optional add-on rather than the primary UI.

### Cited Findings
- **Dashboard_EERO**: Python 3.12, FastAPI, httpx, aiosqlite in WAL mode with a serialized write lock and 60 s busy timeout, Tailwind/Alpine/Chart.js, Prometheus, a Grafana dashboard JSON and MQTT. Source: [GitHub](https://github.com/EnricoFlammini/Dashboard_EERO)
- **eeroVista**: Python, FastAPI, SQLAlchemy, APScheduler, SQLite with rollup tiers, Jinja2 and Chart.js. Source: [GitHub](https://github.com/Yeraze/eeroVista)
- **Language options**:
  - Python clients: eero-api (active) and eero-client (stale).
  - Rust: rusteero. Go: eero-go. TypeScript: eero-ts (last push 2020, **unmaintained**).
  - Sources: [eero-api](https://github.com/fulviofreitas/eero-api), [rusteero](https://github.com/fulviofreitas/rusteero), [eero-go](https://github.com/arvarik/eero-go), [eero-ts](https://github.com/343max/eero-ts)
- **wifi-heatmapper** uses TypeScript, Next.js and Tauri for a cross-platform desktop survey app, storing JSON files. Source: [GitHub](https://github.com/hnykda/wifi-heatmapper)
- **Docker Compose is the deployment norm**: NetAlertX, Scanopy, eeroVista and Dashboard_EERO all ship Compose files or `docker run` commands with a mounted `/data` volume. NetAlertX also ships as an HA add-on and an Unraid app; Scanopy as a Proxmox LXC script and an Unraid app. Sources: [NetAlertX](https://github.com/jokob-sk/NetAlertX), [Scanopy](https://github.com/scanopy/scanopy), [eeroVista](https://github.com/Yeraze/eeroVista)
- **HACS change**: HACS is reportedly being built into Home Assistant from 2026.11. This comes from a single German article and is **unconfirmed**. Source: [tink.de](https://www.tink.de/blog/?p=55154)

### Inferences
- **Python** is the best fit if code reuse matters. It can use the eero-api client, scapy, pandas or DuckDB analytics, and the mcp SDK in one language. **Go or Rust** suit a single static binary for sensors or agents.
- **Storage**: SQLite (WAL) with rollup tables is enough at home scale. Both eero dashboards prove it. Add DuckDB for ad-hoc analytics on exported Parquet. Run Prometheus plus Grafana only if you already have them. InfluxDB and TimescaleDB look like overkill. That last point is a judgement; I found no benchmark source.
- **UI**: a FastAPI app with a light frontend (HTMX/Alpine or Svelte) for the floor plan and topology views. Expose `/metrics` so Grafana stays optional. A TUI could serve on-host diagnostics.
- **Integration surface**: publish to MQTT with HA discovery, as Dashboard_EERO does, so HA users get entities for free.

### Gaps
- I found no sourced comparisons of InfluxDB, TimescaleDB, DuckDB and Prometheus for home-scale network telemetry.
- I did not verify the Svelte versus React choice in comparable projects. Scanopy's frontend stack was not stated on its README page.

## Mobile data collection for walk-around Wi-Fi surveys

### Takeaway
iOS is effectively a dead end for RSSI-based surveys through public APIs. Android works with throttling limits (4 scans per 2 minutes in the foreground) and can disable the limit in developer options. A laptop running wifi-heatmapper or a Linux survey tool is the most practical option today.

### Cited Findings
- **iOS**:
  - NEHotspotHelper requires a gated entitlement. Apple DTS says it is "not a general-purpose Wi-Fi management API", and that technical and business restrictions stop it being used for tasks such as Wi-Fi based location.
  - iOS has no general Wi-Fi scanning API.
  - `NEHotspotNetwork.fetchCurrent` signalStrength reportedly returns 0 or nil without the entitlement.
  - Sources: [Apple Forums 751316](https://developer.apple.com/forums/thread/751316), [Apple Forums 788783](https://developer.apple.com/forums/thread/788783), [Apple Forums 733598](https://developer.apple.com/forums/thread/733598), [Apple Forums 740020](https://developer.apple.com/forums/thread/740020)
- **Android throttling**: on Android 9 and later, each foreground app can call `startScan()` 4 times in 2 minutes. All background apps combined get 1 scan per 30 minutes. Android 10+ adds a developer option (Developer Options > Networking > Wi-Fi scan throttling) to turn throttling off for testing. Source: [Android Developers](https://developer.android.com/develop/connectivity/wifi/wifi-scan)
- **Android permissions**: on Android 10+, apps targeting API 29+ need ACCESS_FINE_LOCATION plus CHANGE_WIFI_STATE (for scanning) or ACCESS_WIFI_STATE (for results), with Location Services switched on. Source: [Android Developers](https://developer.android.com/develop/connectivity/wifi/wifi-scan)
- **Passive listening on Android**: on Android 10+, the `SCAN_RESULTS_AVAILABLE_ACTION` broadcast fires for any full scan run by the platform or other apps, so an app can collect results without spending its own scan budget. Source: [Android Developers](https://developer.android.com/develop/connectivity/wifi/wifi-scan)
- **Laptop surveys**: wifi-heatmapper takes about 2 s per spot in signal-only mode and runs on macOS, Windows and Linux. Source: [GitHub](https://github.com/hnykda/wifi-heatmapper)
- **macOS caveat**: macOS surveys need Location Services permission and a signed app to read BSSIDs. Source: [DEV Community](https://dev.to/jaisonerick/reading-wi-fi-data-from-go-on-macos-after-apple-removed-airport-19g)

### Inferences
- MVP: use a laptop survey with wifi-heatmapper, either as-is or by importing its JSON. Phase 2 could be an Android companion app that records the connected-BSSID RSSI (from connection info, which is not scan-throttled) plus throttled scans while the user taps a floor-plan position. An iOS app could at most record speed or latency tests per room, not RSSI.
- An iOS Shortcuts-based "room tag plus speed test" flow is plausible but unverified.

### Gaps
- I did not verify whether Android's `WifiManager.getConnectionInfo()` RSSI is throttled or deprecated in Android 15/16 (the `ConnectivityManager` NetworkCapabilities TransportInfo path).
- I found no source on iOS Shortcuts automation for Wi-Fi metrics.
- I did not confirm whether CoreWLAN `rssiValue` (as opposed to SSID/BSSID) is gated by Location permission.

## LLMs/AI agents and MCP servers for network diagnostics

### Takeaway
MCP is now a normal integration surface in this space. There is an official Home Assistant MCP server plus a popular community ha-mcp, several nmap MCP servers (some already archived), an MCP mode in wifi-heatmapper, and a brand-new read-only eero-mcp. A Network Explorer should expose its own read-mostly MCP server over its database and safe diagnostic tools, with scope limits on any active scanning.

### Cited Findings
- **Home Assistant has an official MCP server since 2025.2**. It reaches only Assist-exposed entities and cannot edit automations. Source: [raspberry.tips](https://raspberry.tips/en/smart-home/home-assistant-mcp-server-ai-setup)
- **homeassistant-ai/ha-mcp**: an unofficial server with 95+ tools; 5.4k stars, pushed 2026-11-04. It installs as an HA add-on, a custom integration, Docker or stdio. Sources: [GitHub](https://github.com/homeassistant-ai/ha-mcp), [gh search](https://github.com/homeassistant-ai/ha-mcp)
- **voska/hass-mcp**: 351 stars, pushed 2026-11-02. Source: [GitHub](https://github.com/voska/hass-mcp)
- **nmap MCP servers**:
  - PhialsBasement/nmap-mcp-server: Node.js, 49 stars, **archived** (2026-06).
  - samcsta/mcp-nmap: Node 22.5+. **It requires a scope allow-list of authorized targets and refuses every scan if the list is unset.**
  - 0xPratikPatil/NmapMCP: Python, with ARP discovery and UDP scans.
  - Sources: [PhialsBasement](https://awesome.ecosyste.ms/projects/github.com%2Fphialsbasement%2Fnmap-mcp-server), [samcsta](https://github.com/samcsta/mcp-nmap), [lobehub](https://lobehub.com/en/mcp/0xpratikpatil-nmapmcp)
- **Security MCP collections**: cyproxio/mcp-for-security (628 stars) is **archived** (2026-03). DMontgomery40/pentest-mcp has 150 stars and is active (2026-10-30). Source: [gh search](https://github.com/cyproxio/mcp-for-security), [pentest-mcp](https://github.com/DMontgomery40/pentest-mcp)
- **eero-mcp** (read-only, Rust-based): new, 0 stars. Source: [GitHub](https://github.com/fulviofreitas/eero-mcp)
- **wifi-heatmapper's optional MCP server** lets AI agents read surveys and guide measurements. Source: [GitHub](https://github.com/hnykda/wifi-heatmapper)
- **hecisaza/network-mcp-servers**: a curated list of MCP servers for network automation, 3 stars, pushed 2026-07. Source: [GitHub](https://github.com/hecisaza/network-mcp-servers)

### Inferences
- Suggested MCP tool design:
  - Read-only tools over stored data: `list_devices`, `get_device_history`, `get_node_health`, `get_survey(room)`, `compare_periods`.
  - A few bounded active tools: ping, traceroute, DNS lookup, a speed test, and nmap restricted to the home subnet allow-list, following the samcsta pattern.
  - eero write actions (reboot, pause) behind explicit confirmation or left out.
- The pattern used by Dashboard_EERO and eeroVista (precomputed health scores plus history) is ideal context for an LLM. It turns raw time series into a summary the model can reason over.

### Gaps
- I did not assess the code quality or security of eero-mcp or the nmap MCP servers.
- I did not check the official MCP registry listings directly.

## Floor plan and spatial mapping for heatmaps

### Takeaway
The established pattern: upload a floor-plan image (even a phone photo), click your position to record a sample, then interpolate a heatmap. Store samples as (survey, x, y in image pixel coordinates, timestamp, metrics) in JSON or SQLite.

### Cited Findings
- **wifi-heatmapper**: upload your own floor plan or a phone photo of a sketch. Each click creates a dot, and a radius slider adjusts until the dots merge into one map. Surveys are stored locally as plain JSON. Source: [GitHub](https://github.com/hnykda/wifi-heatmapper)
- **python-wifi-survey-heatmap**: load a floor plan image, click to record signal strength and iperf bandwidth, then run `wifi-heatmap` to compute a high-resolution heatmap. Its interpolation derives from Beau Gunderson's MIT wifi-heatmap code. Source: [jantman](https://www.github.com/jantman/python-wifi-survey-heatmap)
- **Fing**: puts 2D coverage heatmaps in a separate app, WiFi Map Explorer. Source: [App Store/Fing](https://apps.apple.com/us/app/-/id430921107)

### Inferences
- Data model sketch:
  - `floorplan` (id, image, scale_px_per_m, floor)
  - `room` (polygon on floorplan, name)
  - `survey` (id, device, started_at)
  - `sample` (survey_id, x, y, room_id, ts, bssid, eero_node, band, channel, rssi, tx_rate, iperf_down, iperf_up, latency)
- Joining samples to eero node data by BSSID or timestamp lets the tool explain which node served each spot. No surveyed project does this for eero.
- Importing wifi-heatmapper JSON avoids rebuilding the survey UX in an MVP.

### Gaps
- I did not research interpolation algorithms (IDW, RBF, kriging) or wall-attenuation modelling.
- I did not verify wifi-heatmapper's JSON schema.

## Security and privacy of the tool itself

### Takeaway
Comparable eero tools store the eero session token on disk (`session.json`, mode 0600) after a 2FA one-time-code login, and add their own local auth for the dashboard. A new tool should do the same, plus keep the dashboard LAN- or VPN-only, run only the scanner component with raw-socket privileges, and keep MCP tools read-only and scoped.

### Cited Findings
- **Dashboard_EERO**:
  - eero login is a 2FA code sent to email or phone. The session token is saved to `./data/session.json` with 0600 permissions and restored after restarts.
  - It has a separate local admin account and RBAC, and the image runs as a non-root user.
  - Its README also says the container runs as root on Linux, which needs sudo or `docker exec` to read the file from the host. These two statements are **inconsistent** and should be verified.
  - Source: [GitHub](https://github.com/EnricoFlammini/Dashboard_EERO)
- **eeroVista**: a read-only design (it cannot change config or reboot). Data stays in local SQLite and is "not sent to external services". Amazon-login accounts need a separate admin account. Source: [GitHub](https://github.com/Yeraze/eeroVista)
- **samcsta/mcp-nmap**: enforces a target scope allow-list before scanning. Source: [GitHub](https://github.com/samcsta/mcp-nmap)
- **wifi-heatmapper**: needs a sudo password for some measurements. Anonymous usage counts are on by default and can be turned off. Source: [GitHub](https://github.com/hnykda/wifi-heatmapper)

### Inferences
- Use a dedicated eero admin (non-owner) account for the tool where possible; eeroVista's guidance suggests this is feasible.
- Store tokens with file permissions or an OS keyring.
- Run the active scanner as a separate container with `NET_RAW`/`NET_ADMIN` capabilities and host networking, and run the web, API and MCP layers unprivileged.
- Bind the dashboard to the LAN and reach it remotely through Tailscale or WireGuard rather than port forwarding.

### Gaps
- I found no published security reviews of any eero third-party tool.
- I did not check eero's terms on unofficial API use (covered by the eero-API researcher).

## A sensible MVP and phased roadmap

### Takeaway
Comparable projects put health scores, device inventory with signal history, new-device and offline alerts, and Prometheus/MQTT export first. Spatial surveys and AI come later. A pragmatic MVP: eero collector plus LAN discovery plus history plus alerts, then surveys, then MCP and AI.

### Cited Findings
- **Features both mature eero dashboards ship first**: health score, device list with signal and bandwidth, node or topology view, speed-test history, alerts (new device, node or device offline, firmware), and Prometheus. Sources: [eeroVista](https://github.com/Yeraze/eeroVista), [Dashboard_EERO](https://github.com/EnricoFlammini/Dashboard_EERO)
- **NetAlertX's core value** is continuous discovery plus alerting for new or unauthorized devices, with 80+ notification targets. Source: [NetAlertX](https://github.com/jokob-sk/NetAlertX)
- **Scanopy's core value** is auto-maintained topology diagrams with Mermaid and SVG export. Source: [Scanopy](https://github.com/scanopy/scanopy)

### Inferences
Proposed phases:
- **Phase 0 (spike)**: run Dashboard_EERO or eeroVista alongside NetAlertX in Docker Compose for a few weeks to learn what data matters. Reuse the eero-api client.
- **Phase 1 (MVP)**:
  - Python/FastAPI collector that polls eero every 30-60 s.
  - ARP/mDNS discovery, merging devices by MAC.
  - SQLite with rollups.
  - Device and node pages, new-device and offline alerts via Apprise.
  - `/metrics` endpoint and LAN-only binding.
- **Phase 2**:
  - Floor-plan upload with room tags.
  - Import or record laptop surveys (wifi-heatmapper JSON or a Linux scanner).
  - Join samples to eero nodes.
  - Heatmaps per band.
- **Phase 3**:
  - Read-only MCP server over the database plus scoped diagnostics.
  - Natural-language "why is X slow" reports.
  - Weekly digest.
- **Phase 4 (optional)**:
  - Android survey companion.
  - Fixed ESP32 or Pi room sensors for continuous per-room RSSI and latency.
  - Monitor-mode capture with Kismet and a MediaTek USB adapter.
  - HA MQTT discovery.
  - Security checks (handed off to the security researcher).

### Gaps
- I found no user surveys or r/eero threads ranking which features users value most. The ordering above is inferred from what the comparable projects chose to build first.
