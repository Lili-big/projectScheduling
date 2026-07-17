import fs from "node:fs";
import { ensureDir, normalizeDeckTemplate, readSpec, resolveProject } from "./shared.ts";
import type { DeckTemplateVariant, SlideSpec } from "./shared.ts";

const spec = readSpec();
const deckTemplate = normalizeDeckTemplate(spec.deck.template);
const pptxModule = await import("pptxgenjs");
const PptxGenJS = (pptxModule.default ?? pptxModule) as unknown as new () => any;
const pptx = new PptxGenJS();

const SLIDE = { w: 13.333, h: 7.5 };

pptx.layout = "LAYOUT_WIDE";
pptx.author = "AI PPT System";
pptx.company = deckTemplate?.id === "company" ? "Glodon" : "Codex";
pptx.subject = spec.deck.scenario;
pptx.title = spec.deck.title;
pptx.lang = "zh-CN";
pptx.theme = {
  headFontFace: "Microsoft YaHei",
  bodyFontFace: "Microsoft YaHei",
  lang: "zh-CN"
};

const C = {
  bg: "F7F9FC",
  ink: "18202F",
  muted: "5A6475",
  line: "D9E0EA",
  primary: "1F5EFF",
  accent: "16A085",
  white: "FFFFFF"
};

interface CompanyTheme {
  variant: DeckTemplateVariant;
  bg: string;
  ink: string;
  muted: string;
  primary: string;
  accent: string;
  line: string;
  card: string;
  cardInk: string;
  cardTransparency: number;
  coverBg: string;
  coverLogo: string;
  agendaImage: string;
  sectionBg: string;
  contentBg: string;
  footerMark: string;
  cornerLogo: string;
  footerText: string;
}

const COMPANY_THEMES: Record<DeckTemplateVariant, CompanyTheme> = {
  light: {
    variant: "light",
    bg: "FFFFFF",
    ink: "15304F",
    muted: "52647A",
    primary: "2E8EF3",
    accent: "64C800",
    line: "D7E7F8",
    card: "FFFFFF",
    cardInk: "15304F",
    cardTransparency: 0,
    coverBg: "image1.jpg",
    coverLogo: "image2.png",
    agendaImage: "image3.jpg",
    sectionBg: "image4.jpg",
    contentBg: "image5.jpg",
    footerMark: "image7.png",
    cornerLogo: "image8.png",
    footerText: "2E8EF3"
  },
  dark: {
    variant: "dark",
    bg: "18367E",
    ink: "FFFFFF",
    muted: "D8E7FF",
    primary: "3F90FC",
    accent: "64C800",
    line: "7FAFF5",
    card: "FFFFFF",
    cardInk: "15304F",
    cardTransparency: 8,
    coverBg: "image10.jpg",
    coverLogo: "image11.png",
    agendaImage: "image12.jpg",
    sectionBg: "image13.jpg",
    contentBg: "image14.jpg",
    footerMark: "image7.png",
    cornerLogo: "image8.png",
    footerText: "BFD9FF"
  }
};

function mediaPath(fileName: string) {
  return resolveProject("assets", "company-template", "media", fileName);
}

function addImageIfAvailable(slide: any, fileName: string, options: { x: number; y: number; w: number; h: number }) {
  const filePath = mediaPath(fileName);
  if (fs.existsSync(filePath)) {
    slide.addImage({ path: filePath, ...options });
  }
}

function addChrome(slide: any, page: number, type: string) {
  slide.background = { color: C.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.1, h: 7.5, fill: { color: C.primary }, line: { color: C.primary } });
  slide.addText(type.replace("_", " ").toUpperCase(), { x: 0.72, y: 0.42, w: 3.5, h: 0.25, fontFace: "Microsoft YaHei", fontSize: 9, bold: true, color: C.accent, margin: 0 });
  slide.addText(String(page).padStart(2, "0"), { x: 12.25, y: 6.92, w: 0.55, h: 0.2, fontSize: 9, color: "8A94A6", align: "right", margin: 0 });
}

function addTitle(slide: any, title: string, message: string) {
  slide.addText(title, { x: 0.72, y: 0.82, w: 9.3, h: 0.65, fontFace: "Microsoft YaHei", fontSize: 28, bold: true, color: C.ink, breakLine: false, fit: "shrink", margin: 0 });
  slide.addText(message, { x: 0.72, y: 1.72, w: 8.8, h: 0.55, fontFace: "Microsoft YaHei", fontSize: 16, color: C.muted, fit: "shrink", margin: 0 });
}

