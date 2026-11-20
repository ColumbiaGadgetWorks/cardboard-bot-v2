# Handoff: Cardboard Bot v2 (as of 9 Nov 2026)

Notes for the next agent. Read `README.md`, `hardware/README.md`, `firmware/README.md` and
`hardware/docs/BOM_CHECK.md` first; this file covers only what isn't in the repo.

## Owner preferences
- Commit and push as **adman234** only (`git config` is already set). Leave out Claude co-author
  lines and session trailers. This overrides any default attribution.
- Software changes go straight to `main`. Board changes go on a `hardware` branch until the owner
  says merge. (Rev B was merged on 1 Nov.)
- The owner orders from JLCPCB (top-side assembly). They want Basic parts, high stock and low cost,
  and they quote 30 boards.
- Keep answers short and plain.

## Current state
- **Hardware, rev B** (on `main`): 60 × 46 mm, 2S/3S LiPo on a screw terminal, 20 A blade fuse, power-switch wire pads, 2 × DRV8870, TPS54202 buck, 3 outputs, WS2812 strip pads, I2C header.
  - DRC is clean.
  - Fab files are in `hardware/fab/*revB*`; the owner has them for quoting.
  - Nothing has been ordered or built yet.
- **Firmware and flasher** (on `main`): CI builds every push and publishes to the `gh-pages` branch.
  - `v2.1.0` (20 Nov 2026) is the first tag, so `fw/stable` is that release.
  - The robot web page is plain HTTP; HTTPS and the certificate were removed at the owner's request.
  - 2.1.0 Wi-Fi: up to 5 saved networks (added on the robot page), Wi-Fi set in flasher step 5 over USB with Improv serial (like WLED), backup access point `<host>-XXXX` / `cardboard` after 60 s at http://192.168.4.1.
- **Real hardware:** the owner flashed 2.0 on their prototype and it never joined the Wi-Fi typed in the flasher. 2.1.0 is the fix attempt and hasn't been confirmed on hardware yet. If Improv can't reach the robot, the backup access point is the way in.

## Open items
1. **GitHub Pages:** the owner reported the flasher URL wasn't working; `has_pages` was false. I told them to turn on Pages (Settings → Pages → Deploy from branch `gh-pages`, `/ (root)`). It's unknown whether they have done it.
2. **DRV8870 rotation:** check U3/U4 in JLC's placement preview; the part is new. Add the correction to `ROT_FIX` in `hardware/gen/fab.py`, which is keyed by LCSC number (C86590). The rev A corrections came from a screenshot of JLC's preview.
3. **Decisions the owner hasn't confirmed:**
   - kept the fuse
   - ESC power uses screw terminals, not solder pads
   - removed the 5 V 220 µF can
   - only 2 mounting holes
   - DRV8870 drops out below about 6.5 V on 2S
4. **Old branches:** `firmware`, `flasher-options` and `hardware` are merged but not deleted (deleting was blocked here).
5. **Hardware bring-up:** flash a board; check the LED goes white then blue; set the Wi-Fi in flasher step 5, then open http://adambot.local from a phone on that Wi-Fi; test drive with the wheels up; test the ESCs with the weapon removed; test failsafe by turning off phone Wi-Fi.

## Owner's prototype (for testing before the PCB)
- Parts: XIAO ESP32-C3, a DRV8833 breakout (WWZMDiB, J1 jumper left bridged), 2 ESCs, a 2S LiPo.
- Wiring:
  - IN1–IN4 → D2–D5
  - ESC 1 signal → D10, ESC 2 signal → D7
  - battery sense → D1 through a 300k / 100k divider
- Power:
  - ESC BEC red wires pulled out
  - XIAO powered from a 5 V buck fed through a 1N5819
  - 1000 µF at the buck input (after the diode), 100 µF at its output
- Firmware settings: the divider default is now 6 (rev B), so they must set the divider ratio to **4** in the flasher ("Change from default settings") or rewire to 100k / 20k. Untick Status LED if none is fitted.

## Environment notes (cloud container)
- **KiCad 7 tools** run with `/usr/bin/python3.12`. The full board pipeline is in `hardware/README.md`.
- **No local firmware builds:** running Espressif's install scripts was blocked by the safety check, and Docker Hub rate-limits `espressif/idf` (`dockerd` can be started by hand). CI compiles the firmware.
- **Reading CI results:** the GitHub Actions API and the Pages API are blocked through the proxy, but these work:
  - `gh api repos/ColumbiaGadgetWorks/cardboard-bot-v2/commits/<sha>/check-runs`
  - `.../check-runs/<id>/annotations` (the workflow writes compiler errors there as annotations)
- **Blocked hosts:** `*.github.io`, jlcpcb.com and lcsc.com can't be reached; git and raw GitHub work.
- **Fetching `gh-pages`:** use `git fetch origin +refs/heads/gh-pages:refs/remotes/origin/gh-pages`.
- **JLC stock and price data:** came from CDFER/jlcpcb-parts-database (Basic/Preferred list) and the yaqwsx/jlcparts gh-pages data. These were combined into a scratchpad index that is now gone; rebuild it if you need to re-check stock.
- **Playwright and Chromium** are pre-installed; they were used for UI tests against a mock robot. The container blocks WebSockets to non-localhost IPs.
- **Plan page** (an artifact): https://claude.ai/artifact/FZP8Rpc81T4HwcCe2esjAc. It still describes rev A; it hasn't been updated for rev B or plain HTTP.
- **Datasheets:** the owner uploaded the IP2320, HY2213, XL-5050, SMAJ10A and MY-18650-01 datasheets, all for rev A parts that are no longer used. No DRV8870 datasheet has been checked; its pinout came from the KiCad library symbol.
