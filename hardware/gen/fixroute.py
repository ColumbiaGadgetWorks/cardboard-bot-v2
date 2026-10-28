"""Small two-layer grid router for finishing / repairing connections.

Usage: /usr/bin/python3.12 gen/fixroute.py [--ripup NET,NET,...]
  1. optionally rips up the unlocked tracks/vias of the listed nets, plus every net that
     has a clearance-type DRC error,
  2. reads the unconnected pairs from KiCad's DRC report,
  3. routes each pair with A* on a 0.05 mm grid (both layers, vias allowed), keeping
     netclass clearance from all other copper, board edges, holes and power keepouts.
"""
import heapq
import math
import os
import re
import sys

import numpy as np
import pcbnew
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
PCB = os.path.join(HW, "cardboard-bot.kicad_pcb")
OX, OY = 100.0, 100.0
W, H = 80.0, 46.0
G = 0.05                     # grid (mm)
NX, NY = int(W / G) + 1, int(H / G) + 1
CLR = 0.2                    # copper clearance
EDGE = 0.45                  # copper to board edge
VIA_D, VIA_DRILL = 0.6, 0.3
SAFE = 0.035                 # rasterisation allowance (about half a grid diagonal)
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu)
QFN_NETS = {"GND"}            # nets that must fit between 0.65 mm pitch pins (DRV8833 GND)


def to_grid(x_nm, y_nm):
    return (int(round((pcbnew.ToMM(x_nm) - OX) / G)), int(round((pcbnew.ToMM(y_nm) - OY) / G)))


def to_nm(gx, gy):
    return pcbnew.VECTOR2I(pcbnew.FromMM(OX + gx * G), pcbnew.FromMM(OY + gy * G))


def poly_points(sps):
    out = []
    for i in range(sps.OutlineCount()):
        ch = sps.Outline(i)
        pts = [ch.CPoint(j) for j in range(ch.PointCount())]
        out.append([((pcbnew.ToMM(p.x) - OX) / G, (pcbnew.ToMM(p.y) - OY) / G) for p in pts])
    return out


def item_polys(item, layer, margin_mm):
    sps = pcbnew.SHAPE_POLY_SET()
    # default error location is ERROR_INSIDE; add the max error to the margin to stay safe
    item.TransformShapeToPolygon(sps, layer, pcbnew.FromMM(margin_mm + 0.005), pcbnew.FromMM(0.005))
    return poly_points(sps)


def draw_track(d, t, margin_mm):
    """Rasterise a track or via (plus margin) as a capsule / disc."""
    if t.GetClass() == "PCB_VIA":
        c = t.GetPosition()
        gx, gy = (pcbnew.ToMM(c.x) - OX) / G, (pcbnew.ToMM(c.y) - OY) / G
        r = (pcbnew.ToMM(t.GetWidth()) / 2 + margin_mm) / G
        d.ellipse([gx - r, gy - r, gx + r, gy + r], fill=1)
        return
    a, b = t.GetStart(), t.GetEnd()
    ax, ay = (pcbnew.ToMM(a.x) - OX) / G, (pcbnew.ToMM(a.y) - OY) / G
    bx, by = (pcbnew.ToMM(b.x) - OX) / G, (pcbnew.ToMM(b.y) - OY) / G
    r = (pcbnew.ToMM(t.GetWidth()) / 2 + margin_mm) / G
    d.line([ax, ay, bx, by], fill=1, width=int(math.ceil(2 * r)))
    for x, y in ((ax, ay), (bx, by)):
        d.ellipse([x - r, y - r, x + r, y + r], fill=1)


def region_cells(item, layer):
    """Grid cells covered by an item's own copper (no margin)."""
    img = Image.new("1", (NX, NY), 0)
    d = ImageDraw.Draw(img)
    if item.GetClass() == "PAD":
        for pl in item_polys(item, layer, -0.02):
            d.polygon(pl, fill=1)
    else:
        draw_track(d, item, -0.02)
    ys, xs = np.nonzero(np.array(img, dtype=bool))
    return list(zip(xs.tolist(), ys.tolist()))


