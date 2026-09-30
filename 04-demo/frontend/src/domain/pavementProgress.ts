import type { ScenarioInput } from "../contracts";
import type { PavementProgressView, PavementProgressCell } from "../contracts/projectMaster";
import { pavementTaskGroups } from "./pavement";

export type ProgressDrafts = Record<string, string>;
export const progressCellKey = (componentId: string, date: string) => JSON.stringify([componentId, date]);
export function parseDailyLength(text: string): {value: number | null; error: string | null} {
  const raw = text.trim();
  if (!raw) return {value: null, error: null};
  if (!/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(raw)) return {value: null, error: "请输入非负完成长度"};
  const fraction = (raw.split(".")[1] ?? "").replace(/0+$/, "");
  if (fraction.length > 3) return {value: null, error: "最多填写3位小数"};
  const value = Number(raw);
  if (!Number.isFinite(value) || !Number.isSafeInteger(Math.round(value * 1000))) return {value: null, error: "数值超出可保存范围"};
  return {value, error: null};
}
export function progressEntryMap(view: PavementProgressView) {
  return new Map(view.entries.map(e => [progressCellKey(e.component_id, e.progress_date), e.completed_length_m]));
}
export function progressChanges(view: PavementProgressView, drafts: ProgressDrafts): PavementProgressCell[] {
  const saved = progressEntryMap(view);
  const changes: PavementProgressCell[] = [];
  for (const [key, text] of Object.entries(drafts)) {
    const parsed = parseDailyLength(text);
    if (parsed.error) throw new Error(parsed.error);
    if (parsed.value === (saved.get(key) ?? null)) continue;
    const [component_id, progress_date] = JSON.parse(key) as [string, string];
    changes.push({component_id, progress_date, completed_length_m: parsed.value});
  }
  return changes;
}
export function progressTotals(view: PavementProgressView, drafts: ProgressDrafts) {
  const entries = progressEntryMap(view);
  for (const [key, text] of Object.entries(drafts)) {
    const parsed = parseDailyLength(text);
    if (parsed.error) continue; // Keep the last saved contribution until the invalid draft is corrected.
    if (parsed.value == null) entries.delete(key); else entries.set(key, parsed.value);
  }
  const sums: Record<string, number> = {};
  for (const [key, value] of entries) {
    const [id] = JSON.parse(key) as [string, string];
    sums[id] = (sums[id] ?? 0) + Math.round(value * 1000);
  }
  return Object.fromEntries([...view.rows, ...view.historical_rows].map(row => {
    const scaled = sums[row.component_id] ?? 0;
    const completed = scaled / 1000;
    const remaining = row.design_length_m == null ? null : Number((row.design_length_m - completed).toPrecision(15));
    return [row.component_id, {completed, remaining, overrun: remaining == null ? null : Math.max(0, -remaining),
      error: Number.isSafeInteger(scaled) ? null : "累计量超出可安全表示范围"}];
  }));
}
export function progressGroups(scenario: ScenarioInput, view: PavementProgressView) {
  const lookup = new Map(view.rows.map(r => [r.component_id, r]));
  return pavementTaskGroups(scenario, null).map(group => ({...group,
    rows: group.rows.map(row => ({...row, master: row.componentId ? lookup.get(row.componentId) ?? null : null})),
  }));
}
export function progressReview(view: PavementProgressView, drafts: ProgressDrafts) {
  const saved = progressEntryMap(view);
  const rows = new Map(view.rows.map(r => [r.component_id, r]));
  return Object.entries(drafts).map(([key, local]) => {
    const [componentId, date] = JSON.parse(key) as [string, string];
    return {key, componentId, date, local, saved: saved.get(key) ?? null, row: rows.get(componentId), editable: rows.has(componentId)};
  });
}
export function progressRequestGate() {
  let revision = 0;
  return {next() {const token = ++revision; return () => token === revision;}, cancel() {revision++;}};
}
export function currentProgressMonth(now = new Date()) {
  return `${now.getFullYear().toString().padStart(4,"0")}-${(now.getMonth()+1).toString().padStart(2,"0")}`;
}
export function progressMonthDays(month: string) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month) || month.startsWith("0000")) return [];
  const [year, m] = month.split("-").map(Number);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const count = [31,leap ? 29 : 28,31,30,31,30,31,31,30,31,30,31][m-1];
  return Array.from({length: count}, (_, i) => `${month}-${String(i+1).padStart(2,"0")}`);
}
export function shiftProgressMonth(month: string, delta: number) {
  if (!progressMonthDays(month).length) return currentProgressMonth();
  const [year, m] = month.split("-").map(Number);
  const total = year * 12 + m - 1 + delta;
  if (total < 12 || total >= 120000) return month;
  return `${Math.floor(total / 12).toString().padStart(4,"0")}-${String(total % 12 + 1).padStart(2,"0")}`;
}
export function progressError(reason: unknown) {
  const message = reason instanceof Error ? reason.message : String(reason);
  try {
    const detail = JSON.parse(message).detail;
    if (detail?.message) return `${detail.message}（${detail.code ?? ""}）`;
    if (Array.isArray(detail)) return detail.map(x => x.msg).join("；");
  } catch { /* Existing API helpers may already return a human-readable message. */ }
  return message;
}
