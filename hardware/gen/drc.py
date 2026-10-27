"""Run KiCad DRC on the board and summarise: /usr/bin/python3.12 gen/drc.py [filter]"""
import collections, os, re, sys
import pcbnew
HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b = pcbnew.LoadBoard(os.path.join(HW, "cardboard-bot.kicad_pcb"))
rpt = "/tmp/drc.rpt"
pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
t = open(rpt).read()
items = re.findall(r'\[(\w+)\]: (.*?)\n(.*?)(?=\n\[|\n\*\* |\Z)', t, re.S)
cnt = collections.Counter(i[0] for i in items)
print("DRC:", dict(cnt))
flt = sys.argv[1] if len(sys.argv) > 1 else None
for kind, msg, body in items:
    if flt and flt not in kind:
        continue
    refs = re.findall(r"@\(([\d.]+) mm, ([\d.]+) mm\): ([^\n]+)", body)
    print(kind, "|", msg.strip()[:60], "|", " ; ".join(f"{r[2][:55]} ({float(r[0])-100:.1f},{float(r[1])-100:.1f})" for r in refs))
m = re.search(r"\*\* Found (\d+) unconnected pads", t)
print("unconnected:", m.group(1) if m else "?")
