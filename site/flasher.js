// Cardboard Bot web flasher: esptool-js over Web Serial.
// Firmware folders are published by CI as fw/<name>/manifest.json + .bin files (see .github/workflows).
import { ESPLoader, Transport } from "./vendor/esptool-js-0.6.1/bundle.js";

const $ = (s) => document.querySelector(s);
const BOTCFG_ADDR = 0x10000, BOTCFG_SIZE = 0x1000;
let port = null, transport = null, loader = null, deviceCfg = null, busy = false;

// ------------------------------------------------------------------ firmware sources
function sanitize(ref) { return ref.replace(/[^A-Za-z0-9._-]/g, "-"); }
function pagesBase(owner, repo) {
  owner = owner.toLowerCase();
  return repo.toLowerCase() === owner + ".github.io" ? `https://${owner}.github.io/` : `https://${owner}.github.io/${repo}/`;
}
function sourceUrl() {
  const src = document.querySelector("input[name=src]:checked").value;
  if (src === "custom") {
    const [owner, repo] = ($("#repo").value.trim() || "ColumbiaGadgetWorks/cardboard-bot-v2").split("/");
    if (!owner || !repo) return null;
    return pagesBase(owner, repo) + "fw/" + sanitize($("#branch").value.trim() || "main") + "/";
  }
  return new URL("fw/" + (src === "beta" ? "beta" : "stable") + "/", location.href).href;
}
async function getManifest(base) {
  let r;
  try { r = await fetch(base + "manifest.json", { cache: "no-cache" }); } catch (e) { r = null; }
  if (!r || !r.ok) throw new Error(`No firmware found at ${base}` + (r ? ` (HTTP ${r.status})` : ""));
  return r.json();
}
async function getBin(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`Download failed: ${url} (HTTP ${r.status})`);
  return new Uint8Array(await r.arrayBuffer());
}
let manifest = null;
async function refreshVersion() {
  const src = document.querySelector("input[name=src]:checked").value;
  $("#customBox").classList.toggle("hidden", src !== "custom");
  $("#localBox").classList.toggle("hidden", src !== "local");
  manifest = null;
  try {
    const base = src === "local" ? new URL("fw/stable/", location.href).href : sourceUrl();
    manifest = await getManifest(base);
    manifest.base = base;
    $("#fwVer").textContent = src === "local" ? "your file (with the Stable bootloader " + manifest.version + ")" :
      `${manifest.version} · built ${manifest.date ? manifest.date.slice(0, 10) : "?"}`;
  } catch (e) {
    $("#fwVer").textContent = e.message;
  }
}
document.querySelectorAll("input[name=src]").forEach((r) => r.addEventListener("change", refreshVersion));
["#repo", "#branch"].forEach((s) => $(s).addEventListener("change", refreshVersion));

// ------------------------------------------------------------------ botcfg image (same format as firmware/main/config.c)
function crc32(bytes) {
  let c = 0xffffffff;
  for (const b of bytes) {
    c ^= b;
    for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1));
  }
  return (c ^ 0xffffffff) >>> 0;
}
export function makeImage(obj) {
  const json = new TextEncoder().encode(JSON.stringify(obj));
  if (json.length > BOTCFG_SIZE - 12) throw new Error("Settings too large");
  const img = new Uint8Array(BOTCFG_SIZE).fill(0xff);
  img.set([0x42, 0x43, 0x46, 0x47, 1, 0, json.length & 255, json.length >> 8], 0);
  new DataView(img.buffer).setUint32(8, crc32(json), true);
  img.set(json, 12);
  return img;
}
export function parseImage(img) {
  if (img.length < 12 || String.fromCharCode(...img.slice(0, 4)) !== "BCFG" || img[4] !== 1) return null;
  const len = img[6] | (img[7] << 8);
  if (!len || 12 + len > img.length) return null;
  const json = img.slice(12, 12 + len);
  if (crc32(json) !== new DataView(img.buffer, img.byteOffset).getUint32(8, true)) return null;
  try { return JSON.parse(new TextDecoder().decode(json)); } catch (e) { return null; }
}
window.cgwTest = { makeImage, parseImage, crc32, sanitize, pagesBase };

