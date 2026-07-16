import { chromium } from "playwright";
import { ensureDir, fileUrl, resolveProject } from "./shared.ts";

const htmlPath = resolveProject("output", "react", "index.html");
const outPath = resolveProject("output", "pdf", "deck.pdf");
ensureDir(resolveProject("output", "pdf"));

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
await page.goto(fileUrl(htmlPath), { waitUntil: "networkidle" });
await page.emulateMedia({ media: "print" });
await page.pdf({
  path: outPath,
  printBackground: true,
  preferCSSPageSize: true,
  width: "1280px",
  height: "720px",
  margin: { top: "0", right: "0", bottom: "0", left: "0" }
});
await browser.close();
console.log("Generated output/pdf/deck.pdf.");

