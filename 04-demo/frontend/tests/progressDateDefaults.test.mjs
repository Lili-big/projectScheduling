import assert from "node:assert/strict";
import test from "node:test";

import {
  applyActualDateStatusDefaults,
  buildPlannedTaskDatesById,
  dateCutoff,
  formatLocalDate,
  markActualDateFieldManual,
  recomputeSuggestedActualDates,
} from "../src/features/planControl/progressDateDefaults.ts";

const today = "2026-07-14";
const statusDate = "2026-07-13";
const planned = {
  taskId: "task-1",
  plannedStartDate: "2026-07-10",
  plannedFinishDate: "2026-07-20",
  isValid: true,
  message: null,
};

function entry(status, actualStartDate = null, actualFinishDate = null) {
  return {
    task_id: "task-1",
    status,
    actual_start_date: actualStartDate,
    actual_finish_date: actualFinishDate,
  };
}

test("按浏览器本地年月日生成业务日期，不使用 UTC 截断", () => {
  assert.equal(formatLocalDate(new Date(2026, 0, 2, 23, 30)), "2026-01-02");
});

test("日期上限取状态日期和系统当前日期中的较早值", () => {
  assert.equal(dateCutoff(statusDate, today), "2026-07-13");
  assert.equal(dateCutoff("2026-07-15", today), "2026-07-14");
  assert.equal(dateCutoff("", today), null);
});

test("计划任务日期映射识别有效、缺失、格式错误和倒置日期", () => {
  const result = buildPlannedTaskDatesById([
    { id: "valid", start_date: "2026-07-10", finish_date: "2026-07-20" },
    { id: "missing", start_date: "", finish_date: "2026-07-20" },
    { id: "invalid", start_date: "2026-02-30", finish_date: "2026-07-20" },
    { id: "reversed", start_date: "2026-07-20", finish_date: "2026-07-10" },
  ]);

  assert.equal(result.valid.isValid, true);
  assert.match(result.missing.message, /缺少/);
  assert.match(result.invalid.message, /格式/);
  assert.match(result.reversed.message, /早于/);
});

test("进行中和暂停只为空字段建议实际开始", () => {
  for (const status of ["in_progress", "paused"]) {
    const result = applyActualDateStatusDefaults(entry("not_started"), status, planned, statusDate, today);
    assert.equal(result.entry.actual_start_date, "2026-07-10");
    assert.equal(result.entry.actual_finish_date, null);
    assert.equal(result.suggestion.actualStartSuggested, true);
    assert.equal(result.suggestion.actualFinishSuggested, false);
  }
});

test("计划开始晚于日期上限时以日期上限作为实际开始建议", () => {
  const futurePlan = { ...planned, plannedStartDate: "2026-07-15" };
  const result = applyActualDateStatusDefaults(entry("not_started"), "in_progress", futurePlan, statusDate, today);
  assert.equal(result.entry.actual_start_date, "2026-07-13");
});

test("已完成任务建议实际起止日期且完成不早于开始", () => {
  const result = applyActualDateStatusDefaults(entry("not_started"), "completed", planned, statusDate, today);
  assert.equal(result.entry.actual_start_date, "2026-07-10");
  assert.equal(result.entry.actual_finish_date, "2026-07-13");
  assert.equal(result.suggestion.actualStartSuggested, true);
  assert.equal(result.suggestion.actualFinishSuggested, true);

  const futurePlan = { ...planned, plannedStartDate: "2026-07-15" };
  const futureResult = applyActualDateStatusDefaults(entry("not_started"), "completed", futurePlan, statusDate, today);
  assert.equal(futureResult.entry.actual_start_date, "2026-07-13");
  assert.equal(futureResult.entry.actual_finish_date, "2026-07-13");
});