// ------------------------------------------------------------------ settings form
// Same as cfg_defaults() in firmware/main/config.c (JSON names from config_json.c)
const DEFAULTS = {
  name: "Robot", driver: "", ap: "", pw: "", ch: 0, src: "stable", srcUrl: "",
  bsense: true, driveOn: true, ledOn: true, captive: true,
  pins: { ain1: 4, ain2: 5, bin1: 6, bin2: 7, out: [10, 20, 3, 21], led: 9, vbat: 3 },
  wifi: { ssid: "", pw: "" },
  drive: { mode: 2, invL: false, invR: false, swap: false, revSteer: false, max: 100, slow: 50, slowBtn: 6,
           turn: 70, spin: 100, expo: 30, dead: 8, ramp: 150, vcap: 6 },
  out: [0, 1, 2, 3].map((i) => ({ type: i === 0 ? 1 : i === 1 ? 2 : 0, mode: 0, btn: i === 0 ? 5 : i === 1 ? 4 : 255,
    axis: 5, min: i === 1 ? 500 : 1000, max: i === 1 ? 2500 : 2000, maxPct: 100, spin: 1000, rest: 0, fire: 90, speed: 0 })),
  safe: { wpnCut: 300, fs: 1000, grace: 1000, drops: 3, lowWpn: 6.4, lowDrv: 6, lockout: true },
};
const XIAO_PINS = [[2, "D0"], [3, "D1"], [4, "D2"], [5, "D3"], [6, "D4"], [7, "D5"], [21, "D6"], [20, "D7"], [8, "D8"], [9, "D9"], [10, "D10"]];
const BTN = ["A / ✕", "B / ○", "X / □", "Y / △", "LB / L1", "RB / R1", "LT / L2", "RT / R2", "Back / Share", "Start / Options",
  "Left stick press", "Right stick press", "D-pad up", "D-pad down", "D-pad left", "D-pad right", "Home / PS"];
const OUT_NAMES = ["Output 1", "Output 2", "Output 3", "Output 4"];

function clone(o) { return JSON.parse(JSON.stringify(o)); }
function merge(a, b) {   // b's values over a, recursively (arrays element by element)
  if (Array.isArray(a)) return a.map((v, i) => (b && i < b.length ? merge(v, b[i]) : clone(v)));
  if (a && typeof a === "object") {
    const r = {};
    for (const k of Object.keys(a)) r[k] = merge(a[k], b ? b[k] : undefined);
    if (b && typeof b === "object") for (const k of Object.keys(b)) if (!(k in a)) r[k] = clone(b[k]);
    return r;
  }
  return b === undefined || b === null ? a : b;
}
function getK(o, k) { return k.split(".").reduce((a, p) => (a == null ? a : a[p]), o); }
function setK(o, k, v) { const p = k.split("."); let a = o; for (let i = 0; i < p.length - 1; i++) a = a[p[i]]; a[p[p.length - 1]] = v; }

// pins in use, and anything that clashes (firmware/main/config.c cfg_out_avail does the same on the robot)
export function checkCfg(c) {
  const errs = [], used = new Map();
  const name = (g) => (XIAO_PINS.find((p) => p[0] === g) || [g, "GPIO" + g])[1];
  const take = (g, what) => {
    if (used.has(g)) errs.push(`${name(g)} is used for both ${used.get(g)} and ${what}`);
    else used.set(g, what);
  };
  if (c.driveOn) [["ain1", "left motor IN1"], ["ain2", "left motor IN2"], ["bin1", "right motor IN3"], ["bin2", "right motor IN4"]]
    .forEach(([k, w]) => take(c.pins[k], w));
  if (c.ledOn) take(c.pins.led, "the status LED");
  if (c.bsense) {
    if (![2, 3, 4].includes(c.pins.vbat)) errs.push("The battery input must be D0, D1 or D2");
    take(c.pins.vbat, "the battery input");
  }
  c.out.forEach((o, i) => { if (o.type) take(c.pins.out[i], OUT_NAMES[i]); });
  if (c.pw && c.pw.length < 8) errs.push("The Wi-Fi password needs 8+ characters, or leave it blank");
  return errs;
}

