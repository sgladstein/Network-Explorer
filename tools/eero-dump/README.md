# eero snapshot (read-only)

Takes one snapshot of what eero's cloud knows about your network. This shows which data your eero units expose before we build the automatic collector, in particular whether eero reports how each satellite connects back to the main eero.

**It doesn't change anything.** It only reads data, apart from signing in and out (the script refuses any other kind of request). It signs out when it's done, so the session it used stops working, and it stores nothing for later.

## Run it on Windows

1. **Install Python** (one time). Open **PowerShell** and run:

   ```powershell
   winget install -e --id Python.Python.3.12
   ```

   Or install it from [python.org](https://www.python.org/downloads/) and tick **Add python.exe to PATH**. Close and reopen PowerShell afterwards.

2. **Get the script.** On GitHub, open `tools/eero-dump/eero_dump.py` on the `claude/home-mesh-network-tools-lxsef7` branch and click **Download raw file**. It lands in your Downloads folder.

3. **Run it:**

   ```powershell
   cd $HOME\Downloads
   py eero_dump.py
   ```

   Enter the email you use for the eero app, then the code eero emails you. Reading takes about 30 seconds.

4. **Same sitting, for comparison:** run a speed test on this computer at [speedtest.net](https://www.speedtest.net), then run the eero app's own speed test. Note both results.

5. **Share the results.** The script writes two files in the same folder:
   - `eero-summary-<time>.txt` is a readable overview. Paste or attach it in our chat.
   - `eero-dump-<time>.json` holds the full data. Attach it if you're comfortable; it lets me see every field.

   Don't commit either file to the repository (`.gitignore` already excludes them).

## What's in the files

| Kept (needed for diagnosis) | Removed |
|---|---|
| eero units: room names, models, status, ports, connection details | Wi-Fi and guest passwords, Thread network key, session tokens |
| Devices: names, MAC addresses, which eero each is on, band, signal, link rates | Your account's email, phone number and name |
| Speed-test history, channel utilisation, neighbouring networks, recent events | Public IP addresses (yours and your devices' IPv6) |
| | Serial numbers, location (city, coordinates) |

Run `py eero_dump.py --anonymize` to also replace device names and MAC addresses with stand-ins. The manufacturer part of each MAC address is kept.

## Notes

- It uses eero's undocumented app API, the same one the open-source [eero-api](https://github.com/fulviofreitas/eero-api) library and Home Assistant integrations use. It makes about 20 requests, well under eero's rate limit.
- Accounts that sign in with Amazon can't use this API. Yours uses email, so it works.
- Some sections may show "skipped" if your eero model doesn't support them. That is useful information in itself.