def escape_cells(pad, ext_mm=0.6):
    """Cells on the pad's centre line, from its centre out past its outer end.
    At 0.5 mm pitch the legal corridor for a track centre is narrower than the grid
    step, so the centre line is opened explicitly; a track centred on it keeps
    clearance to both neighbours. Only the outward direction is opened, so nothing
    leaks toward an exposed pad. Square-ish pads (passives) get no lane."""
    if pad.HasHole():
        return []
    sz = pad.GetSize()
    w_, h_ = pcbnew.ToMM(sz.x), pcbnew.ToMM(sz.y)
    if max(w_, h_) < 1.8 * min(w_, h_):
        return []
    ang = math.radians(pad.GetOrientationDegrees())
    hl = max(w_, h_) / 2 + ext_mm
    if h_ > w_:
        ang += math.pi / 2
    ux, uy = math.cos(ang), -math.sin(ang)
    c = pad.GetPosition()
    cx, cy = pcbnew.ToMM(c.x) - OX, pcbnew.ToMM(c.y) - OY
    f = pad.GetParent().GetPosition()
    if (cx - (pcbnew.ToMM(f.x) - OX)) * ux + (cy - (pcbnew.ToMM(f.y) - OY)) * uy < 0:
        ux, uy = -ux, -uy
    cells = set()
    n = int(hl / (G / 2))
    for i in range(n + 1):
        d_ = i * G / 2
        cells.add((int(round((cx + d_ * ux) / G)), int(round((cy + d_ * uy) / G))))
    return list(cells)


def net_width(board, net):
    if net in QFN_NETS:
        return 0.25
    nc = board.FindNet(net).GetNetClassName()
    return {"Pwr05": 0.4, "Motor": 0.35, "Pwr03": 0.25}.get(nc, 0.25)