let adv = clone(DEFAULTS);   // the advanced settings shown in the form
let formDirty = false;
function buildAdvForm() {
  document.querySelectorAll("select[data-pin]").forEach((s) => {
    const pins = s.dataset.pin === "adc" ? XIAO_PINS.filter((p) => p[0] >= 2 && p[0] <= 4) : XIAO_PINS;
    s.innerHTML = pins.map(([g, d]) => `<option value="${g}">${d} (GPIO${g})</option>`).join("");
    s.dataset.n = "";
  });
  const btnOpts = `<option value="255">On-screen only</option>` + BTN.map((n, i) => `<option value="${i}">${n}</option>`).join("");
  $("#outs").innerHTML = `<tr><th></th><th>Type</th><th>Mode</th><th>Gamepad button</th><th>Pulse min / max (µs)</th></tr>` +
    [0, 1, 2, 3].map((i) => `<tr data-row="${i}"><td>${OUT_NAMES[i]}</td>
      <td><select data-k="out.${i}.type" data-n><option value="0">Off</option><option value="1">ESC</option><option value="2">Servo</option></select></td>
      <td><select data-k="out.${i}.mode" data-n><option value="0">Hold</option><option value="1">Toggle</option><option value="2">Variable</option></select></td>
      <td><select data-k="out.${i}.btn" data-n>${btnOpts}</select></td>
      <td><input type="number" min="400" max="2600" data-k="out.${i}.min"> <input type="number" min="400" max="2600" data-k="out.${i}.max"></td></tr>`).join("");
}
function fillAdv() {
  document.querySelectorAll("#adv [data-k]").forEach((e) => {
    const v = getK(adv, e.dataset.k);
    if (v === undefined) return;
    if (e.type === "checkbox") e.checked = !!v; else e.value = String(v);
  });
  advRefresh();
}
function readAdv() {
  document.querySelectorAll("#adv [data-k]").forEach((e) => {
    let v = e.type === "checkbox" ? e.checked : e.value;
    if (e.type === "number" || e.dataset.n !== undefined) v = Number(v);
    setK(adv, e.dataset.k, v);
  });
}
function advRefresh() {
  readAdv();
  document.querySelectorAll("#adv tr[data-need]").forEach((r) => r.classList.toggle("off", !getK(adv, r.dataset.need)));
  document.querySelectorAll("#adv tr[data-out]").forEach((r) => r.classList.toggle("off", !adv.out[+r.dataset.out].type));
  document.querySelectorAll("#outs tr[data-row]").forEach((r) => r.classList.toggle("off", !adv.out[+r.dataset.row].type));
  const errs = $("#custom").checked ? checkCfg(adv) : [];
  $("#advErr").textContent = errs.join(". ");
}
buildAdvForm();
fillAdv();
$("#custom").addEventListener("change", () => { $("#adv").classList.toggle("hidden", !$("#custom").checked); advRefresh(); });
$("#adv").addEventListener("input", () => { formDirty = true; advRefresh(); });
$("#adv").addEventListener("change", (e) => {
  // switching type: swap the pulse range to the new type's default if it's still the old type's
  const m = (e.target.dataset.k || "").match(/^out\.(\d)\.type$/);
  if (m) {
    const row = document.querySelector(`#outs tr[data-row="${m[1]}"]`), [lo, hi] = row.querySelectorAll("input[type=number]");
    const esc = e.target.value === "1", srv = e.target.value === "2";
    if (esc && lo.value === "500" && hi.value === "2500") { lo.value = "1000"; hi.value = "2000"; }
    if (srv && lo.value === "1000" && hi.value === "2000") { lo.value = "500"; hi.value = "2500"; }
  }
  advRefresh();
});
document.querySelector("#name").closest(".card").addEventListener("input", () => { formDirty = true; });
$("#advReset").onclick = () => {
  const keep = adv;
  adv = clone(DEFAULTS);
  ["name", "driver", "ap", "pw", "ch", "wifi", "src", "srcUrl"].forEach((k) => (adv[k] = keep[k]));
  fillAdv();
};

Object.assign(window.cgwTest, { checkCfg, formToCfg: (b) => formToCfg(b), merge, DEFAULTS });

function formToCfg(base) {
  // only the fields on this page change; everything else on the robot is kept
  const c = clone(base || {});
  if ($("#custom").checked) {
    Object.assign(c, merge(DEFAULTS, c));
    readAdv();
    document.querySelectorAll("#adv [data-k]").forEach((e) => setK(c, e.dataset.k, getK(adv, e.dataset.k)));
  }
  c.name = $("#name").value.trim() || c.name || "Robot";
  c.driver = $("#driver").value.trim();
  c.ap = $("#ap").value.trim();
  c.pw = $("#pw").value;
  c.ch = Number($("#ch").value);
  c.wifi = { ssid: $("#wifiSsid").value.trim(), pw: $("#wifiPw").value };
  const upd = $("#upd").value;
  c.src = upd;
  c.srcUrl = upd === "custom" ? (sourceUrl() || "") : "";
  return c;
}
function cfgToForm(c) {
  $("#name").value = c.name || "";
  $("#driver").value = c.driver || "";
  $("#ap").value = c.ap || "";
  $("#pw").value = c.pw || "";
  $("#ch").value = String(c.ch || 0);
  $("#wifiSsid").value = (c.wifi && c.wifi.ssid) || "";
  $("#wifiPw").value = (c.wifi && c.wifi.pw) || "";
  $("#upd").value = ["stable", "beta", "custom"].includes(c.src) ? c.src : "stable";
}

// ------------------------------------------------------------------ serial
const logEl = $("#log");
const term = {
  clean() { logEl.textContent = ""; },
  writeLine(d) { logEl.textContent += d + "\n"; logEl.scrollTop = 1e9; },
  write(d) { logEl.textContent += d; logEl.scrollTop = 1e9; },
};
function status(t) { $("#status").textContent = t; }
function progress(p) { $("#bar").style.width = Math.round(p * 100) + "%"; }

