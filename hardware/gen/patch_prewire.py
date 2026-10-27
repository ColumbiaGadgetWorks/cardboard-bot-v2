"""Re-sync the locked prewire copper of some nets on a routed board (copper of other nets untouched).

/usr/bin/python3.12 gen/patch_prewire.py NET,NET   -- removes ALL copper of those nets, re-adds their prewire
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pcb  # noqa: E402

nets = set(sys.argv[1].split(","))
b = pcbnew.LoadBoard(gen_pcb.PCB)
for t in list(b.GetTracks()):
    if t.GetNetname() in nets:
        b.Delete(t)
for net, side, w, pts in gen_pcb.PREWIRE:
    if net not in nets:
        continue
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(gen_pcb.mm(x1, y1))
        t.SetEnd(gen_pcb.mm(x2, y2))
        t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(gen_pcb.layer_id(side))
        t.SetNet(b.FindNet(net))
        t.SetLocked(True)
        b.Add(t)
for net, pts in gen_pcb.PREVIAS:
    if net not in nets:
        continue
    for (x, y) in pts:
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(gen_pcb.mm(x, y))
        v.SetWidth(pcbnew.FromMM(0.6))
        v.SetDrill(pcbnew.FromMM(0.3))
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(b.FindNet(net))
        v.SetLocked(True)
        b.Add(v)
b.Save(gen_pcb.PCB)
print("re-synced prewire for", sorted(nets))
