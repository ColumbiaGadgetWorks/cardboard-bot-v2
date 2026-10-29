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

function formToCfg(base) {
  const c = Object.assign({}, base || {});
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
  if (deviceCfg) {
    cfgToForm(deviceCfg);
    $("#cfgNote").textContent = "Loaded this robot's current settings. Drive and output settings are kept.";
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
      if (c.pw && c.pw.length < 8) throw new Error("The Wi-Fi password needs 8+ characters, or leave it blank");
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
