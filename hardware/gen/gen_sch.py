"""Generate the custom symbol library and the KiCad 7 schematic from circuit.py.

The schematic is label-based: every pin gets a net label at its connection
point, so connectivity is exact and matches circuit.py one-to-one. Parts are
grouped into titled blocks.
"""
import os
import re
import uuid

import circuit

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
SYMDIR = "/usr/share/kicad/symbols"
PROJECT = "cardboard-bot"


def uid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Custom symbols
# ---------------------------------------------------------------------------
def pin(num, name, x, y, ang, typ="passive", length=2.54):
    return (f'(pin {typ} line (at {x} {y} {ang}) (length {length}) '
            f'(name "{name}" (effects (font (size 1.27 1.27)))) '
            f'(number "{num}" (effects (font (size 1.27 1.27)))))')


def box_symbol(name, ref, left, right, width=12.7, top=None, bottom=None, desc="", fp=""):
    """left/right: lists of (num, name, type) from top to bottom."""
    top = top or []
    bottom = bottom or []
    rows = max(len(left), len(right), 1)
    h = rows * 2.54 + 2.54
    y0 = h / 2
    pins = []
    for i, (n, nm, t) in enumerate(left):
        pins.append(pin(n, nm, -width / 2 - 2.54, round(y0 - 2.54 * (i + 1), 2), 0, t))
    for i, (n, nm, t) in enumerate(right):
        pins.append(pin(n, nm, width / 2 + 2.54, round(y0 - 2.54 * (i + 1), 2), 180, t))
    for i, (n, nm, t) in enumerate(top):
        pins.append(pin(n, nm, round(-((len(top) - 1) * 2.54) / 2 + 2.54 * i, 2), y0 + 2.54, 270, t))
    for i, (n, nm, t) in enumerate(bottom):
        pins.append(pin(n, nm, round(-((len(bottom) - 1) * 2.54) / 2 + 2.54 * i, 2), -y0 - 2.54, 90, t))
    return f'''  (symbol "{name}" (in_bom yes) (on_board yes)
    (property "Reference" "{ref}" (at 0 {y0 + 1.27} 0) (effects (font (size 1.27 1.27))))
    (property "Value" "{name}" (at 0 {-y0 - 1.27} 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "{fp}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Description" "{desc}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "{name}_0_1" (rectangle (start {-width / 2} {y0}) (end {width / 2} {-y0}) (stroke (width 0.254) (type default)) (fill (type background))))
    (symbol "{name}_1_1" {" ".join(pins)})
  )'''


def fet_symbol(name, pch):
    arrow = "(polyline (pts (xy 0.762 0) (xy 1.778 0.381) (xy 1.778 -0.381) (xy 0.762 0)) (stroke (width 0) (type default)) (fill (type outline)))" if pch else \
            "(polyline (pts (xy 1.778 0) (xy 0.762 0.381) (xy 0.762 -0.381) (xy 1.778 0)) (stroke (width 0) (type default)) (fill (type outline)))"
    pins = [pin("4", "G", -5.08, 0, 0, "input"),
            pin("5", "D", 2.54, 5.08, 270), pin("1", "S", 2.54, -5.08, 90),
            pin("2", "S", 2.54, -5.08, 90).replace("(pin passive line", "(pin passive line"),
            pin("3", "S", 2.54, -5.08, 90)]
    # stacked source pins: mark 2 and 3 hidden-stacked by making them passive at same point
    body = ("(polyline (pts (xy -2.54 0) (xy -0.254 0)) (stroke (width 0) (type default)) (fill (type none))) "
            "(polyline (pts (xy -0.254 1.905) (xy -0.254 -1.905)) (stroke (width 0.254) (type default)) (fill (type none))) "
            "(polyline (pts (xy 0.508 2.286) (xy 0.508 1.27)) (stroke (width 0.254) (type default)) (fill (type none))) "
            "(polyline (pts (xy 0.508 0.508) (xy 0.508 -0.508)) (stroke (width 0.254) (type default)) (fill (type none))) "
            "(polyline (pts (xy 0.508 -1.27) (xy 0.508 -2.286)) (stroke (width 0.254) (type default)) (fill (type none))) "
            "(polyline (pts (xy 0.508 1.778) (xy 2.54 1.778) (xy 2.54 2.54)) (stroke (width 0) (type default)) (fill (type none))) "
            "(polyline (pts (xy 0.508 -1.778) (xy 2.54 -1.778) (xy 2.54 -2.54)) (stroke (width 0) (type default)) (fill (type none))) "
            "(polyline (pts (xy 0.508 0) (xy 2.54 0) (xy 2.54 -1.778)) (stroke (width 0) (type default)) (fill (type none))) "
            + arrow)
    return f'''  (symbol "{name}" (pin_names hide) (in_bom yes) (on_board yes)
    (property "Reference" "Q" (at 5.08 1.27 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Value" "{name}" (at 5.08 -1.27 0) (effects (font (size 1.27 1.27)) (justify left)))
    (property "Footprint" "Package_DFN_QFN:PQFN-8-EP_6x5mm_P1.27mm_Generic" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Description" "{'P' if pch else 'N'}-channel MOSFET, PDFN5x6: 1-3 S, 4 G, 5 (tab) D" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "{name}_0_1" {body})
    (symbol "{name}_1_1" {" ".join(pins)})
  )'''


