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
C22U = dict(lcsc="C45783", mpn="CL21A226MAQNNNE", verified=True)          # 22 uF 25 V X5R 0805
R1K = dict(lcsc="C21190", mpn="0603WAF1001T5E", verified=True)            # 1 k 1 % 0603
R330 = dict(lcsc="C23138", mpn="0603WAF3300T5E", verified=True)           # 330 R 1 % 0603
F0805C = "Capacitor_SMD:C_0805_2012Metric"
# Bulk electrolytics are through-hole, soldered by CGW (no Basic SMD electrolytics at JLC)
CP8 = "Capacitor_THT:CP_Radial_D8.0mm_P3.50mm"
CP63 = "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm"
CP470_NOTE = "470uF 16V radial, 8 mm dia, 3.5 mm pitch, low ESR"
CP220_NOTE = "220uF 16V radial, 6.3 mm dia, 2.5 mm pitch"
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
add(C("C1", "22uF", "VBUS", GND, fp=F0805C, block="charge", **C22U))

# ---------------------------------------------------------------------------
# 2. IP2320 2S boost charger (5 V USB in, 8.4 V CC/CV out)
#    Follows the INJOINIC IP2320 V1.00 datasheet, figure 5 (typical application):
#    VSET open = 8.40 V (100 nF on the pin), RISET open = 1.0 A, LED pin -> 1k -> LED -> GND,
#    NTC 10k B3380 to GND with 100 nF, VIN pin fed from the input through 0.5-1 R + 10 uF,
#    5.1k load on the input, 10 uF at the inductor input, 22 uF on VSYS, 10 uF on VOUT.
# ---------------------------------------------------------------------------
add(dict(ref="U1", sym="cgw:IP2320", value="IP2320", fp="Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.29x3mm",
         lcsc="C19191089", mpn="IP2320", verified=True, place="jlc", block="charge",
         pins={"1": "CHG_VSYS", "2": BAT, "3": "CHG_VSET", "4": "CHG_NTC", "5": "CHG_LED",
               "6": "CHG_VIN", "7": "CHG_BST", "8": "CHG_LX", "9": GND}))
add(dict(ref="L1", sym="Device:L", value="2.2uH 4.8A", fp="Inductor_SMD:L_Cenker_CKCS4030",
         lcsc="C602029", mpn="FHD4020S-2R2MT", verified=True, place="jlc", block="charge",
         pins={"1": "VBUS", "2": "CHG_LX"}))
add(R("R3", "5.1k", "VBUS", GND, lcsc="C23186", mpn="0603WAF5101T5E", verified=True, block="charge"))
add(R("R4", "1R", "VBUS", "CHG_VIN", lcsc="C22936", mpn="0603WAF100KT5E", verified=True, block="charge"))  # datasheet R6 0.5R
add(C("C5", "10uF", "CHG_VIN", GND, fp=F0805C, block="charge", **C10U))
add(C("C2", "22uF", "CHG_VSYS", GND, fp=F0805C, block="charge", **C22U))      # right at pin 1
add(C("C3", "10uF", BAT, GND, fp=F0805C, block="charge", **C10U))
add(C("C4", "100nF", "CHG_BST", "CHG_LX", block="charge", **C100N))
add(C("C6", "100nF", "CHG_VSET", GND, block="charge", **C100N))
add(dict(ref="TH1", sym="Device:Thermistor_NTC", value="10k B3380", fp="Resistor_SMD:R_0603_1608Metric",
         lcsc="C13564", mpn="NCP18XH103F03RB", verified=True, place="jlc", block="charge",
         pins={"1": "CHG_NTC", "2": GND}))
add(C("C7", "100nF", "CHG_NTC", GND, block="charge", **C100N))
# Charge LED on the IP2320 LED pin: on while charging, off when full, blinks on a fault
add(R("R7", "1k", "CHG_LED", "CHG_LED_A", block="charge", **R1K))
add(dict(ref="D1", sym="Device:LED", value="RED", fp="LED_SMD:LED_0603_1608Metric",
         lcsc="C2286", mpn="KT-0603R", verified=True, place="jlc", block="charge",
         pins={"1": GND, "2": "CHG_LED_A"}))

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
add(dict(ref="Q1", sym="cgw:NMOS_PDFN", value="HYG015N03LS1C2 DSG", fp="Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
         lcsc="C18222234", mpn="HYG015N03LS1C2", verified=True, place="jlc", block="bms",
         pins={"1": B_NEG, "2": B_NEG, "3": B_NEG, "4": "BMS_DO", "5": "BMS_DRAIN"}))
add(dict(ref="Q2", sym="cgw:NMOS_PDFN", value="HYG015N03LS1C2 CHG", fp="Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic",
         lcsc="C18222234", mpn="HYG015N03LS1C2", verified=True, place="jlc", block="bms",
         pins={"1": GND, "2": GND, "3": GND, "4": "BMS_CO", "5": "BMS_DRAIN"}))
