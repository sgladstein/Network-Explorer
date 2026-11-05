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

### Phase 0: Confirm the suspect (no code; one or two evenings)
Use the same phone and the same speed-test app throughout (for example speedtest.net). Run 3 tests at each place and note the middle result.

1. **eero app:** for each eero, note its connection type (wired or wireless) and which eero it connects through. Note whether the app shows any end-of-support or update notice for the 2nd-gen units.
2. **Baseline:** phone about 2 m from the main eero. Also note your AT&T plan speed.
3. **Next to each satellite:** phone about 2 m from Satellite A, Satellite B and the extender. Slow even right beside a unit means that unit's backhaul is the bottleneck, not coverage.
4. **Wired computer on Satellite A:** run the speed test there. This measures that unit's backhaul with no Wi-Fi device link involved. About half the baseline confirms the wireless-backhaul penalty.
5. **Slow rooms:** phone in each slow room. Note which eero the phone is on (the eero app shows it).
6. **One experiment:** move Satellite A temporarily to a spot with a clear view of the main eero and repeat step 4.
   - If the speed rises a lot, placement is the issue.
   - If it stays at about half, the cause is the radio sharing itself, and the fix is wired backhaul or new hardware.
7. **Wiring options:** note any Ethernet runs or coax outlets near the main eero and each satellite.

Optional: dump real eero API data (`eero-api` CLI, signing in with your email) to see which fields Phase 1 could use.

**Exit:** a filled-in table of speeds by place. Either the suspect is confirmed and we pick a fix, or it's ruled out and Phase 1 hunts further. If Phase 0 settles it, Phase 1 can be scaled down to before/after verification.

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

## Answers so far

- **Setup:** see the table above.
- **"Full strength":** yes on all three: phone bars, the device signal in the eero app, and the eero units' status.
- **Computers:** one computer is wired to Satellite A. Nothing is wired to the main eero yet. For the LAN test, the core server would ideally sit on the main eero's spare port, but the computer on Satellite A can host it during Phase 1 with that caveat.
- **eero login:** email, so the unofficial eero API works.

## Open questions

1. **AT&T gateway mode:** is the AT&T gateway in IP Passthrough, with the eero acting as the router, or is the eero itself in bridge mode? AT&T gateways usually offer passthrough rather than a true bridge. The answer decides which eero features and API data are available.
2. **AT&T plan speed:** and roughly what you measure near the main eero versus elsewhere.
3. **Wiring:** any Ethernet runs, or coax outlets, near the units?