def clip_symbol():
    return '''  (symbol "BattClip" (pin_names hide) (in_bom yes) (on_board yes)
    (property "Reference" "BT" (at 0 3.81 0) (effects (font (size 1.27 1.27))))
    (property "Value" "BattClip" (at 0 -3.81 0) (effects (font (size 1.27 1.27))))
    (property "Footprint" "cgw:Clip_MY-18650-01" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Description" "18650 cell end clip (one contact, two legs)" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "BattClip_0_1" (rectangle (start -1.27 2.54) (end 1.27 -2.54) (stroke (width 0.254) (type default)) (fill (type none)))
      (polyline (pts (xy -0.635 1.27) (xy 0.635 1.27)) (stroke (width 0.254) (type default)) (fill (type none))))
    (symbol "BattClip_1_1" ''' + pin("1", "~", -3.81, 0, 0) + ''')
  )'''


def write_custom_lib():
    xiao_l = [("1", "D0/GPIO2", "bidirectional"), ("2", "D1/GPIO3", "bidirectional"), ("3", "D2/GPIO4", "bidirectional"),
              ("4", "D3/GPIO5", "bidirectional"), ("5", "D4/GPIO6", "bidirectional"), ("6", "D5/GPIO7", "bidirectional"),
              ("7", "D6/GPIO21", "bidirectional")]
    xiao_r = [("14", "5V", "power_in"), ("13", "GND", "power_in"), ("12", "3V3", "power_out"),
              ("11", "D10/GPIO10", "bidirectional"), ("10", "D9/GPIO9", "bidirectional"),
              ("9", "D8/GPIO8", "bidirectional"), ("8", "D7/GPIO20", "bidirectional")]
    hy_l = [("5", "VDD", "power_in"), ("4", "VC", "input"), ("6", "VSS", "power_in")]
    hy_r = [("1", "OD", "output"), ("2", "OC", "output"), ("3", "CS", "input")]
    ip_l = [("6", "VIN", "power_in"), ("8", "LX", "passive"), ("7", "BST", "passive"), ("4", "NTC", "input")]
    ip_r = [("1", "VSYS", "power_out"), ("2", "VOUT", "power_out"), ("3", "VSET", "input"), ("5", "LED/ISET", "bidirectional"),
            ("9", "GND", "power_in")]
    hb_l = [("2", "VDD", "power_in"), ("3", "VSS", "power_in")]
    hb_r = [("6", "OUT", "output"), ("1", "NC", "no_connect"), ("4", "NC", "no_connect"), ("5", "NC", "no_connect")]
    syms = [
        box_symbol("XIAO_ESP32C3", "U", xiao_l, xiao_r, width=20.32, desc="Seeed XIAO ESP32-C3 on 2x7 sockets",
                   fp="cgw:XIAO_Socket"),
        box_symbol("HY2120", "U", hy_l, hy_r, width=10.16, desc="HYCON HY2120 2-cell Li-ion protection",
                   fp="Package_TO_SOT_SMD:SOT-23-6"),
        box_symbol("IP2320", "U", ip_l, ip_r, width=12.7, desc="INJOINIC IP2320 2S boost charger, ESOP-8",
                   fp="Package_SO:SOIC-8-1EP_3.9x4.9mm_P1.27mm_EP2.41x3.3mm"),
        box_symbol("HY2213", "U", hb_l, hb_r, width=10.16, desc="HYCON HY2213 1-cell balance controller",
                   fp="Package_TO_SOT_SMD:SOT-23-6"),
        fet_symbol("NMOS_PDFN", False),
        fet_symbol("PMOS_PDFN", True),
        clip_symbol(),
    ]
    txt = "(kicad_symbol_lib (version 20220914) (generator cgw_gen)\n" + "\n".join(syms) + "\n)\n"
    os.makedirs(os.path.join(HW, "lib"), exist_ok=True)
    with open(os.path.join(HW, "lib", "cgw.kicad_sym"), "w") as f:
        f.write(txt)
    return txt


