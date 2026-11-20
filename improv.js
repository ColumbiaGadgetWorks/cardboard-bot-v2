// Improv Wi-Fi over serial (https://www.improv-wifi.com/serial/), the same way WLED's installer
// does it: after flashing, the page sends the Wi-Fi name and password over USB and gets the
// robot's address back. Packets share the port with the robot's log; everything that isn't a
// packet goes to the log callback a line at a time.
const HDR = [73, 77, 80, 82, 79, 86];   // "IMPROV"
const T_STATE = 1, T_ERROR = 2, T_RPC = 3, T_RESULT = 4;
const C_WIFI = 1, C_STATE = 2, C_INFO = 3, C_SCAN = 4;
export const S_READY = 2, S_PROVISIONING = 3, S_PROVISIONED = 4;
const ERRORS = { 1: "bad packet", 2: "unknown command", 3: "couldn't join that network", 255: "unknown error" };
const dec = new TextDecoder(), enc = new TextEncoder();
const sum = (a) => a.reduce((s, b) => (s + b) & 255, 0);

export class Improv {
  constructor(port, log) {
    this.port = port;
    this.log = log || (() => {});
    this.pkt = [];
    this.line = [];
    this.waiters = [];
    this.closed = true;
  }

  async open() {
    await this.port.open({ baudRate: 115200 });
    // both low: the USB-JTAG port resets the chip on some combinations of these
    try { await this.port.setSignals({ dataTerminalReady: false, requestToSend: false }); } catch (e) { /* not supported */ }
    this.reader = this.port.readable.getReader();
    this.writer = this.port.writable.getWriter();
    this.closed = false;
    this.loop = this.readLoop();
  }

  async close() {
    this.closed = true;
    try { await this.reader.cancel(); } catch (e) { /* already gone */ }
    try { await this.loop; } catch (e) { /* ignore */ }
    try { this.reader.releaseLock(); } catch (e) { /* ignore */ }
    try { this.writer.releaseLock(); } catch (e) { /* ignore */ }
    try { await this.port.close(); } catch (e) { /* ignore */ }
  }

  async readLoop() {
    try {
      for (;;) {
        const { value, done } = await this.reader.read();
        if (done) break;
        for (const b of value) this.feed(b);
      }
    } catch (e) { /* unplugged or cancelled */ }
    this.closed = true;
    this.waiters.splice(0).forEach((w) => w.reject(new Error("The robot disconnected")));
  }

  feed(b) {
    const p = this.pkt;
    if (p.length < 6) {
      if (b === HDR[p.length]) { p.push(b); return; }
      this.text(p.splice(0));
      if (b === HDR[0]) p.push(b); else this.text([b]);
      return;
    }
    p.push(b);
    if (p.length < 9 || p.length < 10 + p[8]) return;
    const pk = p.splice(0), len = pk[8];
    if (pk[6] !== 1 || sum(pk.slice(0, 9 + len)) !== pk[9 + len]) return;
    this.packet(pk[7], pk.slice(9, 9 + len));
  }

  text(bytes) {
    for (const b of bytes) {
      if (b === 10) {
        if (this.line.length) this.log(dec.decode(new Uint8Array(this.line)));
        this.line = [];
      } else if (b !== 13) this.line.push(b);
    }
  }

  packet(type, d) {
    for (const w of [...this.waiters]) {
      let r;
      try { r = w.fn(type, d); } catch (e) { this.drop(w); w.reject(e); continue; }
      if (r !== undefined) { this.drop(w); w.resolve(r); }
    }
  }

  drop(w) { clearTimeout(w.timer); const i = this.waiters.indexOf(w); if (i >= 0) this.waiters.splice(i, 1); }

  // resolves with fn's first non-undefined answer; fn may throw to fail
  wait(fn, ms, what) {
    return new Promise((resolve, reject) => {
      const w = { fn, resolve, reject };
      w.timer = setTimeout(() => { this.drop(w); reject(new Error("No answer from the robot (" + what + ")")); }, ms);
      this.waiters.push(w);
    });
  }

  async rpc(cmd, args = []) {
    if (this.closed) throw new Error("The robot disconnected");
    const data = [cmd, args.length, ...args];
    const p = [...HDR, 1, T_RPC, data.length, ...data];
    p.push(sum(p), 10);
    await this.writer.write(new Uint8Array(p));
  }

  static strings(d) {   // RPC result: command, length, then length-prefixed strings
    const out = [];
    for (let i = 2; i < d.length;) { const l = d[i++]; out.push(dec.decode(new Uint8Array(d.slice(i, i + l)))); i += l; }
    return out;
  }

  static fail(t, d) { if (t === T_ERROR && d[0]) throw new Error(ERRORS[d[0]] || "error " + d[0]); }

  // { state, urls }
  async state(ms = 1000) {
    const st = this.wait((t, d) => (t === T_STATE ? d[0] : undefined), ms, "state");
    const res = this.wait((t, d) => (t === T_RESULT && d[0] === C_STATE ? Improv.strings(d) : undefined), ms + 500, "address");
    res.catch(() => {});
    await this.rpc(C_STATE);
    const state = await st;
    const urls = state === S_PROVISIONED ? await res.catch(() => []) : [];
    return { state, urls };
  }

  // { firmware, version, chip, name }
  async info() {
    const r = this.wait((t, d) => (Improv.fail(t, d), t === T_RESULT && d[0] === C_INFO ? Improv.strings(d) : undefined), 2000, "info");
    await this.rpc(C_INFO);
    const [firmware, version, chip, name] = await r;
    return { firmware, version, chip, name };
  }

  // [{ ssid, rssi, secure }], strongest first
  async scan() {
    const list = [];
    const r = this.wait((t, d) => {
      Improv.fail(t, d);
      if (t !== T_RESULT || d[0] !== C_SCAN) return undefined;
      if (!d[1]) return list;
      const [ssid, rssi, sec] = Improv.strings(d);
      list.push({ ssid, rssi: +rssi, secure: sec === "YES" });
      return undefined;
    }, 15000, "scan");
    await this.rpc(C_SCAN);
    return r;
  }

  // joins (the robot saves the network only if it worked); returns the robot's addresses
  async wifi(ssid, pw) {
    const s = enc.encode(ssid), p = enc.encode(pw);
    if (!s.length || s.length > 32) throw new Error("The Wi-Fi name must be 1 to 32 characters");
    if (p.length > 64) throw new Error("The Wi-Fi password is too long");
    const r = this.wait((t, d) => (Improv.fail(t, d), t === T_RESULT && d[0] === C_WIFI ? Improv.strings(d) : undefined), 45000, "join");
    await this.rpc(C_WIFI, [s.length, ...s, p.length, ...p]);
    return r;
  }
}