class Router:
    def __init__(self, board):
        self.b = board
        self.pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
        self.holes = [fp for fp in board.GetFootprints() if fp.GetReference().startswith("H")]

    def obstacles(self, net, w):
        """Boolean blocked[layer][y][x] for a track of width w on net."""
        m = CLR + w / 2 + SAFE
        masks = []
        for lay in LAYERS:
            img = Image.new("1", (NX, NY), 0)
            d = ImageDraw.Draw(img)
            for p in self.pads:
                if p.GetNetname() == net and p.GetNetname() != "":
                    continue
                if not p.IsOnLayer(lay) and not p.HasHole():
                    continue
                if p.IsOnLayer(lay):
                    for pl in item_polys(p, lay, m):
                        d.polygon(pl, fill=1)
                if p.HasHole():      # hole clearance on both layers
                    c = p.GetPosition()
                    r = pcbnew.ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2 + 0.25 + w / 2
                    gx, gy = to_grid(c.x, c.y)
                    d.ellipse([gx - r / G, gy - r / G, gx + r / G, gy + r / G], fill=1)
            for t in self.b.GetTracks():
                if t.GetNetname() == net:
                    continue
                if t.GetClass() == "PCB_VIA" or t.GetLayer() == lay:
                    draw_track(d, t, m)
            for z in self.b.Zones():
                if z.GetIsRuleArea() and z.IsOnLayer(lay):
                    owner = z.GetZoneName().replace("KEEPOUT_", "")
                    if owner != net:
                        for pl in poly_points(z.Outline()):
                            d.polygon(pl, fill=1)
            for h in self.holes:
                c = h.GetPosition()
                gx, gy = to_grid(c.x, c.y)
                r = 1.6 + 0.3 + w / 2
                d.ellipse([gx - r / G, gy - r / G, gx + r / G, gy + r / G], fill=1)
            a = np.array(img, dtype=bool)
            e = int(math.ceil((EDGE + w / 2) / G))
            a[:e, :] = a[-e:, :] = True
            a[:, :e] = a[:, -e:] = True
            # rounded corners (r = 2 mm)
            rr = 2.0 / G
            for cx, cy in ((rr, rr), (NX - 1 - rr, rr), (rr, NY - 1 - rr), (NX - 1 - rr, NY - 1 - rr)):
                yy, xx = np.ogrid[:NY, :NX]
                corner = ((xx - cx) ** 2 + (yy - cy) ** 2 > (rr - e) ** 2) & \
                         (((xx < rr) | (xx > NX - 1 - rr)) & ((yy < rr) | (yy > NY - 1 - rr)))
                a |= corner
            masks.append(a)
        # via sites: clear on both layers with via radius
        vm = CLR + VIA_D / 2 + SAFE
        vmask = []
        for li, lay in enumerate(LAYERS):
            img = Image.new("1", (NX, NY), 0)
            d = ImageDraw.Draw(img)
            for p in self.pads:
                if p.GetNetname() == net:
                    continue
                if p.IsOnLayer(lay):
                    for pl in item_polys(p, lay, vm):
                        d.polygon(pl, fill=1)
                if p.HasHole():
                    c = p.GetPosition()
                    r = pcbnew.ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2 + 0.3 + VIA_DRILL / 2 + 0.05
                    gx, gy = to_grid(c.x, c.y)
                    d.ellipse([gx - r / G, gy - r / G, gx + r / G, gy + r / G], fill=1)
            for t in self.b.GetTracks():
                if t.GetNetname() == net:
                    if t.GetClass() == "PCB_VIA":      # hole-to-hole spacing applies within a net too
                        c = t.GetPosition()
                        gx, gy = to_grid(c.x, c.y)
                        r = (VIA_DRILL + 0.3) / G
                        d.ellipse([gx - r, gy - r, gx + r, gy + r], fill=1)
                    continue
                if t.GetClass() == "PCB_VIA" or t.GetLayer() == lay:
                    draw_track(d, t, vm)
            vmask.append(np.array(img, dtype=bool))
        via_ok = ~(vmask[0] | vmask[1] | masks[0] | masks[1])
        return masks, via_ok

    def route(self, net, start_item, goal_item, start_layers, goal_layers):
        w = net_width(self.b, net)
        blocked, via_ok = self.obstacles(net, w)
        self.blocked = blocked
        # own-net pads: open only the centre-line escape lane (see escape_cells)
        for p in self.pads:
            if p.GetNetname() == net:
                for li, lay in enumerate(LAYERS):
                    if p.IsOnLayer(lay):
                        for (x, y) in escape_cells(p):
                            blocked[li][y, x] = False

        def term_cells(item, layers):
            out = []
            for li in layers:
                cells = region_cells(item, LAYERS[li])
                ok = [(x, y) for (x, y) in cells if not blocked[li][y, x]]
                if not ok:
                    c = item.GetPosition()
                    ok = [to_grid(c.x, c.y)]
                    blocked[li][ok[0][1], ok[0][0]] = False
                out += [(x, y, li) for (x, y) in ok]
            return out
        goals = set(term_cells(goal_item, goal_layers))
        starts = term_cells(start_item, start_layers)
        gl_list = list(goals)
        gcx = sum(g[0] for g in gl_list) / len(gl_list)
        gcy = sum(g[1] for g in gl_list) / len(gl_list)

        grad = max(math.hypot(g[0] - gcx, g[1] - gcy) for g in gl_list)

        def hfun(x, y, l):
            return max(0.0, math.hypot(x - gcx, y - gcy) - grad)

        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        openh = []
        best = {}
        for st in starts:
            best[st] = 0.0
            heapq.heappush(openh, (hfun(*st), 0.0, st, None))
        came = {}
        n = 0
        while openh:
            f, gcost, cur, prev = heapq.heappop(openh)
            if cur in came:
                continue
            came[cur] = prev
            n += 1
            if cur in goals:
                path = []
                c = cur
                while c is not None:
                    path.append(c)
                    c = came[c]
                return path[::-1], w
            if n > 4000000:
                break
            x, y, l = cur
            for dx, dy, c in moves:
                nx, ny = x + dx, y + dy
                if 0 <= nx < NX and 0 <= ny < NY and not blocked[l][ny, nx]:
                    nxt = (nx, ny, l)
                    # small penalty for bottom layer under the cells
                    ng = gcost + c
                    if ng < best.get(nxt, 1e18):
                        best[nxt] = ng
                        heapq.heappush(openh, (ng + hfun(nx, ny, l), ng, nxt, cur))
            if via_ok[y, x]:
                nl = 1 - l
                nxt = (x, y, nl)
                ng = gcost + 12.0
                if not blocked[nl][y, x] and ng < best.get(nxt, 1e18):
                    best[nxt] = ng
                    heapq.heappush(openh, (ng + hfun(x, y, nl), ng, nxt, cur))
        return None, w

    def clear_line(self, a, b):
        """True if every grid cell along a->b (same layer) is free for this track."""
        bl = self.blocked[a[2]]
        n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 1
        for i in range(n + 1):
            t = i / n
            x = a[0] + (b[0] - a[0]) * t
            y = a[1] + (b[1] - a[1]) * t
            # nearest cell; SAFE in the obstacle margin covers the half-cell offset
            if bl[int(round(y)), int(round(x))]:
                return False
        return True

    def pull(self, run):
        """String-pulling: replace the grid staircase by the longest straight hops that
        stay on free cells. The first and last hops are kept as found (pad escapes)."""
        if len(run) <= 3:
            return run
        out = [run[0], run[1]]
        i = 1
        last = len(run) - 2
        while i < last:
            j = min(last, i + 800)
            while j > i + 1 and not self.clear_line(run[i], run[j]):
                j -= 1
            out.append(run[j])
            i = j
        out.append(run[-1])
        # drop collinear leftovers
        pts = [out[0]]
        for k in range(1, len(out) - 1):
            a, b_, c = pts[-1], out[k], out[k + 1]
            if (b_[0] - a[0]) * (c[1] - b_[1]) != (b_[1] - a[1]) * (c[0] - b_[0]):
                pts.append(b_)
        pts.append(out[-1])
        return pts

    def commit(self, net, path, w):
        ni = self.b.FindNet(net)
        # split into runs per layer, insert vias at layer changes
        segs = []
        run = [path[0]]
        for p in path[1:]:
            if p[2] != run[-1][2]:
                segs.append(run)
                v = pcbnew.PCB_VIA(self.b)
                v.SetPosition(to_nm(p[0], p[1]))
                v.SetWidth(pcbnew.FromMM(VIA_D))
                v.SetDrill(pcbnew.FromMM(VIA_DRILL))
                v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(ni)
                self.b.Add(v)
                run = [p]
            else:
                run.append(p)
        segs.append(run)
        nseg = 0
        for run in segs:
            if len(run) < 2:
                continue
            pts = self.pull(run)
            for p1, p2 in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(self.b)
                t.SetStart(to_nm(p1[0], p1[1]))
                t.SetEnd(to_nm(p2[0], p2[1]))
                t.SetWidth(pcbnew.FromMM(w))
                t.SetLayer(LAYERS[p1[2]])
                t.SetNet(ni)
                self.b.Add(t)
                nseg += 1
        return nseg