# ---------------------------------------------------------------------------
# S-expression helpers for reading library symbols
# ---------------------------------------------------------------------------
def extract(text, name):
    i = text.find(f'(symbol "{name}"')
    if i < 0:
        raise KeyError(name)
    d = 0
    j = i
    while True:
        c = text[j]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
            if d == 0:
                return text[i:j + 1]
        elif c == '"':
            j += 1
            while text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
        j += 1


_libcache = {}


def libtext(lib):
    if lib not in _libcache:
        path = os.path.join(HW, "lib", "cgw.kicad_sym") if lib == "cgw" else os.path.join(SYMDIR, lib + ".kicad_sym")
        _libcache[lib] = open(path).read()
    return _libcache[lib]


def flat_symbol(lib_id):
    """Return a flattened symbol definition named lib_id (handles 'extends')."""
    lib, name = lib_id.split(":")
    t = libtext(lib)
    s = extract(t, name)
    m = re.search(r'\(extends "([^"]+)"\)', s)
    if m:
        parent = extract(t, m.group(1))
        # take parent's graphical/pin units, rename to child
        units = []
        k = 0
        for um in re.finditer(r'\(symbol "' + re.escape(m.group(1)) + r'_(\d+)_(\d+)"', parent):
            u = extract(parent[um.start():], f'{m.group(1)}_{um.group(1)}_{um.group(2)}')
            units.append(u.replace(f'(symbol "{m.group(1)}_', f'(symbol "{name}_', 1))
        # child's properties + parent's flags
        props = re.findall(r'\(property .*?\n', s)
        head = s[:s.find('(property')]
        head = head.replace(m.group(0), "")
        pflags = re.search(r'\(symbol "[^"]+"(.*?)\(property', parent, re.S).group(1)
        body = "\n".join(re_props(s))
        s = f'(symbol "{name}"{pflags}{body}\n' + "\n".join(units) + ")"
    # rename to lib_id
    s = s.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    return s


def re_props(s):
    out = []
    for m in re.finditer(r'\(property "', s):
        out.append(extract_paren(s, m.start()))
    return out


def extract_paren(text, i):
    d = 0
    j = i
    while True:
        c = text[j]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
            if d == 0:
                return text[i:j + 1]
        elif c == '"':
            j += 1
            while text[j] != '"':
                if text[j] == '\\':
                    j += 1
                j += 1
        j += 1


