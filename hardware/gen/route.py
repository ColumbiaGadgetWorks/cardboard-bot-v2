"""Route the board: Freerouting (via DSN/SES), thermal vias, copper zones, fill.

Run with KiCad's Python:  /usr/bin/python3.12 gen/route.py [--skip-autoroute]
Needs Java + freerouting-1.9.0.jar (FREEROUTING env var or ~/tools) and xvfb-run.
KiCad 7 can only import a Specctra session from the GUI, so this script parses
the .ses file itself and adds the tracks and vias.
"""
import os
import re
import subprocess
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
PCB = os.path.join(HW, "cardboard-bot.kicad_pcb")
JAR = os.environ.get("FREEROUTING", "/home/user/tools/freerouting-1.9.0.jar")
OX, OY = 100.0, 100.0
W, H = 80.0, 46.0


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))


# ---------------------------------------------------------------------------
# Minimal s-expression reader for Specctra session files
# ---------------------------------------------------------------------------
def tokenize(s):
    for m in re.finditer(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', s):
        yield m.group(0)


def parse(s):
    stack = [[]]
    for t in tokenize(s):
        if t == "(":
            stack.append([])
        elif t == ")":
            e = stack.pop()
            stack[-1].append(e)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def import_ses(board, ses_path):
    tree = parse(open(ses_path).read())
    routes = find(tree, "routes")[0]
    res = find(routes, "resolution")[0]
    scale = 1.0 / (1000.0 * float(res[2]))          # (um * res) -> mm
    stacks = {}
    for ps in find(find(routes, "library_out")[0], "padstack") if find(routes, "library_out") else []:
        m = re.match(r'Via\[\d+-\d+\]_(\d+):(\d+)_um', ps[1])
        if m:
            stacks[ps[1]] = (int(m.group(1)) / 1000.0, int(m.group(2)) / 1000.0)
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    nt, nv = 0, 0
    for net in find(find(routes, "network_out")[0], "net"):
        ni = board.FindNet(net[1])
        for wire in find(net, "wire"):
            for path in find(wire, "path"):
                layer = layers[path[1]]
                width = float(path[2]) * scale
                pts = [float(v) * scale for v in path[3:] if not isinstance(v, list)]
                xy = [(pts[i], -pts[i + 1]) for i in range(0, len(pts) - 1, 2)]
                for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
                    t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
                    t.SetWidth(pcbnew.FromMM(width))
                    t.SetLayer(layer)
                    t.SetNet(ni)
                    board.Add(t)
                    nt += 1
        for via in find(net, "via"):
            dia, drill = stacks.get(via[1], (0.6, 0.3))
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(float(via[2]) * scale), pcbnew.FromMM(-float(via[3]) * scale)))
            v.SetWidth(pcbnew.FromMM(dia))
            v.SetDrill(pcbnew.FromMM(drill))
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(ni)
            board.Add(v)
            nv += 1
    return nt, nv


# ---------------------------------------------------------------------------
# Thermal vias in exposed pads, zones
# ---------------------------------------------------------------------------
def add_via(board, x_abs, y_abs, net, dia=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pcbnew.VECTOR2I(x_abs, y_abs))
    v.SetWidth(pcbnew.FromMM(dia))
    v.SetDrill(pcbnew.FromMM(drill))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net)
    board.Add(v)


def add_zone(board, net, layer, pts, priority=0, solid=False, clearance=0.25, min_w=0.25):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    z.SetAssignedPriority(priority)
    z.SetLocalClearance(pcbnew.FromMM(clearance))
    z.SetMinThickness(pcbnew.FromMM(min_w))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if solid else pcbnew.ZONE_CONNECTION_THT_THERMAL)
    z.SetThermalReliefGap(pcbnew.FromMM(0.3))
    z.SetThermalReliefSpokeWidth(pcbnew.FromMM(0.6))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        ol.Append(pcbnew.FromMM(OX + x), pcbnew.FromMM(OY + y))
    board.Add(z)
    return z


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def zones(board):
    sys.path.insert(0, HERE)
    import gen_pcb
    full = rect(0.3, 0.3, W - 0.3, H - 0.3)
    add_zone(board, "GND", pcbnew.B_Cu, full, priority=0)
    add_zone(board, "GND", pcbnew.F_Cu, full, priority=0)
    for net, side, x0, y0, x1, y1 in gen_pcb.POWER_AREAS:
        add_zone(board, net, pcbnew.F_Cu if side == "F" else pcbnew.B_Cu, rect(x0, y0, x1, y1),
                 priority=5, solid=True)


