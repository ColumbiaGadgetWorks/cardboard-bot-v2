"""Debug helper: list copper in a box. usage: near.py x0 y0 x1 y1"""
import sys, pcbnew
b = pcbnew.LoadBoard('/home/user/cardboard-bot-v2/hardware/cardboard-bot.kicad_pcb')
box = list(map(float, sys.argv[1:5]))
def mmv(v): return (round(pcbnew.ToMM(v.x) - 100, 2), round(pcbnew.ToMM(v.y) - 100, 2))
def inb(p): return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        a = e = mmv(t.GetPosition()); lay = 'V'
    else:
        a, e = mmv(t.GetStart()), mmv(t.GetEnd()); lay = 'F' if t.GetLayer() == pcbnew.F_Cu else 'B'
    if inb(a) or inb(e):
        print(lay, t.GetNetname(), a, e, round(pcbnew.ToMM(t.GetWidth()), 2), 'L' if t.IsLocked() else '')
for fp in b.GetFootprints():
    for p in fp.Pads():
        c = mmv(p.GetPosition())
        if inb(c) and p.GetNumber():
            print('PAD', fp.GetReference(), p.GetNumber(), p.GetNetname(), c)
