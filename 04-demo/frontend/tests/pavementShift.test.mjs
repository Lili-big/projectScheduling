import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import ts from "typescript";

const load = async path => import(`data:text/javascript;base64,${Buffer.from(ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText).toString("base64")}`);
const pavement = await load("../src/domain/pavement.ts");

const START = "2026-07-01";
const sc001 = [
  { start_date: "2026-07-01", end_date: "2026-09-30", shifts: 1 },
  { start_date: "2026-10-01", end_date: null, shifts: 2 },
];

test("empty shift regimes keep the baseline duration exactly (FR-005)", () => {
  for (const offset of [0, 62, 96]) {
    assert.equal(pavement.taskDurationForStart(8000, 8, 1000, offset, [], START), 8);
    assert.equal(pavement.taskDurationForStart(8000, 8, 1000, offset, null, START), 8);
  }
});

test("SC-001 samples match the backend duration function", () => {
  assert.equal(pavement.taskDurationForStart(8000, 8, 1000, 96, sc001, START), 4);   // 10-05 双班
  assert.equal(pavement.taskDurationForStart(8000, 8, 1000, 86, sc001, START), 7);   // 9-25 跨界
  assert.equal(pavement.taskDurationForStart(8000, 8, 1000, 62, sc001, START), 8);   // 9-01 单班内
  assert.equal(pavement.taskDurationForStart(8000, 27, 300, 0, [], START), 27);
  assert.equal(pavement.taskDurationForStart(8000, 8, 300, 96, sc001, START), 14);   // 8000/600 -> 14
});

test("crossing tasks split single and double shift days for display", () => {
  assert.deepEqual(pavement.splitShiftDays(86, 93, sc001, START), { 1: 6, 2: 1 });
  assert.deepEqual(pavement.splitShiftDays(62, 70, sc001, START), { 1: 8 });
  assert.equal(pavement.shiftSplitText(86, 93, sc001, START), "单班 6 天 + 双班 1 天");
  assert.equal(pavement.shiftSplitText(62, 70, [], START), "单班 8 天");
});

test("minimum one day and productivity-free tasks keep fixed durations", () => {
  assert.equal(pavement.taskDurationForStart(500, 8, 1000, 0, sc001, START), 1);
  assert.equal(pavement.taskDurationForStart(1, 2, null, 96, sc001, START), 2);
});

test("shift config errors report inverted ranges and overlaps", () => {
  assert.deepEqual(pavement.pavementShiftConfigErrors(sc001), []);
  assert.ok(pavement.pavementShiftConfigErrors([...sc001, { start_date: "2026-11-01", end_date: null, shifts: 1 }]).includes("班制区间相互重叠或起点重复，请合并或调整区间。"));
  assert.deepEqual(pavement.pavementShiftConfigErrors([{ start_date: "2026-10-01", end_date: "2026-09-01", shifts: 2 }]), ["班制区间的结束日不能早于起始日。"]);
  assert.ok(pavement.pavementShiftConfigErrors([...sc001, { start_date: "2026-10-01", end_date: null, shifts: 1 }]).includes("班制区间相互重叠或起点重复，请合并或调整区间。"));
});

test("double shift inside a regime doubles the daily output without touching transfers", () => {
  assert.equal(pavement.shiftsForDay(sc001, "2026-09-30"), 1);
  assert.equal(pavement.shiftsForDay(sc001, "2026-10-01"), 2);
  assert.equal(pavement.shiftsForDay(sc001, "2026-06-30"), 1);
});
