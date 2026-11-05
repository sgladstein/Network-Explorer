# Network Explorer: project plan

Status: **draft for review**. Nothing beyond the prototype gets built until this plan is agreed.

## Goal

Find out why the internet is much slower in some parts of the house even though Wi-Fi and eero signal show full strength. Then fix it by moving eero units (or another change) and re-test to prove it worked.

Security work from the research report is out of scope until this goal is met.

## Your setup and the leading suspect

| Unit | Model | Connection |
|---|---|---|
| Main eero | J010011: eero's model list identifies this as the **eero (2nd generation)**, a 2019 dual-band Wi-Fi 5 unit with 2 Ethernet ports ([eero model numbers](https://eero.com/support/articles/what-are-the-model-numbers-for-each-eero)) | Wired to the AT&T gateway |
| Satellite A | eero (2nd gen) | Wireless; a computer is wired into it |
| Satellite B | eero (2nd gen) | Wireless |
| Extender | eero 6 Extender (dual-band Wi-Fi 6, no Ethernet ports) | Wireless |

Observed: on Wi-Fi in the room with the main eero, internet is **about twice as fast** as in the rest of the house, even though signal is full strength everywhere.

**Leading suspect: wireless backhaul on dual-band units.** None of the four units has a radio reserved for eero-to-eero traffic. eero says its units share all bands between devices and backhaul. So on each satellite, one 5 GHz radio has to receive data from the main eero and resend it to your device, which roughly halves the speed. A device on a satellite that connects through another satellite, rather than straight to the main eero, pays that cost twice. Forum reports put the penalty for wireless backhaul on eero 6-class hardware at up to half ([eero community: wireless backhaul speeds](https://community.eero.com/t/x2ht09b/wireless-backhaul-speeds), [Best Buy Q&A](https://www.bestbuy.com/site/questions/eero-6-dual-band-mesh-wi-fi-6-extender-1-pack-add-on-only-white/6433423/question/cd28f526-91c5-343f-a949-c835dabfadc2)). "Twice as fast near the main eero" matches that pattern. These are user reports rather than lab measurements, so Phase 0 has to confirm it on your network.

Other suspects still to rule out: daisy-chaining, satellites placed too far from the main eero, and the older Wi-Fi 5 units limiting the extender.

If wireless backhaul is confirmed, the fixes in order of effect are:
1. **Wired backhaul** to the satellite(s) covering the slow areas, using Ethernet, MoCA over existing coax, or powerline as a last resort. The 2nd-gen units have Ethernet ports. The extender has none, so it can't be wired. The cable must come from the **eero side** (the main eero's spare port or a switch behind it), not from the AT&T gateway's other ports. Otherwise the satellite lands on AT&T's network instead of the mesh.
2. **Placement**: make every satellite connect directly to the main eero, not through another satellite, and halfway rather than at the edge.
3. **Newer hardware**: units with stronger backhaul. This costs money, so we'd decide it with data from steps 1–2.

## Why "full signal" can still be slow

Signal bars only describe one hop: the device's radio link to the nearest eero. Internet traffic from a far room crosses several hops, and the slowest one sets the speed:

```
 Device ──(1) Wi-Fi link──► nearby eero ──(2) backhaul──► … ──► gateway eero ──(3) WAN──► ISP ──► internet
```

| Hop | Can be slow with full bars because… |
|---|---|
| **1. Device ↔ eero** | 2.4 GHz instead of 5/6 GHz, narrow channel, older device Wi-Fi standard, busy airtime (many devices or neighbours), interference that hurts quality but not signal strength |
| **2. eero ↔ eero (backhaul)** | Wireless backhaul shares airtime. On dual-band models the same 5 GHz radio usually serves both clients and backhaul, roughly halving speed (to be confirmed for your models). Daisy-chained units (A→B→C) lose speed at every hop. Wired backhaul can negotiate 100 Mbps on a bad cable or port, or be limited by powerline/MoCA adapters or an old switch. |
| **3. Gateway ↔ ISP** | Affects every room equally, so it can't explain room-to-room differences. It sets the ceiling and shows whether latency rises under load (bufferbloat). |
| **Other** | One specific device being slow; a node overloaded by busy clients; evening congestion |

The project's job is to say **which hop** loses the speed in each slow room, with numbers.

## Approach: let eero and the wired computer do the measuring

Walking around with a phone running tests is tedious, and you can't control which eero the phone connects to. So the primary data sources are automatic:

| Source | What it gives | How often |
|---|---|---|
| **eero cloud API** (collector) | Which eero every device is on; each device's band, channel, signal and link rates; each eero's status, client count and Ethernet port speeds; channel utilisation per eero per band; live per-device throughput; eero's own speed test from the main eero (the AT&T baseline) | Every 1–2 minutes; speed test hourly |
| **Wired Windows computer on Satellite A** | An internet speed test, plus latency under load, through Satellite A's backhaul with no Wi-Fi device link involved | Hourly, automatically |
| *Optional:* Android app | Spot checks in a specific room | When wanted |

**Not confirmed yet:** whether eero's data includes the eero-to-eero link quality and which unit each satellite connects through. The app shows these, so the data probably has them. The snapshot tool (Phase 0) checks.

How the results read:

| Pattern | Weak link |
|---|---|
| Wired computer on Satellite A gets about half of eero's own speed test at the same time | Satellite A's backhaul (wireless backhaul penalty) |
| Devices on a satellite have high link rates, but their live throughput stays capped and that satellite's 5 GHz utilisation is high | That satellite's backhaul |
| A satellite connects through another satellite | Daisy chain: an extra hop and extra loss |
| eero's own speed test is low | ISP/WAN |
| Slow only at certain times | Congestion |

**Fix-and-verify:** log the change ("ran Ethernet to Office eero", "moved Satellite B 3 m toward the hallway"). The hourly tests and eero history then show before and after without anyone running tests by hand.

## How the pieces fit together

```
 eero cloud API ◄──── eero collector ────┐
                                          ├──► Core service on the wired Windows computer
 hourly speed tests (same computer) ─────┘     (Python, SQLite, web report at http://localhost:…)
 Optional: Android app ──────────────────────► LAN test endpoints on the core
```

- **Core service**: one Python program (SQLite storage, web report). It runs on the Windows computer wired to Satellite A, started at boot as a scheduled task. The prototype survey server's code (FastAPI and SQLite) is the starting point.
- **eero collector**: inside the core, built on the maintained `eero-api` library. It signs in once with your email and code, then keeps the session on that computer only. It uses only reading endpoints, apart from eero's own speed test, which it triggers hourly.
- **Speed tester**: inside the core. Runs an internet speed test hourly and logs it next to eero's gateway result.
- **Report**: topology (which unit connects through which), the satellite penalty over time, per-unit load and client link rates, and before/after for each logged change.

### Data model

| Entity | Meaning |
|---|---|
| eero unit | Model, location, gateway or satellite, ports |
| Client device | MAC, name, manufacturer |
| Snapshot | At time *t*: each device's eero, band, signal and rates; each unit's status, clients and upstream link (if exposed); channel utilisation |
| Speed test | Time, source (eero gateway, wired computer, phone), down/up/latency |
| Change | Time and description of a change you made |
| *(Phone app only)* Floor, spot, measurement | Kept from the prototype for optional spot checks |

## Phases

### Phase 0: eero snapshot (done 2026-11-05)
- Run [`tools/eero-dump`](../tools/eero-dump/) once on the Windows computer. It is read-only and signs out at the end.
- In the same sitting, run a speed test on that computer, and run eero's speed test in the eero app.
- **Exit:** we know which fields your eeros expose, in particular backhaul and upstream link, and have a first penalty number.

#### Results

**Topology** (from eero's `connection_type`, `wired` and `wireless_upstream_node` fields):

```
 AT&T gateway ──wired 1 Gbps──► Hope Office (only wired eero)
                                   │ wireless 5 GHz
                                   ▼
                                 Hallway (also serves 10 devices)
                                   │ wireless 5 GHz        │ wireless 5 GHz
                                   ▼                       ▼
                           Scott Office              Living Room (eero 6 Extender)
                    (Windows PC wired, 1 Gbps)
```

This is a daisy chain: Scott Office and Living Room reach the internet through Hallway, so their traffic crosses **two** wireless hops, and Hallway's single 5 GHz radio carries both satellites plus its own clients. Hope Office's two ports are both in use (gateway uplink at 1 Gbps, a Peloton at 100 Mbps). The eeros run in bridged mode; the AT&T gateway routes.

**Speed tests, same evening:**

| Source | Down (Mbps) | Up (Mbps) |
|---|---|---|
| eero app test (measured at Hope Office) | 390 | 390 |
| Windows PC wired into Scott Office, Ookla CLI, 4 runs | 104–116 | 115–124 |

The PC gets **about 29% of the internet speed** after two wireless hops. Both hops share one 5 GHz radio per unit and the same channel (153, 80 MHz, on all four units), so the data crosses the air twice and uses twice the airtime: that alone roughly halves throughput in total (not per hop). Rough budget: an 867 Mbps link delivers ~500 Mbps in practice (assumed ~60% efficiency), ~250 Mbps across two hops on one channel, perhaps 150–200 Mbps with the channel already 14–37% busy per unit (Scott Office busiest) before testing. The measured ~112 is below that, so the shared channel explains most of the drop but probably not all; the backhaul links may run below 867 (eero doesn't report their rate), or other traffic or the PC may contribute. The PC hasn't yet been tested on a different path. The PC's own cable negotiates 1 Gbps at both ends, and VPNs were ruled out (Tailscale had no exit node; Ookla saw AT&T as the ISP). Latency rose from ~9 ms idle to 90–135 ms during uploads, so a queue builds on the path.

**What eero's API exposes:** backhaul type and upstream unit for every eero (yes); backhaul link rate (no, only `mesh_quality_bars`, which shows 5/5 on every unit and so isn't informative); Ethernet port negotiated speeds (yes); per-client band, channel, signal and link rates (yes); channel utilisation: the dedicated endpoint needs eero Plus (HTTP 403), but per-unit busy percentages appear elsewhere in the dump.

**Next test (to prove it):** plug the PC, or any computer with Ethernet, into Hope Office (port 1, unplugging the Peloton temporarily; its link is 1 Gbps-capable but currently negotiates 100 Mbps, so confirm the test link comes up at 1 Gbps). About 390 there means the wireless path is the problem; about 110 means the PC is. A second test wired into Hallway shows what one hop costs versus two.

**Fixes to try once confirmed, in order:**
1. **Wired backhaul to Hallway or Scott Office.** A cable from the eero side (a small gigabit switch behind Hope Office, since both its ports are in use) to Scott Office's spare port takes both wireless hops out for the PC. Wiring Hallway instead helps all three downstream units.
2. **Break the daisy chain.** Move Scott Office (or Hope Office) so Scott Office connects straight to Hope Office: one wireless hop instead of two, expected roughly 2× on the PC.
3. Re-run the snapshot and the PC speed test after each change to confirm.

### Phase 1: Automatic collection
- Core service on the Windows computer:
  - eero collector polling every 1–2 minutes, keeping history;
  - hourly speed tests from the computer, plus eero's speed test;
  - a basic web report.
- Runs on its own after an install step and a one-time sign-in.
- **Exit:** a few days of history and a report that states each satellite's link type, its upstream unit and the measured penalty.

### Phase 2: Fix-and-verify loop
- Change log and before/after comparisons, plus suggested fixes such as wiring the backhaul, moving a unit, or removing a daisy chain.
- **Exit:** at least one change made and verified with before/after numbers.

### Phase 3: Optional extras
- The Android app for room spot checks (the existing prototype, adapted).
- More probes, and time-of-day analysis.
- Then the security track from the research report.

## What happens to the prototype

- **Survey server:** its FastAPI/SQLite code becomes the base of the core service. The floor-plan survey parts become optional.
- **Android app:** stays on the branch for Phase 3 spot checks. CI keeps building it.
- **Manual checklist:** the walk-around test list from the earlier draft is no longer needed. The wired computer plus eero data cover the same questions automatically.

## Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| 1 | Our own core service, or extend an existing eero dashboard (Dashboard_EERO / eeroVista) | Our own core. Their focus is dashboards, ours is per-hop diagnosis and survey data, but reuse the `eero-api` library they're built on. |
| 2 | Speed test used by the Windows computer | Ookla's Speedtest CLI (free for personal use, and the same service as speedtest.net), with Cloudflare's speed-test endpoints as the fallback. |
| 3 | Where the core service runs | The Windows computer wired to Satellite A. |

## Answers so far

- **Setup:** see the table above.
- **"Full strength":** yes on all three: phone bars, the device signal in the eero app, and the eero units' status.
- **Computers:** a Windows computer is wired to Satellite A. Nothing is wired to the main eero.
- **Approach:** collect data from eero and the wired computer automatically rather than by walking around (agreed).
- **eero login:** email, so the unofficial eero API works.

## Open questions

1. **AT&T gateway mode:** is the AT&T gateway in IP Passthrough, with the eero acting as the router, or is the eero itself in bridge mode? AT&T gateways usually offer passthrough rather than a true bridge. The answer decides which eero features and API data are available.
2. **AT&T plan speed:** and roughly what you measure near the main eero versus elsewhere.
3. **Wiring:** any Ethernet runs, or coax outlets, near the units?
4. **Always on:** does the Windows computer stay on all the time? Hourly tests need it awake, or allowed to wake for them.