# Cell balancing (HY2213 datasheet, P-MOSFET example): HY2213-BB3A per cell switches a P-FET + 100R bleed
# (~42 mA) above 4.20 V. R 100R + C 100nF filter on VDD per the datasheet table.
for (u, r_in, c_in, q, r_b, top, bot, tag) in (("U7", "R29", "C32", "Q4", "R30", BAT, MID, "BAL1"),
                                               ("U8", "R31", "C33", "Q5", "R32", MID, B_NEG, "BAL2")):
    add(dict(ref=u, sym="cgw:HY2213", value="HY2213-BB3A", fp="Package_TO_SOT_SMD:SOT-23-6",
             lcsc="C113632", mpn="HY2213-BB3A", verified=True, place="jlc", block="bal",
             pins={"1": None, "2": f"{tag}_VDD", "3": bot, "4": None, "5": None, "6": f"{tag}_G"}))
    add(R(r_in, "100R", top, f"{tag}_VDD", lcsc="C22775", mpn="0603WAF1000T5E", verified=True, block="bal"))
    add(C(c_in, "100nF", f"{tag}_VDD", bot, block="bal", **C100N))
    add(dict(ref=q, sym="Device:Q_PMOS_GSD", value="AO3401A", fp="Package_TO_SOT_SMD:SOT-23",
             lcsc="C15127", mpn="AO3401A", verified=True, place="jlc", block="bal",
             pins={"1": f"{tag}_G", "2": top, "3": f"{tag}_D"}))
    add(R(r_b, "100R", f"{tag}_D", bot, fp="Resistor_SMD:R_1206_3216Metric", lcsc="C17901",
          mpn="1206W4F1000T5E", verified=True, block="bal"))
add(dict(ref="F1", sym="Device:Fuse", value="20A mini blade", fp="Fuse:Fuseholder_Blade_Mini_Keystone_3568",
         lcsc="", mpn="Mini blade holder (Keystone 3568 footprint)", place="hand", block="bms",
         pins={"1": BAT, "2": VFUSE}))

# ---------------------------------------------------------------------------
# 4. Power switch, VSYS, surge protection, bulk caps
# ---------------------------------------------------------------------------
add(dict(ref="Q3", sym="cgw:PMOS_PDFN", value="CJAB35P03", fp="Package_SO:Vishay_PowerPAK_1212-8_Single",
         lcsc="C504071", mpn="CJAB35P03", verified=True, place="jlc", block="switch",
         pins={"1": VFUSE, "2": VFUSE, "3": VFUSE, "4": "PSW_G", "5": VSYS}))
add(R("R11", "100k", VFUSE, "PSW_G", lcsc="C25803", mpn="0603WAF1003T5E", verified=True, block="switch"))
add(R("R12", "10k", "PSW_G", "PSW_SW", block="switch", **R10K))
add(dict(ref="SW1", sym="Switch:SW_SPDT", value="POWER", fp="Button_Switch_THT:SW_Slide_SPDT_Straight_CK_OS102011MS2Q",
         lcsc="", mpn="SS-12D00 slide switch", place="hand", block="switch",
         pins={"1": None, "2": "PSW_SW", "3": GND}))
add(dict(ref="D2", sym="Device:D_Zener", value="SMAJ10A", fp="Diode_SMD:D_SMA",
         lcsc="C41376407", mpn="SMAJ10A", verified=True, place="jlc", block="switch",
         pins={"1": VSYS, "2": GND}))

# ---------------------------------------------------------------------------
# 5. 5 V buck with hold-up, XIAO feed
# ---------------------------------------------------------------------------
add(DS("D3", "SS34", VHOLD, VSYS, fp="Diode_SMD:D_SMA", lcsc="C8678", mpn="SS34", verified=True, block="buck"))
add(CP("C13", "470uF 16V", VHOLD, GND, fp=CP8, mpn=CP470_NOTE, place="hand", block="buck"))
add(C("C14", "10uF", VHOLD, GND, fp=F0805C, block="buck", **C10U))
add(C("C15", "100nF", VHOLD, GND, block="buck", **C100N))
# TPS54202: same SOT-23-6 pinout as the TPS563201 it replaces; EN floats = enabled (internal pull-up)
add(dict(ref="U3", sym="Regulator_Switching:TPS54202DDC", value="TPS54202DDCR", fp="Package_TO_SOT_SMD:TSOT-23-6",
         lcsc="C191884", mpn="TPS54202DDCR", verified=True, place="jlc", block="buck",
         pins={"1": GND, "2": "BUCK_SW", "3": VHOLD, "4": "BUCK_FB", "5": None, "6": "BUCK_BST"}))
