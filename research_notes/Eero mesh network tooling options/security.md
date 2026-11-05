# Securing an eero Mesh Home Network and Security Tooling for a Hobbyist Developer (as of Nov 2026)

> Research method note: In this session WebFetch could not reach eero.com, blog.eero.com or nvd.nist.gov (DNS resolution blocked by the session's network allowlist). All findings below come from web-search result snippets and summaries, not full-page reads. Treat specific numbers (prices, device limits, version strings) as needing a re-check against the primary page before publishing. Those hosts have to be allowed in the session's network settings before the pages can be fetched directly.
>
> Legal/ethical boundary (applies to every tool below): only scan, sniff or monitor networks and devices you own or have explicit permission to test. Passive Wi-Fi monitoring (Kismet) picks up neighbours' frames. Log and alert only on your own BSSIDs and clients, and never send deauth or other active frames. Active scanning of your own public IP from an external host is fine. Scanning other people's IPs, or Shodan-style probing of third parties, is not. For US users, unauthorised access is covered by the CFAA. Sources stress "Scan only networks and addresses you own or have permission to test" — [Tech Insider](https://tech-insider.org/how-to-run-a-vulnerability-scan-2026/).

## 1. eero built-in security capabilities and limits

### Takeaway
eero gives you a solid managed baseline: automatic, non-disableable firmware updates; WPA3 in *transition mode* (an eero Labs toggle); a guest network; UPnP (on by default); IPv6 firewall rules; and Amazon-account MFA. It has no internal VLANs, no extra IoT SSIDs and no SSID-to-VLAN mapping. The DNS-based protections (threat blocking, ad blocking, content filters) are paywalled in eero Plus and are mutually exclusive with custom DNS. The only published eeroOS CVE found is a 2023 Ethernet DoS.

### Cited Findings
**Wi-Fi encryption (WPA2/WPA3)**
- WPA3 is enabled from the eero app: Discover tab → eero Labs → toggle WPA3. When enabled it operates in "transition mode", so WPA3-capable clients use WPA3 and others fall back to WPA2 — [eero help: What is WPA3?](https://support.eero.com/hc/articles/360042523671-Was-ist-WPA3); [eero blog: eero Now Supports WPA3](https://blog.eero.com/eero-now-supports-wpa3)
- eero chose transition mode rather than WPA3-only because older clients "still need to be able to connect using WPA2, which is not possible with WPA3-only mode". Its testing "revealed interoperability issues with some legacy devices" — [eero blog](https://blog.eero.com/eero-now-supports-wpa3)
- WPA3 support arrived in eeroOS 3.19.0, labelled "WPA3 Transition Mode" in eero Labs — [Android Central](https://www.androidcentral.com/eero-319-update-adds-dynamic-frequency-selection-and-wpa3-support); [iMore](https://www.imore.com/eero-319-update-adds-dynamic-frequency-selection-and-wpa3-support)
- Community reports: HomeKit devices showing "no response" with transition mode on; older iOS versions failing to connect — [eero Community labs thread](https://community.eero.com/t/x1jl6t/eero-labs-features-and-feedback-thread?r=m1hgmcg)

**Firmware updates**
- eeroOS updates install automatically. You can set a "Preferred update time" (Settings → Software updates). Each eero restarts and the whole update takes about 15–20 minutes — [eero: How do eeroOS updates work?](https://eero.com/support/articles/how-do-eeroos-updates-work); [eero zendesk mirror](https://eero.zendesk.com/hc/en-us/articles/213372343-How-do-eero-OS-updates-work)
- Automatic updates cannot be turned off, though you can install an update immediately — [Android Central](https://www.androidcentral.com/can-you-stop-eero-auto-updating-its-software); [smarterhome.guru firmware tracker](https://www.smarterhome.guru/firmware/eero/all-eero-devices-eeroos). One UK guide claims scheduling isn't possible — [Orbus](https://orbus.uk/broadband/guides/eero-firmware-update-uk/). This conflicts with eero's own article, which is likely more current.
- eero says eero Plus "is not required for an eero network to continue to receive our security updates" — [eero help: How much does eero Plus cost?](https://support.eero.com/hc/articles/115002904283-How-much-does-eero-Plus-cost)

**UPnP, port forwarding, IPv6 firewall**
- UPnP is supported and **enabled by default**. To toggle it: Settings → Advanced networking → UPnP — [eero: What advanced features does eero support?](https://support.eero.com/hc/en-us/articles/207613326-What-advanced-features-does-eero-support)
- Port forwards and reservations are under "Reservations & port forwarding": "IPv4 Reservations & Port Forwards" plus a separate "IPv6 Firewall Rules" section — [eero: How do I set up port forwarding?](https://support.eero.com/hc/en-us/articles/207908443-How-do-I-configure-port-forwarding)
- Third-party guides say eero blocks unsolicited inbound IPv6 by default, and IPv4 forwards do not cover IPv6 (pinholes are separate rules) — [OneUptime blog (Mar 2026)](https://oneuptime.com/blog/post/2026-03-20-configure-ipv6-eero-mesh-systems/view). This is a secondary source. An older eero Community thread said inbound IPv6 pinholes weren't possible; that has been superseded by the IPv6 Firewall Rules feature — [eero Community](https://community.eero.com/t/k9rnhn/is-it-possible-to-allow-incoming-ipv6-connections)

**Guest network and segmentation**
- Bridge mode disables eero's network services (routing, DHCP, firewall) while it keeps serving Wi-Fi. You lose app-managed advanced features, including device blocking, IP reservations, port forwarding and custom DNS — [eero: What is bridge mode?](https://eero.com/support/articles/what-is-bridge-mode); [eero: What features do I lose in bridge mode?](https://support.eero.com/hc/en-us/articles/115000825206-What-advanced-features-do-I-lose-access-to-if-I-put-my-eeros-into-bridge-mode)
- A third-party Q&A says the guest network is **not separated** from the main LAN in bridge mode. This is unofficial — [JustAnswer](https://www.justanswer.com/computer-networking/u9725-eero-guest-network-access-main-devices.html)
- eero Plus Advanced Security reportedly does not cover guest-network devices (citing eero FAQ via third-party summaries) — [Android Central: eero Secure](https://www.androidcentral.com/what-eero-secure-and-eero-secure)
- No native internal VLANs: "eero Max 7 does NOT support multiple VLANs for your internal home network" — [Best Buy Q&A](https://www.bestbuy.com/site/questions/eero-max-7-tri-band-mesh-wi-fi-7-router-1-pack-white/10104527?page=2). Another user: "Eero hardware is not going to support VLAN tagging" — [Lawrence Systems forum](https://forums.lawrencesystems.com/t/improving-my-home-network-iot-segregation-vlan/3069)
- eero's VLAN tagging setting is for the **ISP/WAN side** only (ISPs that require a tagged VLAN) and does not segment the LAN — [OzBargain thread](https://www.ozbargain.com.au/node/785896)
- Firewalla staff: "I don't think Eero support VLAN's or SSID to VLAN mapping". A third-party AP is needed for SSID→VLAN mapping — [Firewalla community](https://help.firewalla.com/hc/en-us/community/posts/52619301261075-Eero-Pro-7-in-bridge-mode-can-Firewalla-manage-multiple-SSIDs-mapped-to-VLANs)

**eero Plus (formerly eero Secure / Secure+)**
- eero describes eero Plus as a subscription for "advanced security features and expanded parental controls", plus partner services — [eero: What is eero Plus?](https://eero.com/support/articles/what-is-eero-plus)
- Features per eero support: Advanced Security (threat blocking), DNS-level ad blocking, content filters, block apps/sites, and partner services: **1Password** (Families), **VPN powered by Guardian**, and **Malwarebytes** (antivirus + Identity Protection, eero says up to 20 devices). Older reviews said 3 Malwarebytes devices; that appears outdated — [eero support: What is eero Plus?](https://support.eero.com/hc/en-us/articles/115002766063-What-is-eero-Plus); [How-To Geek](https://www.howtogeek.com/what-is-eero-plus/); [Astound](https://www.astound.com/learn/internet/eero-secure-vs-eero-plus/); [Nextlink eero Plus datasheet, Jan 2026](https://nextlinkinternet.com/wp-content/uploads/2026/01/eero-Plus-Datasheet.pdf)
- The Guardian VPN is per-device (one review says up to 5 activated devices), not a router-wide tunnel — [impulsec review](https://impulsec.com/parental-control-software/eero-plus-security-review/). This is a lower-quality source.
- Advanced Security blocks known malicious sites: "viruses, trojans, spyware, and phishing" — [eero: What is eero Plus?](https://eero.com/support/articles/what-is-eero-plus). Android Central says the threat intel draws on "over 12 billion daily website visits" — [Android Central](https://www.androidcentral.com/what-eero-secure-and-eero-secure)
- Other listed extras include dynamic DNS, Wi-Fi analytics and internet backup — [How-To Geek](https://www.howtogeek.com/what-is-eero-plus/)
- **US price: $9.99/month or $99.99/year**. App Store listings show the same tiers. Legacy eero Secure was $2.99/month or $29.99/year — [eero help: cost](https://support.eero.com/hc/articles/115002904283-How-much-does-eero-Plus-cost); [App Store pricing tracker](https://apppricinglab.com/iap/apple/1023499075); [Subger (aggregator)](https://subger.com/en/service/eero-secure). Australia lists AUD 15.99/month — [eero AU](https://eero.com/en-AU/eero-plus). Engadget's Pro 7 review criticised gating features behind the subscription — [Engadget](https://www.engadget.com/home/smart-home/eero-pro-7-review-paying-to-be-sold-a-subscription-171502767.html)

**Admin account, Amazon linking, privacy**
- Using Amazon login gives Amazon's protections (MFA, security alerts). Switching is **permanent**: the old eero credentials stop working, and reverting means deleting the eero account — [eero: How do I use my Amazon login with eero?](https://support.eero.com/hc/en-us/articles/360058259651-How-do-I-use-my-Amazon-login-with-eero)
- A non-Amazon eero login uses passwordless sign-in (verification code to phone/email) — [eero: Account & App Setup](https://eero.com/support/sections/account-and-app-setup); [eero Security FAQ](https://support.eero.com/hc/en-us/articles/209962973-Frequently-asked-security-questions)
- Amazon linking shares the Amazon account name/email and connected-device info (device nicknames, signal strength). eero states "eero does not track where you go on the internet" — [eero: What is shared when I link my Amazon account?](https://support.eero.com/hc/en-us/articles/360045529291-What-is-shared-when-I-link-my-Amazon-account); [eero Privacy Notice](https://www.amazon.com/b?ie=UTF8&node=122451468011)
- Wi-Fi credentials can be saved to Amazon. To stop sharing, delete them in Amazon "Manage Your Content and Devices" — same eero article as above
- A user claim that MAC addresses are shared with Amazon is **unverified** — [Whirlpool forum](https://forums.whirlpool.net.au/archive/9vw4xknm)

**Advisories / CVEs**
- **CVE-2023-5324**: denial of service via the eeroOS Ethernet interface, affecting eeroOS ≤ 6.16.4-11. Published 1 Oct 2023. CVSS v3 6.5 (Medium), though some aggregators label it critical. A public PoC exists on GitHub — [NVD](https://nvd.nist.gov/vuln/detail/CVE-2023-5324); [Tenable](https://tenable.com/cve/CVE-2023-5324); [OpenCVE](https://www.opencve.io/cve/CVE-2023-5324); [Feedly eero vendor page](https://feedly.com/cve/vendors/eero)
- eero says it patched "tens of millions of eeros across 28 countries" for an industry-wide vulnerability that Amazon Security found. The post's date and CVE were not retrievable — [eero blog: How Amazon and eero continue to keep customers secure](https://blog.eero.com/how-amazon-and-eero-continue-to-keep-customers-secure)

### Inferences
- The default eero LAN is flat: IoT, PCs and phones share one L2 segment. The only built-in isolation is the guest network, which loses Plus threat protection and is unreliable or absent in bridge mode.
- With UPnP on by default, any compromised IoT device can open inbound IPv4 mappings. Turning UPnP off, and re-adding explicit forwards only where needed, is a high-value hardening step.
- WPA3-only and PMF-required modes are not exposed in the consumer app (only transition mode). Transition mode permits downgrade to WPA2-PSK, so passphrase strength still matters.
- With eero Plus active, Pi-hole/AdGuard cannot be set as eero's custom DNS. Choose either eero Plus DNS protection or your own resolver; you can't run both through eero's DNS setting (see section 3).

### Gaps
- Could not confirm whether any 2025–2026 eeroOS release added IoT-dedicated SSIDs, more SSIDs, client isolation toggles, WPA3-only or PMF-required modes. No source found either way.
- Could not confirm when Guardian replaced encrypt.me as the VPN partner, or whether encrypt.me is still offered.
- No source found on whether eero offers a bug bounty or a public PSIRT/advisory page. No eeroOS CVEs after 2023 surfaced in searches (absence of evidence only).
- 2FA specifics for non-Amazon eero accounts (beyond passwordless codes) were not documented in results.

## 2. Segmentation strategies given eero limits

### Takeaway
The realistic options are: (a) put IoT on eero's guest network (router mode only); (b) a second router/AP for IoT; (c) eero in bridge mode behind OPNsense, pfSense or Firewalla, with VLANs on a managed switch and a VLAN-capable AP for IoT, using eero only for the trusted SSID. eero itself does not tag or pass per-SSID VLANs.

### Cited Findings
- NSA's home-network guidance recommends wireless segmentation: separate primary, guest and IoT Wi-Fi networks — [NSA press release, 22 Feb 2023](https://www.nsa.gov/Press-Room/News-Highlights/Article/Article/3304674/nsa-releases-best-practices-for-securing-your-home-network/); summary at [sqmagazine](https://sqmagazine.co.uk/router-security-settings/)
- Common pattern: Firewalla port 2 feeds the eero mesh (bridge mode) for the personal network, and IoT goes on a separate Firewalla port with its own AP — [Firewalla community](https://help.firewalla.com/hc/en-us/community/posts/26523457120275/comments/26526086243859)
- OPNsense user example: 2× eero 6+ in bridge mode, with segmentation done by VLAN-tagging switch ports rather than on the eero — [androidexperto / forum compilation](https://androidexperto.com/use-eero-in-bridge-mode-and-keep-router-features/); [OPNsense forum](https://forum.opnsense.org/index.php?topic=29886.0)
- "eero does not become a full VLAN-aware enterprise access point" in bridge mode — [androidexperto](https://androidexperto.com/use-eero-in-bridge-mode-and-keep-router-features/)
- An eero Community support reply suggests devices on the guest network are isolated from each other and only reach the internet. This is anecdotal — [eero Community: IoT](https://community.eero.com/t/36605g/incorporating-eero-into-safer-network-for-internet-of-things)
- Bridge mode loses device blocking, reservations, port forwarding and custom DNS in the eero app. Those move to the upstream router — [eero support](https://support.eero.com/hc/en-us/articles/115000825206-What-advanced-features-do-I-lose-access-to-if-I-put-my-eeros-into-bridge-mode)
- Managed-switch picks for VLAN/SPAN home labs (2026) — [HomeNode](https://homenode.tech/best-managed-switch-home-lab-2026-vlan-lag-poe-25gbe/)

### Inferences
- Option ranking for an eero owner:
  1. **Guest network for IoT.** Free, but it often breaks casting, HomeKit and Matter discovery across segments, and gets no eero Plus protection.
  2. **Router-behind-router (double NAT).** IoT on the ISP/primary router, trusted devices behind eero. Trusted can reach IoT, but not the reverse. Cheap, but adds double NAT.
  3. **eero bridge + OPNsense/pfSense/Firewalla + managed switch + separate VLAN-capable AP** (e.g. Omada/UniFi) for IoT/guest SSIDs mapped to VLANs. eero carries only the untagged trusted LAN. Firewall rules allow trusted→IoT and block IoT→trusted, with mDNS reflection for casting. This is the strongest option, and the firewall then becomes the visibility point for IDS (section 4).
- "MAC-based profiles" on eero (Profiles / pause / block device) are policy features, not isolation: devices in the same profile are still on the same L2 segment. Randomised/private MACs on phones also weaken MAC-based policy.

### Gaps
- No eero document confirms whether eero in bridge mode passes 802.1Q-tagged frames on its Ethernet ports. Forum consensus is "don't rely on it".
- No source quantified guest-network client isolation on current eeroOS.

## 3. DNS-layer security (Pi-hole, AdGuard Home, NextDNS, Quad9, Cloudflare for Families)

### Takeaway
Custom DNS lives at Settings → Advanced networking → DNS, and it requires turning off Advanced Security, ad blocking and all content filters/block lists first. eero Plus DNS filtering and your own DNS are mutually exclusive. To make DNS filtering hold, you also need to neutralise DoH/DoT bypass: the Firefox canary domain, blocking iCloud Private Relay domains, and firewall-blocking known DoH IPs and port 853. The last of these needs a real firewall, not eero.

### Cited Findings
- Path: eero app → Settings → Advanced networking → DNS → Custom DNS. Before custom DNS can be set: "Toggle off Advanced Security and Ad Blocking. Remove any active Content Filters and blocked or allowed sites/apps". Reason given: eero Plus filters DNS requests, so custom DNS "won't work as expected". Changing DNS reboots the network — [eero: How do I set up custom DNS servers?](https://eero.com/support/articles/how-do-i-set-up-custom-dns-servers-with-eero); [eero: Advanced networking settings](https://eero.com/support/articles/what-are-the-advanced-networking-settings)
- eero's DNS-based protections do not operate while Custom DNS is in use. eero custom DNS takes plain IPs, so encrypted DNS needs a local forwarder workaround — [Dnsium guide](https://www.dnsium.com/blog/eero-custom-dns-settings) (secondary)
- Third-party filtering DNS can be applied to eero for content filtering — [SafeSurfer guide](https://safesurfer.io/articles/guides/how-to-protect-an-eero-wi-fi-mesh-network-from-harmful-online-content/)
- Pi-hole with eero: letting Pi-hole run DHCP effectively forces eero into bridge mode and loses app device management. One author instead pulled device names from the (unofficial) eero API to generate a hosts file for Pi-hole — [Amish Bhadeshia blog](https://www.amishbhadeshia.co.uk/posts/eero-and-pihole/)
- AdGuard Home and Pi-hole both use DNS sinkholing. AdGuard Home has encrypted upstream (DoH/DoT/DoQ) built in, while Pi-hole needs an add-on such as cloudflared or unbound (this is AdGuard's own comparison) — [AdGuard Home wiki: Comparison](https://github.com/adguardTeam/adGuardHome/wiki/Comparison)
- **Firefox DoH canary:** respond NXDOMAIN for `use-application-dns.net` to disable Firefox default DoH. Pi-hole blocklists can override this; the fix is NXDOMAIN blocking mode or allow-listing the domain — [Pi-hole GitHub issue #3167](https://github.com/pi-hole/pi-hole/issues/3167); [Pi-hole discourse](https://discourse.pi-hole.net/t/blocking-dns-over-https-doh/69404)
- **iCloud Private Relay:** blocking `mask.icloud.com` and `mask-h2.icloud.com` (some guides add `mask-api.icloud.com`) makes Apple devices disable Relay on that network — [SDN46](https://www.sdn46.com/how-to-block-apples-icloud-private-relay-using-pi-hole-and-dns-filtering/); [Pi-hole discourse](https://discourse.pi-hole.net/t/icloud-private-relay/49811); [OPNsense forum](https://forum.opnsense.org/index.php?topic=45073.0)
- **Hard-coded DoH clients** need IP-level blocks using lists of DoH server IPs/domains (e.g. hagezi doh-onlydomains) on pfSense/OPNsense — [jpgpi250 Pi-hole manual: Block DoH with pfSense](https://jpgpi250.github.io/piholemanual/doc/Block%20DOH%20with%20pfsense.pdf); [hometechops: force all devices through Pi-hole](https://hometechops.com/guides/force-all-devices-through-pihole)

### Inferences
- With eero as the router, you cannot NAT-redirect stray port-53 traffic or block port 853/DoH IPs, because eero has no outbound firewall rules. Devices with hard-coded resolvers (e.g. 8.8.8.8, common on Chromecast/IoT) bypass Pi-hole. Enforcing DNS needs an OPNsense/pfSense/Firewalla gateway.
- Resolver choices: Quad9 (9.9.9.9, malware blocking), Cloudflare for Families (1.1.1.2 malware; 1.1.1.3 malware+adult), NextDNS (cloud, per-device config, DoH/DoT). Any of these can be entered directly as eero custom DNS IPs. NextDNS's per-device identification needs DoH/DoT or linked IP, so plain-IP use via eero gives network-wide but not per-device policy.
- A tool can verify DNS enforcement by querying a known-blocked test domain from each segment and checking whether direct queries to 8.8.8.8:53 and DoT to 1.1.1.1:853 succeed (bypass possible).

### Gaps
- Could not fetch primary docs for Quad9, Cloudflare for Families or NextDNS in this session. The IPs above are from background knowledge and should be verified at quad9.net and developers.cloudflare.com.
- No source on whether eero hands out IPv6 RDNSS pointing to itself while custom IPv4 DNS is set. This could leak DNS around Pi-hole over IPv6 and is worth testing.

## 4. Intrusion detection / anomaly detection and new-device alerting

### Takeaway
eero gives no packet-level visibility. Real IDS (Suricata/Zeek/Security Onion) needs traffic copies, from a SPAN/mirror port on a managed switch placed between the ISP modem/gateway and eero (or between firewall and eero), or from an inline firewall (OPNsense/pfSense with Suricata, or Firewalla). Without that, a hobbyist can still run ARP/DHCP-based device inventory and new-device alerting (NetAlertX) on the flat LAN.

### Cited Findings
- Zeek docs: a SPAN port is an acceptable alternative to a network tap in SOHO/test environments — [Book of Zeek: Monitoring](https://docs.zeek.org/en/master/about/monitoring.html)
- Dual Zeek+Suricata home sensor: Zeek "gives you rich protocol metadata and context", Suricata "fast signature and protocol anomaly detection". Advice: mirror a single VLAN first and avoid oversubscribing the sensor — [nathanberg.io](https://nathanberg.io/posts/building-a-zeek-and-suricata-dual-sensor-for-a-home-lab/)
- Sensor design: two NICs, management with an IP plus a capture NIC with no IP on the SPAN port. Use promiscuous mode and disable NIC offloads (checksum offload causes false positives/broken reassembly). A cheap managed switch with SPAN (e.g. Netgear GS30xE) suffices — [nathanberg.io](https://nathanberg.io/posts/building-a-zeek-and-suricata-dual-sensor-for-a-home-lab/); [wroberts.me Suricata on Proxmox](https://wroberts.me/?p=242)
- Proxmox: SPAN feed into a Suricata VM via Open vSwitch port mirroring — [Medium: Proxmox port mirroring](https://medium.com/@davidmuth04/proxmox-port-mirroring-how-to-send-span-traffic-to-a-suricata-ids-vm-using-open-vswitch-dab7309f52e0)
- Raspberry Pi sensor: 4 GB minimum, 8 GB preferred for Zeek connection tracking — [HookProbe](https://hookprobe.com/blog/zeek-suricata-raspberry-pi-edge-security/)
- Suricata 8.0 passive IDS setup guide (2026). A passive mirror-port sensor sits off-path and can only alert — [Tech Insider](https://tech-insider.org/au/suricata-ids-ips-setup-2026/)
- Zeek for home-lab forensics — [sumguy.com](https://sumguy.com/zeek-network-forensics-homelab/)
- **NetAlertX** (formerly Pi.Alert, renamed April 2024): scans the LAN and flags unseen devices. It has a "new device joins the network" trigger, and initially every device is "new" until you mark all as known. It runs in Docker (port 20211) and needs host networking to see the LAN. Do not expose its dashboard to the internet. Integrates with Home Assistant notifications — [NetAlertX GitHub](https://github.com/jokob-sk/NetAlertX); [Gladys docs](https://gladysassistant.com/docs/integrations/external/netalertx/); [Home Assistant community](https://community.home-assistant.io/t/netalertx-notification-automation-with-json-correctly-parsed/870932); [Virtualization Howto](https://www.virtualizationhowto.com/2025/06/netalertx-self-hosted-network-monitoring-for-home-labs/); [mariushosting](https://mariushosting.com/how-to-install-pi-alert-on-your-synology-nas/)

### Inferences
- Topology for IDS visibility with eero in router mode: ISP modem → managed switch (mirror the eero-WAN port) → eero WAN. You see all internet-bound traffic, but post-NAT (every flow appears from eero's WAN IP), so per-device attribution is lost. Mirroring a LAN-side port only shows wired traffic plus that port's traffic. Wireless client-to-client traffic stays inside the mesh. Bridge mode behind a firewall restores per-device IPs at the firewall.
- Firewalla (Purple/Gold) in router mode with eero bridged is the turnkey route: IDS-like alerts, per-device flows, VLANs, DNS enforcement. OPNsense/pfSense with Suricata (IPS on WAN/LAN) plus CrowdSec bouncer plus ntopng is the DIY route.
- Hobbyist-buildable anomaly checks without full packet capture: new MAC/OUI seen, device changing hostname/vendor, a device starting to listen on new ports (periodic nmap diff), DNS query anomalies from Pi-hole/AdGuard query logs (DGA-like names, newly registered domains, spikes), and IoT devices contacting unexpected countries/ASNs (from Zeek conn.log or firewall logs).

### Gaps
- Searches returned no usable primary material on **CrowdSec**, **ntopng**, **Security Onion** (minimum specs) or current **Firewalla** product/feature specifics. Consult crowdsec.net docs, ntop.org, docs.securityonion.net and help.firewalla.com directly.
- No source on any official or unofficial eero API that exposes connected-device lists for alerting, beyond the blog mention in section 3. Community Python clients exist but were not verified here.

## 5. Vulnerability assessment of LAN devices and external exposure

### Takeaway
A practical workflow: inventory and port-map with nmap, enrich with NSE (vulners, http-title, ssl-enum-ciphers, upnp-info, default-creds style scripts), run Nuclei templates against discovered HTTP services, and optionally run Greenbone/OpenVAS Community Edition for deep authenticated CVE checks. Then verify the outside view: eero port forwards and UPnP mappings, an external port scan of your own public IP (and IPv6 hosts), and a Shodan lookup of your own IP.

### Cited Findings
- Nmap's NSE "can detect known vulnerabilities and misconfigurations". The vulners NSE script ships with Nmap and maps detected service versions to CVEs. "If you are looking for a fast scan, Nmap plus Vulners is the place for you" — [ManageEngine](https://www.manageengine.com/network-configuration-manager/tech-topics/5-best-open-source-network-vulnerability-scanners.html); [SC World review](https://www.scworld.com/product-test/sw-labs-review-free-and-open-source-vulnerability-management-software)
- Greenbone/OpenVAS Community Edition: a signed NVT feed, but scans take "hours, not minutes" and need Docker/Postgres overhead — [VulnScanners](https://vulnscanners.com/blog/best-open-source-vulnerability-scanners); [VulnScanners CVE scanner guide 2026](https://vulnscanners.com/blog/open-source-cve-scanner-guide)
- Nuclei: lightweight, template-based, strongest on web/HTTP services and weaker on non-HTTP services — [VulnScanners](https://vulnscanners.com/blog/open-source-cve-scanner-guide)
- Suggested sequence: Nmap for mapping, then Nuclei and/or OpenVAS for CVE detection — [Tech Insider 2026](https://tech-insider.org/how-to-run-a-vulnerability-scan-2026/)
- Home router scan write-up found exposed web interfaces and UPnP services — [Medium: Nmap on my home network](https://medium.com/@ibbih.ya.habibie/how-i-used-nmap-to-discover-real-vulnerabilities-on-my-home-network-c675343ac6d6)
- UPnP historic risk: Rapid7 (2013) found more than 6,900 device models from 1,500 vendors vulnerable via UPnP flaws — [The Register](https://www.theregister.com/2013/01/29/hdmoore_upnp_flaw_rapid7/)
- eero has UPnP on by default (section 1). Port forwards and IPv6 rules are viewable in the app — [eero support](https://support.eero.com/hc/en-us/articles/207908443-How-do-I-configure-port-forwarding)

### Inferences
- Concrete commands a tool could wrap (own network only):
  - Discovery: `nmap -sn 192.168.4.0/22` (eero's default LAN is commonly 192.168.4.0/22; verify in the app).
  - Services: `nmap -sV -O --top-ports 1000 <host>`, then `--script vulners,http-title,ssl-enum-ciphers,ssh2-enum-algos,telnet-*,ftp-anon,smb-security-mode,rtsp-url-brute`.
  - UPnP/SSDP: `nmap -sU -p1900 --script upnp-info <lan>` lists devices advertising UPnP. Query the gateway's IGD (e.g. Python `miniupnpc`: enumerate `GetGenericPortMappingEntry`) to list active UPnP port mappings that eero created.
  - Default credentials: Nuclei `default-logins` templates against HTTP admin panels, and nmap `http-default-accounts`. Only against your own devices.
  - Outside view: run nmap from a cloud VM you control against your public IPv4, and against each globally-routable IPv6 address of LAN hosts (eero IPv6 firewall rules). Look up your IP on Shodan (`shodan host <ip>` with a free API key) or Censys to see what has historically been indexed.
- Firmware staleness: compare device banners/versions from nmap -sV with vendor latest versions or CVE feeds (NVD API, CISA KEV catalogue JSON) to flag KEV-listed products.

### Gaps
- No primary Shodan/Censys documentation retrieved. The "check your own IP" workflow is based on general knowledge and should be verified against Shodan's API docs.
- No source on whether eero's IGD/UPnP implementation exposes the standard `GetGenericPortMappingEntry` listing. Test empirically.

## 6. Wireless security monitoring (rogue APs, evil twins, deauth, WPS, PMF)

### Takeaway
Kismet on a Linux box or Raspberry Pi with a monitor-mode USB adapter is the hobbyist WIDS. Its APSPOOF, ADVCRYPTCHANGE, deauth-flood, BSSTIMESTAMP and NOCLIENTMFP alerts cover evil twins, downgrade twins and deauth attacks. PMF/802.11w defeats forged deauth, and WPA3 makes it mandatory, but it doesn't stop an evil twin. eero exposes no WPS button/PIN, no PMF toggle and no WIDS.

### Cited Findings
- Kismet APSPOOF: fires when a beacon or probe response for a known SSID comes from a MAC not on an allow-list. It "will not detect attacks which also spoof the MAC address". ADVCRYPTCHANGE flags a change in an SSID's advertised encryption (possible evil twin). BSSTIMESTAMP can false-positive with multiple datasources or quirky firmware. NOCLIENTMFP flags clients lacking MFP. "MFP (Management Frame Protection), or 802.11w, is standard for protecting clients and Access Points from spoofed management frames" — [Kismet docs: Alerts](https://www.kismetwireless.net/docs/readme/alerts/alerts/)
- 802.11w (ratified 2009): a PMF-enabled device drops forged deauth frames. Research has shown some bypasses, and WPA3-Personal still cannot authenticate network identity, so evil twins remain possible — [Medium: Wi-Fi Exploitation IV](https://rot-ig.medium.com/wi-fi-exploitation-iv-lock-it-down-or-lose-it-all-d713220182d7); [Hive Security](https://hivesecurity.gitlab.io/blog/evil-twin-access-points-wifi-attack/)
- Evil twin detection uses duplicate-SSID and signal-strength anomaly scanning (Kismet/Aircrack-ng) — [CoddyKit Security+](https://www.coddykit.com/courses/comptia_security_plus/wireless-attacks-evil-twin-deauth-and-rogue-ap-11009846)
- Academic approaches to evil-twin prevention via certificate-based AP authentication — [arXiv 2302.00338](https://arxiv.org/pdf/2302.00338)
- WPA3 transition mode on 6 GHz: 6 GHz requires WPA3 (no transition mode) — [Ezurio FAQ](https://www.ezurio.com/support/faqs/in-6ghz-band-is-wpa3-able-to-run-in-transition-mode)

### Inferences
- Hobbyist WIDS build: Kismet server with an allow-list of your eero BSSIDs (one per radio per node; get them from a site survey) for your SSID. Alerts go to a webhook. Also alert on any beacon of your SSID with a different BSSID or security suite (e.g. open or WPA2-only when you run WPA3), and on deauth/disassoc bursts targeting your BSSIDs.
- Because eero runs transition mode on 2.4/5 GHz, PMF is likely "capable" rather than "required" there, so WPA2-only legacy clients stay deauth-able. 6 GHz (eero 6E/7 models) should be WPA3/PMF-required by spec. Verify by capturing beacons (RSN capabilities MFPC/MFPR bits) with Kismet or Wireshark.
- WPS: no source found that eero supports WPS. The audit should still check beacons for a WPS IE.

### Gaps
- No eero documentation found on PMF settings, WPS support, or a WPA3-only option on 2.4/5 GHz.

## 7. Best-practice checklists from authoritative sources and the threat landscape

### Takeaway
NSA's 2023 home-network CSI, NIST IR 8425/8425A, and the FBI's 2025 BADBOX 2.0 PSA define the baseline: modern WPA3 (or WPA2/3) router with auto-updates, segmented IoT/guest Wi-Fi, admin restricted to LAN, unique strong credentials, and avoiding cheap uncertified Android/IoT gear. The IoT threat in 2025–2026 is dominated by huge botnets (Aisuru/Kimwolf, BADBOX 2.0) that monetise home devices as DDoS nodes and residential proxies. The US Cyber Trust Mark label program has had leadership churn.

### Cited Findings
**NSA**
- NSA CSI "Best Practices for Securing Your Home Network" (22 Feb 2023) covers securing routing devices, wireless segmentation and telework confidentiality — [NSA press release](https://www.nsa.gov/Press-Room/News-Highlights/Article/Article/3304674/nsa-releases-best-practices-for-securing-your-home-network/); [CSIAC](https://csiac.dtic.mil/?p=78757)
- Summaries list: WPA3 (or WPA2/3 if older devices), keep firmware updated, limit router administration to the internal network, separate primary/guest/IoT Wi-Fi, strong router authentication, and router firewall — [sqmagazine](https://sqmagazine.co.uk/router-security-settings/); [RPM Technologies](https://www.rpmtechnologies.com/2023/07/05/9-nsa-best-practices-for-securing-your-home-network/); [IKARUS](https://www.ikarussecurity.com/en/security-news-en/nsa-guide-to-secure-home-networks/) (secondary; full PDF on media.defense.gov not retrieved)

**NIST**
- NIST IR 8425 (19 Sep 2022): the consumer IoT core baseline profile, foundation of the US Cyber Trust Mark — [NIST CSRC IR 8425](https://csrc.nist.gov/pubs/ir/8425/final); [NIST Consumer IoT](https://www.nist.gov/itl/applied-cybersecurity/nist-cybersecurity-iot-program/consumer-iot-cybersecurity)
- NIST IR 8425A (published Sept 2024): consumer-grade router requirements, e.g. unique initial passwords that must be changed to a strong passphrase on install — [NIST news Sept 2024](https://www.nist.gov/news-events/news/2024/09/nist-cybersecurity-iot-program-publishes-nist-ir-8425a-recommended); [NIST IR 8425A PDF](https://nvlpubs.nist.gov/nistpubs/ir/2024/NIST.IR.8425A.pdf); [router standards crosswalk](https://www.nist.gov/document/consumer-grade-router-standards-crosswalk)

**FCC US Cyber Trust Mark (status Nov 2026)**
- UL Solutions withdrew as Lead Administrator effective 19 Dec 2025, amid an FCC national-security probe into its China ties — [FCC Cyber Trust Mark page](https://www.fcc.gov/CyberTrustMark); [Nextgov](https://www.nextgov.com/cybersecurity/2026/01/ul-solutions-withdraws-lead-admin-fcc-cyber-label-program-amid-probe-china-ties/410448/); [Cybersecurity Dive](https://www.cybersecuritydive.com/news/fcc-cyber-trust-mark-iot-labeling-ul-withdraw/808732/)
- FCC reopened LA applications (window 7–28 Jan 2026, later extended) — [FCC DA 26-75](https://docs.fcc.gov/public/attachments/DA-26-75A1.pdf); [Global Policy Watch](https://www.globalpolicywatch.com/2026/01/fcc-opens-application-window-for-new-cyber-trust-mark-program-lead-administrator/)
- Per the FCC program page (via search summary): ioXt Alliance was named Lead Administrator effective 13 Apr 2026. There is a 28 Oct 2026 release "Carr Announces Trusty Will Lead U.S. Cyber Trust Mark Program". The FCC recognised accreditation bodies on 28 Sep 2026 and sought comment on label design/surveillance on 27 Oct 2026 — [FCC Cyber Trust Mark](https://www.fcc.gov/CyberTrustMark). **Not verified from the page directly. The relationship between ioXt and Trusty is unclear.**

**Threat landscape (IoT)**
- Aisuru botnet (first seen Aug 2024): at least 700,000 IoT systems (routers, cameras). It shifted from DDoS to renting bots as residential proxies — [KrebsOnSecurity, Oct 2025](https://krebsonsecurity.com/2025/10/aisuru-botnet-shifts-from-ddos-to-residential-proxies/). Barracuda estimates 1–4 million devices and 29.7 Tbps peaks — [Barracuda, Apr 2026](https://blog.barracuda.com/2026/04/13/top-threat-trends-of-the-2025-botnet-landscape) (the size figures conflict)
- Kimwolf abused a residential proxy provider (Ipidea) vulnerability to reach devices behind home firewalls — [Wikipedia: Ipidea](https://en.wikipedia.org/wiki/Ipidea) (secondary)
- FBI PSA I-060525 (5 Jun 2025): BADBOX 2.0 infects off-brand streaming boxes, projectors and similar devices via pre-installed malware or "required apps". Most were made in China. Mitigations: buy reputable/certified devices, update firmware, avoid unofficial app stores, disconnect suspect devices and report to ic3.gov — [Infosecurity Magazine](https://www.infosecurity-magazine.com/news/fbi-smart-home-users-badbox-20/); [HSToday](https://www.hstoday.us/subject-matter-areas/cybersecurity/fbi-issues-announcement-regarding-new-internet-of-things-exploitation/); [FBI on X](https://x.com/FBI/status/1931049029787431259). Google's July 2025 suit described more than 10M devices — [Barracuda](https://blog.barracuda.com/2026/04/13/top-threat-trends-of-the-2025-botnet-landscape)
- 2026: US DOJ reportedly dismantled the Aisuru, Kimwolf, JackSkid and Mossad IoT botnets. A factory backdoor was reported in 20 Zbtlink router models — [SecureWorld](https://www.secureworld.io/industry-news/smart-home-attack-surface) (secondary; DOJ release not retrieved)
- Industry "no universal default passwords" principle — [Cybersecurity Tech Accord](https://cybertechaccord.org/no-universal-default-passwords/)

### Inferences
- Mapping NSA advice to eero: auto-updates (met), WPA3/WPA2-3 (enable the Labs toggle), admin restricted to LAN (eero is cloud/app-managed with no local web UI, so this is moot, but secure the Amazon/eero account with MFA), segmentation (partial, via guest network only), disable UPnP (manual).
- Residential-proxy malware is the most likely home compromise outcome in 2026. Detection signals are a device with abnormal outbound connection counts or bandwidth, and connections to many unrelated destinations. Both can be seen at a firewall/Zeek sensor, or roughly via eero's per-device usage in the app.

### Gaps
- CISA's current home-network guidance pages were not returned by searches and need to be fetched from cisa.gov.
- The primary FBI PSA text (ic3.gov) and DOJ takedown releases were not retrieved.

## 8. What an automated "home security audit" tool could check (concrete checks list)

### Takeaway
A hobbyist tool (e.g. a Python CLI or container on a Pi) can automate about 25 checks across inventory, exposure, DNS, Wi-Fi and threat intel. Some eero settings (UPnP state, WPA3 toggle, DNS mode, guest network) cannot be read through any public eero API, so they need manual attestation or inference from network observations.

### Cited Findings
- Building blocks with sourced capabilities: nmap/NSE/vulners, Nuclei, Greenbone (section 5); NetAlertX new-device detection (section 4); Kismet alerts (section 6); Pi-hole/AdGuard DNS controls and canary/Private Relay domains (section 3); eero settings locations (section 1) — see citations in the sections above.
- NIST IR 8425A router criteria (unique passwords, updates) can serve as a rubric — [NIST IR 8425A](https://nvlpubs.nist.gov/nistpubs/ir/2024/NIST.IR.8425A.pdf)

### Inferences
Proposed check list (method in brackets; all against the user's own network):

**A. Inventory**
1. Enumerate all LAN hosts (ARP sweep / `nmap -sn`; mDNS/SSDP listeners) and diff against a known-device baseline. Alert on new MACs (NetAlertX-style).
2. OUI/vendor lookup. Flag randomised MACs and known-risky vendors or uncertified Android TV boxes (BADBOX indicators per the FBI PSA).
3. Flag devices whose hostname or vendor changed for a stable MAC.

**B. Router/eero configuration (manual attestation plus observation)**
4. UPnP enabled? Detect via an SSDP M-SEARCH for an `InternetGatewayDevice` on the gateway. List active port mappings via IGD SOAP.
5. Port forwards / IPv6 firewall rules present? (Manual from app, cross-checked with an external scan.)
6. WPA3 enabled? Inspect beacons for the RSN AKM suite: SAE (8) present means transition or WPA3. PMF bits MFPC/MFPR.
7. Guest network on, and are IoT devices on it? (Check which subnet each device received.)
8. eero account uses Amazon login with MFA (manual).
9. eeroOS version current (manual/app; compare to eero release notes).

**C. Device exposure (LAN)**
10. Open ports per host (`nmap -sV`). Flag telnet (23), FTP (21), SMB (139/445), RTSP (554), unauthenticated MQTT (1883), HTTP admin on 80/8080, ADB (5555), VNC (5900), SSH with password auth.
11. Known CVEs for service versions (vulners NSE / NVD API). Prioritise CISA KEV matches.
12. Default credentials on admin UIs (Nuclei default-login templates, nmap `http-default-accounts`). Own devices only.
13. Weak TLS/SSH config (ssl-enum-ciphers, ssh2-enum-algos). Expired or self-signed certs.
14. Devices advertising UPnP/SSDP or mDNS services (upnp-info, dns-service-discovery).

**D. External exposure**
15. Scan the public IPv4 from an external vantage point you control (cloud VM) on top TCP/UDP ports.
16. Scan globally routable IPv6 addresses of LAN hosts from outside (verifies the eero IPv6 firewall).
17. Shodan/Censys lookup of your own public IP (API) for historical exposure.
18. Check whether the public IP appears on abuse/blocklists (AbuseIPDB, Spamhaus). That suggests a compromised device or proxyware.

**E. DNS**
19. Which resolver is actually in use (DHCP-provided DNS; leak test).
20. Is filtering effective? Resolve a known malware test domain or blocklisted domain.
21. Is bypass possible? Attempt direct UDP/53 to 8.8.8.8 and TCP/853 to 1.1.1.1. Test the `use-application-dns.net` canary response. Test `mask.icloud.com` resolution.
22. Does IPv6 RDNSS hand out a different DNS server than the IPv4 setting?

**F. Wireless**
23. Rogue/evil-twin detection: beacons with your SSID from unknown BSSIDs, or with a different security suite (Kismet APSPOOF/ADVCRYPTCHANGE).
24. Deauth/disassoc flood detection against your BSSIDs.
25. Clients without PMF support (NOCLIENTMFP). WPS IE present in beacons.

**G. Behaviour (if a firewall or SPAN sensor exists)**
26. Per-device outbound connection counts, bytes and destination diversity, to spot residential-proxy or botnet behaviour (Zeek conn.log / firewall logs).
27. Suricata alert summary (ET Open rules) per device.
28. DNS query anomalies from Pi-hole/AdGuard logs: high-entropy names, newly registered domains, sudden spikes.

Output: a scored report mapped to the NSA/NIST checklist items, with a "manual checks" section for settings that can't be observed on eero.

### Gaps
- Found no supported public eero API. Automating reads of eero settings would rely on unofficial reverse-engineered clients, which may break and may conflict with eero's terms of service. Not verified here.
- No sources were retrieved for the AbuseIPDB/Spamhaus/CISA KEV/NVD APIs in this session. Their use above is based on general knowledge.