def symbol_pins(flat):
    """List of (unit, number, x, y, angle, length) from a flattened symbol."""
    res = []
    for um in re.finditer(r'\(symbol "[^"]*_(\d+)_(\d+)"', flat):
        unit = int(um.group(1))
        block = extract_paren(flat, um.start())
        for pm in re.finditer(r'\(pin \w+ \w+ \(at ([-\d.]+) ([-\d.]+) (\d+)\) \(length ([-\d.]+)\)', block):
            rest = block[pm.end():pm.end() + 400]
            num = re.search(r'\(number "([^"]*)"', rest).group(1)
            res.append((unit, num, float(pm.group(1)), float(pm.group(2)), int(pm.group(3)), float(pm.group(4))))
    return res


def symbol_bbox(flat):
    xs, ys = [0.0], [0.0]
    for m in re.finditer(r'\((?:start|end|xy|at) ([-\d.]+) ([-\d.]+)', flat):
        xs.append(float(m.group(1)))
        ys.append(float(m.group(2)))
    return min(xs), min(ys), max(xs), max(ys)


def units_of(flat):
    us = sorted({int(m.group(1)) for m in re.finditer(r'\(symbol "[^"]*_(\d+)_\d+"', flat)} - {0})
    return us or [1]


# ---------------------------------------------------------------------------
# Schematic
# ---------------------------------------------------------------------------
def snap(v, g=2.54):
    return round(round(v / g) * g, 3)


def esc(s):
    return s.replace('"', '\\"')


