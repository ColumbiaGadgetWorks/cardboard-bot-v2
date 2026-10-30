"""Cardboard Bot v2 main board, rev B: circuit definition.

Rev B runs from a 2S or 3S LiPo on a screw terminal (no cells, charger or BMS on the board).
Every part on the battery side is rated for 3S (12.6 V full, with margin for spikes).

Single source of truth for the schematic, the PCB netlist and the JLC BOM.
Each part lists its symbol, footprint, LCSC number and a pin-number -> net map.

LCSC numbers marked verified=True were confirmed by a search of the part page.
Everything else is a candidate that still needs the human check in
hardware/docs/BOM_CHECK.md before ordering.
"""

STD = "/usr/share/kicad/footprints"

# ---------------------------------------------------------------------------
# Net names
# ---------------------------------------------------------------------------
GND = "GND"            # battery negative
BAT = "BAT+"           # battery positive, from the input screw terminal
VFUSE = "VFUSE"        # after the 20 A blade fuse
VSYS = "VSYS"          # after the power switch, feeds all loads
VHOLD = "VHOLD"        # after the hold-up diode, buck input
V5 = "+5V"
V5_XIAO = "+5V_XIAO"
V3 = "+3V3"


def R(ref, val, a, b, lcsc="", fp="Resistor_SMD:R_0603_1608Metric", block="", mpn="", verified=False):
    return dict(ref=ref, sym="Device:R", value=val, fp=fp, lcsc=lcsc, mpn=mpn, verified=verified,
                place="jlc", pins={"1": a, "2": b}, block=block)


def C(ref, val, a, b, lcsc="", fp="Capacitor_SMD:C_0603_1608Metric", block="", mpn="", verified=False):
    return dict(ref=ref, sym="Device:C", value=val, fp=fp, lcsc=lcsc, mpn=mpn, verified=verified,
                place="jlc", pins={"1": a, "2": b}, block=block)


def CP(ref, val, pos, neg, fp, lcsc="", block="", mpn="", verified=False, place="jlc"):
    return dict(ref=ref, sym="Device:C_Polarized", value=val, fp=fp, lcsc=lcsc, mpn=mpn,
                verified=verified, place=place, pins={"1": pos, "2": neg}, block=block)


def DS(ref, val, k, a, fp, lcsc="", block="", mpn="", verified=False):
    return dict(ref=ref, sym="Device:D_Schottky", value=val, fp=fp, lcsc=lcsc, mpn=mpn,
                verified=verified, place="jlc", pins={"1": k, "2": a}, block=block)


def TP(ref, net, block="", fp="TestPoint:TestPoint_Pad_D1.5mm"):
    return dict(ref=ref, sym="Connector:TestPoint", value=net, fp=fp,
                lcsc="", place="none", pins={"1": net}, block=block)


# Common passives (LCSC numbers from the Scorbot project list, already verified there)
C100N = dict(lcsc="C14663", mpn="CC0603KRX7R9BB104", verified=True)       # 100 nF 50 V X7R 0603
C10U = dict(lcsc="C15850", mpn="CL21A106KAYNNNE", verified=True)          # 10 uF 25 V X5R 0805
R10K = dict(lcsc="C25804", mpn="0603WAF1002T5E", verified=True)           # 10 k 1 % 0603
C22U = dict(lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True)          # 22 uF 25 V X5R 0805
R1K = dict(lcsc="C21190", mpn="0603WAF1001T5E", verified=True)            # 1 k 1 % 0603
R330 = dict(lcsc="C23138", mpn="0603WAF3300T5E", verified=True)           # 330 R 1 % 0603
F0805C = "Capacitor_SMD:C_0805_2012Metric"
# Bulk electrolytics are through-hole, soldered by CGW (no Basic SMD electrolytics at JLC)
CP8 = "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm"
CP63 = "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm"
CP470_NOTE = "470uF 25V radial, 8 mm dia, 3.5 mm pitch, low ESR"
CP220_NOTE = "220uF 10V+ radial, 6.3 mm dia, 2.5 mm pitch"
F0402C = "Capacitor_SMD:C_0402_1005Metric"

parts = []
add = parts.append
R20K = dict(lcsc="C4184", mpn="0603WAF2002T5E", verified=True)           # 20 k 1 % 0603
R100K = dict(lcsc="C25803", mpn="0603WAF1003T5E", verified=True)          # 100 k 1 % 0603
TERM508 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal"
TERM35 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal"

