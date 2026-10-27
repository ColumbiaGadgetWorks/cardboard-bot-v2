"""Fabrication outputs for JLCPCB: gerbers + drill (zipped), BOM, CPL, hand-solder list.

Run from anywhere:  python3 gen/fab.py
Follows the JLC format notes: BOM columns Comment,Designator,Footprint,LCSC Part #;
CPL columns Designator,Mid X,Mid Y,Layer,Rotation; BOM and CPL list exactly the
same designators; hand-soldered parts are left out of both.
"""
import csv
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import circuit  # noqa: E402

PCB = os.path.join(HW, "cardboard-bot.kicad_pcb")
FAB = os.path.join(HW, "fab")

# JLC footprint rotation corrections (degrees added to KiCad rotation).
# Confirm every IC, diode and LED against JLC's placement preview before paying,
# then fix this table, not the CSV.
ROT_FIX = {
    "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.4x5mm_Mask2.46x2.31mm": -90,   # seen on the Scorbot board
}


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def gerbers():
    gdir = os.path.join(FAB, "gerbers")
    shutil.rmtree(gdir, ignore_errors=True)
    os.makedirs(gdir)
    run("kicad-cli", "pcb", "export", "gerbers", "-o", gdir + "/",
        "-l", "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
        "--subtract-soldermask", PCB)
    run("kicad-cli", "pcb", "export", "drill", "-o", gdir + "/", "--format", "excellon",
        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", PCB)
    zpath = os.path.join(FAB, "cardboard-bot-v2-revA-gerbers.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, f), f)
    return zpath


def cpl():
    raw = "/tmp/cb-pos.csv"
    run("kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "front",
        "-o", raw, PCB)   # hand-soldered parts carry the exclude-from-pos attribute
    rows = []
    with open(raw) as f:
        for r in csv.DictReader(f):
            rot = (float(r["Rot"]) + ROT_FIX.get(r["Package"], 0)) % 360
            rows.append({"Designator": r["Ref"], "Mid X": f'{float(r["PosX"]):.3f}mm',
                         "Mid Y": f'{float(r["PosY"]):.3f}mm', "Layer": "Top", "Rotation": f"{rot:g}"})
    out = os.path.join(FAB, "cardboard-bot-v2-revA-CPL.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["Designator"]))
    return out, {r["Designator"] for r in rows}


def bom():
    groups = {}
    for p in circuit.parts:
        if p["place"] != "jlc":
            continue
        key = p["lcsc"]
        g = groups.setdefault(key, {"Comment": p["value"], "Footprint": p["fp"].split(":")[1],
                                    "LCSC Part #": key, "refs": [], "mpn": p.get("mpn", ""),
                                    "verified": p.get("verified", False)})
        g["refs"].append(p["ref"])
    out = os.path.join(FAB, "cardboard-bot-v2-revA-BOM.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for g in sorted(groups.values(), key=lambda g: g["refs"][0]):
            w.writerow([g["Comment"], ",".join(sorted(g["refs"])), g["Footprint"], g["LCSC Part #"]])
    refs = {r for g in groups.values() for r in g["refs"]}
    return out, refs, groups


def hand_list():
    out = os.path.join(FAB, "cardboard-bot-v2-revA-hand-solder.csv")
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Part", "Notes", "LCSC (optional)"])
        for p in circuit.parts:
            if p["place"] == "hand":
                w.writerow([p["ref"], p["value"], p.get("mpn", ""), p.get("lcsc", "")])
    return out


def bom_check(groups):
    """Markdown table for the human C-number check (see hardware/docs/BOM_CHECK.md)."""
    lines = ["| LCSC | Expected part | MPN | Footprint | Qty | Designators | Search-verified |",
             "|---|---|---|---|---|---|---|"]
    for g in sorted(groups.values(), key=lambda g: g["refs"][0]):
        lines.append(f'| {g["LCSC Part #"]} | {g["Comment"]} | {g["mpn"]} | {g["Footprint"]} | '
                     f'{len(g["refs"])} | {", ".join(sorted(g["refs"]))} | {"yes" if g["verified"] else "**NO**"} |')
    return "\n".join(lines)


def main():
    os.makedirs(FAB, exist_ok=True)
    z = gerbers()
    c, cpl_refs = cpl()
    b, bom_refs, groups = bom()
    h = hand_list()
    print("gerbers:", z)
    print("CPL:", c, len(cpl_refs), "parts")
    print("BOM:", b, len(bom_refs), "parts in", len(groups), "lines")
    print("hand-solder list:", h)
    if cpl_refs != bom_refs:
        print("MISMATCH  only in CPL:", sorted(cpl_refs - bom_refs), " only in BOM:", sorted(bom_refs - cpl_refs))
        sys.exit(1)
    print("BOM and CPL designators match")
    with open(os.path.join(FAB, "bom_check_table.md"), "w") as f:
        f.write(bom_check(groups) + "\n")


if __name__ == "__main__":
    main()
