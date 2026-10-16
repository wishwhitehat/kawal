import puppeteer from "puppeteer";
import fs from "fs";

const [V, DEBUG_TOKEN, ...durs] = process.argv.slice(2);
const [N2, N3, N4, N5] = durs.map(Number);
const URL = "https://kawal-ai.web.app";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await puppeteer.launch({
  headless: true,
  args: ["--autoplay-policy=no-user-gesture-required", "--window-size=1600,900"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 900, deviceScaleFactor: 1.2 });
await page.evaluateOnNewDocument((tok) => {
  self.FIREBASE_APPCHECK_DEBUG_TOKEN = tok;
  window.__rec = { sampleStart: null, chunks: [] };
  const origStart = AudioBufferSourceNode.prototype.start;
  AudioBufferSourceNode.prototype.start = function (...a) {
    if (this.buffer && this.buffer.duration > 20 && window.__rec.sampleStart === null) window.__rec.sampleStart = performance.now();
    return origStart.apply(this, a);
  };
  const OrigWS = window.WebSocket;
  window.WebSocket = function (...a) {
    const ws = new OrigWS(...a);
    ws.addEventListener("message", (e) => {
      if (e.data instanceof ArrayBuffer) {
        const u = new Uint8Array(e.data); let s = "";
        for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
        window.__rec.chunks.push({ t: performance.now(), b64: btoa(s) });
      }
    });
    return ws;
  };
  window.WebSocket.prototype = OrigWS.prototype;
  Object.assign(window.WebSocket, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
}, DEBUG_TOKEN);

const click = (text) => page.evaluate((t) => {
  const el = [...document.querySelectorAll("button,label")].find((b) => b.innerText.trim().includes(t));
  if (el) el.click(); return !!el;
}, text);
const smoothScroll = (y, ms = 1500) => page.evaluate((y, ms) => new Promise((res) => {
  const y0 = scrollY, t0 = performance.now();
  const step = (t) => { const k = Math.min(1, (t - t0) / ms); scrollTo(0, y0 + (y - y0) * (0.5 - Math.cos(Math.PI * k) / 2)); k < 1 ? requestAnimationFrame(step) : res(); };
  requestAnimationFrame(step);
}), y, ms);
const elTop = (sel, text) => page.evaluate((sel, text) => {
  const el = [...document.querySelectorAll(sel)].find((e) => !text || e.innerText.includes(text));
  return el ? el.getBoundingClientRect().top + scrollY : null;
}, sel, text);
async function record(name, fn) {
  const rec = await page.screencast({ path: `${V}/${name}.webm` });
  const t0 = await page.evaluate(() => performance.now());
  const extra = await fn(t0);
  const t1 = await page.evaluate(() => performance.now());
  await rec.stop();
  return { t0, dur: (t1 - t0) / 1000, ...extra };
}
const meta = {};

// ---------------------------------------------------------------- warm up (auth + App Check)
await page.goto(URL + "/#check", { waitUntil: "load" });
await sleep(6000);

// ---------------------------------------------------------------- scene: live guardian
await page.goto(URL + "/#live", { waitUntil: "load" });
await sleep(3000);
meta.live = await record("live", async (t0) => {
  await sleep(N2 * 1000 + 300);
  await click("Start guarding");
  let alertSince = null, summaryAt = null;
  for (let i = 0; i < 200; i++) {
    await sleep(500);
    const st = await page.evaluate(() => ({ alert: !!document.querySelector('[role="alertdialog"]'), done: document.body.innerText.includes("Peak risk") }));
    if (st.alert) { alertSince ??= Date.now(); if (Date.now() - alertSince > 3500) { await click("I understand"); alertSince = null; } }
    if (st.done) { summaryAt = await page.evaluate(() => performance.now()); break; }
  }
  const y = await elTop("h3", "");
  await smoothScroll(Math.max(0, (await elTop("section, div", "Call summary")) ? 400 : 0), 1200);
  await sleep(N3 * 1000 + 800);
  const rec = await page.evaluate(() => window.__rec);
  return { summaryAt: (summaryAt - t0) / 1000, sampleStart: rec.sampleStart ? (rec.sampleStart - t0) / 1000 : null,
           chunks: rec.chunks.map((c) => ({ t: (c.t - t0) / 1000, b64: c.b64 })) };
});
console.log("live", meta.live.dur.toFixed(1), "sampleStart", meta.live.sampleStart, "summary", meta.live.summaryAt, "chunks", meta.live.chunks.length);

// ---------------------------------------------------------------- scene: scam check
await page.goto(URL + "/#check", { waitUntil: "load" });
await sleep(2500);
meta.check = await record("check", async () => {
  await sleep(1500);
  await click("parcel fee");
  await sleep(1500);
  await click("Check with Kawal");
  await page.waitForSelector("#result", { timeout: 90000 }).catch(() => {});
  await sleep(1200);
  const top = await elTop("#result");
  await smoothScroll(top - 90, 1500);
  await sleep(3500);
  await smoothScroll(top + 650, 2500);
  await sleep(3000);
  await smoothScroll(top + 1250, 2000);
  const rest = Math.max(1500, N4 * 1000 - 0);
  await sleep(rest / 2);
});
console.log("check", meta.check.dur.toFixed(1));

// ---------------------------------------------------------------- scene: intel console
await page.goto(URL + "/#intel", { waitUntil: "load" });
await sleep(5000);
meta.intel = await record("intel", async () => {
  await sleep(2500);
  await smoothScroll(520, 2500); await sleep(2000);
  await smoothScroll(1050, 2000); await sleep(1500);
  const b = await elTop("h3", "THREAT BULLETIN") ?? await elTop("h3", "Threat bulletin");
  if (b) { await smoothScroll(b - 80, 2000); await sleep(3000); }
  const a = await elTop("h3", "ASK") ?? await elTop("h3", "Ask Kawal");
  if (a) { await smoothScroll(a - 120, 1800); }
  await click("Which scam campaigns are rising this week?");
  await page.waitForFunction(() => document.body.innerText.includes("How Kawal got this answer"), { timeout: 60000 }).catch(() => {});
  await sleep(800);
  await click("How Kawal got this answer");
  const a2 = await elTop("h3", "ASK") ?? await elTop("h3", "Ask Kawal");
  if (a2) await smoothScroll(a2 - 80, 1200);
  await sleep(3500);
});
console.log("intel", meta.intel.dur.toFixed(1));

fs.writeFileSync(`${V}/meta.json`, JSON.stringify(meta));
await browser.close();