# ---------------------------------------------------------------------------
# 1. Battery input, fuse, power switch, surge clamp, bulk
# ---------------------------------------------------------------------------
add(dict(ref="J1", sym="Connector_Generic:Conn_01x02", value="BATTERY", fp=TERM508,
         lcsc="", mpn="2P screw terminal 5.08mm (KF301), 2S or 3S LiPo", place="hand", block="power",
         pins={"1": BAT, "2": GND}))
add(dict(ref="F1", sym="Device:Fuse", value="20A mini blade", fp="Fuse:Fuseholder_Blade_Mini_Keystone_3568",
         lcsc="", mpn="Mini blade holder (Keystone 3568 footprint)", place="hand", block="power",
         pins={"1": BAT, "2": VFUSE}))
# The power switch carries the full battery current, so it's an off-board panel switch on two
# 0.75 mm2 (18 AWG) wire pads (fuse output -> VSYS).
add(dict(ref="SW1", sym="Switch:SW_SPST", value="POWER SW", fp="Connector_Wire:SolderWire-0.75sqmm_1x02_P4.8mm_D1.25mm_OD2.3mm",
         lcsc="", mpn="SPST rocker or toggle, 10 A+ at 16 V DC, panel mount, 18 AWG silicone wire",
         place="hand", block="power", pins={"1": VFUSE, "2": VSYS}))
# 13 V stand-off (3S is 12.6 V full), clamps 21.5 V: below the buck's 28 V and the 25 V capacitors.
# Unidirectional, so a reversed battery forward-biases it and blows the fuse.
add(dict(ref="D1", sym="Device:D_Zener", value="SMAJ13A", fp="Diode_SMD:D_SMA",
         lcsc="C19077533", mpn="SMAJ13A", verified=True, place="jlc", block="power",
         pins={"1": VSYS, "2": GND}))
add(CP("C1", "470uF 25V", VSYS, GND, fp=CP8, mpn=CP470_NOTE, place="hand", block="power"))
add(dict(ref="J8", sym="Connector_Generic:Conn_01x02", value="ESC PWR 1", fp=TERM508,
         lcsc="", mpn="2P screw terminal 5.08mm (KF301)", place="hand", block="power", pins={"1": VSYS, "2": GND}))
add(dict(ref="J9", sym="Connector_Generic:Conn_01x02", value="ESC PWR 2", fp=TERM508,
         lcsc="", mpn="2P screw terminal 5.08mm (KF301)", place="hand", block="power", pins={"1": VSYS, "2": GND}))

# ---------------------------------------------------------------------------
# 2. 5 V buck with hold-up, XIAO feed
# ---------------------------------------------------------------------------
add(DS("D2", "SS34", VHOLD, VSYS, fp="Diode_SMD:D_SMA", lcsc="C8678", mpn="SS34", verified=True, block="buck"))
add(CP("C2", "470uF 25V", VHOLD, GND, fp=CP8, mpn=CP470_NOTE, place="hand", block="buck"))
add(C("C3", "10uF", VHOLD, GND, fp=F0805C, block="buck", **C10U))
add(C("C4", "100nF", VHOLD, GND, block="buck", **C100N))
# TPS54202: 4.5-28 V in; EN floats = enabled (internal pull-up)
add(dict(ref="U1", sym="Regulator_Switching:TPS54202DDC", value="TPS54202DDCR", fp="Package_TO_SOT_SMD:TSOT-23-6",
         lcsc="C191884", mpn="TPS54202DDCR", verified=True, place="jlc", block="buck",
         pins={"1": GND, "2": "BUCK_SW", "3": VHOLD, "4": "BUCK_FB", "5": None, "6": "BUCK_BST"}))
add(C("C5", "100nF", "BUCK_BST", "BUCK_SW", block="buck", **C100N))
add(dict(ref="L1", sym="Device:L", value="10uH 2.35A", fp="Inductor_SMD:L_Cenker_CKCS4030",
         lcsc="C602032", mpn="FHD4020S-100MT", verified=True, place="jlc", block="buck",
         pins={"1": "BUCK_SW", "2": V5}))
add(R("R1", "75k", V5, "BUCK_FB", lcsc="C23242", mpn="0603WAF7502T5E", verified=True, block="buck"))   # 0.596 V x (1 + 75/10) = 5.07 V
add(R("R2", "10k", "BUCK_FB", GND, block="buck", **R10K))
add(C("C6", "22uF", V5, GND, fp=F0805C, block="buck", **C22U))
add(C("C7", "22uF", V5, GND, fp=F0805C, block="buck", **C22U))
add(DS("D3", "B5819W", V5_XIAO, V5, fp="Diode_SMD:D_SOD-123", lcsc="C8598", mpn="B5819W SL", verified=True, block="buck"))
add(C("C9", "10uF", V5_XIAO, GND, fp=F0805C, block="buck", **C10U))
add(C("C10", "100nF", V5_XIAO, GND, block="buck", **C100N))

