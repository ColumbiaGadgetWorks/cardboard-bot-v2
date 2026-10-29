"""Collect the build outputs into one folder with a manifest.json for the web flasher.

python3 ci/manifest.py firmware/build out/ <version> <ref> <sha>
"""
import datetime
import json
import os
import shutil
import sys

build, out, version, ref, sha = sys.argv[1:6]
os.makedirs(out, exist_ok=True)
args = json.load(open(os.path.join(build, "flasher_args.json")))
names = {
    "bootloader": "bootloader.bin",
    "partition-table": "partition-table.bin",
    "otadata": "ota_data_initial.bin",
    "app": "app.bin",
}
parts = []
for key, name in names.items():
    ent = args[key]
    shutil.copy(os.path.join(build, ent["file"]), os.path.join(out, name))
    parts.append({"path": name, "offset": int(ent["offset"], 16)})
parts.sort(key=lambda p: p["offset"])
manifest = {
    "name": "Cardboard Bot",
    "version": version,
    "ref": ref,
    "sha": sha,
    "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    "chip": "ESP32-C3",
    "parts": parts,
    "botcfg": {"offset": 0x10000, "size": 0x1000},
}
json.dump(manifest, open(os.path.join(out, "manifest.json"), "w"), indent=1)
print(json.dumps(manifest, indent=1))
