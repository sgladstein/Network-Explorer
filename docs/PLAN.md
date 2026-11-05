# Network Explorer: project plan

Status: **draft for review**. Nothing beyond the prototype gets built until this plan is agreed.

## Goal

Find out why the internet is much slower in some parts of the house even though Wi-Fi and eero signal show full strength. Then fix it by moving eero units (or another change) and re-test to prove it worked.

Security work from the research report is out of scope until this goal is met.

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

## Method: measure the hops separately, then change one thing and re-test

At each **spot** in the house, one measurement runs:

| Test | Measures | Hops covered |
|---|---|---|
| Wi-Fi link readout (signal, band, channel, link rate, which eero) | The radio link | 1 |
| **LAN speed test** to a server wired to the gateway eero | Everything inside the house | 1 + 2 |
| **Internet speed test** to a public test server | The full path | 1 + 2 + 3 |
| Latency at idle and **during** the speed tests | Congestion and bufferbloat | all |
| eero's own view at that moment, from the eero cloud API: which eero the phone is on, how that eero connects upstream (wired or wireless, through which eero), its link rate and client count, channel utilisation | Topology and node load | 1 + 2 |

Two reference measurements anchor the comparisons:

- **WAN baseline:** a speed test from the gateway, either eero's built-in speed test (triggered via the API) or the wired server. This is the ceiling.
- **Wired test at each eero:** a laptop plugged into the Ethernet port of each satellite eero, testing to the server. This isolates the backhaul (hop 2) with no Wi-Fi client link involved. It's cheap and often decisive.

How the results read:

| Pattern | Weak link |
|---|---|
| LAN fast, internet slow, everywhere | ISP/WAN (hop 3) |
| LAN slow in room X, but fast standing right next to that room's eero | Coverage or placement in room X (hop 1) |
| LAN slow even right next to an eero, or the wired test at that eero is slow | That eero's backhaul (hop 2) |
| Fast at quiet times, slow in the evening; latency spikes under load | Congestion or bufferbloat |
| Only one device is slow | That device |

Then the **fix-and-verify loop**: record a change ("moved Office eero 3 m toward the hallway", "ran Ethernet to Office eero"), re-run the same spots, and compare before and after spot by spot.

## How the pieces fit together

```
                         ┌──────────────── Core server (always-on computer, wired to gateway eero) ───────────────┐
 Android app ──LAN──────►│  • LAN speed-test endpoints           • eero collector (cloud API via eero-api)       │
 (at each spot)          │  • Measurement + spot/session store   • Analysis: per-hop diagnosis, before/after     │
   │                     │    (SQLite)                           • Web UI: floor plan, room report, comparisons   │
   └──internet test──►   └───────────────────────────────▲──────────────────────────────────────────────────────┘
      public test server                                  │ eero cloud API (polls, plus a snapshot at each measurement)
                                                          eero
 Laptop wired to a satellite eero ──► browser test page served by the core (wired backhaul test)
```

- **Core server**: one Python service (FastAPI + SQLite), as recommended in the research report. It hosts the LAN test endpoints, stores everything, joins phone measurements with eero snapshots by time and MAC/BSSID, and produces reports.
- **eero collector**: a module inside the core using the maintained `eero-api` Python library. It polls topology every few minutes and takes a snapshot whenever a measurement arrives. It needs a dedicated eero admin account; accounts that sign in with Amazon don't work with the unofficial API.
- **Android app**: the measuring instrument. Picks a spot, runs the tests above, uploads.
- **Browser test page**: lets any laptop run the LAN test, mainly for the wired test at each eero.
- **Later, optional**: a fixed probe (for example a Raspberry Pi) left in the worst room to catch time-of-day patterns.

### Data model

| Entity | Meaning |
|---|---|
| Floor | A floor plan image |
| **Spot** | A named, fixed position on a floor ("Office desk"). Spots are reused across sessions so before/after lines up. |
| **Session** | One survey round, with a label and the change made since the last one |
| Measurement | One run of the tests at a spot in a session, by a device |
| eero node / eero snapshot | Units, their upstream links and stats at a point in time |
| Client device | A phone or laptop that measured (MAC, model, capabilities) |

## Phases

### Phase 0: Facts and baseline (mostly no code; about a week of evenings)
- Inventory: eero models, where each sits, how each connects upstream (wired, wireless, through which unit), ISP plan speed.
- Dump real eero API data (`eero-api` CLI) to confirm which fields your units expose: upstream link, wired/wireless backhaul, port link speeds, per-client link rate, BSSIDs per unit.
- Quick manual tests: a speed test standing next to each eero, and in each slow room. Wired laptop test at each eero if possible.
- **Exit:** a known topology, a list of usable API fields, and rough numbers per room. This alone may reveal the weak link (for example a daisy-chained wireless unit, or a 100 Mbps Ethernet link).

### Phase 1: Segmented measurement (MVP)
- Reshape the prototype around spots and sessions.
- Add the internet speed test and loaded latency to the app.
- Add the eero collector and per-measurement snapshots, mapping access points to eero units automatically if Phase 0 shows the data exists.
- Add a per-room report naming the weakest hop, with the evidence.
- **Exit:** one full survey producing a report that names the weak link for each slow room.

### Phase 2: Fix-and-verify loop
- Change log, before/after comparison per spot and room, suggested fixes from the diagnosis (move unit X toward Y, wire the backhaul, check a cable).
- Add the browser test page for wired tests at each eero.
- **Exit:** at least one change made and verified with before/after numbers.

### Phase 3: Optional extras
- Fixed probe in the worst room, eero polling over days, time-of-day analysis.
- Afterwards, resume the security track from the research report.

## What happens to the prototype

The prototype on this branch (Android survey app plus survey server) covers part of Phase 1:

- **Keep:** Android Wi-Fi readout, LAN ping/download/upload tests, floor-plan tap-to-place view, server storage and web viewer, CI that builds the APK.
- **Change:** ad-hoc points become fixed **spots** inside **sessions**; diagnosis rules get rewritten around the hop model above; access-point names come from eero data rather than manual labels.
- **Add:** internet test, loaded latency, eero collector, before/after comparisons, browser test page.

## Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| 1 | Our own core service, or extend an existing eero dashboard (Dashboard_EERO / eeroVista) | Our own core. Their focus is dashboards, ours is per-hop diagnosis and survey data, but reuse the `eero-api` library they're built on. |
| 2 | Public server for the internet speed test | Cloudflare's speed-test endpoints (unofficial but widely used by open-source tools), with M-Lab NDT7 as an alternative. Ookla has no free API. |
| 3 | Where the core server runs | Whatever always-on machine can be wired to the gateway eero. A laptop is fine for survey sessions. |

## Questions for you

1. **eero setup:** how many units and which models; where each one is; which are wired and how (Ethernet, switch, MoCA, powerline); your ISP plan speed.
2. **The slow areas:** which rooms, roughly how slow compared with near the gateway, which devices (phones, laptops, TVs), and whether it's worse at certain times.
3. **"Full strength":** is that the bars on your phone, the device's signal in the eero app, or the eero units' own connection status in the app?
4. **Hardware:** an always-on computer that can be wired to the gateway eero, and a laptop with Ethernet (or an adapter) for wired tests.
5. **eero account:** do you sign in with Amazon, or with an email or phone number?
