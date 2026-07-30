import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const PROJECT_ROOT = path.resolve(__dirname, "..");
export const REPOSITORY_ROOT = path.resolve(PROJECT_ROOT, "..", "..", "..");
export const SPEC_PATH = process.env.AI_PPT_SPEC_PATH
  ? path.resolve(PROJECT_ROOT, process.env.AI_PPT_SPEC_PATH)
  : path.join(PROJECT_ROOT, "specs", "slide_spec.json");
export const OUTPUT_ROOT = process.env.AI_PPT_OUTPUT_DIR
  ? path.resolve(PROJECT_ROOT, process.env.AI_PPT_OUTPUT_DIR)
  : path.join(REPOSITORY_ROOT, ".local-data", "archive", "rebuildable", "ai-ppt-system", "output");

export const ALLOWED_TYPES = [
  "cover",
  "agenda",
  "section",
  "problem",
  "insight",
  "solution",
  "process",
  "comparison",
  "timeline",
  "data_card",
  "architecture",
  "case",
  "roadmap",
  "summary"
] as const;

export type SlideType = (typeof ALLOWED_TYPES)[number];

export type DeckTemplateVariant = "light" | "dark";

export interface DeckTemplate {
  id: "company";
  variant: DeckTemplateVariant;
}

export interface SlideSpec {
  page: number;
  type: SlideType;
  title: string;
  message: string;
  points: string[];
  visual: string;
  speaker_note: string;
  layout?: string;
  evidence?: string;
  details?: Record<string, any>;
}

export interface DeckSpec {
  deck: {
    title: string;
    audience: string;
    scenario: string;
    goal: string;
    page_count: number;
    style: string;
    formats: string[];
    template?: DeckTemplate;
  };
  slides: SlideSpec[];
}

export function resolveProject(...parts: string[]) {
  if (parts[0] === "output") {
    return path.join(OUTPUT_ROOT, ...parts.slice(1));
  }
  return path.join(PROJECT_ROOT, ...parts);
}

export function ensureDir(dirPath: string) {
  fs.mkdirSync(dirPath, { recursive: true });
}

export function readText(...parts: string[]) {
  const content = fs.readFileSync(resolveProject(...parts), "utf8");
  return content.charCodeAt(0) === 0xfeff ? content.slice(1) : content;
}

export function writeText(parts: string[], content: string) {
  const outPath = resolveProject(...parts);
  ensureDir(path.dirname(outPath));
  fs.writeFileSync(outPath, content, "utf8");
  return outPath;
}

export function readSpec(): DeckSpec {
  const content = fs.readFileSync(SPEC_PATH, "utf8");
  const normalized = content.charCodeAt(0) === 0xfeff ? content.slice(1) : content;
  return JSON.parse(normalized) as DeckSpec;
}

export function normalizeDeckTemplate(template: unknown): DeckTemplate | undefined {
  if (!template || typeof template !== "object") {
    return undefined;
  }
  const raw = template as Partial<DeckTemplate>;
  if (raw.id !== "company") {
    return undefined;
  }
  return { id: "company", variant: raw.variant === "dark" ? "dark" : "light" };
}

export function writeJson(parts: string[], data: unknown) {
  return writeText(parts, `${JSON.stringify(data, null, 2)}\n`);
}

export function fileUrl(filePath: string) {
  return pathToFileURL(filePath).toString();
}

export function compact(text: string) {
  return text.replace(/\s+/g, " ").trim();
}

export function charLen(text: string) {
  return Array.from(text.replace(/\s+/g, "")).length;
}

export function limitText(text: string, max: number) {
  const cleaned = compact(text);
  const chars = Array.from(cleaned);
  return chars.length <= max ? cleaned : chars.slice(0, max).join("");
}

export function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function escapeMarp(text: string) {
  return text.replace(/\|/g, "\\|").trim();
}

export function isSlideType(value: string): value is SlideType {
  return (ALLOWED_TYPES as readonly string[]).includes(value);
}
