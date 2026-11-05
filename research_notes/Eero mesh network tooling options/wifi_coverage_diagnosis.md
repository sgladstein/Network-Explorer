# Diagnosing Poor Wi-Fi Coverage and Dead Zones in a Home eero Mesh (as of Nov 2026)

Research note: support.eero.com and dev.to could not be fetched directly from this session (DNS blocked by session network policy). eero claims below come from search-result snippets of eero's own support pages and from eero community threads, not from full-page reads.

## Which metrics matter, and which can each client OS measure?

### Takeaway
On Linux, a client can report almost every useful link-layer metric: RSSI, PHY rates, retries/failures, and channel busy time. macOS gives RSSI, noise and Tx rate through CoreWLAN, but the CLI tools are now fragile. Windows gives only a 0-100 "signal quality" (which converts linearly to RSSI) plus Rx/Tx rates. Android throttles scans. iOS has no supported RSSI API at all. A cross-platform tool should therefore lean on active tests (iperf3 throughput, ping latency/jitter/loss), which work everywhere, and treat RSSI/retries as optional extras for each platform.

### Cited Findings
**Linux (nl80211 / `iw`)**
- `iw dev <if> station dump` reports per-station counters, including tx_retries and tx_failed (cumulative). tx_failed counts transmissions that failed after retries ran out or no ACK arrived — [Debian struct station_info manpage](https://manpages.debian.org/wheezy/linux-manual-3.2/struct_station_info.9.en.html)
- "signal avg" is averaged RSSI in dBm. Newer `iw` builds also print an average ACK signal for data frames — [kernel.org patchwork (ack RSSI patch)](https://patchwork.kernel.org/project/linux-wireless/patch/1520493426-26628-1-git-send-email-bpothuno@codeaurora.org/mbox)
- Some drivers/firmware report retries and failures as 0. Example: ath10k SDIO firmware without tx-completion reporting, until a patch fixed it. Zeros do not prove the link is clean — [kernel.org patchwork](https://patchwork.kernel.org/patch/11504903)
- `iw dev <if> survey dump` gives channel active time, busy time (channel sensed busy) and receive time (time spent receiving valid 802.11 traffic) — [ath10k mailing list](https://lists.infradead.org/pipermail/ath10k/2015-June/005469.html)
- Survey counters should increase monotonically, but some ath10k firmware reset them between dumps, so values went backwards. The fix was a non-clearing read — [LKML ath10k patch](https://lkml.iu.edu/hypermail/linux/kernel/2010.3/03630.html)
- Channel utilization ≈ Δbusy / Δactive between two readings (secondary source). The same thread argues that high utilization is not always a problem — [TelecomHall](https://www.telecomhall.net/t/high-channel-utilization-isn-t-always-a-problem/33620)
- A Rust crate (`netlink_wi`) exposes nl80211 station info programmatically, so a tool can avoid parsing `iw` output — [docs.rs netlink_wi station.rs](https://docs.rs/crate/netlink_wi/latest/source/src/station.rs)

**macOS**
- Apple removed the `airport` CLI in macOS Sonoma 14.4. The deprecation notice points users to `wdutil` — [jaisonerick macwifi page](https://jaisonerick.github.io/macwifi/); [Jamf community](https://community.jamf.com/t5/jamf-pro/collecting-active-ssid-with-macos-sonoma-14-4-and-later/m-p/311680)
- `wdutil info` needs sudo. One report says that as of macOS 14.5 it returns `<redacted>` for MAC address, SSID and BSSID — [Jamf community](https://community.jamf.com/t5/jamf-pro/collecting-active-ssid-with-macos-sonoma-14-4-and-later/m-p/311680); [r/macsysadmin thread (mirror)](https://red.127.pp.ua/r/macsysadmin/comments/1bem1e5/view_wifi_signal_level_in_the_terminal_sonoma)
- CoreWLAN (used by the third-party `macwifi` Go package) returns SSID, BSSID, RSSI, noise floor, channel and related fields, but needs Location Services permission — [macwifi](https://jaisonerick.github.io/macwifi/)
- The wifi-heatmapper README says `wdutil` worked on macOS 14, broke on 15.0-15.2 and worked again on 15.3. Parsing CLI output across OS versions is brittle — [hnykda/wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper)
- wifi-heatmapper now ships a native macOS helper (`native/macos-wifi-helper`) and requires macOS 13.5+. This suggests the project moved toward native API access over CLI scraping — [hnykda/wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper)

**Windows**
- The Native Wifi API's `WLAN_ASSOCIATION_ATTRIBUTES` holds SSID, BSSID, PHY type, `wlanSignalQuality`, `ulRxRate` and `ulTxRate` — [Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ns-wlanapi-wlan_association_attributes)
- `wlanSignalQuality` runs 0-100. 0 means -100 dBm and 100 means -50 dBm, and values in between convert to RSSI by linear interpolation. So Windows does not give true dBm through this field, and it clips everything above -50 dBm — [Microsoft Learn](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ns-wlanapi-wlan_association_attributes)
- `netsh wlan` output is localized by language, so it is hard to parse reliably — [hnykda/wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper)

**Android**
- Since Android 9, foreground apps can call `WifiManager.startScan()` 4 times per 2 minutes, and background apps once per 30 minutes. Later versions keep these limits. A developer option ("Wi-Fi scan throttling") turns throttling off for local testing — [Android Developers: Wi-Fi scanning](https://developer.android.com/develop/connectivity/wifi/wifi-scan)
- Throttling broke several network tools when Android 9 shipped — [XDA](https://www.xda-developers.com/android-pie-throttling-wi-fi-scans-crippling-apps/)
- Apps holding NETWORK_SETTINGS are exempt, but that permission is effectively limited to system apps (Stack Overflow relay of a Google issue tracker note) — [SO mirror](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/54192151/handle-wifimanager-startscan-on-foreground-in-android-p)

**iOS**
- Apple DTS: there is no official or supported way to get current Wi-Fi RSSI on iOS, in any iOS version. `NEHotspotHelper` needs special entitlements and is not a general Wi-Fi management API — [Apple Developer Forums 835163](https://developer.apple.com/forums/thread/835163); [Apple Developer Forums 67932](https://developer.apple.com/forums/thread/67932)
- `NEHotspotNetwork.signalStrength` returned 0.0 for developers on iOS 16 and iOS 18, even with the Access WiFi Information capability. SSID and BSSID still worked — [Apple Forums 726270](https://developer.apple.com/forums/thread/726270); [Apple Forums 835163](https://developer.apple.com/forums/thread/835163)
- No public API scans nearby networks on iOS 17+ — [Apple Forums 788783](https://developer.apple.com/forums/thread/788783)

### Inferences
- Metric priority for a "bad room" diagnosis:
  - (1) Latency/jitter/loss to the gateway and to the internet. This is what users actually feel.
  - (2) Throughput with iperf3 to a wired LAN host. This isolates Wi-Fi from the ISP.
  - (3) RSSI and the noise-derived SNR.
  - (4) PHY rate/MCS. A low PHY rate at good RSSI points to interference or client limits.
  - (5) Retries/failures. High retries at good RSSI suggest interference or hidden nodes.
  - (6) Channel busy %. This shows congestion.
  - (7) BSSID changes over time, which reveal roaming and sticky clients.
- Comparing iperf3 to a wired host with a speed test to the internet separates "Wi-Fi/backhaul problem" from "ISP problem".
- On iOS, the only viable measurements are active ones: ping/HTTP latency, throughput, and BSSID via `fetchCurrent()` with entitlements. A custom tool should treat iPhones as active-test-only probes.
- On Linux, logging the BSSID a client is associated with lets a tool identify which eero node serves each room, since each node and band has its own BSSID. This is useful because eero does not expose per-node client maps through any public API.

### Gaps
- No primary Apple documentation for `wdutil` fields was fetched. Redaction behavior in macOS 15/26 is unverified beyond community reports.
- Whether Android `WifiInfo` (RSSI, link speed, Tx/Rx link speed, frequency) needs scan permissions was not verified this session. Reading the current connection's `WifiInfo` is generally not scan-throttled, but no source was retrieved for that.
- The units of `ulRxRate` (Kbps) were not confirmed from the fetched snippet.

## Site survey / heatmap tools: how they work, and could a custom tool replicate them?

### Takeaway
Open-source heatmappers all use the same "active walk survey" pattern: load a floor plan image, click your position, record Wi-Fi stats (and optionally iperf3 throughput to a LAN server) at that point, then interpolate into heatmaps. This is easy to replicate. The hard part is reliably reading Wi-Fi metrics on each platform, not the interpolation.

### Cited Findings
- **jantman/python-wifi-survey-heatmap**
  - **Platform:** Linux only (uses libnl3). The README points macOS/Windows users to hnykda/wifi-heatmapper.
  - **Survey workflow:** wxPython GUI. Left-click a floor-plan PNG to measure, right-click to delete, drag to move. Results go to `Title.json`, and a survey can be resumed.
  - **Per-point data:** Wi-Fi bandwidth, bitrate and signal. Optionally 10 s iperf3 TCP up/down plus UDP (with `--server`), and an AP scan (`--scan`) for channel charts.
  - **Heatmaps produced:** Signal quality, RSSI, TX power, TCP/UDP throughput, jitter, frequency (to check band steering) and channel bitrate, plus 2.4/5 GHz channel bar charts.
  - **Status:** Docker is recommended (`--net=host --privileged`). The README badge says "Inactive" (stable, not actively developed). Tested with Python 3.7.
  - **Origin:** Heatmap code is "roughly based on" Beau Gunderson's wifi-heatmap.
  - Source: [GitHub jantman/python-wifi-survey-heatmap](https://github.com/jantman/python-wifi-survey-heatmap)
- **hnykda/wifi-heatmapper**
  - **Platforms and data sources:** Windows, macOS and Linux. Parses `wdutil`/`ioreg` (macOS), `netsh` (Windows) and `iw` (Linux).
  - **Throughput:** Optional iperf3 against a second machine (e.g., a Raspberry Pi running `iperf3 -s`). No throughput test runs when the server is "localhost".
  - **Stack:** Next.js, plus a Tauri desktop packaging, a native macOS helper, a WebGL heatmap renderer and an optional MCP server for AI agents.
  - **Modes:** "Signal only" (about 2 s per spot) and "signal + speed".
  - **Status:** MIT license, about 277 stars, 2026 copyright, apps not code-signed. Docker works on Linux hosts only.
  - Source: [GitHub hnykda/wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper)
- **whm (wifi-heat-mapper)** is a separate Python package on PyPI that also uses iperf3. It lists Linux x86_64 as the supported platform — [PyPI whm](https://pypi.org/project/whm/)
- **WiFi Explorer Pro 3** (Intuitibits, macOS) documents how to use an external spectrum analyzer alongside its Wi-Fi scanning — [Intuitibits docs](https://docs.intuitibits.com/wifiexplorerpro3/use-a-spectrum-analyzer.md)

### Inferences
- **Passive vs active surveys:**
  - A passive survey scans beacons and records the RSSI of every BSSID at each point. On a mesh this shows coverage from every eero node and the neighbors' networks.
  - An active survey associates and measures real throughput and latency. On eero, the active survey answers "does it work here", and the passive survey explains "why" (which node, which band, how much co-channel competition).
- **Building a custom tool:**
  - (a) Floor-plan canvas with click-to-place points.
  - (b) A platform adapter layer: nl80211 on Linux, CoreWLAN through a small native helper on macOS, the Native Wifi API (not `netsh` parsing) on Windows, `WifiInfo`/scan results on Android, active tests only on iOS.
  - (c) An iperf3 server on a wired host.
  - (d) Interpolation: IDW is simple; Gaussian process/kriging also gives uncertainty.
  - (e) A per-point record holding BSSID, band, channel, RSSI, noise, PHY rate, retries, latency/jitter/loss and throughput.
- Both open-source tools store survey points as JSON. Reusing that format (or importing jantman's `Title.json`) would let a custom tool use existing surveys.

### Gaps
- Commercial tool details (NetSpot, Ekahau, inSSIDer, Acrylic, WiFi Analyzer) were not researched this session for current 2026 pricing or features. No sources were retrieved.
- Current maintenance status of Kismet, wavemon, LinSSID and Sparrow-wifi was not verified this session.
- The interpolation algorithm in wifi-heatmapper (it uses a user-adjustable "radius until dots merge", which suggests a radial-basis/IDW-like blend) was not confirmed from source.

## Fixed sensor / probe approach (Raspberry Pi / ESP32 + Prometheus/Grafana)

### Takeaway
A Raspberry Pi or a WLAN Pi left in each problem room can run iperf3, ping and `iw` collection on a schedule and export results to Prometheus or InfluxDB. This catches intermittent problems, such as evening congestion or roaming flaps, that a one-time walk survey misses. ESP32s are cheap passive sensors for frame counts and RSSI, but not for throughput or true airtime.

### Cited Findings
- **WLAN Pi**
  - **Profiler:** wlanpi-profiler is a client capability analyzer. It broadcasts a fake AP (default SSID "WLAN Pi") and parses clients' association requests to show which features they support (e.g., 802.11k/v/r, spatial streams, bands). This directly shows the capability limits of a client device. Packages were still published in 2025 (1.0.18 for Debian bookworm arm64; 1.0.19-1 dev) — [GitHub WLAN-Pi/wlanpi-profiler](https://github.com/WLAN-Pi/wlanpi-profiler); [packagecloud 1.0.18](https://packagecloud.io/wlanpi/main/packages/debian/bookworm/wlanpi-profiler_1.0.18_arm64.deb)
  - **WLAN Pi 2.0:** Moved to Armbian, can run on a Raspberry Pi, and trimmed the toolset to a core set, including the updated Profiler — [Hackster](https://hackster.io/news/wlan-pi-2-0-now-built-on-armbian-turns-your-raspberry-pi-into-a-network-performance-analyzer-5311ba0c1aeb)
  - **WLAN Pi Go:** Launched July 30, 2025 with an Intel BE200 Wi-Fi 7 chipset (6 GHz capable) running the open-source WLAN Pi OS — [finanzen.net press release](https://www.finanzen.net/nachricht/aktien/wlan-pi-go-brings-wi-fi-7-analysis-to-mobile-by-wi-fi-professionals-for-wi-fi-professionals-14671698); [Oscium WLAN Pi Go user guide](https://oscium.com/wp-content/uploads/2025/06/wlanpi-go-userguide-v1.1-20250526.pdf)
- **ESP32 promiscuous mode**
  - EtherFog hops channels 1-14, counts frames and records per-frame RSSI extremes with moving-average smoothing — [GitHub invpe/ETHERFOG](https://github.com/invpe/ETHERFOG)
  - esp32_promiscuis_mode logs each packet's channel, RSSI and sender MAC over serial — [GitHub mqttiotstuff/esp32_promiscuis_mode](https://github.com/mqttiotstuff/esp32_promiscuis_mode)
  - Minimal pattern: set promiscuous mode with an RX callback and read RSSI from the packet's rx_ctrl — [Gist](https://gist.github.com/prateekrajgautam/1b5b84b7ad6636992f635e3a5f92c66e)
  - None of the ESP32 projects found ships a Prometheus endpoint or computes real airtime utilization — [GitHub invpe/ETHERFOG](https://github.com/invpe/ETHERFOG); [GitHub mqttiotstuff/esp32_promiscuis_mode](https://github.com/mqttiotstuff/esp32_promiscuis_mode)
- In iperf3-based tools, the iperf3 server should be a second machine wired to the router (e.g., a desktop or Pi) — [hnykda/wifi-heatmapper](https://github.com/hnykda/wifi-heatmapper)

### Inferences
- **Suggested probe design:**
  - **Hardware:** A Pi 4/5 (or one with a USB adapter using a well-supported mt76/mt7921 chipset) in each problem room.
  - **Collection, every 1-5 min:** `iw station dump` (RSSI, Tx/Rx bitrate, retries, BSSID), `iw survey dump` (busy %), ping to the gateway and to 1.1.1.1 (loss/jitter), plus a short iperf3 run every 15-30 min to a wired server.
  - **Export:** A small Prometheus exporter (`/metrics`) or a push to InfluxDB, with Grafana on top.
  - **What it reveals:** Comparing probes across rooms and across time of day separates interference/congestion (evening spikes, busy % up) from coverage (consistently low RSSI) and from backhaul (good client RSSI but low throughput on every client of one node).
- **ESP32 limits:** The 2.4 GHz-only ESP32s (most variants) cannot sense 5/6 GHz. They suit 2.4 GHz IoT-band congestion monitoring only.

### Gaps
- No source was fetched for Prometheus blackbox_exporter, smokeping, or speedtest exporters. They are well known but were not verified this session (maintenance status, current versions).
- I found no existing project that combines Pi Wi-Fi probes with eero-specific node mapping.

## Common root causes in eero mesh homes, and how to tell them apart from data

### Takeaway
The main levers on eero are placement (20-30 ft apart, no more than 50 ft, in the open, halfway between the gateway and the dead zone, not inside it) and wired backhaul. Roaming and band selection are ultimately client decisions, and eero's steering features only nudge clients. Data can separate the causes:
- Low RSSI → coverage/placement.
- Good RSSI with low PHY rate or high retries → interference.
- Good client link but slow everywhere on one node → backhaul.
- Stuck on a distant BSSID while a nearer one is stronger → sticky client.

### Cited Findings
- eero placement guidance:
  - Place eeros 20-30 ft apart (no more than 50 ft) in central locations, on a flat surface, not enclosed in cabinets or media consoles.
  - Don't put an eero directly in a dead zone. Place it halfway between the gateway eero and the dead zone.
  - Placement may need experimentation.
  - Source: [eero support: Where should I place my eeros?](https://support.eero.com/hc/articles/207897393) (via search snippet); [eero.com mirror](https://eero.com/support/articles/where-should-i-place-my-eeros)
- An older eero community-manager reply said units should be within 40 ft of each other — [eero community](https://community.eero.com/t/y7tndl/question-about-placement)
- Moving the modem and gateway eero to a more central spot can speed up the whole network — [eero support (snippet)](https://support.eero.com/hc/articles/207897393)
- Rogers (an ISP reseller) suggests one eero per about 1,000 sq ft as a general rule — [Rogers](https://www.rogers.com/support/internet/tips-for-placing-your-eero)
- Wired backhaul behavior (community reports):
  - Setup and placement tests may ignore the wired link. A workaround is to add the node close to the gateway, then move it — [eero community](https://community.eero.com/t/x2h84cp/eero-ignores-wired-backhaul-during-setupplacement-test)
  - Switching to wired can take a few minutes, and the app may show the status inconsistently — [eero community](https://community.eero.com/t/m2z9d3/multiple-eeros-with-wired-connections-to-the-internet)
- MoCA belongs on the LAN side after the gateway eero, and you should check that the remote node reports a wired connection in the app (lower-confidence third-party guide) — [no-dead-zones MoCA guide](https://no-dead-zones.pages.dev/backhaul/moca-with-eero-mesh/)
- Roaming:
  - Forum posts say eero has supported 802.11r since June 2017 and 802.11k/v since October 2021. These claims are not verified against eero release notes — [HardwareZone forum](https://forums.hardwarezone.com.sg/threads/amazon-eero-wireless-devices-master-thread.7181373/post-159439170)
  - 802.11v is advisory, so clients can ignore steering, and the client makes the final roaming decision — [Access Agility](https://support.accessagility.com/hc/802.11k-802.11r-and-802.11v); [Zyxel community](https://community.zyxel.com/en/discussion/20011/understanding-roaming-and-802-11-k-v-r)
  - Not all Windows 10 devices support 802.11k/v/r — [Microsoft: Fast Roaming](https://msdn.microsoft.com/en-us/library/windows/hardware/mt484190)
- Spectrum analysis can find non-Wi-Fi 2.4 GHz interferers (microwaves, baby monitors, Bluetooth), which Wi-Fi chipset scans cannot see — [Georgia Libraries RF Explorer kit](https://galibtech.georgialibraries.org/emerging/tech-loaner-kits/tlk-options/wifi-expansion-kit/rf-explorer); [Social WiFi KB](https://socialwifi.com/knowledge-base/network-monitoring/troubleshooting-wifi-connection-problems-radio-spectrum-analyzers/)
- jantman's heatmapper includes a "frequency" heatmap specifically to check band steering, i.e., whether clients land on 2.4 vs 5 GHz in each area — [jantman/python-wifi-survey-heatmap](https://github.com/jantman/python-wifi-survey-heatmap)

### Inferences
- **Diagnostic decision table** (built from metric definitions above; not from a single source):
  - **Coverage/placement:** RSSI below about -70 dBm, low PHY rate, throughput scales with RSSI.
  - **Interference/congestion:** RSSI -50 to -65 dBm, but high retries, high channel busy %, many neighbor BSSIDs on the same channel, worse at peak hours.
  - **Non-Wi-Fi interference:** retries and noise spike briefly (e.g., the microwave is on), busy % rises without matching Wi-Fi frames. Confirm with a spectrum analyzer.
  - **Weak backhaul:** a client next to a satellite node has strong RSSI and a high PHY rate, but iperf3 to the wired server is far below the PHY rate, and nodes on a wired backhaul do not show this.
  - **Sticky client:** the BSSID stays on a far node while a passive scan at the same spot shows a nearer eero BSSID that is 10+ dB stronger.
  - **Client limits:** wlanpi-profiler shows few spatial streams, no 5/6 GHz, or no k/v/r support.
  - **2.4 GHz fallback:** the frequency heatmap shows 2.4 GHz in an area, with lower PHY rates.
- Each eero node advertises distinct BSSIDs. Grouping BSSIDs that share an OUI or MAC prefix (or that differ only in the last byte) lets a tool label "which eero" served each sample. This is an inference, so verify on real hardware.

### Gaps
- I could not fetch eero's official pages on wired backhaul, the per-device "connection quality" indicator, or the "How many eeros do I need?" article (support.eero.com is blocked in this session). Details of how eero computes its signal/connection-quality indicator remain unverified.
- No sources were retrieved on DFS-channel behavior in eero, or on wall-material attenuation figures.

## eero-specific: what can and can't be tuned

### Takeaway
eero exposes few radio controls. Channels and power are automatic. The user-facing levers are Client Steering (on by default, nudges to 5/6 GHz), Compatibility Mode (which hides Client Steering and WPA3), placement, and wired backhaul. I found no documented way to turn off 6 GHz alone.

### Cited Findings
- Client Steering is at eero app → Settings → Advanced networking → Client steering. On Pro 6E, Pro 7, Max 7 and PoE 7 it nudges compatible devices to 6 GHz, and it is enabled by default — [eero support: advanced features](https://support.eero.com/hc/en-us/articles/207613326) (via search snippet)
- Client Steering "does not guarantee that a device will choose the 5 GHz or 6 GHz bands nor the closest eero to you" — [eero support: advanced features](https://support.eero.com/hc/en-us/articles/207613326) (via search snippet)
- With Compatibility Mode on, Client Steering and WPA3 no longer appear in the app — [eero support: advanced features](https://support.eero.com/hc/en-us/articles/207613326) (via search snippet)
- eero networks with a 6 GHz-capable eero always have WPA3 enabled on 6 GHz — [eero support: advanced features](https://support.eero.com/hc/en-us/articles/207613326) (via search snippet)
- Community: band choice is ultimately up to the phone — [eero labs feedback thread](https://community.eero.com/t/x1jl6t/eero-labs-features-and-feedback-thread?pg=14)
- Community request threads for optional 802.11r/k suggest these are not user-toggleable — [eero community: seamless roaming](https://community.eero.com/t/k9mp5v)

### Inferences
- Because radio settings are not tunable, a custom tool should aim to produce placement and backhaul recommendations (move node X toward room Y, wire node Z) and per-client fixes (forget and rejoin, disable private MAC rotation, replace the client's adapter). It should not try to recommend channel changes.

### Gaps
- eero has no public/official local API for per-node or per-client stats. Unofficial reverse-engineered eero cloud API clients exist, but they were not researched in this note and are covered by other researchers.
- Whether eero Labs features (e.g., "Optimize for Conferencing and Gaming") affect roaming was not verified.

## Spectrum analysis options for hobbyists

### Takeaway
Wi-Fi chipsets only "see" decodable 802.11 frames. To find microwaves, Bluetooth, baby monitors or analog video senders, you need a spectrum analyzer: MetaGeek Wi-Spy (2.4 GHz; DBx adds 5 GHz), RF Explorer (handheld, about 15-2,700 MHz), or possibly a tinySA (unverified for Wi-Fi). Monitor-mode adapters with Kismet/Wireshark and ESP32 promiscuous mode capture frames, not raw RF. Passive receive-only monitoring is not transmission. I found no source on its legality, but the common understanding is that it is lawful, and the limits are around capturing or decrypting others' traffic.

### Cited Findings
- **Wi-Spy:** The Wi-Spy 2.4x covers 2.400-2.495 GHz and shows RF activity from any 2.4 GHz device, not just Wi-Fi. The DBx model adds 5 GHz. Older reviews priced it around $99 — [MetaGeek Wi-Spy datasheet](https://data.kommago.nl/files/pdf/80834_MetaGeek-Wi-Spy-Datasheet.pdf); [Hackster: find RF interference with Wi-Spy](https://hackster.io/patrick-fitzgerald2/find-rf-interference-with-wi-spy-ee7678)
- **RF Explorer:** Covers about 15-2,700 MHz, including 2.4 GHz ISM (Bluetooth, Wi-Fi, ZigBee). Connected to a PC, it can log scans over time, show waterfall spectrograms and record interference events (no 5 GHz in that model) — [Yahoo Tech review](https://www.yahoo.com/tech/s/rf-explorer-good-inexpensive-rf-140003452.html); [Georgia Libraries kit](https://galibtech.georgialibraries.org/emerging/tech-loaner-kits/tlk-options/wifi-expansion-kit/rf-explorer)
- **tinySA:** The only claims about the tinySA Ultra Plus detecting 2.4/5 GHz Wi-Fi interference came from a marketing-style AliExpress page. Treat them as unverified — [AliExpress wiki](https://www.aliexpress.com/s/wiki-ssr/article/tiny-as)
- **Atheros spectral scan:** Some Atheros (ath9k/ath10k) chipsets expose spectral scan data alongside survey dump. This was discussed on the ath10k list — [ath10k mailing list: survey dump and spectral scan](https://lists.infradead.org/pipermail/ath10k/2015-June/005469.html)

### Inferences
- **Cheapest hobbyist path:** An ath9k/ath10k adapter with spectral scan (if obtainable), or an RF Explorer for 2.4 GHz. For 5/6 GHz, rely on Wi-Fi-level metrics (survey busy time, retries) rather than true spectrum analysis, since consumer 5/6 GHz analyzers are expensive.
- **Practicality:** Most home "interference" on 5/6 GHz is co-channel Wi-Fi from neighbors, which a normal scan already shows. Spectrum analyzers mainly pay off for 2.4 GHz mysteries.

### Gaps
- I found no authoritative source on the legality of passive monitoring or packet capture (e.g., the US Wiretap Act's application to Wi-Fi capture). This needs a dedicated legal source.
- Kismet/Wireshark monitor-mode adapter recommendations for 2026 (mt7921au/mt7612u, 6 GHz monitor support) were not verified.

## Academic / practitioner work on coverage estimation and ML diagnosis

### Takeaway
"Radio map estimation" (spectrum cartography) is the academic name for turning sparse, location-tagged RSS readings into a full coverage map. Methods range from kriging and Gaussian processes (which give uncertainty estimates) to deep-learning completion and 3D Gaussian splatting. For a hobby tool, IDW or GP/kriging over walk-survey points is enough. The literature also points to two useful features: uncertainty maps (to show where to measure next) and correction for location error.

### Cited Findings
- Radio map estimation tutorial/survey: covers estimating RSS and channel attenuation at every point from a set of measurements, comparing kriging and other interpolation with data-driven/deep-learning approaches — [Romero & Kim, "Radio Map Estimation: A Data-Driven Approach to Spectrum Cartography" (arXiv 2202.03269)](https://www.alphaxiv.org/abs/2202.03269)
- Theoretical analysis of radio map estimation: how accuracy depends on measurement density and the environment — [arXiv 2310.15106](https://www.alphaxiv.org/abs/2310.15106)
- Adaptive sampling: Matérn GMRF/INLA posterior updates guide where to measure next. Prior width governs accuracy and calibration (UAV/IoT setting, Oct 2026) — [arXiv 2610.40723](https://www.alphaxiv.org/abs/2610.40723)
- Location error: radio map construction with post-hoc calibration of position errors in crowdsourced RSS measurements (Sep 2026) — [arXiv 2609.11142](https://www.alphaxiv.org/abs/2609.11142)
- An indoor dataset combining 3D point clouds and RSSI for radio mapping (Nov 2025) — [arXiv 2511.00494](https://www.alphaxiv.org/abs/2511.00494)
- RadCloudSplat: 3D Gaussian splatting with point-cloud priors for radiomap extrapolation — [arXiv 2502.12686](https://www.alphaxiv.org/abs/2502.12686)
- RADIANCE: GAN-based RF coverage map estimation from limited measurements — [arXiv 2308.10584](https://www.alphaxiv.org/abs/2308.10584)
- Temporal and spatial variability of indoor 2.4 GHz Wi-Fi levels: indoor RSS varies over time, not just space — [arXiv 2402.05083](https://www.alphaxiv.org/abs/2402.05083)
- "Rethinking RSSI for WiFi Sensing" (2026): RSSI on commodity devices carries more information than commonly assumed — [arXiv 2602.14004](https://www.alphaxiv.org/abs/2602.14004)

### Inferences
- **Recommended interpolation stack for a hobby tool:**
  - (1) IDW for an instant preview.
  - (2) Gaussian-process regression (e.g., scikit-learn GPR with a Matérn kernel, which is effectively kriging) to produce both a mean RSSI map and a standard-deviation map. The standard-deviation map tells the user where to take the next measurement (adaptive sampling, per arXiv 2610.40723).
  - (3) Optionally, a log-distance path-loss model per eero node, with walls as attenuation segments drawn on the floor plan. This physics-based prior can extrapolate into unmeasured rooms.
- Because indoor RSS varies over time (arXiv 2402.05083), a survey should take several samples per point (median, plus a spread) and record a timestamp. Fixed probes add the time dimension.
- Interpolate RSSI separately for each eero BSSID or band, not just for "the connected network". This shows where each node's cell ends, which is the key input for deciding where to move or add a node.

### Gaps
- I found no paper specifically on ML-based root-cause classification of home Wi-Fi problems (e.g., classifying "interference vs coverage vs backhaul" from client telemetry). A targeted search may surface work from enterprise WLAN vendors (Mist/Juniper "Marvis", 7signal) but none was retrieved.
- Practitioner blogs (Keith Parsons/WLAN Pros, 7signal, Ekahau) were not fetched this session, so no practitioner RSSI/SNR threshold tables (e.g., the commonly cited -67 dBm for VoIP) are cited here.
