"""Tie isolated GND pour islands to the other layer with a via where one fits.

/usr/bin/python3.12 gen/islands.py   (run after route.py --stage fill; refill afterwards)
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pcb  # noqa: E402

b = pcbnew.LoadBoard(gen_pcb.PCB)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
gnd = b.FindNet("GND")
zf = [z for z in b.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.F_Cu][0]
zb = [z for z in b.Zones() if z.GetNetname() == "GND" and z.GetLayer() == pcbnew.B_Cu][0]
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
# through-hole GND pads join both layers, so an island holding one is already tied
tht_gnd = [q for fp in b.GetFootprints() for q in fp.Pads() if q.GetNetname() == "GND" and q.HasHole()]
others = [t for t in b.GetTracks() if t.GetNetname() != "GND"] + \
         [p for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname() != "GND"]
R = pcbnew.FromMM(0.3)
STEP = pcbnew.FromMM(0.1)


def fits(z, lay, pos):
    for dx, dy in ((0, 0), (R, 0), (-R, 0), (0, R), (0, -R), (R * 7 // 10, R * 7 // 10), (-R * 7 // 10, -R * 7 // 10),
                   (R * 7 // 10, -R * 7 // 10), (-R * 7 // 10, R * 7 // 10)):
        if not z.HitTestFilledArea(lay, pcbnew.VECTOR2I(pos.x + dx, pos.y + dy), 0):
            return False
    return True


added = 0
for (z_this, lay, lay_i, z_other, lay_other) in ((zf, pcbnew.F_Cu, 0, zb, pcbnew.B_Cu), (zb, pcbnew.B_Cu, 1, zf, pcbnew.F_Cu)):
  fill = z_this.GetFilledPolysList(lay)
  big = max(range(fill.OutlineCount()), key=lambda i: abs(fill.Outline(i).Area()))
  for i in range(fill.OutlineCount()):
      if i == big:
          continue
      ol = fill.Outline(i)
      if any(ol.PointInside(v.GetPosition()) for v in vias + tht_gnd):
          continue
      bb = ol.BBox()
      done = False
      y = bb.GetTop()
      while y <= bb.GetBottom() and not done:
          x = bb.GetLeft()
          while x <= bb.GetRight():
              pos = pcbnew.VECTOR2I(x, y)
              if ol.PointInside(pos) and fits(z_this, lay, pos) and fits(z_other, lay_other, pos) and \
                      not any(o.HitTest(pos, pcbnew.FromMM(0.55)) for o in others):
                  v = pcbnew.PCB_VIA(b)
                  v.SetPosition(pos)
                  v.SetWidth(pcbnew.FromMM(0.6))
                  v.SetDrill(pcbnew.FromMM(0.3))
                  v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                  v.SetNet(gnd)
                  b.Add(v)
                  added += 1
                  done = True
                  break
              x += STEP
          y += STEP
      if not done:
          # route a GND track from a pad in the island to the nearest outside GND via
          import fixroute
          r = fixroute.Router(b)
          inside = [q for fp in b.GetFootprints() for q in fp.Pads()
                    if q.GetNetname() == "GND" and q.IsOnLayer(lay) and ol.PointInside(q.GetPosition())]
          outside = [v for v in vias if not ol.PointInside(v.GetPosition())]
          for q in inside[:3]:
              outside.sort(key=lambda v: (v.GetPosition() - q.GetPosition()).EuclideanNorm())
              for v in outside[:6]:
                  path, w = r.route("GND", q, v, [lay_i], [0, 1])
                  if path:
                      r.commit("GND", path, w)
                      done = True
                      print("island tied by track from", q.GetParent().GetReference(), q.GetNumber())
                      break
              if done:
                  break
      if not done:
          print("no via spot in island at", round(pcbnew.ToMM(bb.Centre().x) - 100, 2),
                round(pcbnew.ToMM(bb.Centre().y) - 100, 2), "area mm2", round(abs(ol.Area()) / 1e12, 2))
print("island vias added:", added)
b.Save(gen_pcb.PCB)
