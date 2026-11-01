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

W, H = 60.0, 46.0          # board size (mm)
OX, OY = 100.0, 100.0      # board origin on the KiCad page

# Screw terminals sit with their wire entries at the board edge: rotation 270 = wires from the left,
# 90 = from the right (the KiCad Phoenix footprints open toward +Y at rotation 0).
# ref: (x, y, rotation_deg, side)   side F = top
PLACE = {
    # --- left edge: battery in, left motor --------------------------------
    "J1": (4.6, 3.6, 270, "F"),         # BATTERY: pin 1 (+) top, pin 2 (-) below
    "J3": (4.5, 15.0, 270, "F"),        # LEFT MOTOR
    # --- top edge: fuse, switch pads, VSYS bulk ----------------------------
    "F1": (15.0, 2.3, 0, "F"),
    "SW1": (30.6, 3.0, 0, "F"),         # VFUSE pad here, VSYS pad 4.8 mm right
    "C1": (40.4, 5.0, 0, "F"),          # 470 uF VSYS bulk, next to the ESC terminals
    "D1": (43.5, 12.0, 0, "F"),         # SMAJ13A
    # --- right edge: ESC power, right motor --------------------------------
    "J8": (55.4, 8.6, 90, "F"),         # ESC PWR 1: pin 1 (+) lower, pin 2 (-) upper
    "J9": (55.4, 20.8, 90, "F"),        # ESC PWR 2
    "J4": (55.5, 31.5, 90, "F"),        # RIGHT MOTOR
    # --- left driver -------------------------------------------------------
    "U3": (13.4, 16.8, 180, "F"),       # outputs face J3, inputs face the XIAO
    "C14": (12.2, 12.5, 0, "F"),
    "C15": (15.7, 12.5, 0, "F"),
    "R7": (10.0, 22.4, 0, "F"),         # sense resistor
    # pull-downs and output resistors, two columns between the left driver and the XIAO
    "R11": (14.0, 22.3, 0, "F"), "R12": (17.4, 22.3, 0, "F"),
    "R18": (14.0, 24.1, 0, "F"), "R15": (17.4, 24.1, 0, "F"),
    "R19": (14.0, 25.9, 0, "F"), "R16": (17.4, 25.9, 0, "F"),
    "R20": (14.0, 27.7, 0, "F"), "R17": (17.4, 27.7, 0, "F"),
    "TP1": (14.0, 31.0, 0, "F"), "TP2": (17.4, 31.0, 0, "F"),
    # --- right driver ------------------------------------------------------
    "U4": (46.6, 29.7, 0, "F"),
    "C16": (46.0, 25.2, 0, "F"),
    "C17": (42.6, 25.2, 0, "F"),
    "R8": (52.0, 36.5, 270, "F"),
    "R13": (40.2, 28.8, 90, "F"),
    "R14": (40.2, 31.9, 90, "F"),
    # --- bottom left: outputs and I2C --------------------------------------
    "D4": (3.4, 31.6, 90, "F"), "D5": (7.0, 31.6, 90, "F"), "D6": (10.6, 31.6, 90, "F"),
    "J5": (3.4, 36.2, 0, "F"), "J6": (7.0, 36.2, 0, "F"), "J7": (10.6, 36.2, 0, "F"),
    "J2": (14.6, 36.2, 0, "F"),
    # --- XIAO, USB end at the bottom edge ----------------------------------
    "U2": (29.5, 35.5, 180, "F"),
    # under the XIAO (all parts lower than its sockets)
    "R21": (25.4, 27.6, 0, "F"), "D7": (29.6, 27.6, 0, "F"), "C18": (33.7, 27.6, 0, "F"),
    "R9": (25.4, 30.0, 0, "F"), "R10": (25.4, 31.7, 0, "F"), "C13": (25.4, 33.4, 0, "F"),
    "U1": (29.9, 31.4, 0, "F"), "C5": (33.9, 30.0, 0, "F"),
    "R1": (33.9, 31.7, 0, "F"), "R2": (33.9, 33.4, 0, "F"),
    "L1": (29.7, 36.2, 0, "F"),
    "C6": (34.3, 36.0, 90, "F"),
    "D2": (25.3, 38.6, 90, "F"),
    "C3": (28.5, 40.3, 90, "F"), "C4": (30.6, 40.3, 90, "F"),
    "C7": (34.3, 39.7, 90, "F"),
    "D3": (27.2, 43.3, 0, "F"), "C9": (31.6, 43.3, 0, "F"), "C10": (34.3, 43.0, 90, "F"),
    # battery divider in the strip right of the XIAO, beside D1 (GPIO3)
    "R5": (39.7, 35.3, 90, "F"), "R6": (39.7, 38.4, 90, "F"), "C12": (39.7, 41.5, 90, "F"),
    # I2C pull-ups and 3V3 decoupling between the I2C header and the XIAO
    "R3": (17.6, 35.6, 90, "F"), "R4": (17.6, 38.8, 90, "F"), "C11": (19.3, 37.2, 90, "F"),
    # --- top middle: LED strip, DIN end at the left ------------------------
    "J10": (28.2, 14.5, 180, "F"),
    # --- bottom right: hold-up capacitor -----------------------------------
    "C2": (43.8, 40.2, 0, "F"),
}
FRONT_LOGO = None            # no room on top; the logo is on the back
BACK_LOGO = (24.0, 14.5)
MOUNT_HOLES = [(3.5, 25.5), (56.5, 42.5)]
SLOTS = []

