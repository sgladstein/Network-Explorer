# Network discovery, inventory, and traffic/performance monitoring on an eero mesh home network (2026)

> Method note: Searches and fetches ran on 2026-11-05. **eero.com and support.eero.com could not be fetched from this session** (DNS blocked by the sandbox). eero facts below come from search-result snippets of eero's own support pages, not full-page reads. Citations marked **(ref, not re-fetched)** point to canonical project docs/repos for long-stable facts (protocol behavior, library APIs) that came from prior knowledge and were not re-checked this session. The report writer should treat those as reliable background, but they are not freshly verified.

## 1. Device discovery techniques and existing inventory tools (and their maintenance status)

### Takeaway
No single technique finds every device. A good home inventory combines active ARP sweeps (the most reliable on IPv4), passive listening (mDNS, SSDP, NetBIOS/LLMNR, DHCP), and nmap for OS/service enrichment. On eero, the eero cloud API's device list is the authoritative source of DHCP-lease and node data. NetAlertX (very active, monthly "vYY.M.D" releases through 2026) and WatchYourLAN (active, Go, lighter) are the leading open-source inventory tools. Fing Agent is commercial and needs a subscription. MAC randomization is the biggest data-quality problem.

### Cited Findings
**Active techniques**
- ARP scanning: `arp-scan` sends ARP requests to every address on the local subnet. Devices must answer ARP to talk on IPv4, so it finds hosts that drop ICMP and all TCP/UDP probes. It only works on the local L2 segment and needs raw-socket privileges — [arp-scan (royhills) GitHub](https://github.com/royhills/arp-scan) **(ref, not re-fetched)**
- nmap host discovery (`-sn`) uses ARP automatically on a local Ethernet LAN. Add `-O` for OS detection, `-sV` for service/version detection, and NSE scripts such as `broadcast-dns-service-discovery`, `broadcast-upnp-info`, `nbstat` — [Nmap host discovery docs](https://nmap.org/book/man-host-discovery.html) **(ref, not re-fetched)**
- scapy can craft ARP (`srp(Ether(dst="ff:ff:ff:ff:ff:ff")/ARP(pdst="192.168.4.0/22"))`), ICMPv6 and other probes from Python, and needs root/CAP_NET_RAW — [Scapy docs](https://scapy.readthedocs.io/) **(ref, not re-fetched)**

**Passive or semi-passive techniques**
- mDNS/DNS-SD (Bonjour, UDP 5353, 224.0.0.251 / ff02::fb): Apple devices, Chromecasts, printers, HomeKit/Matter and other IoT devices advertise hostnames and service types (`_airplay._tcp`, `_googlecast._tcp`, `_hap._tcp`, `_ipp._tcp`). The Python library is `python-zeroconf` — [python-zeroconf GitHub](https://github.com/python-zeroconf/python-zeroconf) **(ref, not re-fetched)**
- SSDP/UPnP (UDP 1900, 239.255.255.250): `M-SEARCH` replies give a `LOCATION` URL to a device-description XML with manufacturer, model and friendlyName. This works well for smart TVs, Sonos, game consoles and media servers — [UPnP Device Architecture (Open Connectivity Foundation)](https://openconnectivity.org/developer/specifications/upnp-resources/upnp/) **(ref, not re-fetched)**
- NetBIOS name service (UDP 137) and LLMNR (UDP 5355) give Windows hostnames. `nmap --script nbstat` or `nbtscan` query them — [Nmap nbstat NSE](https://nmap.org/nsedoc/scripts/nbstat.html) **(ref, not re-fetched)**
- DHCP fingerprinting: Option 55 (parameter request list), Option 60 (vendor class) and Option 12 (hostname) identify the OS and device type. The Fingerbank DB/API (Inverse/PacketFence) maps these fingerprints to devices. This only works if you can see DHCP traffic, i.e. you run DHCP yourself or sit on the broadcast domain — [Fingerbank](https://www.fingerbank.org/) **(ref, not re-fetched)**
- MAC OUI vendor lookup uses the IEEE registry. Python options are `mac-vendor-lookup`, `manuf` (Wireshark's manuf file) and `netaddr`'s `EUI(...).oui.registration()` — [IEEE OUI registry](https://standards-oui.ieee.org/) **(ref, not re-fetched)**. A randomized MAC has the "locally administered" bit (second-least-significant bit of the first octet) set, so its second hex digit is 2, 6, A or E. That bit is a reliable flag for "OUI lookup will fail" — [IEEE 802 / RFC 7042 §2.1](https://www.rfc-editor.org/rfc/rfc7042) **(ref, not re-fetched)**

**Randomized/private MAC addresses**
- iOS 18 / macOS 15 added a "Rotate Wi-Fi Address" option per network, which MacRumors reports is opt-in and replaces the Private Wi-Fi Address toggle — [MacRumors via search](https://www.macrumors.com/505/). A vendor blog says iOS 18 rotates the address about every 14 days on open or weak-security networks — [purple.ai](https://www.purple.ai/en-us/blogs/randomizzazione-dei-mac-101). Sources conflict on the details, so check against Apple's own documentation.
- Android 10–15 uses a unique randomized MAC per SSID by default. Android 12+ may rotate it in some cases, e.g. reconnecting after more than 24 h — [purple.ai](https://www.purple.ai/en-us/blogs/randomizzazione-dei-mac-101); [Ubiety/HomeAware help](https://ubiety.notion.site/What-is-Private-Address-or-Randomized-MAC-Address-1f3a385f423381bb9e76e4ce2e2cf063)
- Inventory impact: when MACs rotate, inventory tools show duplicate "new" devices, presence tracking breaks, and duplicates pile up. The vendor guidance is to turn off rotation per network for devices you want tracked — [Ubiety/HomeAware help](https://ubiety.notion.site/What-is-Private-Address-or-Randomized-MAC-Address-1f3a385f423381bb9e76e4ce2e2cf063); [Wifinity](https://wifinity.co.uk/support/generic/whats-happening-with-ios-18)

**Off-the-shelf inventory tools: status**
- **NetAlertX** (formerly Pi.Alert; repo moved from jokob-sk to the `netalertx` org). GPL-3.0, about 7.4k stars and 468 forks. Discovery plugins include arp-scan, Pi-hole DB and DHCP-lease import, generic DHCP-lease import, UniFi controller import and SNMP router import. Integrations: Home Assistant, webhooks, an API, Prometheus metrics, and Apprise (80+ notification services) plus ntfy/Pushover. The Docker image `ghcr.io/netalertx/netalertx` runs with `--network=host` and `NET_RAW`/`NET_ADMIN`/`NET_BIND_SERVICE` capabilities. It also ships as a Home Assistant add-on — [NetAlertX GitHub](https://github.com/netalertx/NetAlertX)
- NetAlertX 2026 cadence:
  - v26.1.17 added AdGuard Home import — [newreleases.io](https://newreleases.io/project/github/netalertx/NetAlertX/release/v26.1.17)
  - v26.7.1 deprecated the old API endpoints, to be removed in the next release — [newreleases.io v26.7.1](https://newreleases.io/project/github/netalertx/NetAlertX/release/v26.7.1)
  - The last release was reported as 2026-08-04 — [ideaproof](https://ideaproof.io/open-source/project/netalertx)
  - A blog reports v26.9.0 (2026-09-02) with a built-in MCP server bridge — [sumguy.com](https://sumguy.com/netalertx-mcp-presence-agent/). This is a single source and was not confirmed.
  - Community catalogs froze a "legacy" build at 25.11.29 because v26 broke compatibility — [BigBear community](https://community.bigbeartechworld.com/t/netalertx-legacy-v26-split-in-bigbearuniversal-apps/5246)
- **WatchYourLAN** (aceberg): Go, MIT, about 7.1k stars. It is an arp-scan-based IP scanner with a web GUI (port 8840) that tracks new hosts and online/offline history and sends notifications via Shoutrrr (Discord, email, Gotify, ntfy). It has no built-in auth (use Authelia or ForAuth), default history retention `TRIM_HIST`=48 h, and an API in docs/API.md. The latest release seen was 2.1.4 (2025-09-10, per a third-party listing) — [WatchYourLAN GitHub](https://github.com/aceberg/WatchYourLAN); [ecosyste.ms](https://awesome.ecosyste.ms/projects/github.com%2Faceberg%2FWatchYourLAN)
- **Fing / Fing Agent**: Fing Agent is an always-on monitor that installs as a snap on Raspberry Pi and needs a paid Fing subscription (Starter or Premium) — [Fing help: install Fing Agent on RPi](https://help.fing.com/hc/en-us/articles/14429872073244). In September 2025 Fing launched a Raspberry Pi 4 (2 GB) Fing Agent kit, about $108 at Pimoroni, as the successor to the 2017 Fingbox — [CNX Software](https://www.cnx-software.com/2025/09/27/fing-agent-raspberry-pi-kit-an-all-in-one-raspberry-pi-4-based-network-monitoring-solution/); [Pimoroni](https://shop.pimoroni.com/products/fing-agent-rpi). The Fingbox hardware was reported discontinued, with no further firmware, by community moderators in 2023 — [r/Fing_App mirror](https://redlib.hbubli.cc/r/Fing_App/comments/14506jt/is_fingbox_alive). Fing is closed-source, and Fing's device-recognition DB is its main draw.
- **Zeek known-hosts / known-services / software logs** build an inventory passively from traffic, but need a SPAN/tap feed (see §3) — [Zeek docs: known_hosts](https://docs.zeek.org/en/master/scripts/policy/protocols/conn/known-hosts.zeek.html) **(ref, not re-fetched)**
- **ntopng** builds a host inventory with nDPI application classification from mirrored traffic or flows (see §4).

### Inferences
- On eero, ARP scanning from a wired box can see all wired and wireless clients on the same /22 (eero's default LAN is usually 192.168.4.0/22, from prior knowledge, unverified). That is because eero bridges Wi-Fi clients onto one L2 broadcast domain. This does not apply to the guest network, which is isolated.
- Use a stable device key (eero device ID or hostname plus mDNS name plus DHCP fingerprint) rather than the MAC alone, to cope with randomization. Flag locally-administered MACs explicitly in the UI.
- NetAlertX has no native eero importer (none appears in the plugin list on the README). A custom plugin that calls the unofficial eero API is a clear opportunity for a hobbyist tool.

### Gaps
- Could not confirm NetAlertX's full plugin list (nmap, mDNS, NSLOOKUP, ICMP, etc.). The README fetch only listed the headline plugins, so check docs/PLUGINS.md.
- No primary Apple or Google documentation was fetched for exact MAC-rotation schedules. Windows "Random hardware addresses" behavior was not researched.
- Did not verify the maintenance status of nbtscan, arp-scan, Fingerbank API pricing, or "LANDrop-like" tools. LANDrop is a file-sharing app, not an inventory tool.

## 2. Monitoring stacks (Prometheus/Grafana, InfluxDB/Telegraf, Uptime Kuma, Smokeping, LibreNMS/Zabbix, Home Assistant)

### Takeaway
Because eero exposes no SNMP or local API, monitoring has to be either probe-based from a LAN host (blackbox_exporter, Smokeping, Uptime Kuma, speedtest exporters) or cloud-API-based (eero data via the unofficial API or Home Assistant). SNMP-centric NMS tools (LibreNMS, Zabbix SNMP templates) can only monitor your own hosts and switches, not the eero nodes.

### Cited Findings
- **Uptime Kuma 2.0.0** went stable around 20 Oct 2025. Changes: MariaDB support alongside SQLite, rootless Docker, a UI refresh, and breaking changes to badges, backups, retry defaults and email templates (back up before upgrading). One report flags an ARMv7/Raspbian Buster libseccomp2 startup issue — [Linuxiac](https://linuxiac.com/uptime-kuma-2-0-arrives-with-mariadb-support-modern-ui-refresh/); [AlternativeTo](https://alternativeto.net/news/2025/10/uptime-kuma-2-0-introduces-mariadb-support-rootless-docker-modern-ui-and-upgrade-tools); [heise](https://www.heise.de/en/news/Uptime-Kuma-2-0-Monitoring-tool-now-with-MariaDB-support-10793657.html?view=print)
- Prometheus `blackbox_exporter` probes ICMP, TCP, HTTP(S) and DNS endpoints and exposes `probe_success` and `probe_duration_seconds`. ICMP needs CAP_NET_RAW or unprivileged ping sockets (`net.ipv4.ping_group_range`) — [blackbox_exporter GitHub](https://github.com/prometheus/blackbox_exporter) **(ref, not re-fetched)**
- `node_exporter` covers host metrics (including NIC counters) on Linux boxes you own — [node_exporter GitHub](https://github.com/prometheus/node_exporter) **(ref, not re-fetched)**
- Smokeping (Tobi Oetiker) graphs latency and packet-loss distributions over time with fping/RRD. It is good for spotting ISP or Wi-Fi backhaul jitter — [SmokePing site](https://oss.oetiker.ch/smokeping/) **(ref, not re-fetched)**
- Telegraf has `ping`, `dns_query`, `net_response`, `http_response` and `internet_speed` input plugins that write to InfluxDB or Prometheus — [Telegraf plugins](https://docs.influxdata.com/telegraf/v1/plugins/) **(ref, not re-fetched)**
- NetAlertX exports Prometheus metrics and integrates with Home Assistant, so it can feed the same Grafana or HA dashboards — [NetAlertX GitHub](https://github.com/netalertx/NetAlertX)
- Home Assistant as a hub: the custom HACS integration `schmittx/home-assistant-eero` exposes eero networks, eero nodes, profiles and devices. Device entities carry a "Connected to" attribute naming the eero node a client uses, and device_trackers are created for clients chosen at setup — [HA community thread](https://community.home-assistant.io/t/new-custom-component-eero-integration/244583); [issue mirror](https://issues.ecosyste.ms/hosts/GitHub/repositories/schmittx%2Fhome-assistant-eero/issues). The issue tracker shows HA-version breakages (e.g. #48 after HA 2023.5) and a recent deprecation-warning issue (#97), so it is community-maintained and needs periodic fixes.
- Why no SNMP/LibreNMS on eero: eero's advanced-feature list includes DNS, DHCP/NAT, reservations, port forwarding, UPnP, IPv6 and so on. SNMP is not in it (from eero support search snippets; full page unreadable) — [What advanced features does eero support?](https://support.eero.com/hc/en-us/articles/207613326). NetAlertX's "SNMP-enabled router import" therefore only helps if you run your own router in front of eero — [NetAlertX GitHub](https://github.com/netalertx/NetAlertX)

### Inferences
- A practical eero-friendly stack is a Pi or mini-PC running Prometheus, blackbox_exporter (ICMP to each eero node IP, the gateway, 1.1.1.1, ISP hop; DNS probes against Pi-hole), a speedtest exporter on a cron-like interval, Grafana, and Uptime Kuma for alerting. Pinging each eero node's LAN IP from a wired host gives rough per-node backhaul health.
- eero's own speed test, per-device usage and node data are only reachable through the cloud (app or unofficial API), so a custom exporter that polls the eero API on a slow interval is the way to get per-node and per-client metrics into Prometheus.

### Gaps
- Did not verify the current maintenance of specific speedtest exporters (e.g. MiguelNdeCarvalho/speedtest-exporter, danopstech/speedtest_exporter) or Ookla CLI licensing.
- No fresh source on LibreNMS/Zabbix 2026 releases. Excluded as low-relevance given there is no SNMP.
- Could not read eero's support page in full to confirm that the absence of SNMP is explicit rather than implied.

## 3. Traffic visibility options given eero has no port mirroring

### Takeaway
There are four realistic options:
1. **DNS-level visibility.** Set Pi-hole or AdGuard Home as eero's custom DNS. It is cheap, but per-client attribution needs extra steps on eero.
2. **eero in bridge mode behind your own router** (OPNsense/pfSense/Firewalla/UniFi). This gives full NetFlow, ntopng and IDS capability, but you lose eero routing features, Profiles and most of eero Plus.
3. **A managed switch with a SPAN port** between modem and eero, which only shows WAN-side, NATed traffic.
4. **An inline Linux bridge** (two-NIC box) between modem and eero, also WAN-side only.

Options 3 and 4 cannot see intra-LAN or Wi-Fi-to-Wi-Fi traffic, and all internal hosts appear behind eero's NAT address.

### Cited Findings
**Custom DNS on eero (option 1)**
- Custom IPv4 and IPv6 DNS servers can be set in the eero app (Settings > Network settings > Advanced > DNS > Custom DNS). eero Plus works by filtering DNS, so custom DNS won't behave as expected while Plus filters are on. You must disable each eero Plus Security & privacy filter. "Local DNS caching" is not available with eero Plus features active — [eero support: custom DNS](https://support.eero.com/hc/articles/360059988432-Setting-up-custom-DNS-servers-with-eero); [eero: custom DNS](https://eero.com/support/articles/how-do-i-set-up-custom-dns-servers-with-eero) (search-snippet level; page fetch blocked)
- Pi-hole client attribution on eero: users report Pi-hole sees every query coming from the eero gateway IP. The fixes reported:
  - Turn off eero "Local DNS Caching" in the app.
  - Disable eero HomeKit support, which forces DNS through the gateway. After this, client IPs appear, but hostnames still don't.
  - Use Pi-hole conditional forwarding, or run DHCP on the Pi-hole instead of eero.

  — [Pi-hole discourse: majority of traffic through one client](https://discourse.pi-hole.net/t/majority-of-traffic-through-one-client-eero-settings/12536); [Pi-hole discourse: Eero, Pi-hole, Homebridge](https://discourse.pi-hole.net/t/eero-pi-hole-homebridge-strongswan/53185)
- A practitioner write-up pulls device names and IPs from the eero API and writes them into a Pi-hole custom hosts list, relying on eero IP reservations for stability — [engineered.at: fixing niggles between eero & Pi-hole](https://engineered.at/articles/fixing-some-niggles-between-eero-pihole)
- NetAlertX can import devices from Pi-hole's DB and DHCP leases, and from AdGuard Home since v26.1.17. A Pi-hole or AdGuard DNS sidecar therefore doubles as a discovery source — [NetAlertX GitHub](https://github.com/netalertx/NetAlertX); [v26.1.17 notes](https://newreleases.io/project/github/netalertx/NetAlertX/release/v26.1.17)

**Bridge mode (option 2)**
- Bridge mode turns off eero's network services (routing, NAT, DHCP) but keeps eeros providing Wi-Fi. At least one eero must stay wired — [eero: What is bridge mode?](https://eero.com/support/articles/what-is-bridge-mode); [support.eero.com/hc/articles/208276903](https://support.eero.com/hc/articles/208276903)
- Features lost in bridge mode, per eero's support article (search snippets of two versions):
  - Older version: custom DNS, UPnP, all eero Plus features except the Malwarebytes, 1Password and Guardian VPN partner services, eligibility to subscribe to eero Plus/eero Business, and Apple HomeKit Secure Router.
  - Newer version: WAN configurations, Local DNS caching, Dynamic DNS, Multi-Link Operation (Wi-Fi 7 eeros only), IP reservations, port forwarding.

  Radio features (DFS, client steering, WPA3) are not affected. Plus subscribers keep 1Password, Guardian VPN, Malwarebytes, DDNS and Wi-Fi radio analytics — [eero: What features do I lose in bridge mode?](https://eero.com/support/articles/what-features-do-i-lose-if-i-put-my-eeros-in-bridge-mode); [support.eero.com 115000825206](https://support.eero.com/hc/en-us/articles/115000825206). The two versions disagree. A third-party (Windscribe) guide also lists Advanced Security, ad blocking, content filters, historical data usage and Hotspot Backup as disabled — [Windscribe KB](https://windscribe.com/knowledge-base/articles/how-to-use-windscribe-on-a-eero-mesh-router)
- Profiles (per-person device groups, pause and schedules) do not work in bridge mode — [eero: Do Profiles work in bridge mode?](https://support.eero.com/hc/en-us/articles/210819583-Do-Profiles-work-in-bridge-mode)
- Upstream modem/gateway combos may need to be bridged to avoid double NAT — [eero: modem/router combo bridge mode](https://eero.com/support/articles/how-do-i-put-my-modem-router-combo-in-bridge-mode)

**SPAN/tap or inline bridge (options 3 and 4)**
- A pfSense user suggests port-mirroring to a Raspberry Pi running ntopng rather than running it on a small firewall, and notes that ntopng writes heavily, so it needs an SSD — [Netgate forum](https://forum.netgate.com/post/1116941)

### Inferences
- **Bridge mode trade-off.** You keep eero's mesh Wi-Fi, but the eero app's device list keeps fewer features (no reservations, DHCP or Profiles, since DHCP moves to your router). Your router becomes the source of truth for leases and ARP tables, which makes discovery easier. OPNsense and pfSense can export NetFlow (softflowd/pflow) and run ntopng or Suricata locally. Firewalla and UniFi gateways have their own flow and IDS dashboards.
- **SPAN between modem and eero.** You see only the eero WAN IP talking to the internet: useful for total bandwidth, top destinations, DNS-over-UDP and IDS against WAN threats, but with no per-device attribution. Combining it with DNS logs (Pi-hole) gives partial attribution by query timing.
- **Intra-LAN Wi-Fi traffic.** No option gives full visibility of this traffic in router mode, because eero switches it internally. Only host-based agents (e.g. on PCs) or Wi-Fi monitor-mode sniffing (which only shows encrypted frames on WPA2/WPA3 without the keys and handshakes) would.
- **IPv6.** Clients may use eero-advertised IPv6 DNS or DoH/DoT (browsers, Android Private DNS, iCloud Private Relay), so DNS-level visibility is never complete. Set the IPv6 custom DNS fields too.

### Gaps
- Could not fetch the current full eero bridge-mode article to resolve the conflicting feature lists. The report should flag this conflict.
- No 2025–2026 source on whether eero "Wi-Fi radio analytics" or device lists still show per-node client association in bridge mode (believed yes, since radio features are kept, but unverified).
- Did not find a source quantifying how commonly r/eero users run the SPAN or inline approach.

## 4. Packet analysis tools (Zeek, Suricata, ntopng, Wireshark/tshark, Arkime) and resources on Pi 4/5 or a mini PC

### Takeaway
At home-broadband rates (up to about 1 Gbps), a Pi 5 (8 GB, NVMe/SSD) can run ntopng or Suricata with tuning. Zeek is more RAM-hungry. Arkime (full PCAP plus Elasticsearch/OpenSearch) really wants an x86 mini PC with lots of disk. Independent benchmarks are scarce, and most Pi IDS numbers are vendor marketing.

### Cited Findings
- **ntopng install.** ntopng (with nDPI) installs from ntop's apt repo for Raspberry Pi OS arm64 (`apt-get install nprobe ntopng`, repo at packages.ntop.org/RaspberryPI). The Community edition is GPLv3 and free, while some components (e.g. PF_RING ZC) need licenses — [ntop software installation](https://www.ntop.org/software-installation/). Community mode can be forced via a `--community` line in `/etc/ntopng/ntopng.conf` — [Pi-hole discourse: ntopng on RPi](https://discourse.pi-hole.net/t/monitoring-dns-on-your-raspberry-pi-with-ntopng/26997)
- **ntopng storage.** ntopng is write-heavy, so use an SSD rather than an SD card — [Netgate forum](https://forum.netgate.com/post/1116941)
- **Sending only suspicious traffic to an IDS.** ntop documents using ntopng to flag hosts and sending only those to Zeek/Suricata on demand (at 40/100G, but the principle scales down) — [ntop blog](https://www.ntop.org/?p=10475)
- **Pi 5 IDS throughput claims (vendor, unverified).** Stock Suricata on a Pi 5 handled about 300 Mbps before drops, versus about 850 Mbps for the vendor's own XDP engine. Zeek's per-connection state can exhaust Pi RAM on busy links — [HookProbe on dev.to](https://dev.to/hookprobe/suricata-vs-zeek-vs-napse-choosing-the-best-edge-ids-for-raspberry-pi-4hmm). Self-reported marketing, not independently reproduced.
- **Pi 5 vs Pi 4.** A university lab write-up found the Pi 5 about 40% faster on CPU and more stable than the Pi 4 for a security-tools stack (not IDS-specific) — [ITS in a Box wiki](https://elvis.hcw.ac.at/wiki/index.php/ITS_in_a_Box)
- **Wireshark/tshark/dumpcap.** On Linux, dumpcap can be granted `cap_net_raw,cap_net_admin` so non-root users in the `wireshark` group can capture — [Wireshark wiki: CaptureSetup/CapturePrivileges](https://wiki.wireshark.org/CaptureSetup/CapturePrivileges) **(ref, not re-fetched)**
- **Arkime** (formerly Moloch) does full packet capture and indexing, backed by OpenSearch/Elasticsearch — [Arkime](https://arkime.com/) **(ref, not re-fetched)**

### Inferences
- **Recommended tiers:**
  - Pi 4: ntopng Community plus Pi-hole.
  - Pi 5 8 GB with NVMe: ntopng plus Suricata (ET Open rules), or Zeek alone.
  - x86 N100-class mini PC with 16 GB RAM and two NICs: inline bridge with Zeek plus Suricata, optionally Arkime or Security Onion-lite.
- All of these tools need a traffic feed (SPAN, inline bridge, or own router via bridge mode). Pointed only at an eero LAN port, they see broadcast/multicast plus their own traffic.

### Gaps
- No independent 2025–2026 benchmarks of Zeek/Suricata throughput on a Pi 5 were found.
- Did not verify the Arkime 5.x or Zeek 7/8 versions, or Security Onion's minimum specs (believed far above a Pi).

## 5. Building a topology map (which device is on which eero node, wired vs wireless)

### Takeaway
LAN scanning cannot tell which eero node a client is attached to, because all nodes bridge to one L2 domain and eero has no LLDP/SNMP. Node association, wired/wireless status, band and signal come only from eero's cloud API (unofficial). The practical design is to join the eero API device list (MAC, node, connection type) with scan data (IP, hostname, mDNS services, OS) on MAC/IP.

### Cited Findings
- Unofficial eero Python clients:
  - `eero-client` (343max lineage, v2.2.x on PyPI). It notes the API is undocumented and its models only cover objects seen on the author's own network — [PyPI eero-client](https://pypi.org/project/eero-client/)
  - `eero-api` (v8.4.0), an async Python SDK. It lists the companion Home Assistant HACS integration for eero networks, eeros, profiles and devices — [PyPI eero-api 8.4.0](https://pypi.org/project/eero-api/8.4.0/) (search snippet only; page did not render on fetch)
- The Home Assistant eero integration (schmittx) exposes a per-device "Connected to" attribute naming the eero node — [HA community](https://community.home-assistant.io/t/new-custom-component-eero-integration/244583)
- The older `jrlucier/eero_tracker` HA device tracker uses eero-client and requires generating an eero.session file through the SMS/email login flow — [eero_tracker GitHub](https://github.com/jrlucier/eero_tracker)
- The eero API also supplies device names and IPs, which practitioners use to label Pi-hole clients — [engineered.at](https://engineered.at/articles/fixing-some-niggles-between-eero-pihole)

### Inferences
- **Data model:** network → eero nodes (gateway vs leaf, wired/wireless backhaul, IP) → clients (MAC, IP(s), hostname, connected node, wired/wireless, band/signal) → enrichment (OUI vendor, mDNS services, SSDP model, nmap OS/ports, DHCP fingerprint). Render with a graph library (e.g. Cytoscape.js, D3 force, vis-network) with the eero nodes as hubs.
- **Polling:** the API is undocumented and cloud-based, so poll slowly (minutes), cache the session token, expect breaking changes, and degrade gracefully to scan-only mode.
- **Wired devices behind an unmanaged switch** on a leaf eero appear attached to that eero node. Anything below that needs LLDP from a managed switch, if one is present.

### Gaps
- Could not read the eero-api or eero-client READMEs to list the exact JSON fields (e.g. `source.location`, `connection_type`, `interface.frequency`) or the auth flow details. These are unverified field names from memory.
- No source found on eero API rate limits or ToS stance on unofficial clients.

## 6. Libraries for a custom tool (Python, Go, Rust) and permissions

### Takeaway
Python has the richest ecosystem: scapy, python-nmap, zeroconf, netaddr, mac-vendor-lookup/manuf, and async eero clients. Go and Rust have solid equivalents for a single static binary. Raw L2 work (ARP, ICMP, packet capture) needs root or CAP_NET_RAW (plus CAP_NET_ADMIN for some operations), and containers need host networking to see the LAN broadcast domain.

### Cited Findings
- **NetAlertX's container requirements** illustrate the permission model: `--network=host` plus NET_RAW, NET_ADMIN and NET_BIND_SERVICE capabilities — [NetAlertX GitHub](https://github.com/netalertx/NetAlertX)
- **Python libraries:**
  - scapy (packet crafting/sniffing) — [scapy](https://scapy.net/) **(ref)**
  - python-nmap, which wraps the nmap binary and parses its XML output — [python-nmap PyPI](https://pypi.org/project/python-nmap/) **(ref)**
  - python-zeroconf (mDNS browse/resolve, pure Python, no root) — [GitHub](https://github.com/python-zeroconf/python-zeroconf) **(ref)**
  - netaddr (IP/CIDR math, EUI/OUI lookup) — [netaddr docs](https://netaddr.readthedocs.io/) **(ref)**
  - mac-vendor-lookup (async, downloads the IEEE list) — [PyPI](https://pypi.org/project/mac-vendor-lookup/) **(ref)**
  - eero-api, eero-client — [PyPI eero-api](https://pypi.org/project/eero-api/8.4.0/); [PyPI eero-client](https://pypi.org/project/eero-client/)
- **Go libraries:**
  - gopacket (google/gopacket; the maintained fork is gopacket/gopacket) for capture/crafting — [gopacket](https://github.com/gopacket/gopacket) **(ref)**
  - mdlayher/arp and mdlayher/ndp for ARP and IPv6 NDP — [mdlayher/arp](https://github.com/mdlayher/arp), [mdlayher/ndp](https://github.com/mdlayher/ndp) **(ref)**
  - grandcat/zeroconf or hashicorp/mdns for mDNS — [grandcat/zeroconf](https://github.com/grandcat/zeroconf) **(ref)**
  - prometheus/client_golang to write an exporter — [client_golang](https://github.com/prometheus/client_golang) **(ref)**
- **Rust libraries:**
  - pnet (raw packets, datalink) — [libpnet](https://github.com/libpnet/libpnet) **(ref)**
  - pcap crate — [pcap](https://crates.io/crates/pcap) **(ref)**
  - mdns-sd — [mdns-sd](https://crates.io/crates/mdns-sd) **(ref)**
  - surge-ping (ICMP) — [surge-ping](https://crates.io/crates/surge-ping) **(ref)**
- **Linux permissions:**
  - Without root, grant capabilities with `setcap cap_net_raw,cap_net_admin+eip <binary>`. Note that setcap on the Python interpreter itself grants the capability to all Python scripts, so prefer a small privileged helper — [capabilities(7)](https://man7.org/linux/man-pages/man7/capabilities.7.html) **(ref)**
  - Unprivileged ICMP is possible via `net.ipv4.ping_group_range` — [icmp(7)](https://man7.org/linux/man-pages/man7/icmp.7.html) **(ref)**
- **macOS and Windows:** raw capture needs BPF device access on macOS (Wireshark's ChmodBPF) and Npcap on Windows — [Wireshark CapturePrivileges](https://wiki.wireshark.org/CaptureSetup/CapturePrivileges) **(ref)**

### Inferences
- **Architecture:** a privileged scanner daemon (ARP/NDP/pcap) writes to SQLite or Postgres. An unprivileged web app, plus an eero-API poller and Prometheus exporter, reads from it. This mirrors NetAlertX and WatchYourLAN.
- mDNS and SSDP discovery need no root (ordinary UDP multicast sockets), so they can run in the unprivileged component.

### Gaps
- Did not verify the 2026 maintenance status of python-nmap, mac-vendor-lookup, grandcat/zeroconf or libpnet. Check last-commit dates before adopting.

## 7. IPv6 considerations for discovery

### Takeaway
eero supports IPv6 (including custom IPv6 DNS). On IPv6, sweeping the /64 is infeasible, so discovery must rely on multicast and passive methods:
- ping ff02::1 (all-nodes)
- read the kernel neighbor cache (`ip -6 neigh`)
- listen for NDP neighbor/router solicitations, DAD and MLD
- mDNS over ff02::fb

Clients use multiple temporary privacy addresses (RFC 8981), so the MAC (from NDP link-layer options) is the join key, not the IPv6 address.

### Cited Findings
- eero lets you set custom DNS servers for both IPv4 and IPv6 — [eero support: custom DNS](https://support.eero.com/hc/articles/360059988432-Setting-up-custom-DNS-servers-with-eero) (search snippet)
- A 2026 guide covers enabling IPv6 on eero mesh systems — [OneUptime blog (2026-03-20)](https://oneuptime.com/blog/post/2026-03-20-configure-ipv6-eero-mesh-systems/markdown) (not fetched; not verified in detail)
- Temporary/privacy IPv6 addresses rotate (RFC 8981, which obsoletes RFC 4941) — [RFC 8981](https://www.rfc-editor.org/rfc/rfc8981) **(ref)**
- Neighbor Discovery (RFC 4861) covers NS/NA and RS/RA. The all-nodes multicast group is ff02::1 — [RFC 4861](https://www.rfc-editor.org/rfc/rfc4861) **(ref)**
- Tools: nmap's `targets-ipv6-multicast-echo` and `targets-ipv6-multicast-slaac` NSE scripts discover local IPv6 hosts — [Nmap NSE targets-ipv6-multicast-echo](https://nmap.org/nsedoc/scripts/targets-ipv6-multicast-echo.html) **(ref)**. The THC-IPv6 toolkit (`alive6`) and Go's mdlayher/ndp do the same — [mdlayher/ndp](https://github.com/mdlayher/ndp) **(ref)**

### Inferences
- **What the inventory should store:** each device's set of IPv6 addresses (link-local fe80::, stable SLAAC/GUA, temporaries), keyed on MAC. It should also expire temporary addresses.
- **Unreliable responders:** some OSes (e.g. Windows with its firewall on) won't answer ff02::1 echo. Passive NDP/MLD listening and ICMPv6 "parameter problem" tricks (the slaac script) improve coverage.
- **IPv6 bypasses IPv4 DNS settings.** If IPv6 is enabled on eero but only IPv4 custom DNS points to Pi-hole, clients may send DNS via the IPv6 resolver and bypass Pi-hole. Set both.

### Gaps
- Could not confirm from eero docs whether eero uses SLAAC, DHCPv6 or both on the LAN, or which prefix sizes it accepts via prefix delegation.
- Did not find eero-specific reports about NDP or multicast behavior across mesh nodes (e.g. whether ff02::1 reaches clients on all nodes reliably).