function addPointCard(slide: any, text: string, x: number, y: number, w: number, h: number) {
  slide.addShape(pptx.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: { color: C.white }, line: { color: C.line, transparency: 0 } });
  slide.addText(text, { x: x + 0.18, y: y + 0.18, w: w - 0.36, h: h - 0.36, fontFace: "Microsoft YaHei", fontSize: 16, color: C.ink, fit: "shrink", valign: "mid", margin: 0 });
}

function addList(slide: any, points: string[]) {
  points.forEach((point, index) => addPointCard(slide, point, 0.72, 2.65 + index * 0.86, 7.8, 0.66));
}

function addCards(slide: any, points: string[]) {
  points.forEach((point, index) => addPointCard(slide, point, 0.72 + index * 3.55, 3.0, 3.2, 1.55));
}

function addSteps(slide: any, points: string[]) {
  points.forEach((point, index) => {
    const x = 0.72 + index * 3.55;
    addPointCard(slide, "", x, 3.0, 3.2, 1.65);
    slide.addText(String(index + 1).padStart(2, "0"), { x: x + 0.22, y: 3.25, w: 0.8, h: 0.35, fontSize: 21, bold: true, color: C.primary, margin: 0 });
    slide.addText(point, { x: x + 0.22, y: 3.82, w: 2.65, h: 0.46, fontFace: "Microsoft YaHei", fontSize: 15, color: C.ink, fit: "shrink", margin: 0 });
  });
}

function renderDefaultSlide(item: SlideSpec) {
  const slide = pptx.addSlide();
  addChrome(slide, item.page, item.type);
  if (item.type === "cover") {
    slide.addText(item.title, { x: 0.72, y: 2.1, w: 9.8, h: 0.9, fontFace: "Microsoft YaHei", fontSize: 34, bold: true, color: C.ink, fit: "shrink", margin: 0 });
    slide.addText(item.message, { x: 0.72, y: 3.18, w: 9.2, h: 0.56, fontFace: "Microsoft YaHei", fontSize: 18, color: C.muted, fit: "shrink", margin: 0 });
    item.points.forEach((point, index) => addPointCard(slide, point, 0.72 + index * 4.15, 4.24, 3.85, 0.58));
  } else {
    addTitle(slide, item.title, item.message);
    if (["process", "timeline", "roadmap", "agenda"].includes(item.type)) {
      addSteps(slide, item.points);
    } else if (["solution", "data_card", "architecture", "comparison"].includes(item.type)) {
      addCards(slide, item.points);
    } else {
      addList(slide, item.points);
    }
  }
  (slide as unknown as { addNotes?: (notes: string) => void }).addNotes?.(item.speaker_note);
}

function addCompanyBackground(slide: any, theme: CompanyTheme, kind: "cover" | "agenda" | "section" | "content") {
  slide.background = { color: theme.bg };
  if (kind === "cover") {
    addImageIfAvailable(slide, theme.coverBg, { x: 0, y: 0, w: SLIDE.w, h: SLIDE.h });
    addImageIfAvailable(slide, theme.coverLogo, { x: 0.8, y: 0.57, w: 3.34, h: 0.63 });
    return;
  }
  if (kind === "agenda") {
    if (theme.variant === "light") {
      addImageIfAvailable(slide, theme.agendaImage, { x: 0, y: 0.57, w: 4.2, h: 5.6 });
    } else {
      slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: SLIDE.w, h: SLIDE.h, fill: { color: theme.bg }, line: { color: theme.bg } });
      slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 4.1, h: SLIDE.h, fill: { color: "102A64" }, line: { color: "102A64" } });
      addImageIfAvailable(slide, theme.agendaImage, { x: 0.01, y: 1.77, w: 3.82, h: 4.49 });
    }
    return;
  }
  if (kind === "section") {
    if (theme.variant === "light") {
      addImageIfAvailable(slide, theme.sectionBg, { x: 0, y: 4.88, w: SLIDE.w, h: 2.62 });
    } else {
      addImageIfAvailable(slide, theme.sectionBg, { x: 0, y: 0, w: SLIDE.w, h: SLIDE.h });
    }
    return;
  }
  addImageIfAvailable(slide, theme.contentBg, { x: 0, y: 0, w: SLIDE.w, h: SLIDE.h });
  addImageIfAvailable(slide, theme.cornerLogo, { x: 0.42, y: 0.28, w: 0.36, h: 0.27 });
  addImageIfAvailable(slide, theme.footerMark, { x: 11.16, y: 6.93, w: 0.59, h: 0.57 });
  slide.addText("数字建筑平台服务商", { x: 11.55, y: 7.12, w: 1.47, h: 0.22, fontFace: "Microsoft YaHei", fontSize: 7.5, color: theme.footerText, fit: "shrink", margin: 0 });
}