add(C("C16", "100nF", "BUCK_BST", "BUCK_SW", block="buck", **C100N))
add(dict(ref="L2", sym="Device:L", value="10uH 2.35A", fp="Inductor_SMD:L_Cenker_CKCS4030",
         lcsc="C602032", mpn="FHD4020S-100MT", verified=True, place="jlc", block="buck",
         pins={"1": "BUCK_SW", "2": V5}))
add(R("R13", "75k", V5, "BUCK_FB", lcsc="C23242", mpn="0603WAF7502T5E", verified=True, block="buck"))   # 0.596 V x (1 + 75/10) = 5.07 V
add(R("R14", "10k", "BUCK_FB", GND, block="buck", **R10K))
add(C("C17", "22uF", V5, GND, fp=F0805C, block="buck", **C22U))
add(C("C18", "22uF", V5, GND, fp=F0805C, block="buck", **C22U))
add(CP("C19", "220uF 16V", V5, GND, fp=CP63, mpn=CP220_NOTE, place="hand", block="buck"))
add(DS("D4", "B5819W", V5_XIAO, V5, fp="Diode_SMD:D_SOD-123", lcsc="C8598", mpn="B5819W SL", verified=True, block="buck"))
add(C("C20", "22uF", V5_XIAO, GND, fp=F0805C, block="buck", **C22U))
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
# Battery voltage on GPIO3 (ADC1 ch3): VSYS / 4 -> 2.1 V at 8.4 V. JP1 is bridged copper;
# cut it to use IO3 as a plain GPIO on J7.
add(R("R27", "300k", VSYS, "VBAT_SNS", lcsc="C23024", mpn="0603WAF3003T5E", verified=True, block="mcu"))
add(R("R28", "100k", "VBAT_SNS", GND, lcsc="C25803", mpn="0603WAF1003T5E", verified=True, block="mcu"))
add(C("C31", "100nF", "VBAT_SNS", GND, block="mcu", **C100N))
add(dict(ref="JP1", sym="Jumper:SolderJumper_2_Bridged", value="VBAT>IO3",
         fp="Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm", lcsc="", mpn="PCB copper jumper",
         place="none", block="mcu", pins={"1": "VBAT_SNS", "2": "IO3"}))
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
add(R("R18", "0.1R", "DRV_AISEN", GND, fp="Resistor_SMD:R_1206_3216Metric", lcsc="C25334",
      mpn="1206W4F100LT5E", verified=True, block="drive"))   # 0.2 V / 0.1 R = 2 A limit
add(R("R19", "0.1R", "DRV_BISEN", GND, fp="Resistor_SMD:R_1206_3216Metric", lcsc="C25334",
      mpn="1206W4F100LT5E", verified=True, block="drive"))   # 0.2 V / 0.1 R = 2 A limit
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
add(CP("C27", "470uF 16V", VSYS, GND, fp=CP8, mpn=CP470_NOTE, place="hand", block="outputs"))

# ---------------------------------------------------------------------------
# 9. RGB status LED
# ---------------------------------------------------------------------------
# WS2812-type LED run from 5 V minus a diode (~4.2 V), so the ESP32's 3.3 V data meets VIH = 0.7 x VDD
add(dict(ref="D10", sym="Device:D", value="1N4148W", fp="Diode_SMD:D_SOD-123",
         lcsc="C81598", mpn="1N4148W", verified=True, place="jlc", block="led",
         pins={"1": "LED_VDD", "2": V5}))
add(R("R26", "330R", "LED_DIN3", "LED_DIN", block="led", **R330))
add(dict(ref="D9", sym="LED:WS2812B", value="XL-5050RGBC-2812B-S", fp="LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm",
         lcsc="C22461793", mpn="XL-5050RGBC-2812B-S", verified=True, place="jlc", block="led",
         pins={"1": "LED_VDD", "2": None, "3": GND, "4": "LED_DIN"}))
add(C("C30", "100nF", "LED_VDD", GND, block="led", **C100N))

# Power flags for ERC (nets driven only by passive parts)
POWER_FLAGS = [GND, "VBUS", BAT, B_NEG, MID, VSYS, VHOLD, V5, V5_XIAO, V3, VFUSE, "CHG_VSYS", "CHG_VIN", "LED_VDD",
               "DRV_VINT", "DRV_VCP", "BAL1_VDD", "BAL2_VDD"]

BLOCK_TITLES = {
    "charge": "1  USB-C charge input + IP2320 2S boost charger",
    "bms": "2  Cells, 2S BMS (HY2120), 20 A blade fuse",
    "bal": "2b Cell balancing (2x HY2213)",
    "switch": "3  Power switch (P-FET), surge clamp, bulk",
    "buck": "4  Hold-up + 5 V buck (TPS54202), XIAO feed",
    "mcu": "5  XIAO ESP32-C3, I2C, battery sense",
    "drive": "6  DRV8833 drive, 2 A current limit",
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
