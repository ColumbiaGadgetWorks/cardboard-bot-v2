#!/bin/bash
# Render top/bottom previews of the PCB to PNG (needs kicad-cli + ImageMagick)
set -e
cd "$(dirname "$0")/.."
OUT=${1:-/tmp/render}
mkdir -p "$OUT"
kicad-cli pcb export svg --exclude-drawing-sheet --page-size-mode 2 -l "F.Cu,F.SilkS,Edge.Cuts" -o "$OUT/top.svg" cardboard-bot.kicad_pcb >/dev/null
kicad-cli pcb export svg --exclude-drawing-sheet --page-size-mode 2 -m -l "B.Cu,B.SilkS,Edge.Cuts" -o "$OUT/bottom.svg" cardboard-bot.kicad_pcb >/dev/null
for s in top bottom; do node gen/svg2png.js "$OUT/$s.svg" "$OUT/$s.png" ${2:-1800}; done
ls "$OUT"
