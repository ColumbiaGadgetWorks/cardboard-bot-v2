"""List GND copper (pour fragments, pads, vias, tracks) not connected to the main GND cluster.

/usr/bin/python3.12 gen/gnd_check.py   -- KiCad 7 DRC only says "zone to zone"; this says where.
"""
import os
import math, pcbnew
b = pcbnew.LoadBoard(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cardboard-bot.kicad_pcb'))
NET = 'GND'
frags = []   # (layer, outline)
for z in b.Zones():
    if z.GetNetname() != NET or z.GetIsRuleArea():
        continue
    lay = z.GetLayer()
    fill = z.GetFilledPolysList(lay)
    for i in range(fill.OutlineCount()):
        frags.append((lay, fill.Outline(i), abs(fill.Outline(i).Area()) / 1e12))
items = []
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname() == NET:
            items.append(('pad', p))
for t in b.GetTracks():
    if t.GetNetname() == NET:
        items.append(('via' if t.GetClass() == 'PCB_VIA' else 'trk', t))
N = len(frags) + len(items)
parent = list(range(N))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, c):
    parent[find(a)] = find(c)
def pts_of(kind, it):
    out = []
    if kind == 'trk':
        s, e = it.GetStart(), it.GetEnd()
        L = max(1, int((e - s).EuclideanNorm() / pcbnew.FromMM(0.1)))
        w = it.GetWidth() / 2 + pcbnew.FromMM(0.02)
        for k in range(L + 1):
            x = s.x + (e.x - s.x) * k / L; y = s.y + (e.y - s.y) * k / L
            for a in range(8):
                out.append((it.GetLayer(), pcbnew.VECTOR2I(int(x + w * math.cos(a * math.pi / 4)), int(y + w * math.sin(a * math.pi / 4)))))
    else:
        c = it.GetPosition()
        if kind == 'via':
            r = it.GetWidth() / 2 + pcbnew.FromMM(0.02); lays = (pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            r = max(it.GetSize().x, it.GetSize().y) / 2 + pcbnew.FromMM(0.02)
            lays = [l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if it.IsOnLayer(l)]
        for l in lays:
            for a in range(24):
                for f in (0.35, 0.7, 1.0):
                    out.append((l, pcbnew.VECTOR2I(int(c.x + f * r * math.cos(a * math.pi / 12)), int(c.y + f * r * math.sin(a * math.pi / 12)))))
    return out
for j, (kind, it) in enumerate(items):
    jj = len(frags) + j
    for (l, pt) in pts_of(kind, it):
        for i, (fl, ol, _) in enumerate(frags):
            if fl == l and ol.PointInside(pt):
                union(jj, i)
# item-item contact (tracks to pads/vias): endpoints
for j, (kind, it) in enumerate(items):
    if kind != 'trk':
        continue
    for k, (k2, it2) in enumerate(items):
        if k == j:
            continue
        for e in (it.GetStart(), it.GetEnd()):
            if it2.HitTest(e, 0) and (k2 != 'trk' or it2.GetLayer() == it.GetLayer()):
                union(len(frags) + j, len(frags) + k)
groups = {}
for i in range(N):
    groups.setdefault(find(i), []).append(i)
main = max(groups.values(), key=len)
for g in groups.values():
    if g is main:
        continue
    desc = []
    for i in g:
        if i < len(frags):
            l, ol, a = frags[i]; c = ol.BBox().Centre()
            desc.append(f"frag {'F' if l == pcbnew.F_Cu else 'B'} {a:.2f}mm2 @({pcbnew.ToMM(c.x) - 100:.2f},{pcbnew.ToMM(c.y) - 100:.2f})")
        else:
            kind, it = items[i - len(frags)]
            c = it.GetPosition() if kind != 'trk' else it.GetStart()
            nm = f"{it.GetParent().GetReference()}-{it.GetNumber()}" if kind == 'pad' else kind
            desc.append(f"{nm} @({pcbnew.ToMM(c.x) - 100:.2f},{pcbnew.ToMM(c.y) - 100:.2f})")
    print('ISOLATED GROUP:', desc)
print('groups', len(groups), 'main size', len(main))