function addCompanyPage(slide: any, item: SlideSpec, theme: CompanyTheme) {
  slide.addText(String(item.page).padStart(2, "0"), { x: 12.16, y: 6.9, w: 0.62, h: 0.2, fontSize: 8.5, color: theme.footerText, align: "right", margin: 0 });
}

function addCompanyPointCard(slide: any, theme: CompanyTheme, text: string, x: number, y: number, w: number, h: number) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x,
    y,
    w,
    h,
    rectRadius: 0.06,
    fill: { color: theme.card, transparency: theme.cardTransparency },
    line: { color: theme.line, transparency: theme.variant === "dark" ? 30 : 0 }
  });
  slide.addText(text, { x: x + 0.22, y: y + 0.17, w: w - 0.44, h: h - 0.34, fontFace: "Microsoft YaHei", fontSize: 15.5, color: theme.cardInk, fit: "shrink", valign: "mid", margin: 0 });
}

function addCompanyTitle(slide: any, item: SlideSpec, theme: CompanyTheme) {
  slide.addText(item.title, { x: 0.94, y: 0.1, w: 10.33, h: 0.58, fontFace: "Microsoft YaHei", fontSize: 24, bold: true, color: theme.ink, fit: "shrink", margin: 0 });
  slide.addShape(pptx.ShapeType.rect, { x: 0.94, y: 0.73, w: 0.84, h: 0.04, fill: { color: theme.primary }, line: { color: theme.primary } });
  slide.addText(item.message, { x: 0.94, y: 0.91, w: 9.8, h: 0.48, fontFace: "Microsoft YaHei", fontSize: 13.5, color: theme.muted, fit: "shrink", margin: 0 });
}

function addCompanyList(slide: any, item: SlideSpec, theme: CompanyTheme) {
  item.points.forEach((point, index) => addCompanyPointCard(slide, theme, point, 0.94, 2.08 + index * 0.93, 7.9, 0.72));
}

function addCompanyCards(slide: any, item: SlideSpec, theme: CompanyTheme) {
  item.points.forEach((point, index) => {
    const x = 0.94 + index * 3.65;
    addCompanyPointCard(slide, theme, point, x, 2.55, 3.28, 1.48);
    slide.addShape(pptx.ShapeType.rect, { x: x + 0.22, y: 2.83, w: 0.34, h: 0.05, fill: { color: theme.accent }, line: { color: theme.accent } });
  });
}

function addCompanySteps(slide: any, item: SlideSpec, theme: CompanyTheme) {
  item.points.forEach((point, index) => {
    const x = 0.94 + index * 3.65;
    addCompanyPointCard(slide, theme, "", x, 2.48, 3.28, 1.55);
    slide.addText(String(index + 1).padStart(2, "0"), { x: x + 0.24, y: 2.74, w: 0.74, h: 0.34, fontFace: "Microsoft YaHei", fontSize: 20, bold: true, color: theme.primary, margin: 0 });
    slide.addText(point, { x: x + 0.24, y: 3.3, w: 2.74, h: 0.44, fontFace: "Microsoft YaHei", fontSize: 14.5, color: theme.cardInk, fit: "shrink", margin: 0 });
  });
}

function renderCompanyCover(item: SlideSpec, theme: CompanyTheme) {
  const slide = pptx.addSlide();
  addCompanyBackground(slide, theme, "cover");
  slide.addText(item.title, { x: 0.8, y: 1.48, w: 6.85, h: 1.45, fontFace: "Microsoft YaHei", fontSize: 34, bold: true, color: theme.ink, fit: "shrink", margin: 0 });
  slide.addText(item.message, { x: 0.8, y: 3.24, w: 6.7, h: 0.36, fontFace: "Microsoft YaHei", fontSize: 14.5, color: theme.muted, fit: "shrink", margin: 0 });
  slide.addText(item.points.join(" | "), { x: 0.8, y: 3.64, w: 6.3, h: 0.32, fontFace: "Microsoft YaHei", fontSize: 11, color: theme.muted, fit: "shrink", margin: 0 });
  (slide as unknown as { addNotes?: (notes: string) => void }).addNotes?.(item.speaker_note);
}

