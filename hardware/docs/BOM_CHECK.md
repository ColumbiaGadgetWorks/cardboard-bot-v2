# LCSC part check (rev B)

Stock, price and library type are from a JLC parts snapshot taken **28 Oct 2026**:
- [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) for stock and price
- [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database) for the Basic and Preferred lists

They change daily. Open each part on <https://jlcpcb.com/parts> before ordering and tick it off.

- **Basic** and **Preferred** parts have no feeder fee.
- Each **Extended** line usually adds about $3 per order.
- JLC stocks no Basic motor driver, buck converter or power inductor, so those three are
  well-stocked Extended parts. There is no Basic TVS with a stand-off above 3S, so D1 is the
  SMAJ13A (Preferred).

## 3S ratings

| Part | Rating | On the 12.6 V rail |
|---|---|---|
| DRV8870 (U3, U4) | 45 V | motor supply |
| TPS54202 (U1) | 28 V | buck input |
| SMAJ13A (D1) | 13 V stand-off, clamps 21.5 V | surge clamp |
| SS34 (D2) | 40 V | hold-up diode |
| 10 µF 0805 (C3, C14, C16) | 25 V | bulk ceramics |
| 100 nF 0603 | 50 V | decoupling |
| 470 µF radials (C1, C2) | 25 V | bulk, hand-soldered |

## Check by hand before paying

- **U3, U4 DRV8870DDAR:** pin 1 GND, 2 IN2, 3 IN1, 4 VREF, 5 VM, 6 OUT1, 7 ISEN, 8 OUT2, pad GND
  (TI SLVSCY9). Check the pin-1 dot in JLC's placement preview; this part is new on rev B.
- **Rotations:** `ROT_FIX` in `gen/fab.py` holds the rev A corrections (U1 TPS54202 is the same part).
- **U1 footprint warning:** JLC lists the TPS54202DDCR as SOT-23-6; the board uses KiCad's TSOT-23-6,
  which is TI's DDC land pattern (same pin pitch and pad positions). The warning is about the name only.

## Assembled by JLCPCB (top side)

| LCSC | Value | MPN | Footprint | Qty/board | Designators | JLC library | JLC stock | Unit price |
|---|---|---|---|---|---|---|---|---|
| C15850 | 10uF | CL21A106KAYNNNE | C_0805_2012Metric | 4 | C14, C16, C3, C9 | Basic | 3,710,191 | $0.0692 |
| C14663 | 100nF | CC0603KRX7R9BB104 | C_0603_1608Metric | 9 | C10, C11, C12, C13, C15, C17, C18, C4, C5 | Basic | 50,349,394 | $0.0141 |
| C45783 | 22uF | CL21A226MAQNNNE | C_0805_2012Metric | 2 | C6, C7 | Basic | 3,360,923 | $0.2384 |
| C19077533 | SMAJ13A | SMAJ13A | D_SMA | 1 | D1 | Preferred (no fee) | 45,855 | $0.0382 |
| C8678 | SS34 | SS34 | D_SMA | 1 | D2 | Basic | 4,004,526 | $0.0351 |
| C8598 | B5819W | B5819W SL | D_SOD-123 | 1 | D3 | Basic | 384,842 | $0.0284 |
| C191023 | 1N5819WS | 1N5819WS | D_SOD-323 | 3 | D4, D5, D6 | Basic | 4,286,668 | $0.0139 |
| C81598 | 1N4148W | 1N4148W | D_SOD-123 | 1 | D7 | Basic | 4,633,707 | $0.0124 |
| C602032 | 10uH 2.35A | FHD4020S-100MT | L_Cenker_CKCS4030 | 1 | L1 | Extended ($3 fee) | 99,381 | $0.0640 |
| C23242 | 75k | 0603WAF7502T5E | R_0603_1608Metric | 1 | R1 | Basic | 1,012,894 | $0.0021 |
| C4216 | 33k | 0603WAF3302T5E | R_0603_1608Metric | 1 | R10 | Basic | 3,644,037 | $0.0021 |
| C21190 | 1k | 0603WAF1001T5E | R_0603_1608Metric | 3 | R15, R16, R17 | Basic | 24,277,749 | $0.0020 |
| C25804 | 10k | 0603WAF1002T5E | R_0603_1608Metric | 9 | R11, R12, R13, R14, R18, R19, R2, R20, R9 | Basic | 32,380,385 | $0.0052 |
| C23138 | 330R | 0603WAF3300T5E | R_0603_1608Metric | 1 | R21 | Basic | 3,527,043 | $0.0022 |
| C23162 | 4.7k | 0603WAF4701T5E | R_0603_1608Metric | 2 | R3, R4 | Basic | 19,500,720 | $0.0028 |
| C25803 | 100k | 0603WAF1003T5E | R_0603_1608Metric | 1 | R5 | Basic | 19,748,113 | $0.0031 |
| C4184 | 20k | 0603WAF2002T5E | R_0603_1608Metric | 1 | R6 | Basic | 7,868,484 | $0.0022 |
| C25334 | 0.1R | 1206W4F100LT5E | R_1206_3216Metric | 2 | R7, R8 | Basic | 552,267 | $0.0091 |
| C191884 | TPS54202DDCR | TPS54202DDCR | TSOT-23-6 | 1 | U1 | Extended ($3 fee) | 299,988 | $0.1786 |
| C86590 | DRV8870DDAR | DRV8870DDAR | Texas_HTSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.95x4.9mm_Mask2.4x3.1mm_ThermalVias | 2 | U3, U4 | Extended ($3 fee) | 158,471 | $0.3456 |

**20 BOM lines.** Basic: 16, Preferred: 1, Extended: 3 (about $9 in feeder fees per order, if JLC charges them).
Parts cost about **$2.06 per board** at single-unit prices, so about $62 for 30 boards, before JLC's setup and assembly fees.

## Hand-soldered by CGW

| Designator | Part | Notes |
|---|---|---|
| J1 | BATTERY | 2P screw terminal 5.08mm (KF301), 2S or 3S LiPo |
| F1 | 20A mini blade | Mini blade holder (Keystone 3568 footprint) |
| SW1 | POWER SW | SPST rocker or toggle, 10 A+ at 16 V DC, panel mount, 18 AWG silicone wire |
| C1 | 470uF 25V | 470uF 25V radial, 8 mm dia, 3.5 mm pitch, low ESR |
| J8 | ESC PWR 1 | 2P screw terminal 5.08mm (KF301) |
| J9 | ESC PWR 2 | 2P screw terminal 5.08mm (KF301) |
| C2 | 470uF 25V | 470uF 25V radial, 8 mm dia, 3.5 mm pitch, low ESR |
| U2 | XIAO ESP32-C3 | Seeed XIAO ESP32C3 + 2x 1x7 female header |
| J2 | I2C | 1x4 female header 2.54 |
| J3 | LEFT MOTOR | 2P screw terminal 3.5mm |
| J4 | RIGHT MOTOR | 2P screw terminal 3.5mm |
| J5 | OUT1 | 1x3 male header 2.54 |
| J6 | OUT2 | 1x3 male header 2.54 |
| J7 | OUT3 | 1x3 male header 2.54 |
| J10 | LED STRIP | 1 LED cut from a WS2812B strip: 5 V, 60 LED/m, 10 mm wide, pads +5V/DIN/GND |
