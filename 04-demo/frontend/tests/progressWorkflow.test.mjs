import assert from "node:assert/strict";
import test from "node:test";

import {
  deriveProgressWorkflowSteps,
  hasUnsavedProgressChanges,
  planControlErrorMessage,
  validateProgressEntry,
} from "../src/features/planControl/progressWorkflow.ts";

const task = {
  id: "task-1",
  name: "1#墩-墩柱",
  structure_id: "pier-1",
  structure_name: "1#墩",
  structure_type: "pier",
  component_type: "pier_body",
  process_name: "爬模施工",
  productivity_rule_id: "rule",
  quantity: 10,
  quantity_label: "10m",
  duration_days: 5,
  compatible_resource_types: [],
  properties: {},
};

const baseEntry = {
  task_id: task.id,
  status: "not_started",
  percent_complete: 0,
  completed_quantity: 0,
  remaining_quantity: 10,
  remaining_days: 5,
  remaining_days_source: "baseline",
  notes: "",
};

test("实际日期晚于状态日期和日期倒置均定位到任务字段", () => {
  const issues = validateProgressEntry({
    ...baseEntry,
    status: "completed",
    percent_complete: 100,
    completed_quantity: 10,
    remaining_quantity: 0,
    actual_start_date: "2026-07-14",
    actual_finish_date: "2026-07-13",
  }, task, "2026-07-13");
  assert.ok(issues.some((item) => item.code === "actual_date_after_status" && item.field === "actual_start_date"));
  assert.ok(issues.some((item) => item.code === "finish_before_start"));
});

test("进行中任务缺少剩余工期依据时阻断", () => {
  const issues = validateProgressEntry({
    ...baseEntry,
    status: "in_progress",
    percent_complete: 40,
    completed_quantity: 4,
    remaining_quantity: 6,
    actual_start_date: "2026-07-10",
  }, task, "2026-07-13");
  assert.ok(issues.some((item) => item.code === "missing_remaining_duration" && item.severity === "error"));
});

test("暂停任务缺少恢复日期可以保存事实但产生警告", () => {
  const issues = validateProgressEntry({
    ...baseEntry,
    status: "paused",
    percent_complete: 40,
    completed_quantity: 4,
    remaining_quantity: 6,
    actual_start_date: "2026-07-10",
    estimated_remaining_days: 6,
    reason: "等待场地",
  }, task, "2026-07-13");
  assert.equal(issues.filter((item) => item.severity === "error").length, 0);
  assert.ok(issues.some((item) => item.code === "missing_resume_date" && item.severity === "warning"));
});

test("已保存快照相同数据不脏，状态日期或任务值变化后变脏", () => {
  const snapshot = {
    progress_snapshot_id: "p1",
    plan_version_id: "plan-1",
    status_date: "2026-07-13",
    revision_no: 1,
    is_current: true,
    entries: [baseEntry],
    data_quality_status: "valid",
    validation_messages: [],
    submitted_by: "计划工程师",
    submitted_at: "2026-07-13T00:00:00Z",
  };
  assert.equal(hasUnsavedProgressChanges({ [task.id]: baseEntry }, snapshot, "2026-07-13"), false);
  assert.equal(hasUnsavedProgressChanges({ [task.id]: { ...baseEntry, notes: "已核查" } }, snapshot, "2026-07-13"), true);
  assert.equal(hasUnsavedProgressChanges({ [task.id]: baseEntry }, snapshot, "2026-07-14"), true);
});

test("三步状态由快照、未保存修改和预测共同推导", () => {
  const noSnapshot = deriveProgressWorkflowSteps({ activePlan: true, snapshot: null, forecast: null, dirty: false, busy: null });
  assert.deepEqual(noSnapshot.map((item) => item.status), ["ready", "blocked", "blocked"]);

  const snapshot = {
    progress_snapshot_id: "p1", plan_version_id: "plan-1", status_date: "2026-07-13", revision_no: 1,
    is_current: true, entries: [], data_quality_status: "valid", validation_messages: [], submitted_by: "计划工程师", submitted_at: "2026-07-13T00:00:00Z",
  };
  const saved = deriveProgressWorkflowSteps({ activePlan: true, snapshot, forecast: null, dirty: false, busy: null });
  assert.deepEqual(saved.map((item) => item.status), ["complete", "ready", "blocked"]);
  const dirty = deriveProgressWorkflowSteps({ activePlan: true, snapshot, forecast: null, dirty: true, busy: null });
  assert.deepEqual(dirty.map((item) => item.status), ["ready", "stale", "blocked"]);

  const failedForecast = {
    forecast_id: "f1",
    progress_snapshot_id: "p1",
    source_plan_version_id: "plan-1",
    status: "failed",
    generated_at: "2026-07-13T00:00:00Z",
  };
  const reloadedFailure = deriveProgressWorkflowSteps({
    activePlan: true,
    snapshot,
    forecast: failedForecast,
    dirty: false,
    busy: null,
  });
  assert.deepEqual(reloadedFailure.map((item) => item.status), ["complete", "failed", "failed"]);
});

test("网络错误提示明确未保存或未重排", () => {
  assert.match(planControlErrorMessage(new TypeError("Failed to fetch"), "save"), /未形成进度快照/);
  assert.match(planControlErrorMessage(new TypeError("Failed to fetch"), "forecast"), /未生成新的关键节点结论/);
});