NETCLASSES = {
    # name: (track, clearance, via_dia, via_drill, nets). Router widths; the heavy
    # current paths get extra copper from prewire() and the zones in route.py.
    "Pwr05": (0.5, 0.2, 0.8, 0.4, ["+5V", "+5V_XIAO", "VHOLD", "BUCK_SW", "OUT1_VP", "OUT2_VP", "OUT3_VP"]),
    "Pwr08": (0.8, 0.2, 0.8, 0.4, ["VSYS", "VFUSE", "BAT+"]),
    "Pwr03": (0.3, 0.2, 0.6, 0.3, ["GND"]),
    "Motor": (0.6, 0.2, 0.8, 0.4, ["MOTL_A", "MOTL_B", "MOTR_A", "MOTR_B", "ISEN_L", "ISEN_R"]),
}
# Copper reserved for the high-current nets: (net, layer, x0, y0, x1, y1).
# prewire() puts router keepouts here; route.py replaces them with solid zones.
POWER_AREAS = [
    ("BAT+", "F", 1.6, 0.7, 16.6, 6.2),       # battery terminal + to the fuse
    ("VFUSE", "F", 23.4, 0.7, 32.0, 6.4),     # fuse to the switch pad
]
# Pre-routed wide tracks: (net, layer, width, [points])
PREWIRE = [
    # switch pad -> C1 -> both ESC terminals (bottom layer, 2 mm)
    ("VSYS", "B", 2.0, [(35.4, 3.0), (40.4, 5.0)]),
    ("VSYS", "B", 2.0, [(40.4, 5.0), (44.0, 8.6), (55.4, 8.6)]),
    ("VSYS", "B", 2.0, [(44.0, 8.6), (49.0, 13.6), (49.0, 20.8), (55.4, 20.8)]),
    # on to the right driver's VM pin (via just below it)
    ("VSYS", "B", 1.2, [(49.0, 20.8), (49.0, 33.0)]),
    ("VSYS", "F", 0.8, [(49.0, 33.0), (49.475, 31.605)]),
    # across the top to the left driver (under the fuse holder and LED strip)
    ("VSYS", "B", 1.2, [(40.4, 5.0), (38.4, 8.4), (11.0, 8.4), (9.8, 9.6), (9.8, 12.4)]),
    ("VSYS", "F", 0.8, [(9.8, 12.4), (10.825, 12.4)]),
    ("VSYS", "F", 0.8, [(10.825, 12.4), (10.525, 14.895)]),
    # motor outputs straight to their terminals
    ("MOTL_A", "F", 1.0, [(10.525, 16.165), (7.6, 16.165), (6.5, 15.0), (4.5, 15.0)]),
    ("MOTL_B", "F", 1.0, [(10.525, 18.705), (6.6, 18.705), (6.4, 18.5), (4.5, 18.5)]),
    ("MOTR_A", "F", 1.0, [(49.475, 30.335), (52.4, 30.335), (53.6, 31.5), (55.5, 31.5)]),
    ("MOTR_B", "F", 1.0, [(49.475, 27.795), (53.3, 27.795), (53.5, 28.0), (55.5, 28.0)]),
    # left sense pin sits between the two outputs: drop to the bottom layer right away
    ("ISEN_L", "F", 0.6, [(10.525, 17.435), (8.6, 17.435)]),
    ("ISEN_L", "B", 0.8, [(8.6, 17.435), (8.6, 20.9)]),
    ("ISEN_L", "F", 0.6, [(8.6, 20.9), (8.45, 22.4)]),
    ("ISEN_R", "F", 0.6, [(49.475, 29.065), (51.0, 29.065)]),
    ("ISEN_R", "B", 0.8, [(51.0, 29.065), (51.0, 33.6)]),
    ("ISEN_R", "F", 0.6, [(51.0, 33.6), (52.0, 34.95)]),
]
# Thermal / current vias: (net, [(x, y), ...])
PREVIAS = [
    ("VSYS", [(49.0, 33.0), (9.8, 12.4)]),
    ("ISEN_L", [(8.6, 17.435), (8.6, 20.9)]),
    ("ISEN_R", [(51.0, 29.065), (51.0, 33.6)]),
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

    # battery in (pin 1 + at the top), fuse, switch
    near("J1", 6.3, 0, "+", 1.3, bold=True)
    near("J1", 6.3, 5.08, "-", 1.3, bold=True)
    near("J1", 6.3, 2.54, "BAT", 0.7, 90, bold=True)
    near("F1", 5.0, 1.7, "FUSE 20A", 0.8, bold=True)
    near("SW1", 2.4, 2.3, "SWITCH", 0.7, bold=True)
    near("SW1", 2.4, 3.3, "10A+ DC", 0.6)
    # ESC power (pin 1 + below pin 2 -)
    for ref, lab in (("J8", "ESC 1"), ("J9", "ESC 2")):
        near(ref, -6.7, 0, "+", 1.2, bold=True)
        near(ref, -6.7, -5.08, "-", 1.2, bold=True)
        near(ref, -6.7, -2.54, lab, 0.7, 90, bold=True)
    # motors on opposite edges
    add_text(board, "LEFT MOTOR", 8.85, 16.8, 0.7, F, 90, bold=True)
    add_text(board, "RIGHT MOTOR", 51.25, 29.7, 0.7, F, 90, bold=True)
    # outputs: G / V+ / S legend at the left edge, number under each header
    for i, lab in enumerate(("G", "V+", "S")):
        add_text(board, lab, 1.0, PLACE["J5"][1] + i * 2.54, 0.6, F)
    for ref, lab in (("J5", "OUT1"), ("J6", "OUT2"), ("J7", "OUT3")):
        near(ref, 0, 7.7, lab[-1], 0.9, bold=True)
    add_text(board, "OUT", 7.0, PLACE["J5"][1] - 2.1, 0.7, F, bold=True)
    near("J2", 0, -2.1, "I2C", 0.7, bold=True)
    for ref, lab in (("TP1", "3V3"), ("TP2", "GND")):
        near(ref, 0, 1.6, lab, 0.6)

    # back: logo, title, wiring notes
    add_text(board, "CARDBOARD BOT v2", 42.0, 12.0, 1.0, B, bold=True)
    add_text(board, "COLUMBIA GADGET WORKS  rev B", 42.0, 13.6, 0.7, B)
    add_text(board, "github.com/ColumbiaGadgetWorks/cardboard-bot-v2", 30.0, 25.3, 0.6, B)
    add_text(board, "2S or 3S LiPo only", 42.0, 15.2, 0.7, B)
    for i, lab in enumerate(("GND", "3V3", "SCL", "SDA")):
        add_text(board, lab, PLACE["J2"][0] - 2.4, PLACE["J2"][1] + i * 2.54, 0.6, B)


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
            v.SetWidth(pcbnew.FromMM(0.5 if net in ("BIN1", "BIN2", "MOTR_B", "MOTL_B", "MOTL_A") else 0.6))
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
                continue
            n = pins.get(num)
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
    if FRONT_LOGO:
        logo = load_fp("cgw:CGW_Logo_6mm")
        logo.SetReference("LOGO1")
        board.Add(logo)
        logo.SetPosition(mm(*FRONT_LOGO))
    logo_b = load_fp("cgw:CGW_Logo")
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