def main():
    write_custom_lib()
    root = uid()
    lib_ids = sorted({p["sym"] for p in circuit.parts} | {"power:PWR_FLAG"})
    flats = {lid: flat_symbol(lid) for lid in lib_ids}

    out = []
    labels = []
    noconns = []
    texts = []
    used_points = {}

    def claim(pt, what):
        """Return True if this point is new; stacked pins on the same net share one label."""
        key = (round(pt[0], 2), round(pt[1], 2))
        if key in used_points:
            if used_points[key] != what:
                raise RuntimeError(f"point collision {key}: {used_points[key]} vs {what}")
            return False
        used_points[key] = what
        return True

    def place(lib_id, ref, value, fp, x, y, pinmap, extra_props=(), unit_list=None):
        flat = flats[lib_id]
        pins = symbol_pins(flat)
        for unit in (unit_list or units_of(flat)):
            props = [("Reference", ref), ("Value", value), ("Footprint", fp), ("Datasheet", "")] + list(extra_props)
            pr = []
            bx0, by0, bx1, by1 = symbol_bbox(flat)
            for i, (k, v) in enumerate(props):
                hide = " hide" if k not in ("Reference", "Value") else ""
                py = y - by1 - 1.27 if k == "Reference" else (y - by0 + 1.27 if k == "Value" else y)
                pr.append(f'    (property "{k}" "{esc(v)}" (at {x} {round(py, 2)} 0) (effects (font (size 1.27 1.27)){hide}))')
            pin_uuids = " ".join(f'(pin "{n}" (uuid {uid()}))' for (u, n, *_r) in pins if u in (0, unit))
            out.append(f'''  (symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit {unit}) (in_bom yes) (on_board yes) (dnp no)
    (uuid {uid()})
{chr(10).join(pr)}
    {pin_uuids}
    (instances (project "{PROJECT}" (path "/{root}" (reference "{ref}") (unit {unit}))))
  )''')
            for (u, n, px, py, ang, ln) in pins:
                if u not in (0, unit):
                    continue
                X = round(x + px, 3)
                Y = round(y - py, 3)
                net = pinmap.get(n, "__missing__")
                if net == "__missing__":
                    raise RuntimeError(f"{ref} pin {n} has no net entry")
                if net is None:
                    if not claim((X, Y), f"nc:{ref}"):
                        continue
                    noconns.append(f'  (no_connect (at {X} {Y}) (uuid {uid()}))')
                    continue
                if not claim((X, Y), f"net:{net}"):
                    continue
                # label direction: away from the body
                lang = {0: 180, 180: 0, 90: 270, 270: 90}[ang]
                just = "right" if lang in (180, 270) else "left"
                labels.append(f'  (label "{esc(net)}" (at {X} {Y} {lang}) (fields_autoplaced) '
                              f'(effects (font (size 1.0 1.0)) (justify {just} bottom)) (uuid {uid()}))')

    # layout: blocks laid out left-to-right, top-to-bottom on an A1 sheet
    blocks = list(circuit.BLOCK_TITLES.keys())
    col_w = 150.0
    x_base, y_base = 25.4, 30.48
    block_pos = {}
    ncols = 5
    for i, b in enumerate(blocks):
        block_pos[b] = (x_base + (i % ncols) * col_w, y_base + (i // ncols) * 270.0)

    for b in blocks:
        bx, by = block_pos[b]
        texts.append(f'  (text "{esc(circuit.BLOCK_TITLES[b])}" (at {bx} {by - 10.16} 0) '
                     f'(effects (font (size 3 3) bold) (justify left bottom)) (uuid {uid()}))')
        cx, cy = bx + 20, by
        row_h = 0
        for p in [q for q in circuit.parts if q["block"] == b]:
            flat = flats[p["sym"]]
            x0, y0, x1, y1 = symbol_bbox(flat)
            w = (x1 - x0) + 34
            h = (y1 - y0) + 14
            if cx + w > bx + col_w - 5:
                cx = bx + 20
                cy += row_h
                row_h = 0
            X = snap(cx - x0 + 12)
            Y = snap(cy + y1 + 4)
            props = [("LCSC", p.get("lcsc", "")), ("MPN", p.get("mpn", "")), ("Assembly", p.get("place", ""))]
            place(p["sym"], p["ref"], p["value"], p["fp"], X, Y, p["pins"], props)
            cx += w
            row_h = max(row_h, h)

    # power flags along the bottom
    fx, fy = 25.4, 510.54
    texts.append(f'  (text "Power flags (ERC)" (at {fx} {fy - 10} 0) (effects (font (size 2 2)) (justify left bottom)) (uuid {uid()}))')
    for i, net in enumerate(circuit.POWER_FLAGS):
        place("power:PWR_FLAG", f"#FLG{i + 1:02d}", "PWR_FLAG", "", snap(fx + i * 25.4), snap(fy), {"1": net})

    notes = [
        "Cardboard Bot v2 main board  -  rev A  -  Columbia Gadget Works",
        "Generated from hardware/gen/circuit.py (do not hand-edit; edit circuit.py and regenerate).",
        "All connections are made by net labels at pin ends.",
        "XIAO pins: D0 SDA(GPIO2) D1 IO3 D2-D5 DRV8833 AIN1/AIN2/BIN1/BIN2 D6 IO21 D7 OUT2(GPIO20) D8 SCL(GPIO8) D9 LED(GPIO9) D10 OUT1(GPIO10)",
        "IP2320 per INJOINIC V1.00 datasheet fig. 5; HY2213 per HYCON DS-HY2213-V05 P-MOSFET example; clip per MYOUNG WD-CP-0056.",
        "Battery sense: VSYS/4 on GPIO3 through bridged jumper JP1 (cut JP1 to use IO3 as plain GPIO).",
    ]
    for i, n in enumerate(notes):
        texts.append(f'  (text "{esc(n)}" (at 25.4 {535 + i * 5} 0) (effects (font (size 2 2)) (justify left bottom)) (uuid {uid()}))')

    libsyms = "\n".join("    " + flats[l].replace("\n", "\n    ") for l in lib_ids)
    sch = f'''(kicad_sch (version 20230121) (generator cgw_gen)
  (uuid {root})
  (paper "A1")
  (title_block (title "Cardboard Bot v2 main board") (date "2026-10-27") (rev "A") (company "Columbia Gadget Works"))
  (lib_symbols
{libsyms}
  )
{chr(10).join(out)}
{chr(10).join(labels)}
{chr(10).join(noconns)}
{chr(10).join(texts)}
  (sheet_instances (path "/" (page "1")))
)
'''
    with open(os.path.join(HW, PROJECT + ".kicad_sch"), "w") as f:
        f.write(sch)
    print("wrote schematic:", len(circuit.parts), "parts,", len(labels), "labels,", len(noconns), "no-connects")


if __name__ == "__main__":
    main()
