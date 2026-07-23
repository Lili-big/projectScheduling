import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
const presenter = readFileSync(resolve(root, "src/features/scheduleResults/presenter.ts"), "utf8");

test("schedule results presenter owns status and summary formatting", () => {
  assert.match(presenter, /scheduleStatusLabels/);
  assert.match(presenter, /export function formatScheduleStatus/);
  assert.match(presenter, /export function scheduleResultSummary/);
  assert.match(presenter, /objective_days/);
  assert.match(presenter, /summarizeDiagnostics/);
  assert.match(presenter, /objectiveBreakdownEntries/);
  assert.match(presenter, /export function unifiedSolvePresentation/);
  assert.match(presenter, /未自动增配、未重搜、未重试/);
});
