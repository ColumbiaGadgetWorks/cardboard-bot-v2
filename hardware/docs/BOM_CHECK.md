# LCSC part check (rev A)

Stock, price and library type are from a JLC parts snapshot taken **28 Oct 2026**:
- [yaqwsx/jlcparts](https://github.com/yaqwsx/jlcparts) for stock and price
- [CDFER/jlcpcb-parts-database](https://github.com/CDFER/jlcpcb-parts-database) for the Basic and Preferred lists

They change daily. Open each part on <https://jlcpcb.com/parts> before ordering and tick it off.

- **Basic** and **Preferred** parts have no feeder fee.
- Each **Extended** line usually adds about $3 per order.
- JLC stocks no Basic version of the charger, BMS, buck, motor driver, BMS FETs, USB-C or power
  inductors. For each of those, the pick is a well-stocked Extended part.
- There is no Basic TVS between 6.5 V and 13 V stand-off, so D2 is the SMF10CA (Preferred).

## Check by hand before paying

These were checked against the LCSC datasheets (C19191089, C2979183):
- **U1 IP2320:** wired as the datasheet's typical application, including the 2.2 µH inductor, the
  input RC and 5.1k, the BST, VSET and NTC capacitors, and the charge LED on the LED/ISET pin.
  R4 is 1 Ω, where the datasheet shows 0.5 Ω (the nearest Basic value). The NTC pin has a fixed
  10k (R33), which reads as 25 °C, so temperature sensing is off.
- **BT1–BT4 MY-18650-01:** three legs per clip, Ø1.8 mm holes, 48 mm between the two clips of a cell.

Still to check:
- **D2 SMF10CA (C19077505):** check it shows as Basic or Preferred on jlcpcb.com/parts. If it shows
  Extended, it still works; it just adds the feeder fee.
- **Rotations:** `ROT_FIX` in `gen/fab.py` holds the corrections read off JLC's preview of rev A
  (U1, U2, U3, U5, Q1, Q2). Check the preview again after uploading the new CPL, including D2 (new part).
- **U3 footprint warning:** JLC lists the TPS54202DDCR as SOT-23-6; the board uses KiCad's TSOT-23-6,
  which is TI's DDC land pattern (same pin pitch and pad positions). The warning is about the name only.

## Assembled by JLCPCB (top side)

| LCSC | Value | MPN | Footprint | Qty/board | Designators | JLC library | JLC stock | Unit price |
|---|---|---|---|---|---|---|---|---|
| C15850 | 10uF | CL21A106KAYNNNE | C_0805_2012Metric | 6 | C1, C14, C20, C23, C3, C5 | Basic | 3,710,191 | $0.0692 |
| C45783 | 22uF | CL21A226MAQNNNE | C_0805_2012Metric | 3 | C17, C18, C2 | Basic | 3,360,923 | $0.2384 |
| C12530 | 2.2uF | CL05A225MQ5NSNC | C_0402_1005Metric | 1 | C25 | Basic | 4,549,915 | $0.0054 |
| C15195 | 10nF | CL05B103KB5NNNC | C_0402_1005Metric | 1 | C26 | Basic | 6,322,666 | $0.0041 |
| C14663 | 100nF | CC0603KRX7R9BB104 | C_0603_1608Metric | 12 | C10, C11, C15, C16, C21, C22, C24, C30, C31, C4, C6, C7 | Basic | 50,349,394 | $0.0141 |
| C2286 | RED | KT-0603R | LED_0603_1608Metric | 1 | D1 | Basic | 7,858,146 | $0.0077 |
| C81598 | 1N4148W | 1N4148W | D_SOD-123 | 1 | D10 | Basic | 4,633,707 | $0.0124 |
| C19077505 | SMF10CA | SMF10CA | D_SOD-123F | 1 | D2 | Preferred (no fee) | 377,051 | $0.0304 |
| C8678 | SS34 | SS34 | D_SMA | 1 | D3 | Basic | 4,004,526 | $0.0351 |
| C8598 | B5819W | B5819W SL | D_SOD-123 | 1 | D4 | Basic | 384,842 | $0.0284 |
| C191023 | 1N5819WS | 1N5819WS | D_SOD-323 | 4 | D5, D6, D7, D8 | Basic | 4,286,668 | $0.0139 |
| C165948 | USB-C CHARGE | TYPE-C-31-M-12 | USB_C_Receptacle_HRO_TYPE-C-31-M-12 | 1 | J1 | Extended ($3 fee) | 367,975 | $0.1872 |
| C602029 | 2.2uH 4.8A | FHD4020S-2R2MT | L_Cenker_CKCS4030 | 1 | L1 | Extended ($3 fee) | 106,719 | $0.0697 |
| C602032 | 10uH 2.35A | FHD4020S-100MT | L_Cenker_CKCS4030 | 1 | L2 | Extended ($3 fee) | 99,381 | $0.0640 |
| C18222234 | HYG015N03LS1C2 DSG | HYG015N03LS1C2 | PQFN-8-EP_6x5mm_P1.27mm_Generic | 2 | Q1, Q2 | Extended ($3 fee) | 56,579 | $0.3674 |
| C23186 | 5.1k | 0603WAF5101T5E | R_0603_1608Metric | 3 | R1, R2, R3 | Basic | 23,749,760 | $0.0015 |
| C22975 | 2k | 0603WAF2001T5E | R_0603_1608Metric | 1 | R10 | Basic | 11,836,427 | $0.0024 |
| C23242 | 75k | 0603WAF7502T5E | R_0603_1608Metric | 1 | R13 | Basic | 1,012,894 | $0.0021 |
| C23162 | 4.7k | 0603WAF4701T5E | R_0603_1608Metric | 2 | R15, R16 | Basic | 19,500,720 | $0.0028 |
| C25334 | 0.1R | 1206W4F100LT5E | R_1206_3216Metric | 2 | R18, R19 | Basic | 552,267 | $0.0091 |
| C23024 | 300k | 0603WAF3003T5E | R_0603_1608Metric | 1 | R27 | Basic | 594,835 | $0.0042 |
| C25803 | 100k | 0603WAF1003T5E | R_0603_1608Metric | 1 | R28 | Basic | 19,748,113 | $0.0031 |
| C25804 | 10k | 0603WAF1002T5E | R_0603_1608Metric | 5 | R14, R17, R21, R23, R33 | Basic | 32,380,385 | $0.0052 |
| C22936 | 1R | 0603WAF100KT5E | R_0603_1608Metric | 1 | R4 | Basic | 168,770 | $0.0027 |
| C21190 | 1k | 0603WAF1001T5E | R_0603_1608Metric | 4 | R20, R22, R7, R9 | Basic | 24,277,749 | $0.0020 |
| C23138 | 330R | 0603WAF3300T5E | R_0603_1608Metric | 4 | R24, R25, R26, R8 | Basic | 3,527,043 | $0.0022 |
| C19191089 | IP2320 | IP2320 | SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm | 1 | U1 | Extended ($3 fee) | 20,831 | $0.2856 |
| C116509 | HY2120-CB | HY2120-CB | SOT-23-6 | 1 | U2 | Extended ($3 fee) | 19,426 | $0.2423 |
| C191884 | TPS54202DDCR | TPS54202DDCR | TSOT-23-6 | 1 | U3 | Extended ($3 fee) | 299,988 | $0.1786 |
| C50506 | DRV8833PWPR | DRV8833PWPR | HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm | 1 | U5 | Extended ($3 fee) | 12,910 | $1.9850 |

**30 BOM lines.** Basic: 21, Preferred: 1, Extended: 8 (about $24 in feeder fees per order, if JLC charges them).
Parts cost about **$5.31 per board** at single-unit prices, so about $159 for 30 boards, before JLC's setup and assembly fees.

Cheaper option, not taken (CGW chose to keep the 1.5 A part): HR8833MTER (C128666, about $0.36) is sold as a DRV8833 drop-in and
would save about $1.60 per board. Its pinout hasn't been verified here, so U5 stays a genuine DRV8833.

## Hand-soldered by CGW

| Designator | Part | Notes |
|---|---|---|
| BT1 | 18650 clip | MY-18650-01 |
| BT2 | 18650 clip | MY-18650-01 |
| BT3 | 18650 clip | MY-18650-01 |
| BT4 | 18650 clip | MY-18650-01 |
| F1 | 20A mini blade | Mini blade holder (Keystone 3568 footprint) |
| SW1 | POWER SW | SPST rocker or toggle, 10 A+ at 12 V DC, panel mount, 18 AWG silicone wire |
| C13 | 470uF 16V | 470uF 16V radial, 8 mm dia, 3.5 mm pitch, low ESR |
| C19 | 220uF 16V | 220uF 16V radial, 6.3 mm dia, 2.5 mm pitch |
| U4 | XIAO ESP32-C3 | Seeed XIAO ESP32C3 + 2x 1x7 female header |
| J2 | I2C | 1x4 female header 2.54 |
| J3 | MOTOR L | 2P screw terminal 3.5mm |
| J4 | MOTOR R | 2P screw terminal 3.5mm |
| J5 | OUT1 | 1x3 male header 2.54 |
| J6 | OUT2 | 1x3 male header 2.54 |
| J7 | IO3 | 1x3 male header 2.54 |
| J8 | IO21 | 1x3 male header 2.54 |
| J9 | ESC PWR 1 | 2P screw terminal 5.08mm (KF301) |
| J10 | ESC PWR 2 | 2P screw terminal 5.08mm (KF301) |
| C27 | 470uF 16V | 470uF 16V radial, 8 mm dia, 3.5 mm pitch, low ESR |
| J11 | LED STRIP | 1 LED cut from a WS2812B strip: 5 V, 60 LED/m, 10 mm wide, pads +5V/DIN/GND |
