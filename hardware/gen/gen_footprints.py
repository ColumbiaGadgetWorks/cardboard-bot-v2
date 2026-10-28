"""Custom footprints: XIAO socket, MY-18650-01 battery clip, WS2812B strip pads, CGW logo."""
import os
import uuid

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
OUT = os.path.join(HW, "lib", "cgw.pretty")

# MY-18650-01 clip (LCSC C2979183, MYOUNG drawing WD-CP-0056): three legs per clip, all one
# piece of metal. Two legs 5.00 mm apart across the cell axis, one leg 7.60 mm outboard on the
# cell axis. Holes 1.80 mm. The leg pairs of the two clips for one 18650 are 48.00 mm apart.
CLIP_PAIR = 5.00
CLIP_OUTBOARD = 7.60
CLIP_SPACING_18650 = 48.00
CLIP_DRILL = 1.8
CLIP_PAD = 3.0


def u():
    return str(uuid.uuid4())


def text(kind, val, x, y, layer, size=1.0, hide=False):
    h = " hide" if hide else ""
    return (f'  (fp_text {kind} "{val}" (at {x} {y}) (layer "{layer}"){h} (tstamp {u()})\n'
            f'    (effects (font (size {size} {size}) (thickness {round(size * 0.15, 3)}))))\n')


def line(x1, y1, x2, y2, layer, w=0.12):
    return (f'  (fp_line (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) '
            f'(layer "{layer}") (tstamp {u()}))\n')


def rect(x1, y1, x2, y2, layer, w=0.12, fill="none"):
    return (f'  (fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width {w}) (type solid)) '
            f'(fill {fill}) (layer "{layer}") (tstamp {u()}))\n')


def tht(num, x, y, size, drill, shape="circle"):
    return (f'  (pad "{num}" thru_hole {shape} (at {x} {y}) (size {size} {size}) (drill {drill}) '
            f'(layers "*.Cu" "*.Mask") (tstamp {u()}))\n')


def smd(num, x, y, w, h):
    return (f'  (pad "{num}" smd rect (at {x} {y}) (size {w} {h}) '
            f'(layers "F.Cu" "F.Paste" "F.Mask") (tstamp {u()}))\n')


# One LED cut from a 60 LED/m, 10 mm WS2812B strip: 16.67 mm long, pads +5V / DIN / GND across
# each cut end (pitch about 3.3 mm). The strip lies flat on the board, LED up.
STRIP_LEN = 16.67
STRIP_W = 10.0
STRIP_PITCH = 3.3


def write(name, body, descr, attr="through_hole"):
    s = (f'(footprint "{name}" (version 20221018) (generator cgw_gen) (layer "F.Cu")\n'
         f'  (descr "{descr}")\n  (attr {attr})\n' + body + ')\n')
    with open(os.path.join(OUT, name + ".kicad_mod"), "w") as f:
        f.write(s)


def xiao():
    b = text("reference", "REF**", 0, -12.2, "F.SilkS")
    b += text("value", "XIAO_Socket", 0, 12.2, "F.Fab")
    # body 17.5 x 21, USB end at -y
    b += rect(-8.75, -10.5, 8.75, 10.5, "F.Fab", 0.1)
    # courtyard only around the socket rows: the module sits ~8 mm up on sockets,
    # so low SMD parts may go underneath between the rows
    b += rect(-9.0, -9.0, -6.2, 9.0, "F.CrtYd", 0.05)
    b += rect(6.2, -9.0, 9.0, 9.0, "F.CrtYd", 0.05)
    b += line(-8.85, -10.6, 8.85, -10.6, "F.SilkS", 0.15)
    b += line(-8.85, 10.6, 8.85, 10.6, "F.SilkS", 0.15)
    b += line(-8.85, -10.6, -8.85, 10.6, "F.SilkS", 0.15)
    b += line(8.85, -10.6, 8.85, 10.6, "F.SilkS", 0.15)
    b += rect(-4.5, -11.2, 4.5, -10.6, "F.SilkS", 0.15)   # USB-C marker
    b += text("user", "USB", 0, -8.9, "F.SilkS", 0.8)
    left = ["D0", "D1", "D2", "D3", "D4", "D5", "D6"]
    right = ["5V", "GND", "3V3", "D10", "D9", "D8", "D7"]
    for i in range(7):
        y = round(-7.62 + 2.54 * i, 2)
        b += tht(str(i + 1), -7.62, y, 1.7, 1.0, "rect" if i == 0 else "circle")
        b += tht(str(14 - i), 7.62, y, 1.7, 1.0)
        b += text("user", left[i], -5.6, y, "F.SilkS", 0.7)
        b += text("user", right[i], 5.4, y, "F.SilkS", 0.7)
    write("XIAO_Socket", b, "Seeed XIAO (ESP32-C3) on two 1x7 2.54 mm female sockets, USB toward -Y")


