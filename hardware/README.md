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

Parts were picked for JLC stock: Basic or no-fee Preferred parts wherever JLC has one, otherwise a
well-stocked Extended part (stock checked 28 Oct 2026, see `docs/BOM_CHECK.md`).

- **Charging:** USB-C (5 V) feeds an IP2320 2S boost charger (8.40 V CC/CV, 1.0 A), wired as in
  the datasheet's typical application. A 10k NTC sits in the gap between the cells and stops
  charging below about 0 °C or above about 45 °C. The red charge LED is on while charging, off
  when full, and blinks on a fault. It works with the robot switched off.
- **Balancing:** one HY2213-BB3A per cell. When a cell passes 4.20 V it switches on a P-FET and a
  100 Ω bleed resistor (about 42 mA) until the other cell catches up.
- **Cells:** 2 × 18650 in four MY-18650-01 clips on the back. Each clip has three legs, and the
  two clips of a cell sit 48 mm apart (leg pair to leg pair), per the MYOUNG drawing. A HY2120 BMS plus two
  HYG015N03LS1C2 FETs give over-current, over-charge and over-discharge protection.
  A 20 A mini blade fuse follows.
- **Power switch:** a slide switch drives the gate of a P-FET (CJAB35P03), so the switch never
  carries motor current. Charging still works when the switch is off.
- **VSYS (≈6–8.4 V)** feeds the following:
  - SMAJ10A surge diode
  - a 470 µF through-hole bulk capacitor by the ESC terminals
  - both ESC screw terminals (J9, J10)
  - the DRV8833
- **Reset protection:** the TPS54202 5 V buck runs from VSYS behind a Schottky diode and a
  470 µF hold-up capacitor. The ESC current spikes that used to reset the ESP32 can't pull the
  5 V rail down.
- **Drive:** DRV8833 with 0.1 Ω sense resistors (Basic part), so each motor is limited to about 2 A.
  Motor outputs go to 3.5 mm screw terminals J3 (left) and J4 (right).
- **Outputs:** four 3-pin 2.54 mm headers, pinned GND / V+ / SIG:
  - OUT1 (GPIO10) and OUT2 (GPIO20), with 10k pull-downs so ESCs see "low" while the ESP32 boots
  - IO3 and IO21 (spare GPIO)

  V+ is 5 V through a Schottky diode, so a BEC on an ESC can't back-feed the board.
  The firmware decides whether each output drives a servo, an ESC or a plain on/off signal.
- **Battery sense:** VSYS ÷ 4 goes to GPIO3 (ADC) through JP1, a bridged solder jumper under the
  XIAO. To use IO3 as a normal GPIO on J7, cut JP1.
- **I2C header** J2 (GND, 3V3, SCL, SDA) for add-ons.
- **Status LED:** a WS2812B-type 5050 LED, soldered by CGW (JLC won't place the XL-5050 part). It runs from 5 V through a 1N4148W
  diode (about 4.2 V), so the ESP32's 3.3 V data line is above the LED's 0.7 × VDD input
  threshold without a level shifter.
- **Bulk capacitors** C13, C19 and C27 are through-hole radial parts, soldered by CGW.
  JLC has no Basic SMD electrolytics, and the old SMD ones were out of stock.

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
(I2C pull-ups, and the BOOT button with the LED data line), so the chip always boots normally.

## Firmware notes

- **Quiet boot:** burn the `UART_PRINT_CONTROL` eFuse (or set the GPIO8-based log suppression),
  and build with the console off (`CONFIG_ESP_CONSOLE_NONE`). Then GPIO21 stays silent at power-up.
  The web flasher's first-flash step should do this.
- **Battery voltage:** read GPIO3 with 11 dB attenuation and multiply by 4 (300k / 100k divider).
  It reads VSYS, so it only works with the power switch on. Use it for the battery gauge, the
  low-voltage motor cut-off and the "charge me" warning. The charger has no data link to the ESP32.
- The DRV8833 nFAULT pin is not connected.
- The DRV8833 nSLEEP pin is pulled up to 5 V, so the driver is always awake. The 1 s failsafe
  in firmware brings both inputs low.

## Before ordering – check these

The IP2320, HY2213, XL-5050 LED, SMAJ10A and clip were checked against their datasheets
(LCSC C19191089, C113632, C22461793, C41376407, C2979183).

1. **LCSC part numbers and stock.** Go through `docs/BOM_CHECK.md` line by line on
   jlcpcb.com/parts. Stock and Basic/Preferred status change daily.
2. **JLC placement preview.** `ROT_FIX` in `gen/fab.py` (keyed by LCSC number) holds the corrections
   read off JLC's first preview. Check every IC, transistor and diode again after uploading;
   fix that table, not the CSV. JLC flags U3's footprint name (TSOT-23-6 vs SOT-23-6); the pads match.
3. **Values to sanity-check against the datasheets:**
   - HY2120 RC filter values
   - TPS54202 output inductor (10 µH) and capacitors (2 × 22 µF)
   - R4, which is 1 Ω where the IP2320 datasheet shows 0.5 Ω (the nearest Basic value)
4. **Fit check:** put a real cell in two clips on a printed 1:1 copy of the board before soldering.
5. **Assembly:** trim the clip, header and capacitor leads flush on the back. Put a layer of
   Kapton tape under the cells. Fit the fuse last. The two ESC screw terminals overhang the
   bottom edge, so their wire entries face outward.

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
$PY gen/gnd_check.py                   # lists GND copper cut off from the main cluster (DRC won't say where)
(cd gen && $PY tie_pad.py --min 3 REF PAD)   # route a stranded pad to a GND via, if gnd_check finds one
$PY gen/route.py --stage drop-keepouts && $PY gen/route.py --stage fill
$PY gen/silk.py                        # redraw labels only (safe on a routed board)
$PY gen/drc.py                         # DRC summary
python3 gen/fab.py                     # fab/ outputs; BOM and CPL designators are cross-checked
bash gen/render.sh                     # PNG previews
```

`gen_pcb.py` builds the board from scratch, which wipes the routing. A full re-route takes about
20 minutes. After small changes it is usually easier to edit `cardboard-bot.kicad_pcb` in KiCad directly.
`gen/patch_prewire.py NET,...` re-applies the fixed copper of individual nets on a routed board.

This board was routed with `gen/fixroute.py`. `gen/route.py` can also run Freerouting if you have
Java and `freerouting.jar` installed (`route.py` with no arguments).

## Preview

| Top | Bottom (mirrored) |
|---|---|
| ![top](docs/pcb-top.png) | ![bottom](docs/pcb-bottom.png) |