async function connect() {
  if (loader) return;
  port = await navigator.serial.requestPort({ filters: [{ usbVendorId: 0x303a }] });
  transport = new Transport(port, true);
  loader = new ESPLoader({ transport, baudrate: 921600, terminal: term, debugLogging: false });
  status("Connecting…");
  const chip = await loader.main();
  if (!/ESP32-C3/i.test(chip)) {
    await disconnect(false);
    throw new Error(`This is a ${chip}, not the robot's ESP32-C3`);
  }
  $("#chipInfo").textContent = "Connected: " + chip;
  status("Reading the robot's settings…");
  try {
    deviceCfg = parseImage(await loader.readFlash(BOTCFG_ADDR, BOTCFG_SIZE));
  } catch (e) {
    deviceCfg = null;
  }
  if (formDirty) {
    $("#cfgNote").textContent = deviceCfg ? "Read this robot's settings. What you typed here is kept; everything else on the robot stays as it was."
      : "This robot has no saved settings yet; it starts with the defaults plus what you enter here.";
  } else if (deviceCfg) {
    cfgToForm(deviceCfg);
    adv = merge(DEFAULTS, deviceCfg);
    fillAdv();
    $("#cfgNote").textContent = "Loaded this robot's current settings. Anything you don't change is kept.";
  } else {
    $("#cfgNote").textContent = "This robot has no saved settings yet; it starts with the defaults plus what you enter here.";
  }
  status("Connected. Pick an action.");
}
async function disconnect(reset = true) {
  try { if (reset && loader) await loader.after("hard_reset"); } catch (e) { /* robot may already be gone */ }
  try { if (transport) await transport.disconnect(); } catch (e) { /* ignore */ }
  loader = transport = port = null;
  $("#chipInfo").textContent = "";
}

async function firmwareFiles() {
  if (!manifest) throw new Error("No firmware selected: " + $("#fwVer").textContent);
  const files = [];
  for (const p of manifest.parts) {
    if (p.path === "app.bin" && document.querySelector("input[name=src]:checked").value === "local") {
      const f = $("#localFile").files[0];
      if (!f) throw new Error("Pick a local .bin file");
      const data = new Uint8Array(await f.arrayBuffer());
      if (data[0] !== 0xe9) throw new Error("That file isn't an ESP32 app image");
      files.push({ data, address: p.offset });
    } else {
      status("Downloading " + p.path + "…");
      files.push({ data: await getBin(manifest.base + p.path), address: p.offset });
    }
  }
  return files;
}

async function run(kind) {
  if (busy) return;
  busy = true;
  setButtons();
  progress(0);
  try {
    if (kind === "erase" && !confirm("Erase everything on this robot, including its settings?")) return;
    await connect();
    let files = [];
    if (kind === "install" || kind === "update") files = await firmwareFiles();
    if (kind === "install" || kind === "settings") {
      const c = formToCfg(deviceCfg);
      const errs = checkCfg(merge(DEFAULTS, c));
      if (errs.length) throw new Error(errs.join(". "));
      files.push({ data: makeImage(c), address: BOTCFG_ADDR });
    }
    files.sort((a, b) => a.address - b.address);
    if (kind === "erase") {
      status("Erasing (about 20 s)…");
      await loader.eraseFlash();
    } else {
      const total = files.reduce((n, f) => n + f.data.length, 0);
      const done = files.map(() => 0);
      status("Writing…");
      await loader.writeFlash({
        fileArray: files, flashSize: "keep", flashMode: "keep", flashFreq: "keep", eraseAll: false, compress: true,
        reportProgress: (i, written) => { done[i] = written; progress(done.reduce((a, b) => a + b, 0) / total); },
      });
    }
    progress(1);
    await disconnect(true);
    status({ install: "Installed. The robot is restarting.", update: "Updated, settings kept. The robot is restarting.",
             settings: "Settings saved. The robot is restarting.", erase: "Erased." }[kind]);
  } catch (e) {
    status("Error: " + (e.message || e));
    term.writeLine(String(e && e.stack || e));
    await disconnect(false);
  } finally {
    busy = false;
    setButtons();
  }
}

function setButtons() {
  const ok = !!navigator.serial && !busy;
  ["#install", "#update", "#settingsOnly", "#erase", "#connect"].forEach((s) => ($(s).disabled = !ok));
}
$("#connect").onclick = async () => {
  if (busy) return;
  busy = true;
  setButtons();
  try { await connect(); } catch (e) { status("Error: " + (e.message || e)); await disconnect(false); }
  busy = false;
  setButtons();
};
$("#install").onclick = () => run("install");
$("#update").onclick = () => run("update");
$("#settingsOnly").onclick = () => run("settings");
$("#erase").onclick = () => run("erase");

if (!navigator.serial) $("#noSerial").classList.remove("hidden");
setButtons();
refreshVersion();
