import puppeteer from "puppeteer";
import fs from "fs";
const D = process.argv[2];
const b = await puppeteer.launch({ headless: true });
const p = await b.newPage();
await p.setViewport({ width: 1920, height: 1080 });
await p.goto("file://" + D + "/deck.html", { waitUntil: "networkidle0" });
const n = await p.$$eval("section.s", (s) => s.length);
fs.mkdirSync(D + "/render", { recursive: true });
const secs = await p.$$("section.s");
for (let i = 0; i < secs.length; i++) await secs[i].screenshot({ path: `${D}/render/s${String(i + 1).padStart(2, "0")}.png` });
// geometry for PPTX
const geo = await p.$$eval("section.s", (ss) => ss.map((s) => {
  const bg = getComputedStyle(s).backgroundImage.match(/bg\/(p\d+\.png)/)?.[1];
  const r0 = s.getBoundingClientRect();
  const els = [...s.children].map((e) => {
    const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
    const base = { x: r.left - r0.left, y: r.top - r0.top, w: r.width, h: r.height };
    if (e.tagName === "IMG") return { kind: "img", src: e.getAttribute("src"), fit: cs.objectFit, ...base };
    if (e.classList.contains("box")) return { kind: "box", fill: cs.backgroundColor, ...base };
    // text: walk nodes into runs, split paragraphs at <br>
    const paras = [[]];
    const walk = (node, st) => {
      for (const c of node.childNodes) {
        if (c.nodeType === 3) { if (c.textContent) paras[paras.length - 1].push({ t: c.textContent, ...st }); }
        else if (c.tagName === "BR") paras.push([]);
        else { const ccs = getComputedStyle(c); walk(c, { b: ccs.fontWeight >= 700, color: ccs.color, size: parseFloat(ccs.fontSize) }); }
      }
    };
    walk(e, { b: cs.fontWeight >= 700, color: cs.color, size: parseFloat(cs.fontSize) });
    return { kind: "text", paras, ...base };
  });
  return { bg, els };
}));
fs.writeFileSync(D + "/geo.json", JSON.stringify(geo));
await p.pdf({ path: D + "/deck.pdf", width: "1920px", height: "1080px", printBackground: true });
await b.close();
console.log("slides", n);