def drc_items(board):
    rpt = "/tmp/fix_drc.rpt"
    # refill first so the GND pours connect what they can and stale fill isn't reported
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    t = open(rpt).read()
    return re.findall(r'\[(\w+)\]: (.*?)\n(.*?)(?=\n\[|\n\*\* |\Z)', t, re.S)


def find_item(board, desc, x, y):
    """Map a DRC item description back to (net, grid point, layers)."""
    pos = pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
    m = re.match(r"(?:PTH )?[Pp]ad (\S+) \[([^\]]*)\] of (\S+)", desc)
    if m:
        num, net, ref = m.groups()
        fp = board.FindFootprintByReference(ref)
        best = None
        for p in fp.Pads():
            if p.GetNumber() == num:
                d = (p.GetPosition() - pos).EuclideanNorm()
                if best is None or d < best[0]:
                    best = (d, p)
        p = best[1]
        c = p.GetPosition()
        layers = [i for i, l in enumerate(LAYERS) if p.IsOnLayer(l)]
        return net, to_grid(c.x, c.y), layers, p
    m = re.match(r"Track \[([^\]]*)\] on (\S)\.Cu", desc)
    if m:
        net, lay = m.groups()
        # pick the nearest point on that track
        bestd, bp = None, None
        for t in board.GetTracks():
            if t.GetNetname() == net and t.GetClass() == "PCB_TRACK":
                for q in (t.GetStart(), t.GetEnd()):
                    d = (q - pos).EuclideanNorm()
                    if bestd is None or d < bestd:
                        bestd, bp, bl, bt = d, q, t.GetLayer(), t
        return net, to_grid(bp.x, bp.y), [0 if bl == pcbnew.F_Cu else 1], bt
    m = re.match(r"Via \[([^\]]*)\]", desc)
    if m:
        v = None
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA" and (t.GetPosition() - pos).EuclideanNorm() < pcbnew.FromMM(0.05):
                v = t
        return m.group(1), to_grid(pos.x, pos.y), [0, 1], v
    return None, None, None, None


def ripup(board, nets):
    n = 0
    for t in list(board.GetTracks()):
        if t.GetNetname() in nets and not t.IsLocked():
            board.Remove(t)
            n += 1
    return n