test("未开始清空实际日期，取消保留已有开始但不生成完成", () => {
  const notStarted = applyActualDateStatusDefaults(
    entry("completed", "2026-07-10", "2026-07-12"),
    "not_started",
    planned,
    statusDate,
    today,
    { actualStartSuggested: true, actualFinishSuggested: true },
  );
  assert.equal(notStarted.entry.actual_start_date, null);
  assert.equal(notStarted.entry.actual_finish_date, null);
  assert.deepEqual(notStarted.suggestion, { actualStartSuggested: false, actualFinishSuggested: false });

  const cancelled = applyActualDateStatusDefaults(
    entry("in_progress", "2026-07-11"),
    "cancelled",
    planned,
    statusDate,
    today,
  );
  assert.equal(cancelled.entry.actual_start_date, "2026-07-11");
  assert.equal(cancelled.entry.actual_finish_date, null);
});

test("切换状态只补空值并保留人工或历史实际开始", () => {
  const result = applyActualDateStatusDefaults(
    entry("in_progress", "2026-07-09"),
    "completed",
    planned,
    statusDate,
    today,
  );
  assert.equal(result.entry.actual_start_date, "2026-07-09");
  assert.equal(result.entry.actual_finish_date, "2026-07-13");
  assert.equal(result.suggestion.actualStartSuggested, false);
  assert.equal(result.suggestion.actualFinishSuggested, true);
});

test("从已完成切换为进行中时清空实际完成并保留实际开始", () => {
  const result = applyActualDateStatusDefaults(
    entry("completed", "2026-07-09", "2026-07-12"),
    "in_progress",
    planned,
    statusDate,
    today,
  );
  assert.equal(result.entry.actual_start_date, "2026-07-09");
  assert.equal(result.entry.actual_finish_date, null);
  assert.equal(result.suggestion.actualFinishSuggested, false);
});

test("状态日期变化只重算仍为系统建议的字段", () => {
  const source = entry("completed", "2026-07-10", "2026-07-13");
  const suggestion = { actualStartSuggested: false, actualFinishSuggested: true };
  const result = recomputeSuggestedActualDates(
    source,
    suggestion,
    planned,
    "2026-07-12",
    today,
  );
  assert.equal(result.entry.actual_start_date, "2026-07-10");
  assert.equal(result.entry.actual_finish_date, "2026-07-12");
});

test("用户修改或主动清空日期后取消对应自动建议资格", () => {
  const suggestion = { actualStartSuggested: true, actualFinishSuggested: true };
  assert.deepEqual(markActualDateFieldManual(suggestion, "actual_start_date"), {
    actualStartSuggested: false,
    actualFinishSuggested: true,
  });
  assert.deepEqual(markActualDateFieldManual(suggestion, "actual_finish_date"), {
    actualStartSuggested: true,
    actualFinishSuggested: false,
  });
});

test("无效计划日期或空状态日期不生成新的日期建议", () => {
  const invalidPlan = { ...planned, isValid: false, message: "计划完成日期早于计划开始日期" };
  const invalidPlanResult = applyActualDateStatusDefaults(
    entry("not_started"),
    "completed",
    invalidPlan,
    statusDate,
    today,
  );
  assert.equal(invalidPlanResult.entry.actual_start_date, null);
  assert.equal(invalidPlanResult.entry.actual_finish_date, null);

  const emptyStatusResult = applyActualDateStatusDefaults(
    entry("not_started"),
    "completed",
    planned,
    "",
    today,
  );
  assert.equal(emptyStatusResult.entry.actual_start_date, null);
  assert.equal(emptyStatusResult.entry.actual_finish_date, null);
});

test("人工实际开始晚于新日期上限时不生成冲突的实际完成建议", () => {
  const result = applyActualDateStatusDefaults(
    entry("in_progress", "2026-07-14"),
    "completed",
    planned,
    "2026-07-13",
    today,
  );
  assert.equal(result.entry.actual_start_date, "2026-07-14");
  assert.equal(result.entry.actual_finish_date, null);
  assert.equal(result.suggestion.actualFinishSuggested, false);
});
