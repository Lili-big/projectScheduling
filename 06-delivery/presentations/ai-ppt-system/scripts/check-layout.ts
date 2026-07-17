import fs from "node:fs";
import { chromium } from "playwright";
import { ALLOWED_TYPES, charLen, ensureDir, fileUrl, isSlideType, readSpec, resolveProject, writeJson } from "./shared.ts";

interface Finding {
  severity: "error" | "warning";
  page?: number;
  code: string;
  message: string;
}

const spec = readSpec();
const findings: Finding[] = [];

for (const slide of spec.slides) {
  if (!isSlideType(slide.type)) {
    findings.push({ severity: "error", page: slide.page, code: "invalid_type", message: `Unknown slide type: ${slide.type}` });
  }
  if (!slide.title.trim()) {
    findings.push({ severity: "error", page: slide.page, code: "empty_title", message: "Slide title is empty." });
  }
  if (!slide.message.trim()) {
    findings.push({ severity: "error", page: slide.page, code: "empty_message", message: "Slide message is empty." });
  }
  if (charLen(slide.title) > 18) {
    findings.push({ severity: "error", page: slide.page, code: "long_title", message: `Title is ${charLen(slide.title)} chars; max is 18.` });
  }
  if (slide.points.length > 3) {
    findings.push({ severity: "error", page: slide.page, code: "too_many_points", message: `Slide has ${slide.points.length} points; max is 3.` });
  }
  slide.points.forEach((point, index) => {
    if (charLen(point) > 24) {
      findings.push({ severity: "error", page: slide.page, code: "long_point", message: `Point ${index + 1} is ${charLen(point)} chars; max is 24.` });
    }
  });
  const totalChars = charLen([slide.title, slide.message, ...slide.points].join(""));
  if (totalChars > 110) {
    findings.push({ severity: "warning", page: slide.page, code: "dense_slide", message: `Slide has ${totalChars} compact chars; consider reducing content.` });
  }
}

if (!spec.slides.length) {
  findings.push({ severity: "error", code: "empty_deck", message: "No slides found." });
}

if (!spec.slides.some((slide) => slide.type === "cover")) {
  findings.push({ severity: "warning", code: "missing_cover", message: "Deck has no cover slide." });
}

if (!spec.slides.every((slide) => ALLOWED_TYPES.includes(slide.type))) {
  findings.push({ severity: "error", code: "type_set", message: "At least one slide type is outside the allowed set." });
}

const htmlPath = resolveProject("output", "react", "index.html");
if (fs.existsSync(htmlPath)) {
  const htmlSource = fs.readFileSync(htmlPath, "utf8");
  if (!/\.deck\s*\{[\s\S]*?overflow:\s*hidden/i.test(htmlSource)) {
    findings.push({ severity: "error", code: "html_deck_not_fixed", message: "HTML output must use a fixed .deck stage with overflow hidden." });
  }
  if (!htmlSource.includes(".slide.active")) {
    findings.push({ severity: "error", code: "html_missing_active_slide", message: "HTML output must expose one active slide at a time." });
  }
  if (!htmlSource.includes("page-break-after: always")) {
    findings.push({ severity: "error", code: "html_missing_print_break", message: "HTML output must preserve page breaks for print export." });
  }
  if (!/addEventListener\(['\"]wheel['\"]/.test(htmlSource)) {
    findings.push({ severity: "error", code: "html_missing_wheel_navigation", message: "HTML output must support wheel navigation." });
  }
  if (/ArrowLeft|ArrowRight/.test(htmlSource)) {
    findings.push({ severity: "error", code: "html_disallowed_horizontal_keys", message: "HTML output must not bind ArrowLeft or ArrowRight for slide navigation by default." });
  }
  if (/<button\b[^>]*(?:prev|next)|(?:id|class)=["'][^"']*(?:prev|next)[^"']*["']/i.test(htmlSource)) {
    findings.push({ severity: "error", code: "html_disallowed_prev_next_controls", message: "HTML output must not show previous/next navigation controls by default." });
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await page.goto(fileUrl(htmlPath), { waitUntil: "networkidle" });
  const domFindings = await page.evaluate(() => {
    const results: Array<{ severity: "error" | "warning"; page?: number; code: string; message: string }> = [];
    const deck = document.querySelector<HTMLElement>(".deck");
    if (!deck) {
      results.push({ severity: "error", code: "html_missing_deck", message: "HTML output must wrap slides in a .deck container." });
    } else {
      const deckStyle = window.getComputedStyle(deck);
      if (deckStyle.overflowX !== "hidden" || deckStyle.overflowY !== "hidden") {
        results.push({ severity: "error", code: "html_deck_overflow", message: ".deck must hide overflow in presentation mode." });
      }
    }

    const slides = Array.from(document.querySelectorAll<HTMLElement>(".slide"));
    const activeSlides = slides.filter((slide) => slide.classList.contains("active"));
    if (activeSlides.length !== 1) {
      results.push({ severity: "error", code: "html_active_slide_count", message: `Expected exactly one active slide, found ${activeSlides.length}.` });
    }
    for (const slide of slides) {
      const pageNo = Number(slide.dataset.page || "0") || undefined;
      const fitItems = Array.from(slide.querySelectorAll<HTMLElement>(".fit-check"));
      for (const item of fitItems) {
        if (item.scrollWidth > item.clientWidth + 4 || item.scrollHeight > item.clientHeight + 8) {
          results.push({ severity: "error", page: pageNo, code: "text_overflow", message: item.textContent?.trim() || "Text overflow detected." });
        }
      }
      const boxes = Array.from(slide.querySelectorAll<HTMLElement>(".layout-item")).map((el) => {
        const rect = el.getBoundingClientRect();
        return { text: el.textContent?.trim() || el.tagName, left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom, width: rect.width, height: rect.height };
      });
      for (let i = 0; i < boxes.length; i += 1) {
        for (let j = i + 1; j < boxes.length; j += 1) {
          const a = boxes[i];
          const b = boxes[j];
          const x = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
          const y = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
          const overlap = x * y;
          const smaller = Math.min(a.width * a.height, b.width * b.height);
          if (smaller > 0 && overlap / smaller > 0.18) {
            results.push({ severity: "warning", page: pageNo, code: "possible_overlap", message: `${a.text} / ${b.text}` });
          }
        }
      }
    }
    return results;
  });
  findings.push(...domFindings);
  await browser.close();
} else {
  findings.push({ severity: "warning", code: "missing_react_html", message: "React HTML output not found; DOM layout checks skipped." });
}

const report = {
  status: findings.some((item) => item.severity === "error") ? "fail" : "pass",
  allowed_types: ALLOWED_TYPES,
  checked_at: new Date().toISOString(),
  findings
};

ensureDir(resolveProject("output", "checks"));
writeJson(["output", "checks", "layout-report.json"], report);
console.log(`Layout check ${report.status}: ${findings.length} finding(s).`);
if (report.status === "fail") {
  process.exitCode = 1;
}