function renderCompanyAgenda(item: SlideSpec, theme: CompanyTheme) {
  const slide = pptx.addSlide();
  addCompanyBackground(slide, theme, "agenda");
  slide.addText("CONTENTS", { x: 4.48, y: 1.63, w: 2.7, h: 0.58, fontFace: "Microsoft YaHei", fontSize: 23, bold: true, color: theme.primary, margin: 0 });
  slide.addText(item.title, { x: 4.4, y: 0.72, w: 3.8, h: 0.7, fontFace: "Microsoft YaHei", fontSize: 30, bold: true, color: theme.ink, fit: "shrink", margin: 0 });
  item.points.forEach((point, index) => {
    const y = 2.75 + index * 0.58;
    slide.addText(String(index + 1).padStart(2, "0"), { x: 4.58, y, w: 0.5, h: 0.26, fontFace: "Microsoft YaHei", fontSize: 13, bold: true, color: theme.primary, margin: 0 });
    slide.addText(point, { x: 5.25, y, w: 4.6, h: 0.3, fontFace: "Microsoft YaHei", fontSize: 14.5, color: theme.ink, fit: "shrink", margin: 0 });
  });
  (slide as unknown as { addNotes?: (notes: string) => void }).addNotes?.(item.speaker_note);
}

function renderCompanySection(item: SlideSpec, theme: CompanyTheme) {
  const slide = pptx.addSlide();
  addCompanyBackground(slide, theme, "section");
  slide.addText(String(item.page).padStart(2, "0"), { x: 5.86, y: 2.01, w: 1.61, h: 1.22, fontFace: "Microsoft YaHei", fontSize: 45, bold: true, color: theme.primary, align: "center", margin: 0 });
  slide.addText(item.title, { x: 3.87, y: 3.5, w: 5.59, h: 0.88, fontFace: "Microsoft YaHei", fontSize: 28, bold: true, color: theme.ink, align: "center", fit: "shrink", margin: 0 });
  slide.addText(item.message, { x: 3.9, y: 4.37, w: 5.55, h: 0.34, fontFace: "Microsoft YaHei", fontSize: 13, color: theme.muted, align: "center", fit: "shrink", margin: 0 });
  (slide as unknown as { addNotes?: (notes: string) => void }).addNotes?.(item.speaker_note);
}

function renderCompanyContent(item: SlideSpec, theme: CompanyTheme) {
  const slide = pptx.addSlide();
  addCompanyBackground(slide, theme, "content");
  addCompanyTitle(slide, item, theme);
  if (["process", "timeline", "roadmap"].includes(item.type)) {
    addCompanySteps(slide, item, theme);
  } else if (["solution", "data_card", "architecture", "comparison", "summary"].includes(item.type)) {
    addCompanyCards(slide, item, theme);
  } else {
    addCompanyList(slide, item, theme);
  }
  addCompanyPage(slide, item, theme);
  (slide as unknown as { addNotes?: (notes: string) => void }).addNotes?.(item.speaker_note);
}

function renderCompanySlide(item: SlideSpec, theme: CompanyTheme) {
  if (item.type === "cover") {
    renderCompanyCover(item, theme);
  } else if (item.type === "agenda") {
    renderCompanyAgenda(item, theme);
  } else if (item.type === "section") {
    renderCompanySection(item, theme);
  } else {
    renderCompanyContent(item, theme);
  }
}

const companyTheme = deckTemplate ? COMPANY_THEMES[deckTemplate.variant] : undefined;

for (const item of spec.slides) {
  if (companyTheme) {
    renderCompanySlide(item, companyTheme);
  } else {
    renderDefaultSlide(item);
  }
}

const outDir = resolveProject("output", "pptx");
ensureDir(outDir);
await pptx.writeFile({ fileName: resolveProject("output", "pptx", "deck.pptx") });
console.log(`Generated output/pptx/deck.pptx${companyTheme ? ` with company ${companyTheme.variant} template` : ""}.`);