def stitch(board, pitch=3.0):
    """GND stitching vias wherever both GND pours are solid and nothing else is near."""
    gz = [z for z in board.Zones() if z.GetNetname() == "GND"]
    gnd = board.FindNet("GND")
    r = pcbnew.FromMM(0.3)
    margin = pcbnew.FromMM(0.3 + 0.3)
    items = list(board.GetTracks()) + [p for fp in board.GetFootprints() for p in fp.Pads()]
    holes = [fp for fp in board.GetFootprints() if fp.GetReference().startswith("H")]
    n = 0
    y = 1.5
    while y < H - 1.4:
        x = 1.5
        while x < W - 1.4:
            pos = mm(x, y)
            ok = True
            for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
                z = [q for q in gz if q.GetLayer() == lay][0]
                for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)):
                    if not z.HitTestFilledArea(lay, pcbnew.VECTOR2I(pos.x + dx, pos.y + dy), pcbnew.FromMM(0.25) * -1 if False else 0):
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                for it in items:
                    if it.GetNetname() == "GND" and it.GetClass() == "PCB_VIA":
                        if it.HitTest(pos, pcbnew.FromMM(1.0)):
                            ok = False
                            break
                    elif it.HitTest(pos, margin):
                        ok = False
                        break
            if ok:
                for h in holes:
                    if (h.GetPosition() - pos).EuclideanNorm() < pcbnew.FromMM(3.6):
                        ok = False
            if ok:
                v = pcbnew.PCB_VIA(board)
                v.SetPosition(pos)
                v.SetWidth(pcbnew.FromMM(0.6))
                v.SetDrill(pcbnew.FromMM(0.3))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(gnd)
                board.Add(v)
                items.append(v)
                n += 1
            x += pitch
        y += pitch
    return n


def autoroute():
    b = pcbnew.LoadBoard(PCB)       # still has the keepout rule areas from gen_pcb
    dsn = "/tmp/cb.dsn"
    ses = "/tmp/cb.ses"
    pcbnew.ExportSpecctraDSN(b, dsn)
    cmd = ["xvfb-run", "-a", "java", "-jar", JAR, "-de", dsn, "-do", ses, "-mp", "100"]
    print("running freerouting ...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3600)
    return ses


def stage_import(ses):
    b = pcbnew.LoadBoard(PCB)
    # keep the locked prewire, drop any previous autorouted copper; drop keepouts/zones
    for t in list(b.GetTracks()):
        if not t.IsLocked():
            b.Remove(t)
    for z in list(b.Zones()):
        b.Remove(z)
    nt, nv = import_ses(b, ses)
    print(f"imported {nt} track segments and {nv} vias")
    b.Save(PCB)


def stage_zones():
    b = pcbnew.LoadBoard(PCB)
    zones(b)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("zones added and filled")


def stage_stitch():
    b = pcbnew.LoadBoard(PCB)
    print("stitching vias:", stitch(b))
    b.Save(PCB)


def stage_fill():
    b = pcbnew.LoadBoard(PCB)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(PCB)
    print("refilled, saved", PCB)


def stage_drop_keepouts():
    """The KEEPOUT_* rule areas only steer the routers; the solid pours replace them."""
    b = pcbnew.LoadBoard(PCB)
    for z in list(b.Zones()):
        if z.GetIsRuleArea() and z.GetZoneName().startswith("KEEPOUT_"):
            b.Delete(z)
    b.Save(PCB)
    print("router keepouts removed")


def main():
    # each stage runs in its own process: KiCad 7's SWIG wrappers get confused when
    # zones are removed and re-added inside one session
    if len(sys.argv) > 2 and sys.argv[1] == "--stage":
        st = sys.argv[2]
        {"import": lambda: stage_import(sys.argv[3]), "zones": stage_zones,
         "stitch": stage_stitch, "fill": stage_fill, "drop-keepouts": stage_drop_keepouts}[st]()
        return
    ses = "/tmp/cb.ses" if "--skip-autoroute" in sys.argv else autoroute()
    for st in (["import", ses], ["zones"], ["stitch"], ["fill"]):
        subprocess.run([sys.executable, __file__, "--stage"] + st, check=True)


if __name__ == "__main__":
    main()
