"""Build cardboard-bot.kicad_pcb from circuit.py: outline, placement, nets, silkscreen.

Run with KiCad's Python:  /usr/bin/python3.12 gen/gen_pcb.py
Routing and zones are added afterwards by route.py.
"""
import json
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit  # noqa: E402

PCB = os.path.join(HW, "cardboard-bot.kicad_pcb")
STD = "/usr/share/kicad/footprints"
CGW = os.path.join(HW, "lib", "cgw.pretty")

W, H = 80.0, 46.0          # board size (mm)
OX, OY = 100.0, 100.0      # board origin on the KiCad page
CELL_Y = (12.5, 33.5)      # cell centre lines (bottom side)
CLIP_X = (5.0, 75.0)       # clip leg rows (ESTIMATED, see gen_footprints.py)

# ref: (x, y, rotation_deg, side)   side F = top, B = bottom
PLACE = {
    # --- cells (bottom) ---------------------------------------------------
    "BT4": (CLIP_X[0], CELL_Y[0], 0, "B"),   # cell A +  -> BAT+
    "BT2": (CLIP_X[1], CELL_Y[0], 0, "B"),   # cell A -  -> MID
    "BT3": (CLIP_X[1], CELL_Y[1], 0, "B"),   # cell B +  -> MID
    "BT1": (CLIP_X[0], CELL_Y[1], 0, "B"),   # cell B -  -> B_NEG
    # --- fuse + power switch FET (top left) -------------------------------
    "F1": (10.4, 2.3, 0, "F"),
    "Q3": (27.2, 4.4, 0, "F"),         # PowerPAK 1212-8: source pads left, drain pad right
    "R11": (25.0, 8.6, 0, "F"),
    "R12": (28.6, 8.6, 0, "F"),
    # --- USB-C + charger --------------------------------------------------
    "J1": (3.65, 23.0, 270, "F"),
    "U1": (16.5, 19.0, 0, "F"),        # IP2320: VSYS/VOUT on the left, VIN/BST/LX on the right
    "C2": (11.0, 17.1, 180, "F"),      # VSYS cap right at pin 1
    "C3": (11.0, 19.2, 180, "F"),      # VOUT (BAT+) cap
    "C4": (21.0, 18.0, 90, "F"),       # BST-LX
    "L1": (24.0, 18.0, 90, "F"),
    "C1": (22.6, 21.8, 0, "F"),        # boost input cap
    "TH1": (15.0, 23.2, 0, "F"),       # in the gap between the two cells
    "R1": (10.4, 22.4, 0, "F"),
    "R2": (10.4, 24.8, 0, "F"),
    "R7": (10.4, 26.3, 0, "F"),
    "D1": (10.4, 28.0, 180, "F"),
    # --- cell balancing: top cell under the fuse, bottom cell between the cells --------
    "R29": (12.6, 11.2, 0, "F"),
    "C32": (12.6, 12.8, 0, "F"),
    "U7": (16.2, 12.0, 0, "F"),
    "Q4": (20.2, 12.0, 0, "F"),
    "R30": (16.4, 14.9, 0, "F"),
    "R31": (13.9, 28.2, 0, "F"),
    "C33": (13.9, 29.8, 0, "F"),
    "U8": (17.6, 29.0, 0, "F"),
    "Q5": (21.6, 29.0, 0, "F"),
    "R32": (24.7, 29.0, 90, "F"),
    # --- BMS (bottom left) -------------------------------------------------
    "Q1": (11.8, 36.4, 0, "F"),
    "Q2": (19.6, 36.4, 180, "F"),
    "U2": (12.0, 42.4, 0, "F"),
    "R8": (8.6, 41.0, 90, "F"),
    "C10": (8.6, 44.1, 90, "F"),
    "R9": (16.0, 41.0, 0, "F"),
    "C11": (16.0, 42.6, 0, "F"),
    "R10": (16.0, 44.2, 0, "F"),
    "TP7": (19.4, 41.6, 0, "F"),
    # --- switch / VSYS -------------------------------------------------------
    "SW1": (31.6, 42.6, 0, "F"),
    "D2": (69.6, 4.3, 90, "F"),
    # --- hold-up + buck ------------------------------------------------------
    "D3": (27.4, 24.6, 0, "F"),
    "C13": (28.45, 31.8, 0, "F"),      # radial 8 mm, body centre (30.2, 31.8)
    "C14": (35.2, 25.2, 90, "F"),
    "C15": (33.0, 24.6, 90, "F"),
    "U3": (38.4, 26.6, 0, "F"),
    "C16": (38.4, 23.6, 0, "F"),
    "L2": (43.2, 26.8, 0, "F"),
    "R13": (37.6, 30.0, 0, "F"),
    "R14": (37.6, 31.8, 0, "F"),
    "C17": (47.0, 26.6, 90, "F"),
    "C18": (49.0, 26.6, 90, "F"),
    "C19": (43.35, 33.6, 0, "F"),      # radial 6.3 mm, body centre (44.6, 33.6)
    "TP4": (36.0, 34.6, 0, "F"),
    "D4": (44.6, 5.6, 90, "F"),        # under the XIAO, next to its 5V pin
    "C20": (44.6, 9.8, 90, "F"),
    "C21": (42.6, 9.4, 90, "F"),
    # --- XIAO, I2C ------------------------------------------------------------
    "U4": (40.0, 12.5, 0, "F"),
    "R15": (36.0, 4.6, 90, "F"),
    "R16": (37.6, 4.6, 90, "F"),
    "C22": (39.2, 4.6, 90, "F"),
    "R17": (60.5, 17.6, 180, "F"),
    "TP5": (39.0, 9.0, 0, "F"),
    "JP1": (35.4, 10.4, 90, "F"),       # VBAT sense -> IO3, cut to free IO3
    "R27": (36.6, 14.4, 90, "F"),
    "R28": (38.4, 14.4, 90, "F"),
    "C31": (38.4, 17.6, 90, "F"),
    "TP6": (39.0, 11.6, 0, "F"),
    "J2": (28.1, 12.0, 0, "F"),
    "R24": (35.6, 7.0, 0, "F"),
    "R25": (35.6, 20.0, 0, "F"),
    # --- RGB LED ---------------------------------------------------------------
    "R26": (43.6, 16.8, 90, "F"),
    "D9": (45.2, 41.4, 0, "F"),
    "C30": (40.8, 40.4, 90, "F"),
    "D10": (38.8, 36.6, 90, "F"),
    # --- drive -------------------------------------------------------------------
    "J3": (56.0, 5.4, 180, "F"),
    "J4": (64.4, 5.4, 180, "F"),
    "U5": (56.0, 13.8, 180, "F"),
    "R18": (64.15, 15.0, 0, "F"),
    "R19": (64.15, 12.6, 0, "F"),
    "C24": (50.6, 10.5, 0, "F"),
    "C23": (56.0, 17.6, 0, "F"),
    "C25": (50.9, 14.78, 180, "F"),
    "C26": (51.7, 13.3, 270, "F"),
    # --- outputs (OUT1, OUT2, IO3, IO21) ------------------------------------------
    "J5": (52.8, 24.0, 0, "F"),
    "J6": (56.4, 24.0, 0, "F"),
    "J7": (60.0, 24.0, 0, "F"),
    "J8": (63.6, 24.0, 0, "F"),
    "D5": (52.8, 20.4, 90, "F"),
    "D6": (56.4, 20.4, 90, "F"),
    "D7": (60.0, 20.4, 90, "F"),
    "D8": (63.6, 20.4, 90, "F"),
    "R20": (44.6, 13.4, 90, "F"),
    "R21": (42.6, 13.4, 90, "F"),
    "R22": (44.6, 20.2, 90, "F"),
    "R23": (42.6, 20.2, 90, "F"),
    "C27": (70.4, 26.75, 90, "F"),     # radial 8 mm, body centre (70.4, 25.0)
    "J9": (52.8, 40.8, 0, "F"),
    "J10": (64.0, 40.8, 0, "F"),
}


