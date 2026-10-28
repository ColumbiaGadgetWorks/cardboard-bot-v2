"""Tie a pad to the nearest reachable GND via or through-hole pad with the grid router (for pour fragments DRC flags).

/usr/bin/python3.12 gen/tie_pad.py [--min MM] REF PAD [REF PAD ...]
--min skips vias closer than MM (they may sit on the same isolated fragment).
"""
import sys

import pcbnew

import fixroute

b = pcbnew.LoadBoard(fixroute.PCB)
r = fixroute.Router(b)
args = sys.argv[1:]
min_d = 0.0
if args and args[0] == "--min":
    min_d, args = float(args[1]), args[2:]
for ref, num in zip(args[::2], args[1::2]):
    pad = [p for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == num][0]
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == pad.GetNetname()]
    # through-hole pads of the net are on both layers too, so they work as targets
    vias += [q for fp in b.GetFootprints() for q in fp.Pads()
             if q.GetNetname() == pad.GetNetname() and q.HasHole() and fp.GetReference() != ref]
    vias = [v for v in vias if (v.GetPosition() - pad.GetPosition()).EuclideanNorm() >= pcbnew.FromMM(min_d)]
    vias.sort(key=lambda v: (v.GetPosition() - pad.GetPosition()).EuclideanNorm())
    for v in vias[:12]:
        lays = [0, 1] if pad.HasHole() else [0 if pad.IsOnLayer(pcbnew.F_Cu) else 1]
        path, w = r.route(pad.GetNetname(), pad, v, lays, [0, 1])
        if path:
            print(f"tied {ref}-{num}: {r.commit(pad.GetNetname(), path, w)} segments")
            break
    else:
        print(f"could not tie {ref}-{num}")
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(fixroute.PCB)