# ---------------------------------------------------------------------------
# 3. XIAO ESP32-C3 (socketed), I2C, battery sense
# ---------------------------------------------------------------------------
add(dict(ref="U2", sym="cgw:XIAO_ESP32C3", value="XIAO ESP32-C3", fp="cgw:XIAO_Socket",
         lcsc="", mpn="Seeed XIAO ESP32C3 + 2x 1x7 female header", place="hand", block="mcu",
         pins={"1": "SDA",        # D0 GPIO2  (strap, pulled up)
               "2": "VBAT_SNS",   # D1 GPIO3  battery / 6
               "3": "AIN1",       # D2 GPIO4  left motor
               "4": "AIN2",       # D3 GPIO5
               "5": "BIN1",       # D4 GPIO6  right motor
               "6": "BIN2",       # D5 GPIO7
               "7": "IO21",       # D6 GPIO21 OUT3 (ROM boot log for a moment at power-up)
               "8": "IO20",       # D7 GPIO20 OUT2
               "9": "SCL",        # D8 GPIO8  (strap, pulled up)
               "10": "LED_DIN3",  # D9 GPIO9  RGB LED + BOOT button
               "11": "IO10",      # D10 GPIO10 OUT1
               "12": V3, "13": GND, "14": V5_XIAO}))
add(R("R3", "4.7k", V3, "SDA", lcsc="C23162", mpn="0603WAF4701T5E", verified=True, block="mcu"))
add(R("R4", "4.7k", V3, "SCL", lcsc="C23162", mpn="0603WAF4701T5E", verified=True, block="mcu"))
add(C("C11", "100nF", V3, GND, block="mcu", **C100N))
add(dict(ref="J2", sym="Connector_Generic:Conn_01x04", value="I2C", fp="Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical",
         lcsc="", mpn="1x4 female header 2.54", place="hand", block="mcu",
         pins={"1": GND, "2": V3, "3": "SCL", "4": "SDA"}))
# Battery voltage on GPIO3 (ADC1 ch3): VSYS / 6 -> 2.1 V at 12.6 V (3S full)
add(R("R5", "100k", VSYS, "VBAT_SNS", block="mcu", **R100K))
add(R("R6", "20k", "VBAT_SNS", GND, block="mcu", **R20K))
add(C("C12", "100nF", "VBAT_SNS", GND, block="mcu", **C100N))
add(TP("TP1", V3, block="mcu"))
add(TP("TP2", GND, block="mcu"))

# ---------------------------------------------------------------------------
# 4. Drive: one DRV8870 per motor (6.5-45 V, 3.6 A peak), current limit ITRIP = VREF / (10 x RISEN)
# ---------------------------------------------------------------------------
DRV = "DRV8870DDAR"
DRV_FP = "Package_SO:Texas_HTSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.95x4.9mm_Mask2.4x3.1mm_ThermalVias"
for (u, a, b, oa, ob, isen, rs, cb, cs, j, label) in (
        ("U3", "AIN1", "AIN2", "MOTL_A", "MOTL_B", "ISEN_L", "R7", "C14", "C15", "J3", "LEFT MOTOR"),
        ("U4", "BIN1", "BIN2", "MOTR_A", "MOTR_B", "ISEN_R", "R8", "C16", "C17", "J4", "RIGHT MOTOR")):
    add(dict(ref=u, sym="Driver_Motor:DRV8870DDA", value=DRV, fp=DRV_FP,
             lcsc="C86590", mpn=DRV, verified=True, place="jlc", block="drive",
             pins={"1": GND, "2": b, "3": a, "4": "DRV_VREF", "5": VSYS, "6": oa, "7": isen, "8": ob, "9": GND}))
    add(R(rs, "0.1R", isen, GND, fp="Resistor_SMD:R_1206_3216Metric", lcsc="C25334",
          mpn="1206W4F100LT5E", verified=True, block="drive"))
    add(C(cb, "10uF", VSYS, GND, fp=F0805C, block="drive", **C10U))
    add(C(cs, "100nF", VSYS, GND, block="drive", **C100N))
    add(dict(ref=j, sym="Connector_Generic:Conn_01x02", value=label, fp=TERM35,
             lcsc="", mpn="2P screw terminal 3.5mm", place="hand", block="drive", pins={"1": oa, "2": ob}))
