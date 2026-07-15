import { chromium } from "playwright";
import { ensureDir, fileUrl, resolveProject } from "./shared.ts";

const htmlPath = resolveProject("output", "react", "index.html");
const outDir = resolveProject("output", "png");
ensureDir(outDir);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
await page.goto(fileUrl(htmlPath), { waitUntil: "networkidle" });

const slides = page.locator(".slide");
const count = await slides.count();
for (let i = 0; i < count; i += 1) {
  await page.evaluate((activeIndex) => {
    const items = Array.from(document.querySelectorAll<HTMLElement>(".slide"));
    items.forEach((item, index) => {
      const active = index === activeIndex;
      item.classList.toggle("active", active);
      item.setAttribute("aria-hidden", active ? "false" : "true");
    });
  }, i);
  await page.waitForTimeout(450);
  const outPath = resolveProject("output", "png", `slide-${String(i + 1).padStart(2, "0")}.png`);
  await slides.nth(i).screenshot({ path: outPath });
}

await browser.close();
console.log(`Generated ${count} PNG slide images.`);
