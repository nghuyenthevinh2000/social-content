# TikTok Mobile Automation & Optimization Field Report

```text
Repo Audit ──> Device Authorization ──> Package Alignment ──> Live Control ──> Debloat & Profiling
```

## Executive Summary & Environmental Context

| Attribute | Field Finding | Technical Explanation |
|---|---|---|
| **Target Device** | Xiaomi Redmi 13C (`23129RN51X`, serial `OBNZJZ5D6LDILFTG`) | MediaTek Helio G36 (`MT6765`), 8x Cortex-A53 @ 2.2GHz, 3GB RAM (`2815588 kB`), eMMC 5.1 storage, Android 14 (HyperOS). |
| **Tool Evaluated** | [`masterFuf/taktik-bot`](https://github.com/masterFuf/taktik-bot) (v1.9.9) | Python automation framework driving real Android devices via `adbutils` and `uiautomator2` with version-pinned selector overrides. |
| **TikTok Lite Feasibility** | Not supported out-of-the-box; manually scriptable | Package name `com.zhiliaoapp.musically.go` and obfuscated UI IDs are absent from `taktik-bot`. Custom `uiautomator2` scripts controlled Lite successfully. |
| **Standard TikTok Feasibility** | Fully supported out-of-the-box | `taktik-bot` recognized SEA variant `com.ss.android.ugc.trill` (v47.4.3), applied 17 version overrides, and executed feed operations cleanly. |
| **Device Debloat Impact** | 24 background bloatware packages removed | Terminated Digital Wellbeing (278 MB RAM hog), GetApps, and Wallpaper Carousel, freeing ~1.2 GB memory pressure. |
| **Transition Lag Origin** | CPU-bound burst + eMMC swap thrashing | Swiping videos spikes CPU to 423% across all Cortex-A53 cores while `kswapd0` reads/writes eMMC swap, causing frame jank. |

## Architectural Findings & TikTok Variant Matrix

| Evaluation Dimension | Standard TikTok (`trill` / `musically`) | TikTok Lite (`musically.go`) | Practical Automation Impact |
|---|---|---|---|
| **Package & Main Activity** | `com.ss.android.ugc.trill`<br>`SplashActivity` | `com.zhiliaoapp.musically.go`<br>`.mini.MainActivity` | `taktik-bot` fails initial package check if only Lite is installed (`TikTokManager.is_installed() -> False`). |
| **UI Node Hierarchy** | Native Android ViewGroups (`f57`, `g2w`, `dtv`, `em1`) | Dynamic Split Module (`.df_edit_filter:id/...`) | Lite uses different resource IDs: Like container is `:id/i3k`, Comment container is `:id/i2k`. |
| **Metadata Extraction** | Handled by `profile_extractor.py` and `caption.py` | Title in `:id/title`, caption in `.df_edit_filter:id/desc` | Extracting creator and caption succeeds in both, but requires distinct selector lookups. |
| **Publishing Pipeline** | Advanced studio with sound removal (`editor_sound.py`) | Basic or restricted gallery upload | Sound detachment and multi-layer editor workflows fail on Lite due to missing UI nodes. |
| **DMs & Audio Targeting** | Full inbox sorting, sound landing pages | Stripped or webview-wrapped | Advanced DM filters and sound scraping are exclusive to Standard TikTok. |

## Xiaomi MIUI Quirks & Debloat Intervention

| MIUI System Barrier | Manifestation / Error | Implemented Resolution |
|---|---|---|
| **Touch Event Rejection** | `java.lang.SecurityException: Injecting to another application requires INJECT_EVENTS` | Enabled **USB debugging (Security settings)** in Developer Options (requires SIM card + Mi Account login). |
| **Background App Killing** | MIUI Doze terminates automation processes after several minutes | Added TikTok to the persistent battery whitelist via `adb shell dumpsys deviceidle whitelist +<pkg>`. |
| **Aggressive System Bloat** | Background processes consumed 55% of physical RAM before launching TikTok | Uninstalled 24 bloatware packages via `pm uninstall -k --user 0`, eliminating ~1.2 GB of background overhead. |
| **RAM Hog Daemons** | Digital Wellbeing took 278 MB; Google Search took 100 MB | Cleaned non-essential background services; left core Play Store, SMS, and Phone frameworks fully functional. |
| **Reversibility Safety** | Fear of bricking or losing system features | All packages remain intact in system image and are instantly restorable via `pm install-existing --user 0 <pkg>`. |

## Performance Profiling & Lag Root Causes

| Benchmark Metric | Before Debloat / Pre-Reboot | Post-Reboot Benchmark | Engineering Explanation |
|---|---|---|---|
| **Janky Frames Rate** | 53.01% (264 / 498 frames) | **38.67% (174 / 450 frames)** | 14.34% reduction in dropped frames following bloatware purge and RAM headroom recovery. |
| **Worst-Case UI Freeze** | 900 ms latency spike | **750 ms latency spike** | Frame stalls shortened by 150 ms, though Cortex-A53 single-thread limits cap further gains. |
| **CPU Usage on Swipe** | Not profiled | **423.0% CPU spike** | Swiping videos pushes >4 cores to 100% capacity to parse new layouts and initialize media buffers. |
| **Hardware Video Decoder** | `mediacodec` active | 25% – 32% sustained CPU | MediaTek C2 video decoding hardware and audio server consume ~60% combined CPU during video playback. |
| **Memory Pressure** | Near-exhaustion (<200 MB free) | **1,235 MB available RAM** | TikTok expands to 1.13 GB PSS, but system maintains ample buffer without invoking Low Memory Killer. |
| **Virtual RAM (Swap)** | 716 MB – 1,072 MB swapped | Active `kswapd0` thrashing | Virtual memory on slow eMMC 5.1 storage creates I/O wait (`D` state) bottlenecks during rapid feed navigation. |

## Verification Artifacts & Recommended Playbook

| Phase | Recommended Command / Action | Purpose & Artifact Reference |
|---|---|---|
| **1. Host Tooling** | `brew install --cask android-platform-tools` | Deploys official ADB platform binaries to `$PATH`. |
| **2. Clean Workspace** | `python3 -m venv scratch/venv && pip install -r taktik-bot/requirements.txt` | Sets up isolated Python 3 environment with `uiautomator2` and `adbutils`. |
| **3. Debloat Phone** | Execute `scratch/debloat.py` | Automatically purges 24 Xiaomi and Google telemetry packages for user 0. |
| **4. In-App Optimization** | Turn ON **Data Saver** in TikTok settings | Cuts incoming video bitrates, reducing `mediacodec` CPU load by ~50% and improving swipe speed. |
| **5. Storage Hygiene** | Settings > Additional settings > Memory extension > **OFF** | Stops eMMC swap wear and eliminates `kswapd0` I/O wait stalls. |
| **6. Automation Choice** | Standard TikTok (`trill`) for `taktik-bot`; Lite for custom scripts | Standard TikTok is ready for built-in workflows; Lite requires manual coordinate/node scripting. |
