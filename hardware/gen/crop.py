"""Debug helper: render F.Cu+B.Cu+silk of a board region to PNG. usage: crop.py x0 y0 x1 y1 out.png"""
import sys, pcbnew
from PIL import Image, ImageDraw
x0, y0, x1, y1 = map(float, sys.argv[1:5]); out = sys.argv[5]
S = 40.0  # px/mm
b = pcbnew.LoadBoard('/home/user/cardboard-bot-v2/hardware/cardboard-bot.kicad_pcb')
W, H = int((x1 - x0) * S), int((y1 - y0) * S)
img = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(img, 'RGBA')
def P(v): return ((pcbnew.ToMM(v.x) - 100 - x0) * S, (pcbnew.ToMM(v.y) - 100 - y0) * S)
cols = {pcbnew.B_Cu: (40, 90, 220, 150), pcbnew.F_Cu: (220, 40, 40, 170)}
for lay in (pcbnew.B_Cu, pcbnew.F_Cu):
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_TRACK' and t.GetLayer() == lay:
            d.line([P(t.GetStart()), P(t.GetEnd())], fill=cols[lay], width=max(1, int(pcbnew.ToMM(t.GetWidth()) * S)))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.IsOnLayer(lay):
                sps = pcbnew.SHAPE_POLY_SET(); p.TransformShapeToPolygon(sps, lay, 0, pcbnew.FromMM(0.01))
                for i in range(sps.OutlineCount()):
                    ch = sps.Outline(i); d.polygon([P(ch.CPoint(j)) for j in range(ch.PointCount())], fill=cols[lay])
for t in b.GetTracks():
    if t.GetClass() == 'PCB_VIA':
        c = P(t.GetPosition()); r = pcbnew.ToMM(t.GetWidth()) / 2 * S
        d.ellipse([c[0]-r, c[1]-r, c[0]+r, c[1]+r], fill=(0, 150, 0, 220))
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNumber() and (p.IsOnLayer(pcbnew.F_Cu)):
            c = P(p.GetPosition()); d.text((c[0]-6, c[1]-5), (p.GetNetname() or '-')[:6], fill=(0, 0, 0))
img.save(out)
