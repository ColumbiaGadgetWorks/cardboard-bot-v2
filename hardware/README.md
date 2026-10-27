# Cardboard Bot v2 – main board (rev A)

80 × 46 mm, 2-layer, 2 oz copper. JLCPCB assembles the SMD parts on the top side.
CGW hand-solders all through-hole parts.

| What | Where |
|---|---|
| Schematic (PDF) | `docs/schematic.pdf` |
| KiCad 7 project | `cardboard-bot.kicad_pro` / `.kicad_sch` / `.kicad_pcb` |
| JLCPCB upload files | `fab/` (gerber zip, BOM, CPL) |
| Hand-solder list | `fab/cardboard-bot-v2-revA-hand-solder.csv` |
| Part-number check list | `docs/BOM_CHECK.md` |

## What's on the board

- **Charging:** USB-C (5 V) feeds a BQ25887 2S boost charger with cell balancing. An SMD NTC
  sits next to the cells for temperature cut-off. The yellow charge LED runs from USB power,
  so it works with the power switch off.
- **Cells:** 2 × 18650 in four MY-18650-01 clips on the back. A HY2120 BMS plus two
  CJAC80N03 FETs give over-current, over-charge and over-discharge protection.
  A 20 A mini blade fuse follows.
- **Power switch:** a slide switch drives the gate of a P-FET (AGM30P05A), so the switch never
  carries motor current. Charging still works when the switch is off.
- **VSYS (≈7–8.4 V)** feeds the following:
  - SMBJ9.0A surge diode
  - 470 µF + 220 µF bulk capacitors
  - both ESC screw terminals (J9, J10)
  - the DRV8833
- **Reset protection:** the TPS563201 5 V buck runs from VSYS behind a Schottky diode and a
  hold-up capacitor. The ESC current spikes that used to reset the ESP32 can't pull the
  5 V rail down.
- **Drive:** DRV8833 with 0.15 Ω sense resistors, so each motor is limited to about 1.3 A.
  Motor outputs go to 3.5 mm screw terminals J3 (left) and J4 (right).
- **Outputs:** four 3-pin 2.54 mm headers, pinned GND / V+ / SIG:
  - OUT1 (GPIO10) and OUT2 (GPIO20), with 10k pull-downs so ESCs see "low" while the ESP32 boots
  - IO3 and IO21 (spare GPIO)

  V+ is 5 V through a Schottky diode, so a BEC on an ESC can't back-feed the board.
  The firmware decides whether each output drives a servo, an ESC or a plain on/off signal.
- **I2C header** J2 (GND, 3V3, SCL, SDA) for add-ons. It shares the bus with the charger.
- **Status LED:** one WS2812B, driven through a 74VHC1GT125 level shifter.

### XIAO pin map

| XIAO | GPIO | Use |
|---|---|---|
| D0 | 2 | SDA |
| D1 | 3 | IO3 (spare header J7) |
| D2 / D3 | 4 / 5 | DRV8833 AIN1 / AIN2 (left motor) |
| D4 / D5 | 6 / 7 | DRV8833 BIN1 / BIN2 (right motor) |
| D6 | 21 | IO21 (spare header J8) – also UART TX, see quiet boot below |
| D7 | 20 | OUT2 |
| D8 | 8 | SCL |
| D9 | 9 | RGB LED data (BOOT button pin) |
| D10 | 10 | OUT1 |

GPIO2, GPIO8 and GPIO9 are strapping pins. They only carry signals that idle high at boot
(I2C pull-ups, and the BOOT button with the LED buffer input), so the chip always boots normally.

## Firmware notes

- **Quiet boot:** burn the `UART_PRINT_CONTROL` eFuse (or set the GPIO8-based log suppression),
  and build with the console off (`CONFIG_ESP_CONSOLE_NONE`). Then GPIO21 stays silent at power-up.
  The web flasher's first-flash step should do this.
- The BQ25887 /PG and /INT pins and the DRV8833 nFAULT pin are not connected. Read their
  status over I2C instead (BQ25887 address 0x6A).
- BQ25887 CD is tied to GND, so charging is always enabled. Set the charge current and
  timers over I2C.
- The DRV8833 nSLEEP pin is pulled up to 5 V, so the driver is always awake. The 1 s failsafe
  in firmware brings both inputs low.

## Before ordering – check these

1. **Battery clip leg spacing.** The MY-18650-01 footprint assumes **5.0 mm** between the legs
   and 1.5 mm holes, because the drawing couldn't be downloaded. Measure a real clip or check
   the LCSC drawing (C2979183). Then change `CLIP_LEG_PITCH` in `gen/gen_footprints.py` and
   rebuild the board.
2. **LCSC part numbers.** Go through `docs/BOM_CHECK.md` line by line on jlcpcb.com/parts.
   Each number was confirmed with a web search, but stock and Basic/Extended status change.
   R13 (56k, C23206) was out of stock in one snapshot; C25603 (5 %) works too.
3. **JLC placement preview.** Check the rotation of every IC, diode, LED and polarised capacitor.
   If one is wrong, fix `ROT_FIX` in `gen/fab.py`, not the CSV.
4. **Values to sanity-check against the datasheets:**
   - BQ25887 ILIM/PSEL straps
   - HY2120 RC filter values
   - L2 saturation current (2 A part, ~1 A peak load)
5. **Assembly:** trim the clip and header leads flush on the back. Put a layer of Kapton tape
   under the cells. Fit the fuse last.

## Regenerating

Everything is generated from `gen/circuit.py` (parts, LCSC numbers, nets).
You need KiCad 7 (`kicad-cli` and its Python module), python3-numpy and python3-pil.

```sh
python3 gen/gen_footprints.py          # lib/cgw.pretty (XIAO socket, clip, CGW logos)
python3 gen/gen_sch.py                 # schematic + lib/cgw.kicad_sym
kicad-cli sch export pdf -o docs/schematic.pdf cardboard-bot.kicad_sch
PY=/usr/bin/python3.12
$PY gen/gen_pcb.py                     # outline, placement, silkscreen, pre-routed power copper, router keepouts
$PY gen/route.py --stage zones         # GND pours (both layers) + solid power pours
$PY gen/fixroute.py                    # A* grid router for every remaining connection (rips up and retries)
$PY gen/route.py --stage stitch        # GND stitching vias
$PY gen/islands.py                     # ties any leftover GND pour islands
$PY gen/route.py --stage drop-keepouts && $PY gen/route.py --stage fill
$PY gen/silk.py                        # redraw labels only (safe on a routed board)
$PY gen/drc.py                         # DRC summary
python3 gen/fab.py                     # fab/ outputs; BOM and CPL designators are cross-checked
bash gen/render.sh                     # PNG previews
```

`gen_pcb.py` builds the board from scratch, which wipes the routing. A full re-route takes about
20 minutes. After small changes it is usually easier to edit `cardboard-bot.kicad_pcb` in KiCad directly.
`gen/patch_prewire.py NET,...` re-applies the fixed copper of individual nets on a routed board.

Rev A was routed with `gen/fixroute.py`. `gen/route.py` can also run Freerouting if you have
Java and `freerouting.jar` installed (`route.py` with no arguments).

## Preview

| Top | Bottom (mirrored) |
|---|---|
| ![top](docs/pcb-top.png) | ![bottom](docs/pcb-bottom.png) |
