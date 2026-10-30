# Cardboard Bot v2 firmware

ESP-IDF 5.3 firmware for the Seeed XIAO ESP32-C3 on the CGW main board (`hardware/`).

- **Install it** from the web flasher: <https://columbiagadgetworks.github.io/cardboard-bot-v2/>
  (desktop Chrome or Edge, or Firefox 151+).
- **Drive:** join the robot's Wi-Fi (`CGW-<name>`), then open **https://192.168.4.1** in Chrome or
  Safari on the phone.

## What it does

| Part | Details |
|---|---|
| Wi-Fi | Robot hosts its own access point. At power-on it scans channels 1, 6 and 11 for about 0.5 s and takes the quietest. Other `CGW-` robots count three times as much as other networks. After a brownout reset it reuses the last channel. A fixed channel can be set. |
| Phone page | Served over HTTPS (the browser Gamepad API needs a secure page) with a secure WebSocket at `/ws`. It has touch sticks, gamepad input, ARM, fire buttons, settings, diagnostics and updates. Plain HTTP and DNS answer everything with a landing page that links to `https://192.168.4.1`. |
| Driver | The first phone after power-on drives, and the same phone gets control back when it reconnects. Other phones watch until they take control (with the Wi-Fi password, if one is set). |
| Drive | DRV8833, slow decay, 20 kHz. Tank, arcade (one stick) or split arcade. Settings: deadzone, expo, turn rate, ramp, extra ramp when spinning, slow mode and invert/swap. A motor voltage cap (default 6 V) scales the PWM to the live pack voltage. |
| Outputs | OUT1, OUT2, IO21 and IO3 (IO3 only when JP1 is cut). Each is an ESC (hold / toggle / variable, spin-up ramp, max %) or a servo (hold / toggle / position, rest and fire angles, speed). A second ESC starts 300 ms after the first. |
| Safety | Starts disarmed. With no packets for 300 ms the weapon goes to zero but stays armed. At 1 s it fails safe: drive stops and the light flashes amber. If the link returns within 1 s of failsafe the robot is still armed, and the weapon waits for its button to be released and pressed again. After that it disarms, and the 3rd drop in 60 s disarms even on a quick reconnect. Below 6.4 V for 2 s the weapon locks out; below 6.0 V the drive stops. Every time is a setting. |
| Status light | White blink: starting or updating · blue pulse: waiting for a phone · green: connected, safe · red: armed (fast flash: weapon running) · amber flash: link lost · purple blink: battery low |
| Updates | Two app slots with automatic rollback: a new version that doesn't stay up for 10 s is replaced by the old one. Update from the phone (upload `app.bin`) or let the robot join the club Wi-Fi and download from GitHub Pages. Blocked while armed. |

The charger has no data line to the ESP32, so the firmware can't tell when it's charging. Charge
state is the red LED by the USB-C port. Cell voltages are also not measured separately: the board
reads the pack (VSYS ÷ 4 on GPIO3), and the page shows pack ÷ 2 per cell.

## Pins and features

Everything defaults to the main board's wiring, and can be changed for a prototype or other wiring:
- in the web flasher (tick **Change from default settings**), or
- on the phone page (**Settings → Hardware**, then restart the robot).

| Setting | Default | Notes |
|---|---|---|
| Motor driver connected | on | Off: no motor pins used |
| Battery voltage reading | on, D1 (GPIO3) | Divider must be pack ÷ 4 (300k / 100k); input must be D0, D1 or D2 |
| Low-battery lockouts | on, 6.4 V weapon / 6.0 V drive | Needs battery reading |
| Status LED | on, D9 (GPIO9) | WS2812 data |
| "Sign in to network" pop-up | on | Off: no captive DNS |
| Motor IN1–IN4 | D2, D3, D4, D5 | DRV8833 inputs |
| Outputs 1–4 | D10, D7, D1, D6 | Each Off / ESC / Servo |

Two things can't share a pin. Both pages refuse to save a clash, and the firmware itself turns off a
clashing output (and resets clashing motor pins to the defaults), so a bad settings file can't drive a
pin two ways.

## Settings

Settings are JSON in the 4 KB `botcfg` partition at 0x10000. The image is `"BCFG"`, version 1,
16-bit length, then the CRC-32 of the JSON, then the JSON, padded with 0xFF. The web flasher reads
and writes the same format (`site/flasher.js`), so it can change the name and Wi-Fi settings without
touching drive or output settings. Keys and defaults: `cfg_defaults()` in `main/config.c`, names in
`main/config_json.c`.

## Building

CI builds every push (`.github/workflows/firmware.yml`) and publishes to the `gh-pages` branch:

| Path | What |
|---|---|
| `fw/<branch or tag>/` | Every build: `manifest.json`, `bootloader.bin`, `partition-table.bin`, `ota_data_initial.bin`, `app.bin` |
| `fw/beta/` | Latest `main` |
| `fw/stable/` | Latest `v*` tag (`main` until the first tag) |

Release a stable version by pushing a tag, e.g. `git tag v2.0.0 && git push origin v2.0.0`.

To build locally with ESP-IDF 5.3:

```sh
cd firmware
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

Host tests for the control logic and the settings image (no ESP-IDF needed):

```sh
cc -I firmware/main firmware/test/test_control.c firmware/main/control.c firmware/main/config.c -lm -o /tmp/t && /tmp/t
```

### Forks

A fork builds and publishes to its own Pages site, and its robots pull updates from there. The CI
passes the fork's address in as `FW_PAGES_BASE`. In the fork:
1. Enable Actions.
2. Under **Settings → Pages**, set the source to the `gh-pages` branch.

In the flasher, pick **Custom repo / branch** and enter `owner/repo` and the branch.

## Files

| File | |
|---|---|
| `main/main.c` | Start-up, 100 Hz control loop, rollback confirmation |
| `main/control.c` | Mixing, outputs, arm / failsafe / battery rules (plain C, tested on a PC) |
| `main/hw.c` | LEDC motor and servo PWM, battery ADC, WS2812 over RMT |
| `main/net.c` | Access point, channel pick, club Wi-Fi |
| `main/web.c`, `main/dns.c` | HTTPS / WebSocket server, captive landing page and DNS |
| `main/ota.c` | Download updates |
| `main/store.c`, `main/config*.c` | Settings and diagnostics storage |
| `main/www/index.html` | Phone page (gzipped into the firmware at build time) |
| `main/certs/` | The shared HTTPS certificate (see its README) |
| `partitions.csv` | nvs, otadata, botcfg, phy, two 1.875 MB app slots |
