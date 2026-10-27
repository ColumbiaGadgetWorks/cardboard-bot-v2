"""Redo the board-level silkscreen on the routed board without touching copper.

Run with KiCad's Python:  /usr/bin/python3.12 gen/silk.py
Deletes board texts/lines on the silk layers and redraws them from gen_pcb.silkscreen().
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_pcb  # noqa: E402

b = pcbnew.LoadBoard(gen_pcb.PCB)
silk = (pcbnew.F_SilkS, pcbnew.B_SilkS)
for d in list(b.GetDrawings()):
    if d.GetLayer() in silk:
        b.Delete(d)
for fp in b.GetFootprints():
    if fp.GetReference().startswith("H"):
        fp.Reference().SetVisible(False)
    if fp.GetReference() == "LOGO2":
        fp.SetPosition(gen_pcb.mm(*gen_pcb.BACK_LOGO))
gen_pcb.silkscreen(b, {fp.GetReference(): fp for fp in b.GetFootprints()})
b.Save(gen_pcb.PCB)
gen_pcb.write_project()
print("silkscreen redrawn")