def stage_ripup(extra):
    board = pcbnew.LoadBoard(PCB)
    rip = set(extra)
    for kind, msg, body in drc_items(board):
        if kind in ("clearance", "hole_clearance", "solder_mask_bridge", "track_dangling", "via_dangling",
                    "shorting_items", "copper_edge_clearance", "hole_near_hole", "holes_co_located"):
            for net in re.findall(r"\[([^\]]+)\]", body):
                rip.add(net)
    rip.discard("GND")      # GND is carried by the pours; never rip it up wholesale
    print("ripping up:", sorted(rip), ripup(board, rip), "items")
    board.Save(PCB)


def blockers(board, items, net, radius_mm=1.6):
    """Other nets with unlocked copper close to the given items."""
    found = set()
    rad = pcbnew.FromMM(radius_mm)
    for it in items:
        bb = it.GetBoundingBox()
        bb.Inflate(rad)
        for t in board.GetTracks():
            n = t.GetNetname()
            if n in (net, "GND") or t.IsLocked():
                continue
            if bb.Intersects(t.GetBoundingBox()):
                found.add(n)
    return found


def stage_route():
    board = pcbnew.LoadBoard(PCB)
    r = Router(board)
    failed = []
    import json
    state_f = "/tmp/fixroute_state.json"
    ripped_count = json.load(open(state_f)) if os.path.exists(state_f) else {}
    deleted = False
    for it in range(10):
        pairs = []
        for kind, msg, body in drc_items(board):
            if kind != "unconnected_items":
                continue
            refs = re.findall(r"@\(([\d.]+) mm, ([\d.]+) mm\): ([^\n]+)", body)
            if len(refs) == 2:
                pairs.append(refs)
        if not pairs:
            break
        # shortest connections first: they need the tight pin escapes most
        def prio(pr):
            txt = pr[0][2] + pr[1][2]
            fine = (" of U1 " in txt) or (" of U5 " in txt) or (" of J1 " in txt)
            dist = math.hypot(float(pr[0][0]) - float(pr[1][0]), float(pr[0][1]) - float(pr[1][1]))
            return (0 if fine else 1, dist)
        pairs.sort(key=prio)
        print(f"pass {it}: {len(pairs)} unconnected pairs")
        progress = False
        failed = []
        for a, b in pairs:
            na, pa, la, ia = find_item(board, a[2], float(a[0]), float(a[1]))
            nb, pb, lb, ib = find_item(board, b[2], float(b[0]), float(b[1]))
            if ia is None or ib is None:
                failed.append((a[2], b[2]))
                continue
            path, w = r.route(na, ia, ib, la, lb)
            if not path:
                # rip up nearby blockers once or twice each, then retry
                bl = {n for n in blockers(board, [ia, ib], na, 1.0) if ripped_count.get(n, 0) < 1}
                if bl:
                    for n in bl:
                        ripped_count[n] = ripped_count.get(n, 0) + 1
                    for t in [t for t in board.GetTracks() if t.GetNetname() in bl and not t.IsLocked()]:
                        board.Delete(t)
                    deleted = True
                    print(f"  ripped {sorted(bl)} for {na}")
                    path, w = r.route(na, ia, ib, la, lb)
                    progress = True
            if path:
                ns = r.commit(na, path, w)
                print(f"  routed {na}: {a[2][:34]} -> {b[2][:34]} ({ns} segs)")
                progress = True
            else:
                print(f"  FAILED {na}: {a[2][:40]} -> {b[2][:40]}")
                failed.append((a[2], b[2]))
        if not progress or deleted:
            break
    board.Save(PCB)
    json.dump(ripped_count, open(state_f, "w"))
    print("saved; unresolved:", len(failed))
    for f in failed:
        print("   ", f)
    # KiCad 7 cannot run DRC again in a session after Delete(); restart in a new process
    sys.exit(3 if deleted else (1 if failed else 0))


def main():
    import subprocess
    if len(sys.argv) > 2 and sys.argv[1] == "--stage":
        if sys.argv[2] == "ripup":
            stage_ripup(sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else [])
        else:
            stage_route()
        return
    extra = sys.argv[sys.argv.index("--ripup") + 1] if "--ripup" in sys.argv else ""
    subprocess.run([sys.executable, __file__, "--stage", "ripup", extra], check=True)
    if os.path.exists("/tmp/fixroute_state.json"):
        os.remove("/tmp/fixroute_state.json")
    for _ in range(15):
        rc = subprocess.run([sys.executable, __file__, "--stage", "route"]).returncode
        if rc != 3:
            break
    print("router finished with code", rc)


if __name__ == "__main__":
    main()