# VREF = 3.3 V x 33k / 43k = 2.53 V -> 2.5 A limit per motor with 0.1 R
add(R("R9", "10k", V3, "DRV_VREF", block="drive", **R10K))
add(R("R10", "33k", "DRV_VREF", GND, lcsc="C4216", mpn="0603WAF3302T5E", verified=True, block="drive"))
add(C("C13", "100nF", "DRV_VREF", GND, block="drive", **C100N))
# 10k pull-downs: the motor inputs stay low (coast) while the ESP32 resets and boots
for r, n in (("R11", "AIN1"), ("R12", "AIN2"), ("R13", "BIN1"), ("R14", "BIN2")):
    add(R(r, "10k", n, GND, block="drive", **R10K))

# ---------------------------------------------------------------------------
# 5. PWM outputs (ESC or servo): GND / V+ / SIG, 10k pull-down so an ESC sees "off" during boot
# ---------------------------------------------------------------------------
for (ref_j, io, sig, rs, rp, dref, label) in (
        ("J5", "IO10", "OUT1_SIG", "R15", "R18", "D4", "OUT1"),
        ("J6", "IO20", "OUT2_SIG", "R16", "R19", "D5", "OUT2"),
        ("J7", "IO21", "OUT3_SIG", "R17", "R20", "D6", "OUT3")):
    vp = f"{label}_VP"
    add(R(rs, "1k", io, sig, block="outputs", **R1K))
    add(R(rp, "10k", io, GND, block="outputs", **R10K))
    add(DS(dref, "1N5819WS", vp, V5, fp="Diode_SMD:D_SOD-323", lcsc="C191023", mpn="1N5819WS", verified=True, block="outputs"))
    add(dict(ref=ref_j, sym="Connector_Generic:Conn_01x03", value=label,
             fp="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", lcsc="", mpn="1x3 male header 2.54",
             place="hand", block="outputs", pins={"1": GND, "2": vp, "3": sig}))

# ---------------------------------------------------------------------------
# 6. RGB status LED
# ---------------------------------------------------------------------------
# WS2812B strip LED run from 5 V minus a diode (~4.2 V), so the ESP32's 3.3 V data meets VIH = 0.7 x VDD
add(dict(ref="D7", sym="Device:D", value="1N4148W", fp="Diode_SMD:D_SOD-123",
         lcsc="C81598", mpn="1N4148W", verified=True, place="jlc", block="led",
         pins={"1": "LED_VDD", "2": V5}))
add(R("R21", "330R", "LED_DIN3", "LED_DIN", block="led", **R330))
# One LED cut from a WS2812B strip, laid flat on the board and soldered to three pads at its DIN end
add(dict(ref="J10", sym="Connector_Generic:Conn_01x03", value="LED STRIP", fp="cgw:WS2812B_Strip_1LED",
         lcsc="", mpn="1 LED cut from a WS2812B strip: 5 V, 60 LED/m, 10 mm wide, pads +5V/DIN/GND",
         place="hand", block="led", pins={"1": "LED_VDD", "2": "LED_DIN", "3": GND}))
add(C("C18", "100nF", "LED_VDD", GND, block="led", **C100N))

# Power flags for ERC (nets driven only by passive parts)
POWER_FLAGS = [GND, BAT, VSYS, VHOLD, V5, V5_XIAO, V3, VFUSE, "LED_VDD"]

BLOCK_TITLES = {
    "power": "1  Battery input (2S / 3S LiPo), 20 A blade fuse, power switch, surge clamp, ESC power",
    "buck": "2  Hold-up + 5 V buck (TPS54202), XIAO feed",
    "mcu": "3  XIAO ESP32-C3, I2C, battery sense",
    "drive": "4  2x DRV8870 drive, 2.5 A current limit",
    "outputs": "5  PWM outputs (ESC or servo)",
    "led": "6  RGB status LED (WS2812B strip piece)",
}


def by_ref():
    return {p["ref"]: p for p in parts}


def nets():
    n = {}
    for p in parts:
        for pin, net in p["pins"].items():
            if net:
                n.setdefault(net, []).append((p["ref"], pin))
    return n


if __name__ == "__main__":
    n = nets()
    print(len(parts), "parts,", len(n), "nets")
    for k, v in sorted(n.items()):
        if len(v) < 2:
            print("single-node net:", k, v)