def clip():
    """Origin at the centre of the leg pair; the outboard leg is at -X (rotate 180 for the other end)."""
    p = CLIP_PAIR / 2
    b = text("reference", "REF**", -3.8, -5.2, "F.SilkS", 0.8)
    b += text("value", "MY-18650-01", -3.8, 5.2, "F.Fab", 0.8)
    b += tht("1", 0, -p, CLIP_PAD, CLIP_DRILL)
    b += tht("1", 0, p, CLIP_PAD, CLIP_DRILL)
    b += tht("1", -CLIP_OUTBOARD, 0, CLIP_PAD, CLIP_DRILL)
    # clip footprint on the board: 16 mm wide contact plate over the pair, 9.6 mm deep
    b += rect(-CLIP_OUTBOARD - 1.0, -8.0, 1.0, 8.0, "F.Fab", 0.1)
    b += rect(-CLIP_OUTBOARD - 1.75, -8.25, 1.75, 8.25, "F.CrtYd", 0.05)
    write("Clip_MY-18650-01", b, "MYOUNG MY-18650-01 18650 clip, LCSC C2979183: 3 legs, 1.8 mm holes, "
          "pair 5.0 mm, outboard leg 7.6 mm; pairs 48.0 mm apart for 18650")


def strip():
    """Origin at the strip centre; DIN end at +X, data flows toward -X. Tin the pads, lay the strip
    on them and heat each strip pad from the top. The DOUT-end pads have no net: they only hold it down."""
    hx, hw = STRIP_LEN / 2, STRIP_W / 2
    px = round(hx - 0.5, 3)            # pads run 1.0 mm in under the strip and 0.5 mm past its end
    b = text("reference", "REF**", 0, -hw - 1.0, "F.Fab", 0.8)
    b += text("value", "WS2812B_Strip_1LED", 0, hw + 1.0, "F.Fab", 0.8)
    for i, num in enumerate(("1", "2", "3")):
        y = round((i - 1) * STRIP_PITCH, 3)
        b += smd(num, px, y, 2.0, 1.8)
        b += smd("", -px, y, 2.0, 1.8)
    b += rect(-hx, -hw, hx, hw, "F.Fab", 0.1)
    b += rect(-hx - 1.0, -hw - 0.25, hx + 1.0, hw + 0.25, "F.CrtYd", 0.05)
    # silk: top edge of the strip, pad names and data arrow (under the strip, for assembly)
    b += line(-hx + 1.4, -hw, hx - 1.4, -hw, "F.SilkS", 0.15)
    for lab, y in (("+5V", -STRIP_PITCH), ("DIN", 0), ("GND", STRIP_PITCH)):
        b += text("user", lab, round(hx - 3.6, 2), y, "F.SilkS", 0.7)
    b += line(2.0, 0, -3.0, 0, "F.SilkS", 0.15)
    b += line(-3.0, 0, -2.0, -0.7, "F.SilkS", 0.15)
    b += line(-3.0, 0, -2.0, 0.7, "F.SilkS", 0.15)
    b += text("user", "WS2812B STRIP", 0, -1.6, "F.SilkS", 0.7)
    b += text("user", "60/m 10mm", 0, 1.6, "F.SilkS", 0.6)
    write("WS2812B_Strip_1LED", b, "One LED cut from a 60 LED/m 10 mm WS2812B strip, soldered flat: "
          "+5V/DIN/GND at +X, unconnected hold-down pads at the DOUT end", attr="smd")


def logo(size_mm=11.0, name="CGW_Logo", layer="F.SilkS"):
    im = Image.open(os.path.join(HW, "docs", "cgw_logo.png")).convert("RGBA")
    W, H = im.size
    px = im.load()
    mask = [[px[x, y][3] > 128 for x in range(W)] for y in range(H)]
    s = size_mm / max(W, H)
    # row runs, merged vertically into rectangles
    runs_prev = {}
    rects = []
    for y in range(H + 1):
        runs = {}
        if y < H:
            x = 0
            while x < W:
                if mask[y][x]:
                    x0 = x
                    while x < W and mask[y][x]:
                        x += 1
                    runs[(x0, x)] = y
                else:
                    x += 1
        cur = {}
        for k, y0 in runs.items():
            cur[k] = runs_prev.get(k, y)
        for k, y0 in runs_prev.items():
            if k not in runs:
                rects.append((k[0], y0, k[1], y))
        runs_prev = cur
    b = text("reference", "LOGO", 0, 0, "F.Fab", 0.8, hide=True)
    b += text("value", name, 0, 0, "F.Fab", 0.8, hide=True)
    ox, oy = W / 2, H / 2
    for (x0, y0, x1, y1) in rects:
        X0, Y0 = round((x0 - ox) * s, 3), round((y0 - oy) * s, 3)
        X1, Y1 = round((x1 - ox) * s, 3), round((y1 - oy) * s, 3)
        b += (f'  (fp_poly (pts (xy {X0} {Y0}) (xy {X1} {Y0}) (xy {X1} {Y1}) (xy {X0} {Y1})) '
              f'(stroke (width 0) (type solid)) (fill solid) (layer "{layer}") (tstamp {u()}))\n')
    write(name, b, f"Columbia Gadget Works logo, {size_mm} mm", attr="board_only exclude_from_pos_files exclude_from_bom")
    return len(rects)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    xiao()
    clip()
    strip()
    print("logo rects:", logo(11.0, "CGW_Logo", "F.SilkS"))
    logo(7.0, "CGW_Logo_7mm", "F.SilkS")
    logo(6.0, "CGW_Logo_6mm", "F.SilkS")
    logo(7.0, "CGW_Logo_Small_Back", "F.SilkS")   # flipped to the back on the board
