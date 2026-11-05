# Wi-Fi Survey (Android)

A walk-around Wi-Fi survey app that reports to the [Network Explorer survey server](../server/). See the [main README](../README.md) for how to use it.

## Why Android only

Android lets an app read the Wi-Fi signal strength, link rate, channel, the BSSID of the access point (which eero you're on) and nearby networks. iPhones don't give apps signal strength at all.

## What it measures

| Measurement | Source |
|---|---|
| Signal (RSSI, dBm), median of readings taken every 0.5 s during the test | `WifiInfo.getRssi()` |
| Band, channel, channel width | `WifiInfo.getFrequency()`, matching `ScanResult.channelWidth` |
| Link rate (overall, transmit, receive) and Wi-Fi standard | `WifiInfo` |
| Connected access point (BSSID) | `WifiInfo.getBSSID()` (needs location permission) |
| Nearby access points and their signal | `WifiManager.startScan()` / `getScanResults()` |
| Latency, jitter, packet loss | 20 HTTP round trips to the server |
| Download and upload speed | Timed transfers to and from the server (about 5 s each) |

All tests are sent over the Wi-Fi network (not mobile data), even if the phone has both.

### Android limits to know about

- **Scan throttling.** Android allows an app 4 Wi-Fi scans every 2 minutes. When the limit is hit, the app uses the phone's recent cached scan, if it is under 2 minutes old. To scan on every measurement, turn off **Developer options → Wi-Fi scan throttling**.
- **Location permission and the Location switch** are both required for the BSSID and scan results. Without them the app still records signal and speed, but can't tell which eero you're on.
- Readings vary between phone models. Survey with the same phone each time so that results are comparable.

## Building

The app uses only the Android framework, with no AndroidX or other libraries.

- **GitHub Actions** builds `app-debug.apk` on every push (artifact `wifi-survey-debug-apk`). Each CI build is signed with a fresh debug key, so to install a newer build over an older one you may need to uninstall the old one first.
- **Android Studio**: open the `android/` folder, wait for Gradle sync, then run it on your phone with USB debugging enabled.
- **Command line** (with the Android SDK installed and `ANDROID_HOME` set):

  ```bash
  ./gradlew testDebugUnitTest assembleDebug
  # APK: app/build/outputs/apk/debug/app-debug.apk
  ```

Requirements: JDK 17+, Android SDK platform 35. The app runs on Android 10 (API 29) and newer.

## Code layout

| File | Role |
|---|---|
| `MainActivity.kt` | Screen, permissions, measurement flow |
| `FloorPlanView.kt` | Floor plan with pinch-zoom, pan, tap-to-place and coloured dots |
| `WifiCollector.kt` | Current Wi-Fi link (network callback) and scans |
| `SurveyServer.kt` | Server API client plus the ping, download and upload tests |
| `core/Measurements.kt` | Pure Kotlin maths (median, jitter, channels, colours), unit-tested on the JVM |
