"""Cardboard Bot v2 main board: circuit definition.

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
GND = "GND"            # system ground = pack negative after the BMS (P-)
B_NEG = "B_NEG"        # bottom of the cell stack (before the BMS FETs)
MID = "MID"            # junction between the two cells
BAT = "BAT+"           # top of the stack = pack positive
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
F0805C = "Capacitor_SMD:C_0805_2012Metric"
F0402C = "Capacitor_SMD:C_0402_1005Metric"

parts = []
add = parts.append

# ---------------------------------------------------------------------------
# 1. USB-C charge input
# ---------------------------------------------------------------------------
add(dict(ref="J1", sym="Connector:USB_C_Receptacle_USB2.0_16P", value="USB-C CHARGE",
         fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C165948", mpn="TYPE-C-31-M-12", verified=True,
         place="jlc", block="charge",
         pins={"A1": GND, "A12": GND, "B1": GND, "B12": GND,
               "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS",
               "A5": "CC1", "B5": "CC2", "S1": GND,
               "A6": None, "A7": None, "B6": None, "B7": None, "A8": None, "B8": None}))
add(R("R1", "5.1k", "CC1", GND, lcsc="C23186", mpn="0603WAF5101T5E", verified=True, block="charge"))
add(R("R2", "5.1k", "CC2", GND, lcsc="C23186", mpn="0603WAF5101T5E", verified=True, block="charge"))
add(C("C1", "1uF", "VBUS", GND, lcsc="C15849", mpn="CL10A105KB8NNNC", verified=True, block="charge"))

# ---------------------------------------------------------------------------
# 2. BQ25887 2S boost charger with cell balancing
# ---------------------------------------------------------------------------
add(dict(ref="U1", sym="Battery_Management:BQ25887", value="BQ25887RGER",
         fp="Package_DFN_QFN:VQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm",
         lcsc="C2761614", mpn="BQ25887RGER", verified=True, place="jlc", block="charge",
         pins={"1": None, "2": "CHG_STAT", "3": GND, "4": "SDA", "5": "SCL", "6": None,   # PG/INT unused, CD low = charge enabled
               "7": "CHG_TS", "8": GND,            # ILIM unused -> GND (datasheet: do not float)
               "9": MID, "10": "CHG_CBSET", "11": "REGN", "12": "CHG_BTST",
               "13": BAT, "14": BAT, "15": "CHG_SNS", "16": "CHG_SNS",
               "17": "CHG_SW", "18": "CHG_SW", "19": GND, "20": GND,
               "21": "PMID", "22": "PMID", "23": "VBUS", "24": GND,   # PSEL low = 3 A adapter
               "25": GND}))
add(C("C2", "10uF", "PMID", GND, fp=F0805C, block="charge", **C10U))
add(C("C3", "10uF", "PMID", GND, fp=F0805C, block="charge", **C10U))
add(dict(ref="L1", sym="Device:L", value="1uH 4A", fp="Inductor_SMD:L_Cenker_CKCS4030",
         lcsc="C5291823", mpn="CKCS4030-1uH/N", verified=True, place="jlc", block="charge",
         pins={"1": "PMID", "2": "CHG_SW"}))
add(C("C4", "47nF", "CHG_BTST", "CHG_SW", lcsc="C1622", mpn="CL10B473KB8NNNC", verified=True, block="charge"))
add(C("C5", "4.7uF", "REGN", GND, lcsc="C19666", mpn="CL10A475KO8NNNC", verified=True, block="charge"))
# SNS needs 44 uF for stability and must not be loaded (TI E2E)
add(C("C6", "22uF", "CHG_SNS", GND, fp=F0805C, lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True, block="charge"))
add(C("C7", "22uF", "CHG_SNS", GND, fp=F0805C, lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True, block="charge"))
add(C("C8", "10uF", BAT, GND, fp=F0805C, block="charge", **C10U))
add(C("C9", "10uF", BAT, GND, fp=F0805C, block="charge", **C10U))
# Balancing current resistor CBSET -> MID (~0.15 A at 3.2 V, about 0.5 W in a 1 W 2512)
add(R("R3", "22R 1W", "CHG_CBSET", MID, fp="Resistor_SMD:R_2512_6332Metric", lcsc="C118189",
      mpn="25121WF220JT4E", verified=True, block="charge"))
# TS: RT1 from REGN, RT2 to GND, NTC to GND (datasheet example 5.24k / 30.31k for 103AT)
add(R("R5", "5.1k", "REGN", "CHG_TS", lcsc="C23186", mpn="0603WAF5101T5E", verified=True, block="charge"))
add(R("R6", "30k", "CHG_TS", GND, lcsc="C22984", mpn="0603WAF3002T5E", verified=True, block="charge"))
add(dict(ref="TH1", sym="Device:Thermistor_NTC", value="10k B3950", fp="Resistor_SMD:R_0603_1608Metric",
         lcsc="C47118797", mpn="CMFA103F3950HANT", verified=True, place="jlc", block="charge",
         pins={"1": "CHG_TS", "2": GND}))
# Charge LED, powered from VBUS (only live with USB plugged in), works with the ESP32 off
add(R("R7", "2.2k", "VBUS", "CHG_LED_A", lcsc="C4190", mpn="0603WAF2201T5E", verified=True, block="charge"))
add(dict(ref="D1", sym="Device:LED", value="YELLOW", fp="LED_SMD:LED_0603_1608Metric",
         lcsc="C72038", mpn="19-213/Y2C-CQ2R2L/3T(CY)", verified=True, place="jlc", block="charge",
         pins={"1": "CHG_STAT", "2": "CHG_LED_A"}))

# ---------------------------------------------------------------------------
# 3. Cells, BMS, fuse
# ---------------------------------------------------------------------------
for ref, net in (("BT1", B_NEG), ("BT2", MID), ("BT3", MID), ("BT4", BAT)):
    add(dict(ref=ref, sym="cgw:BattClip", value="18650 clip", fp="cgw:Clip_MY-18650-01",
             lcsc="C2979183", mpn="MY-18650-01", verified=True, place="hand", block="bms",
             pins={"1": net}))
add(dict(ref="U2", sym="cgw:HY2120", value="HY2120-CB", fp="Package_TO_SOT_SMD:SOT-23-6",
         lcsc="C116509", mpn="HY2120-CB", verified=True, place="jlc", block="bms",
         pins={"1": "BMS_DO", "2": "BMS_CO", "3": "BMS_CS", "4": "BMS_VC", "5": "BMS_VDD", "6": B_NEG}))
add(R("R8", "330R", BAT, "BMS_VDD", lcsc="C23138", mpn="0603WAF3300T5E", verified=True, block="bms"))
add(C("C10", "100nF", "BMS_VDD", B_NEG, block="bms", **C100N))
add(R("R9", "1k", MID, "BMS_VC", lcsc="C21190", mpn="0603WAF1001T5E", verified=True, block="bms"))
add(C("C11", "100nF", "BMS_VC", B_NEG, block="bms", **C100N))
add(R("R10", "2k", GND, "BMS_CS", lcsc="C22975", mpn="0603WAF2001T5E", verified=True, block="bms"))
# Back-to-back low-side FETs: Q1 discharge (S=B-), Q2 charge (S=P-), drains common
add(dict(ref="Q1", sym="cgw:NMOS_PDFN", value="CJAC80N03 DSG", fp="Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
         lcsc="C504096", mpn="CJAC80N03", verified=True, place="jlc", block="bms",
         pins={"1": B_NEG, "2": B_NEG, "3": B_NEG, "4": "BMS_DO", "5": "BMS_DRAIN"}))
add(dict(ref="Q2", sym="cgw:NMOS_PDFN", value="CJAC80N03 CHG", fp="Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
         lcsc="C504096", mpn="CJAC80N03", verified=True, place="jlc", block="bms",
         pins={"1": GND, "2": GND, "3": GND, "4": "BMS_CO", "5": "BMS_DRAIN"}))
add(dict(ref="F1", sym="Device:Fuse", value="20A mini blade", fp="Fuse:Fuseholder_Blade_Mini_Keystone_3568",
         lcsc="", mpn="Mini blade holder (Keystone 3568 footprint)", place="hand", block="bms",
         pins={"1": BAT, "2": VFUSE}))

# ---------------------------------------------------------------------------
# 4. Power switch, VSYS, surge protection, bulk caps
# ---------------------------------------------------------------------------
add(dict(ref="Q3", sym="cgw:PMOS_PDFN", value="AGM30P05A", fp="Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
         lcsc="C6719407", mpn="AGM30P05A", verified=True, place="jlc", block="switch",
         pins={"1": VFUSE, "2": VFUSE, "3": VFUSE, "4": "PSW_G", "5": VSYS}))
add(R("R11", "100k", VFUSE, "PSW_G", lcsc="C25803", mpn="0603WAF1003T5E", verified=True, block="switch"))
add(R("R12", "10k", "PSW_G", "PSW_SW", block="switch", **R10K))
add(dict(ref="SW1", sym="Switch:SW_SPDT", value="POWER", fp="Button_Switch_THT:SW_Slide_SPDT_Straight_CK_OS102011MS2Q",
         lcsc="", mpn="SS-12D00 slide switch", place="hand", block="switch",
         pins={"1": None, "2": "PSW_SW", "3": GND}))
add(dict(ref="D2", sym="Device:D_Zener", value="SMBJ9.0A", fp="Diode_SMD:D_SMB",
         lcsc="C3720683", mpn="SMBJ9.0A", verified=True, place="jlc", block="switch",
         pins={"1": VSYS, "2": GND}))
add(CP("C12", "220uF 16V", VSYS, GND, fp="Capacitor_SMD:CP_Elec_6.3x7.7", lcsc="C179798",
       mpn="16CE220AX", verified=True, block="switch"))

# ---------------------------------------------------------------------------
# 5. 5 V buck with hold-up, XIAO feed
# ---------------------------------------------------------------------------
add(DS("D3", "SS34", VHOLD, VSYS, fp="Diode_SMD:D_SMA", lcsc="C8678", mpn="SS34", verified=True, block="buck"))
add(CP("C13", "470uF 16V", VHOLD, GND, fp="Capacitor_SMD:CP_Elec_8x10", lcsc="C82006",
       mpn="RVT1C471M0810", verified=True, block="buck"))
add(C("C14", "10uF", VHOLD, GND, fp=F0805C, block="buck", **C10U))
add(C("C15", "100nF", VHOLD, GND, block="buck", **C100N))
add(dict(ref="U3", sym="Regulator_Switching:TPS563200", value="TPS563201DDCR", fp="Package_TO_SOT_SMD:TSOT-23-6",
         lcsc="C116592", mpn="TPS563201DDCR", verified=True, place="jlc", block="buck",
         pins={"1": GND, "2": "BUCK_SW", "3": VHOLD, "4": "BUCK_FB", "5": VHOLD, "6": "BUCK_BST"}))
add(C("C16", "100nF", "BUCK_BST", "BUCK_SW", block="buck", **C100N))
add(dict(ref="L2", sym="Device:L", value="4.7uH 2A", fp="Inductor_SMD:L_Cenker_CKCS4030",
         lcsc="C354587", mpn="CKCS4030-4.7uH/M", verified=True, place="jlc", block="buck",
         pins={"1": "BUCK_SW", "2": V5}))
add(R("R13", "56k", V5, "BUCK_FB", lcsc="C23206", mpn="0603WAF5602T5E", verified=True, block="buck"))   # check stock; C25603 (5%) is a fallback
add(R("R14", "10k", "BUCK_FB", GND, block="buck", **R10K))
add(C("C17", "22uF", V5, GND, fp=F0805C, lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True, block="buck"))
add(C("C18", "22uF", V5, GND, fp=F0805C, lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True, block="buck"))
add(CP("C19", "220uF 16V", V5, GND, fp="Capacitor_SMD:CP_Elec_6.3x7.7", lcsc="C179798",
       mpn="16CE220AX", verified=True, block="buck"))
add(DS("D4", "B5819W", V5_XIAO, V5, fp="Diode_SMD:D_SOD-123", lcsc="C8598", mpn="B5819W SL", verified=True, block="buck"))
add(C("C20", "22uF", V5_XIAO, GND, fp=F0805C, lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True, block="buck"))
add(C("C21", "100nF", V5_XIAO, GND, block="buck", **C100N))
add(TP("TP4", V5, block="buck"))

# ---------------------------------------------------------------------------
# 6. XIAO ESP32-C3 (socketed)
# ---------------------------------------------------------------------------
add(dict(ref="U4", sym="cgw:XIAO_ESP32C3", value="XIAO ESP32-C3", fp="cgw:XIAO_Socket",
         lcsc="", mpn="Seeed XIAO ESP32C3 + 2x 1x7 female header", place="hand", block="mcu",
         pins={"1": "SDA",        # D0 GPIO2  (strap, pulled up)
               "2": "IO3",        # D1 GPIO3  spare
               "3": "AIN1",       # D2 GPIO4
               "4": "AIN2",       # D3 GPIO5
               "5": "BIN1",       # D4 GPIO6
               "6": "BIN2",       # D5 GPIO7
               "7": "IO21",       # D6 GPIO21 spare (boot log silenced in firmware)
               "8": "IO20",       # D7 GPIO20 OUT2
               "9": "SCL",        # D8 GPIO8  (strap, pulled up)
               "10": "LED_DIN3",  # D9 GPIO9  RGB LED + BOOT button
               "11": "IO10",      # D10 GPIO10 OUT1
               "12": V3, "13": GND, "14": V5_XIAO}))
add(R("R15", "4.7k", V3, "SDA", lcsc="C23162", mpn="0603WAF4701T5E", verified=True, block="mcu"))
add(R("R16", "4.7k", V3, "SCL", lcsc="C23162", mpn="0603WAF4701T5E", verified=True, block="mcu"))
add(C("C22", "100nF", V3, GND, block="mcu", **C100N))
add(dict(ref="J2", sym="Connector_Generic:Conn_01x04", value="I2C", fp="Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical",
         lcsc="", mpn="1x4 female header 2.54", place="hand", block="mcu",
         pins={"1": GND, "2": V3, "3": "SCL", "4": "SDA"}))
add(TP("TP5", V3, block="mcu"))
add(TP("TP6", GND, block="mcu"))
add(TP("TP7", MID, block="bms"))

# ---------------------------------------------------------------------------
# 7. Drive: DRV8833
# ---------------------------------------------------------------------------
add(dict(ref="U5", sym="Driver_Motor:DRV8833PWP", value="DRV8833PWPR",
         fp="Package_SO:HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm",
         lcsc="C50506", mpn="DRV8833PWPR", verified=True, place="jlc", block="drive",
         pins={"1": "DRV_SLEEP", "2": "MOTL_A", "3": "DRV_AISEN", "4": "MOTL_B", "5": "MOTR_B",
               "6": "DRV_BISEN", "7": "MOTR_A", "8": None, "9": "BIN1", "10": "BIN2",   # nFAULT unused
               "11": "DRV_VCP", "12": VSYS, "13": GND, "14": "DRV_VINT", "15": "AIN2", "16": "AIN1",
               "17": GND}))
add(R("R17", "10k", V5, "DRV_SLEEP", block="drive", **R10K))   # nSLEEP abs max 7 V
add(R("R18", "0.15R", "DRV_AISEN", GND, fp="Resistor_SMD:R_1206_3216Metric", lcsc="C104932",
      mpn="RTT06R150FTP", verified=True, block="drive"))
add(R("R19", "0.15R", "DRV_BISEN", GND, fp="Resistor_SMD:R_1206_3216Metric", lcsc="C104932",
      mpn="RTT06R150FTP", verified=True, block="drive"))
add(C("C23", "10uF", VSYS, GND, fp=F0805C, block="drive", **C10U))
add(C("C24", "100nF", VSYS, GND, block="drive", **C100N))
add(C("C25", "2.2uF", "DRV_VINT", GND, lcsc="C12530", mpn="CL05A225MQ5NSNC", verified=True, fp=F0402C, block="drive"))
add(C("C26", "10nF", "DRV_VCP", VSYS, lcsc="C15195", mpn="CL05B103KB5NNNC", verified=True, fp=F0402C, block="drive"))
add(dict(ref="J3", sym="Connector_Generic:Conn_01x02", value="MOTOR L", fp="TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal",
         lcsc="", mpn="2P screw terminal 3.5mm", place="hand", block="drive", pins={"1": "MOTL_A", "2": "MOTL_B"}))
add(dict(ref="J4", sym="Connector_Generic:Conn_01x02", value="MOTOR R", fp="TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-2-3.5-H_1x02_P3.50mm_Horizontal",
         lcsc="", mpn="2P screw terminal 3.5mm", place="hand", block="drive", pins={"1": "MOTR_A", "2": "MOTR_B"}))

# ---------------------------------------------------------------------------
# 8. PWM outputs (ESC or servo) + spare GPIO headers, all GND / V+ / SIG
# ---------------------------------------------------------------------------
for i, (ref_j, io, sig, ser, pd, dref, rs, rp, label) in enumerate((
        ("J5", "IO10", "OUT1_SIG", "1k", True, "D5", "R20", "R21", "OUT1"),
        ("J6", "IO20", "OUT2_SIG", "1k", True, "D6", "R22", "R23", "OUT2"),
        ("J7", "IO3", "IO3_SIG", "330R", False, "D7", "R24", None, "IO3"),
        ("J8", "IO21", "IO21_SIG", "330R", False, "D8", "R25", None, "IO21"))):
    vp = f"{label}_VP"
    lc = ("C21190", "0603WAF1001T5E") if ser == "1k" else ("C23138", "0603WAF3300T5E")
    add(R(rs, ser, io, sig, lcsc=lc[0], mpn=lc[1], verified=True, block="outputs"))
    if pd:
        add(R(rp, "10k", io, GND, block="outputs", **R10K))
    add(DS(dref, "1N5819WS", vp, V5, fp="Diode_SMD:D_SOD-323", lcsc="C191023", mpn="1N5819WS", verified=True, block="outputs"))
    add(dict(ref=ref_j, sym="Connector_Generic:Conn_01x03", value=label,
             fp="Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", lcsc="", mpn="1x3 male header 2.54",
             place="hand", block="outputs", pins={"1": GND, "2": vp, "3": sig}))
for ref, label in (("J9", "ESC PWR 1"), ("J10", "ESC PWR 2")):
    add(dict(ref=ref, sym="Connector_Generic:Conn_01x02", value=label,
             fp="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
             lcsc="", mpn="2P screw terminal 5.08mm (KF301)", place="hand", block="outputs",
             pins={"1": VSYS, "2": GND}))
add(CP("C27", "470uF 16V", VSYS, GND, fp="Capacitor_SMD:CP_Elec_8x10", lcsc="C82006",
       mpn="RVT1C471M0810", verified=True, block="outputs"))

# ---------------------------------------------------------------------------
# 9. RGB status LED
# ---------------------------------------------------------------------------
add(dict(ref="U6", sym="74xGxx:74LVC1G125", value="74VHCT1G125", fp="Package_TO_SOT_SMD:SOT-353_SC-70-5",
         lcsc="C154805", mpn="M74VHC1GT125DF1G", verified=True, place="jlc", block="led",
         pins={"1": GND, "2": "LED_DIN3", "3": GND, "4": "LED_DIN5", "5": V5}))
add(C("C29", "100nF", V5, GND, block="led", **C100N))
add(R("R26", "330R", "LED_DIN5", "LED_DIN", lcsc="C23138", mpn="0603WAF3300T5E", verified=True, block="led"))
add(dict(ref="D9", sym="LED:WS2812B", value="WS2812B", fp="LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm",
         lcsc="C2761795", mpn="WS2812B-B/T", verified=True, place="jlc", block="led",
         pins={"1": V5, "2": None, "3": GND, "4": "LED_DIN"}))
add(C("C30", "100nF", V5, GND, block="led", **C100N))

# Power flags for ERC (nets driven only by passive parts)
POWER_FLAGS = [GND, "VBUS", BAT, B_NEG, VSYS, VHOLD, V5, V5_XIAO, V3, VFUSE, "REGN", "PMID", "CHG_SNS", "DRV_VINT", "DRV_VCP"]

BLOCK_TITLES = {
    "charge": "1  USB-C charge input + BQ25887 2S balance charger",
    "bms": "2  Cells, 2S BMS (HY2120), 20 A blade fuse",
    "switch": "3  Power switch (P-FET), surge clamp, bulk",
    "buck": "4  Hold-up + 5 V buck (TPS563201), XIAO feed",
    "mcu": "5  XIAO ESP32-C3, I2C",
    "drive": "6  DRV8833 drive, 1.3 A current limit",
    "outputs": "7  PWM outputs (ESC or servo) + spare GPIO",
    "led": "8  RGB status LED",
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