BACK_LOGO = (40.0, 33.5)    # inside the cell B outline, visible with the cell out
MOUNT_HOLES = [(3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
# zip-tie slots (centre x, centre y, length, width) between the cells
SLOTS = []   # zip ties go through the M3 corner holes

NETCLASSES = {
    # name: (track, clearance, via_dia, via_drill, nets). Router widths; the heavy
    # current paths get extra copper from prewire() and the zones in route.py.
    "Pwr05": (0.5, 0.2, 0.8, 0.4, ["VSYS", "VFUSE", "B_NEG", "BMS_DRAIN", "+5V", "+5V_XIAO", "VHOLD",
                                   "BUCK_SW", "OUT1_VP", "OUT2_VP", "IO3_VP", "IO21_VP",
                                   "VBUS", "CHG_LX", "CHG_VSYS"]),
    "Pwr03": (0.3, 0.2, 0.6, 0.3, ["BAT+", "MID", "GND", "BAL1_D", "BAL2_D"]),
    "Motor": (0.4, 0.2, 0.8, 0.4, ["MOTL_A", "MOTL_B", "MOTR_A", "MOTR_B", "DRV_AISEN", "DRV_BISEN"]),
}
# Copper reserved for the high-current nets: (net, layer, x0, y0, x1, y1).
# prewire() puts router keepouts here; route.py replaces them with solid zones.
POWER_AREAS = [
    ("BAT+", "B", 1.0, 0.8, 11.6, 16.6),
    ("VFUSE", "F", 18.9, 0.7, 25.2, 5.5),
    ("B_NEG", "F", 3.6, 29.5, 9.8, 37.4),
    ("B_NEG", "B", 1.0, 29.0, 9.0, 38.0),
    ("BMS_DRAIN", "F", 10.4, 33.6, 21.0, 39.2),
    ("BMS_DRAIN", "B", 10.4, 33.6, 21.0, 39.2),
    ("MID", "B", 71.4, 8.0, 79.6, 38.0),
]
# Pre-routed wide tracks: (net, layer, width, [points])
PREWIRE = [
    ("BAT+", "B", 3.0, [(5.0, 15.0), (5.0, 10.0), (10.4, 5.7), (10.4, 2.3)]),
    ("VFUSE", "F", 2.5, [(20.32, 2.3), (20.32, 5.7)]),
    ("VFUSE", "F", 2.0, [(20.32, 3.9), (25.4, 3.9)]),       # onto the three source pads of Q3
    ("B_NEG", "B", 3.0, [(5.0, 31.0), (5.0, 36.0)]),
    ("B_NEG", "F", 3.0, [(5.0, 31.0), (5.0, 36.0)]),
    ("B_NEG", "F", 2.2, [(5.0, 35.76), (8.9, 35.76)]),
    ("BMS_DRAIN", "F", 3.0, [(11.8, 36.4), (19.6, 36.4)]),
    ("MID", "B", 3.0, [(75.0, 10.0), (75.0, 36.0)]),
    # VSYS backbone: Q3 tab -> along the top edge -> down the right side -> both ESC terminals
    ("VSYS", "B", 2.5, [(28.6, 3.4), (30.2, 1.8), (66.8, 1.8), (67.4, 2.4), (67.4, 35.6), (64.0, 38.0),
                        (54.4, 38.0), (52.8, 40.8)]),
    ("VSYS", "B", 2.5, [(64.0, 38.0), (64.0, 40.8)]),
    ("VSYS", "B", 1.0, [(27.4, 5.05), (27.4, 3.75), (28.2, 3.75), (28.6, 3.4)]),
    ("VSYS", "B", 1.0, [(28.2, 5.05), (28.2, 3.75)]),
    # gate pull-up R11 to VFUSE (the VFUSE pour area is closed to the router)
    ("VFUSE", "F", 0.5, [(20.32, 5.7), (21.6, 7.2), (23.4, 8.6), (24.2, 8.6)]),
    # HY2120 VSS to the cell stack bottom (B_NEG pour areas are closed to the router)
    ("B_NEG", "B", 0.5, [(5.0, 36.0), (7.0, 39.4), (13.9, 39.6)]),
    ("B_NEG", "F", 0.5, [(13.9, 39.6), (13.9, 40.8), (13.14, 41.45)]),
    # bottom-cell balancer (C33 / U8 VSS / R32) into the B_NEG pour
    ("B_NEG", "F", 0.5, [(14.7, 29.8), (14.7, 30.9), (13.6, 32.0), (9.4, 32.0)]),
    # DRV8833 (rotated 180): sense pins straight to R18/R19, motor outputs via planned vias
    ("DRV_BISEN", "F", 0.3, [(58.86, 12.83), (62.45, 12.83), (62.69, 12.6)]),
    ("DRV_AISEN", "F", 0.3, [(58.86, 14.78), (62.47, 14.78), (62.69, 15.0)]),
    ("MOTR_A", "F", 0.35, [(58.86, 12.17), (59.9, 12.17), (60.6, 11.47), (63.2, 8.87), (64.4, 7.67), (64.4, 5.4)]),
    ("MOTR_B", "F", 0.3, [(58.86, 13.47), (60.4, 13.47)]),
    ("MOTR_B", "B", 0.35, [(60.4, 13.47), (60.4, 7.0), (60.9, 6.5), (60.9, 5.4)]),
    ("MOTL_B", "F", 0.3, [(58.86, 14.12), (61.3, 14.12)]),
    ("MOTL_B", "B", 0.35, [(61.3, 14.12), (62.0, 14.82), (62.0, 17.2), (51.8, 17.2), (51.8, 7.0), (52.5, 6.3), (52.5, 5.4)]),
    ("MOTL_A", "F", 0.3, [(58.86, 15.42), (60.4, 15.42)]),
    ("MOTL_A", "B", 0.35, [(60.4, 15.42), (60.4, 16.4), (53.6, 16.4), (53.6, 7.2), (55.4, 6.0), (56.0, 5.4)]),
    ("DRV_SLEEP", "F", 0.25, [(58.86, 16.08), (59.725, 16.08), (59.725, 17.6)]),
    # IP2320 power loop: LX pin 8 -> C4 -> L1, VIN pin 6 -> L1 -> C1, VSYS pin 1 -> C2, VOUT pin 2 -> C3
    ("CHG_LX", "F", 0.8, [(19.6, 17.1), (22.6, 17.1)]),
    ("CHG_BST", "F", 0.3, [(19.6, 18.37), (21.0, 18.78)]),
    ("VBUS", "F", 0.8, [(19.6, 19.64), (20.6, 19.9), (23.0, 19.9)]),
    ("VBUS", "F", 0.8, [(22.2, 19.9), (21.65, 21.3), (21.65, 21.8)]),
    ("CHG_VSYS", "F", 0.6, [(11.95, 17.1), (14.0, 17.1)]),
    ("BAT+", "F", 0.4, [(11.95, 19.2), (12.9, 18.4), (14.0, 18.37)]),
    # DRV8833 charge pump / VINT caps on the logic side, VM drops to the bottom-layer VSYS
    ("DRV_VCP", "F", 0.3, [(51.7, 12.82), (53.14, 12.83)]),
    ("DRV_VINT", "F", 0.3, [(51.38, 14.78), (53.14, 14.78)]),
    ("VSYS", "F", 0.3, [(51.0, 13.75), (51.7, 13.78), (52.1, 13.47), (53.14, 13.47)]),
    ("VSYS", "B", 0.5, [(51.0, 13.75), (51.0, 8.0), (50.0, 7.0), (50.0, 2.6)]),
    # C24 (VM decoupling) straight down onto that bottom-layer VSYS run, clear of the BIN lanes
    ("VSYS", "F", 0.4, [(49.8, 10.5), (50.4, 9.4), (51.0, 9.0)]),
    # C22 (I2C pull-up decoupling) GND: the bottom layer under it is the VSYS backbone, so via to the side
    ("GND", "F", 0.3, [(39.2, 3.83), (40.4, 3.83)]),
]
# Thermal / current vias: (net, [(x, y), ...])
PREVIAS = [
    ("GND", [(16.5 + dx, 19.0 + dy) for dx in (-0.55, 0.55) for dy in (-1.0, 0, 1.0)]),   # U1 EP
    ("GND", [(56.0 + dx, 13.8 + dy) for dx in (-0.9, 0.9) for dy in (-1.5, -0.5, 0.5, 1.5)]),  # U5 EP
    ("VSYS", [(27.4, 3.75), (28.2, 3.75), (27.4, 5.05), (28.2, 5.05)]),                    # Q3 drain pad
    ("B_NEG", [(13.9, 39.6)]),
    ("MOTR_B", [(60.4, 13.47)]),
    ("MOTL_B", [(61.3, 14.12)]),
    ("MOTL_A", [(60.4, 15.42)]),
    ("VSYS", [(51.0, 13.75), (51.0, 9.0)]),
    ("GND", [(40.4, 3.83)]),
    ("BMS_DRAIN", [(11.2, 36.4), (12.6, 36.4), (19.0, 36.4), (20.4, 36.4), (15.7, 36.4)]),  # Q1/Q2 tabs
]
DEFAULT = (0.25, 0.2, 0.6, 0.3)


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = CGW if lib == "cgw" else os.path.join(STD, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def add_text(board, txt, x, y, size=1.0, layer=pcbnew.F_SilkS, angle=0, bold=False, justify=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(mm(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
    t.SetTextThickness(pcbnew.FromMM(size * (0.2 if bold else 0.15)))
    t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    if layer in (pcbnew.B_SilkS, pcbnew.B_Fab, pcbnew.B_Cu):
        t.SetMirrored(True)
    if justify == "left":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    elif justify == "right":
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)
    return t


def add_seg(board, x1, y1, x2, y2, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(mm(x1, y1))
    s.SetEnd(mm(x2, y2))
    s.SetLayer(layer)
    s.SetWidth(pcbnew.FromMM(w))
    board.Add(s)


def add_arc(board, cx, cy, sx, sy, angle_deg, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(mm(cx, cy))
    s.SetStart(mm(sx, sy))
    s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(angle_deg, pcbnew.DEGREES_T), True)
    s.SetLayer(layer)
    s.SetWidth(pcbnew.FromMM(w))
    board.Add(s)


def add_rect(board, x1, y1, x2, y2, layer, w=0.15):
    for a, b, c, d in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)):
        add_seg(board, a, b, c, d, layer, w)


def outline(board, r=2.0):
    add_seg(board, r, 0, W - r, 0)
    add_seg(board, W, r, W, H - r)
    add_seg(board, W - r, H, r, H)
    add_seg(board, 0, H - r, 0, r)
    add_arc(board, r, r, 0, r, 90)
    add_arc(board, W - r, r, W - r, 0, 90)
    add_arc(board, W - r, H - r, W, H - r, 90)
    add_arc(board, r, H - r, r, H, 90)
    for (cx, cy, ln, wd) in SLOTS:
        rr = wd / 2
        add_seg(board, cx - ln / 2 + rr, cy - rr, cx + ln / 2 - rr, cy - rr)
        add_seg(board, cx - ln / 2 + rr, cy + rr, cx + ln / 2 - rr, cy + rr)
        add_arc(board, cx + ln / 2 - rr, cy, cx + ln / 2 - rr, cy - rr, 180)
        add_arc(board, cx - ln / 2 + rr, cy, cx - ln / 2 + rr, cy + rr, 180)


def silkscreen(board, fps):
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS

    def near(ref, dx, dy, txt, size=0.8, angle=0, layer=F, bold=False):
        x, y, *_ = PLACE[ref]
        add_text(board, txt, x + dx, y + dy, size, layer, angle, bold)

    # charge input + fuse + switch
    add_text(board, "USB-C", 2.2, 17.0, 0.7, F, bold=True)
    add_text(board, "CHARGE", 2.6, 29.1, 0.7, F, bold=True)
    near("D1", 0, 1.3, "USB", 0.7)
    near("F1", 5.6, 1.7, "FUSE 20A", 0.8, bold=True)
    near("SW1", -1.0, -3.6, "OFF", 0.8)
    near("SW1", 4.6, -3.6, "ON", 0.8, bold=True)
    # motors
    for ref, lab in (("J3", "MOTOR L"), ("J4", "MOTOR R")):
        near(ref, -1.75, 5.1, lab, 0.75, bold=True)
        near(ref, 0, 3.9, "A", 0.7)
        near(ref, -3.5, 3.9, "B", 0.7)
    # PWM outputs: pin legend at the left, names under each header
    for i, lab in enumerate(("G", "V+", "S")):
        add_text(board, lab, PLACE["J5"][0] - 2.3, PLACE["J5"][1] + i * 2.54, 0.7, F)
    for ref, lab in (("J5", "OUT1"), ("J6", "OUT2"), ("J7", "IO3"), ("J8", "IO21")):
        near(ref, 0, 7.6, lab, 0.7, bold=True)
    # ESC power
    for ref, lab in (("J9", "ESC PWR 1"), ("J10", "ESC PWR 2")):
        near(ref, 2.54, -6.9, lab, 0.7)
        near(ref, -1.7, -6.9, "+", 1.0, bold=True)
        near(ref, 6.8, -6.9, "-", 1.0, bold=True)
    # I2C
    near("J2", 0, -2.2, "I2C", 0.7, bold=True)
    for i, lab in enumerate(("G", "3V3", "SCL", "SDA")):
        near("J2", 2.15, i * 2.54, lab, 0.6)      # tight gap to the XIAO outline
    near("D9", 0, 3.5, "STATUS", 0.7)
    for ref, lab, dx, dy in (("TP4", "5V", 1.8, 0), ("TP5", "3V3", 1.9, 0), ("TP6", "GND", 2.0, 0),
                             ("TP7", "MID", 0, 1.7)):
        near(ref, dx, dy, lab, 0.7)
    # title
    add_text(board, "CARDBOARD BOT v2", 31.2, 36.7, 0.9, F, bold=True)
    add_text(board, "COLUMBIA GADGET WORKS", 31.6, 37.9, 0.7, F)

    # bottom: cells, polarity, assembly warnings
    for i, (cy, plus_left) in enumerate(((CELL_Y[0], True), (CELL_Y[1], False))):
        x0, x1 = 8.0, 72.0
        add_rect(board, x0, cy - 9.0, x1, cy + 9.0, B, 0.2)
        add_text(board, "+" if plus_left else "-", x0 + 3.0, cy, 3.0, B, bold=True)
        add_text(board, "-" if plus_left else "+", x1 - 3.0, cy, 3.0, B, bold=True)
        add_text(board, f"CELL {'AB'[i]}", 26.0, cy + (5.5 if i == 0 else -5.5), 1.2, B, bold=True)
    add_text(board, "TRIM ALL LEADS FLUSH + KAPTON TAPE BEFORE FITTING CELLS", 40.0, 23.0, 0.75, B, bold=True)
    add_text(board, "2S 18650: flat top, unprotected, 20A+, matched pairs", 50.0, CELL_Y[1] + 5.5, 0.7, B)
    add_text(board, "github.com/ColumbiaGadgetWorks/cardboard-bot-v2  rev A", 50.0, CELL_Y[0] + 5.5, 0.7, B)


def layer_id(side):
    return pcbnew.F_Cu if side == "F" else pcbnew.B_Cu


def prewire(board, nets):
    for net, side, w, pts in PREWIRE:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(mm(x1, y1))
            t.SetEnd(mm(x2, y2))
            t.SetWidth(pcbnew.FromMM(w))
            t.SetLayer(layer_id(side))
            t.SetNet(nets[net])
            t.SetLocked(True)
            board.Add(t)
    for net, pts in PREVIAS:
        for (x, y) in pts:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(mm(x, y))
            # 0.5 mm vias where they sit between 0.5/0.65 mm pitch pins (JLC: 0.3 drill, 0.45 min dia)
            v.SetWidth(pcbnew.FromMM(0.5 if net in ("SDA", "SCL", "MOTR_B", "MOTL_B", "MOTL_A") else 0.6))
            v.SetDrill(pcbnew.FromMM(0.3))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(nets[net])
            v.SetLocked(True)
            board.Add(v)
    for net, side, x0, y0, x1, y1 in POWER_AREAS:
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetDoNotAllowTracks(True)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowCopperPour(False)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        z.SetLayer(layer_id(side))
        z.SetZoneName(f"KEEPOUT_{net}")
        ol = z.Outline()
        ol.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ol.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
        board.Add(z)


def main():
    board = pcbnew.BOARD()
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2)
    ds.m_TrackMinWidth = pcbnew.FromMM(0.2)
    ds.m_ViasMinSize = pcbnew.FromMM(0.5)
    ds.m_MinThroughDrill = pcbnew.FromMM(0.3)
    ds.m_MinClearance = pcbnew.FromMM(0.2)
    ds.m_HoleClearance = pcbnew.FromMM(0.25)
    ds.m_CopperEdgeClearance = pcbnew.FromMM(0.4)
    ds.m_MinSilkTextHeight = pcbnew.FromMM(0.5)
    ds.m_MinSilkTextThickness = pcbnew.FromMM(0.075)

    nets = {}

    def net(name):
        if name not in nets:
            ni = pcbnew.NETINFO_ITEM(board, name)
            board.Add(ni)
            nets[name] = ni
        return nets[name]

    fps = {}
    for p in circuit.parts:
        ref = p["ref"]
        if ref not in PLACE:
            print("NOT PLACED:", ref)
            continue
        fp = load_fp(p["fp"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        x, y, rot, side = PLACE[ref]
        board.Add(fp)
        fp.SetPosition(mm(x, y))
        fp.SetOrientationDegrees(rot)
        if side == "B":
            fp.Flip(fp.GetPosition(), False)
        if p["place"] != "jlc":
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        if p["place"] == "none":
            fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM)
        fp.SetProperty("LCSC", p.get("lcsc", ""))
        fp.SetProperty("MPN", p.get("mpn", ""))
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.6), pcbnew.FromMM(0.6)))
        fp.Reference().SetTextThickness(pcbnew.FromMM(0.1))
        fp.Reference().SetVisible(False)    # refs go on the assembly drawing (Fab), not the silk
        pins = p["pins"]
        for pad in fp.Pads():
            num = pad.GetNumber()
            if num == "":
                if ref in ("Q1", "Q2", "Q3") and pad.IsOnCopperLayer():
                    n = pins.get("5")
                    pad.SetNet(net(n))
                continue
            n = pins.get(num)
            if n is None and ref == "U1" and num == "25":
                n = "GND"
            if n is None and num not in pins:
                # exposed pad / mounting pads of known parts
                if ref in ("U5",) and num == "17":
                    n = "GND"
            if n:
                pad.SetNet(net(n))
        fps[ref] = fp

    # mounting holes + logos
    for i, (x, y) in enumerate(MOUNT_HOLES):
        fp = load_fp("MountingHole:MountingHole_3.2mm_M3")
        fp.SetReference(f"H{i + 1}")
        fp.Reference().SetVisible(False)
        board.Add(fp)
        fp.SetPosition(mm(x, y))
    logo = load_fp("cgw:CGW_Logo_7mm")
    logo.SetReference("LOGO1")
    board.Add(logo)
    logo.SetPosition(mm(24.3, 42.0))
    logo_b = load_fp("cgw:CGW_Logo_Small_Back")
    logo_b.SetReference("LOGO2")
    board.Add(logo_b)
    logo_b.SetPosition(mm(*BACK_LOGO))
    logo_b.Flip(logo_b.GetPosition(), False)

    outline(board)
    silkscreen(board, fps)
    prewire(board, nets)

    board.Save(PCB)
    write_project()
    print("saved", PCB, "with", len(fps), "footprints and", len(nets), "nets")


def write_project():
    pro = os.path.join(HW, "cardboard-bot.kicad_pro")
    classes = [{
        "name": "Default", "clearance": DEFAULT[1], "track_width": DEFAULT[0], "via_diameter": DEFAULT[2],
        "via_drill": DEFAULT[3], "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25,
        "diff_pair_width": 0.2, "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12,
        "line_style": 0, "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
    }]
    patterns = []
    for name, (tw, cl, vd, vdr, nl) in NETCLASSES.items():
        c = dict(classes[0])
        c.update(name=name, track_width=tw, clearance=cl, via_diameter=vd, via_drill=vdr)
        classes.append(c)
        patterns += [{"netclass": name, "pattern": n} for n in nl]
    data = {
        "board": {"design_settings": {"rules": {"min_clearance": 0.2, "min_track_width": 0.2,
                                                 "min_via_diameter": 0.5, "min_through_hole_diameter": 0.3,
                                                 "min_copper_edge_clearance": 0.4, "min_hole_clearance": 0.25,
                                                 "min_text_height": 0.6, "min_text_thickness": 0.09}}},
        "meta": {"filename": "cardboard-bot.kicad_pro", "version": 1},
        "net_settings": {"classes": classes, "meta": {"version": 3}, "netclass_patterns": patterns},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [],
        "text_variables": {},
    }
    with open(pro, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    main()
