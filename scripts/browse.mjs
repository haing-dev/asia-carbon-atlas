// Discovery helper (CI only): open each URL once in headless Chromium and log the JSON/API requests the page makes,
// so an adapter can read the same public endpoints directly. Usage: node scripts/browse.mjs URL [URL ...]
import { chromium } from "playwright";
import fs from "node:fs";
fs.mkdirSync("work/discover", { recursive: true });
const b = await chromium.launch();
const ua = "AsiaCarbonAtlas/0.1 (non-commercial research; +https://github.com/haing-dev/asia-carbon-atlas)";
let n = 0;
for (const url of process.argv.slice(2)) {
  const p = await b.newPage({ userAgent: ua });
  const log = [];
  p.on("response", async (r) => {
    const ct = r.headers()["content-type"] || "";
    if (r.request().resourceType() === "xhr" || r.request().resourceType() === "fetch" || ct.includes("json")) {
      if (/cookielaw|\/i18n\/|\/images\//.test(r.url())) return;
      let body = ""; try { body = (await r.body()).toString("utf8").slice(0, 20000); } catch (e) { body = "BODY ERROR " + e.message; }
      const hdr = JSON.stringify(r.request().headers()).slice(0, 600);
      log.push(`### ${r.request().method()} ${r.status()} ${r.url()}\nreqheaders: ${hdr}\nreq: ${(r.request().postData() || "").slice(0, 1500)}\n${body}\n`);
    }
  });
  try { await p.goto(url, { waitUntil: "networkidle", timeout: 60000 }); } catch (e) { log.push("GOTO ERROR " + e.message); }
  await p.waitForTimeout(15000);
  const text = (await p.evaluate(() => document.body.innerText).catch(() => "")).slice(0, 6000);
  fs.writeFileSync(`work/discover/browse-${n++}.txt`, `URL: ${url}\n\nPAGE TEXT:\n${text}\n\nREQUESTS:\n${log.join("\n")}`);
  await p.close();
  await new Promise((r) => setTimeout(r, 2000));
}
await b.close();
