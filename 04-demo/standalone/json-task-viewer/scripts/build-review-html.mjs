#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const reviewRoot = path.resolve(__dirname, "..");
const defaultInput = path.join(reviewRoot, "input", "固定资源最小工期结果.json");
const defaultOutput = path.join(reviewRoot, "output", "固定资源最小工期结果可视化.html");

const inputPath = resolvePath(process.argv[2], defaultInput);
const outputPath = resolvePath(process.argv[3], defaultOutput);

const source = JSON.parse(readFileSync(inputPath, "utf8"));
const review = buildReview(source, inputPath);
const html = renderHtml(review);

mkdirSync(path.dirname(outputPath), { recursive: true });
writeFileSync(outputPath, html, "utf8");

console.log(`Generated: ${outputPath}`);
console.log(
  `Summary: ${display(review.summary.solveStatus)}, ${display(review.summary.objectiveDays)} days, `
    + `${review.summary.taskCount} tasks, ${review.summary.resourceAllocationCount} allocations, `
    + `${review.summary.resourceCount} resources`,
);

function resolvePath(value, fallback) {
  if (!value) return fallback;
  return path.isAbsolute(value) ? value : path.resolve(process.cwd(), value);
}

function buildReview(sourceJson, sourcePath) {
  const root = isRecord(sourceJson) ? sourceJson : {};
  const data = isRecord(root.data) ? root.data : root;
  const rawTasks = arrayValue(data.tasks);
  const tasks = rawTasks.map(normalizeTask).sort(compareTaskSchedule);
  const taskById = new Map(tasks.map((task) => [task.taskId, task]).filter(([taskId]) => taskId));
  const allocations = arrayValue(data.resourceAllocations)
    .map((allocation, index) => normalizeAllocation(allocation, index, taskById))
    .sort(compareAllocationSchedule);
  const milestones = arrayValue(data.milestones).map(normalizeMilestone);
  const diagnostics = arrayValue(data.diagnostics).map(normalizeDiagnostic);
  const resourceRecommendations = arrayValue(data.resourceRecommendations).map((item, index) => ({
    index: index + 1,
    value: displayUnknown(item),
  }));
  const resourceGroups = buildResourceGroups(allocations);
  const ganttGroups = buildGanttGroups(tasks);
  const timelineDays = Math.max(
    1,
    numberOrNull(data.objectiveDays) ?? 0,
    maxNumber(tasks.map((task) => task.endOffsetDays)) ?? 0,
    maxNumber(allocations.map((allocation) => allocation.endOffsetDays)) ?? 0,
  );
  const derivedPlanStartDate = minString(tasks.map((task) => task.startDate));
  const derivedPlanLastTaskEndDate = maxString(tasks.map((task) => task.endDate));
  const checks = buildCompletenessChecks({
    root,
    data,
    tasks,
    allocations,
    milestones,
    diagnostics,
    resourceRecommendations,
  });

  return {
    source: {
      inputPath: sourcePath,
      generatedAt: new Date().toISOString(),
      topLevelKeys: Object.keys(root),
      dataKeys: Object.keys(data),
      code: root.code ?? null,
      message: root.message ?? null,
    },
    summary: {
      solveStatus: data.solveStatus ?? null,
      objectiveDays: numberOrNull(data.objectiveDays),
      planFinishDate: stringOrNull(data.planFinishDate),
      derivedPlanStartDate,
      derivedPlanLastTaskEndDate,
      taskCount: tasks.length,
      resourceAllocationCount: allocations.length,
      resourceCount: resourceGroups.length,
      milestoneCount: milestones.length,
      diagnosticCount: diagnostics.length,
      resourceRecommendationCount: resourceRecommendations.length,
      unconstrainedTaskCount: tasks.filter((task) => task.unconstrained === true).length,
      noResourceTaskCount: tasks.filter((task) => !task.assignedResourceId).length,
      timelineDays,
    },
    tasks,
    allocations,
    milestones,
    diagnostics,
    resourceRecommendations,
    resourceGroups,
    ganttGroups,
    checks,
  };
}

function normalizeTask(task, index) {
  const record = isRecord(task) ? task : {};
  const taskId = stringOrNull(record.taskId) ?? `row-${index + 1}`;
  const taskName = stringOrNull(record.taskName) ?? taskId;
  const startOffsetDays = numberOrNull(record.startOffsetDays);
  const endOffsetDays = numberOrNull(record.endOffsetDays);
  const durationDays = startOffsetDays !== null && endOffsetDays !== null ? endOffsetDays - startOffsetDays : null;
  const assignedResourceId = stringOrNull(record.assignedResourceId);
  const assignedResourceLabel = stringOrNull(record.assignedResourceLabel);
  return {
    index: index + 1,
    taskId,
    taskName,
    workPointId: stringOrNull(record.workPointId),
    startOffsetDays,
    endOffsetDays,
    startDate: stringOrNull(record.startDate),
    endDate: stringOrNull(record.endDate),
    assignedResourceId,
    assignedResourceLabel,
    unconstrained: booleanOrNull(record.unconstrained),
    durationDays,
    derivedGroup: taskNameGroup(taskName),
    missingOffsets: startOffsetDays === null || endOffsetDays === null,
    missingDates: !stringOrNull(record.startDate) || !stringOrNull(record.endDate),
    invalidOffsets: startOffsetDays !== null && endOffsetDays !== null && endOffsetDays < startOffsetDays,
  };
}

function normalizeAllocation(allocation, index, taskById) {
  const record = isRecord(allocation) ? allocation : {};
  const taskId = stringOrNull(record.taskId);
  const task = taskId ? taskById.get(taskId) : null;
  const startOffsetDays = numberOrNull(record.startOffsetDays);
  const endOffsetDays = numberOrNull(record.endOffsetDays);
  const resourceId = stringOrNull(record.resourceId);
  const resourceLabel = stringOrNull(record.resourceLabel) ?? resourceId ?? "JSON 未提供资源";
  return {
    index: index + 1,
    resourceId,
    resourceLabel,
    resourceKey: resourceId ?? resourceLabel,
    taskId,
    taskName: stringOrNull(record.taskName) ?? task?.taskName ?? taskId ?? `allocation-${index + 1}`,
    startOffsetDays,
    endOffsetDays,
    startDateFromTask: task?.startDate ?? null,
    endDateFromTask: task?.endDate ?? null,
    matchedTask: Boolean(task),
    durationDays: startOffsetDays !== null && endOffsetDays !== null ? endOffsetDays - startOffsetDays : null,
    missingOffsets: startOffsetDays === null || endOffsetDays === null,
    invalidOffsets: startOffsetDays !== null && endOffsetDays !== null && endOffsetDays < startOffsetDays,
  };
}

function normalizeMilestone(milestone, index) {
  const record = isRecord(milestone) ? milestone : {};
  return {
    index: index + 1,
    milestoneId: stringOrNull(record.milestoneId),
    workPointId: stringOrNull(record.workPointId),
    name: stringOrNull(record.name),
    targetDate: stringOrNull(record.targetDate),
    actualFinishDate: stringOrNull(record.actualFinishDate),
    delayDays: numberOrNull(record.delayDays),
    status: stringOrNull(record.status),
  };
}

function normalizeDiagnostic(diagnostic, index) {
  if (typeof diagnostic === "string") {
    return { index: index + 1, level: "info", message: diagnostic };
  }
  const record = isRecord(diagnostic) ? diagnostic : {};
  return {
    index: index + 1,
    level: stringOrNull(record.level) ?? "info",
    message: stringOrNull(record.message) ?? displayUnknown(diagnostic),
  };
}

function buildResourceGroups(allocations) {
  const groups = new Map();
  for (const allocation of allocations) {
    const key = allocation.resourceKey;
    const group = groups.get(key) ?? {
      resourceKey: key,
      resourceId: allocation.resourceId,
      resourceLabel: allocation.resourceLabel,
      taskCount: 0,
      firstStartOffsetDays: allocation.startOffsetDays,
      lastEndOffsetDays: allocation.endOffsetDays,
      allocations: [],
    };
    group.taskCount += 1;
    group.firstStartOffsetDays = minNullableNumber(group.firstStartOffsetDays, allocation.startOffsetDays);
    group.lastEndOffsetDays = maxNullableNumber(group.lastEndOffsetDays, allocation.endOffsetDays);
    group.allocations.push(allocation);
    groups.set(key, group);
  }
  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      allocations: group.allocations.sort(compareAllocationSchedule),
    }))
    .sort((left, right) =>
      (left.firstStartOffsetDays ?? 999999) - (right.firstStartOffsetDays ?? 999999)
      || left.resourceLabel.localeCompare(right.resourceLabel, "zh-CN"),
    );
}

function buildGanttGroups(tasks) {
  const groups = new Map();
  for (const task of tasks) {
    const group = groups.get(task.derivedGroup) ?? {
      id: task.derivedGroup,
      title: task.derivedGroup,
      taskCount: 0,
      firstStartOffsetDays: task.startOffsetDays,
      lastEndOffsetDays: task.endOffsetDays,
      firstStartDate: task.startDate,
      lastEndDate: task.endDate,
      tasks: [],
    };
    group.taskCount += 1;
    group.firstStartOffsetDays = minNullableNumber(group.firstStartOffsetDays, task.startOffsetDays);
    group.lastEndOffsetDays = maxNullableNumber(group.lastEndOffsetDays, task.endOffsetDays);
    group.firstStartDate = minNullableString(group.firstStartDate, task.startDate);
    group.lastEndDate = maxNullableString(group.lastEndDate, task.endDate);
    group.tasks.push(task);
    groups.set(task.derivedGroup, group);
  }
  return Array.from(groups.values())
    .map((group) => ({ ...group, tasks: group.tasks.sort(compareTaskSchedule) }))
    .sort((left, right) =>
      (left.firstStartOffsetDays ?? 999999) - (right.firstStartOffsetDays ?? 999999)
      || left.title.localeCompare(right.title, "zh-CN"),
    );
}

function buildCompletenessChecks({
  root,
  data,
  tasks,
  allocations,
  milestones,
  diagnostics,
  resourceRecommendations,
}) {
  const taskIds = new Set(tasks.map((task) => task.taskId).filter(Boolean));
  const duplicateTaskIds = duplicates(tasks.map((task) => task.taskId).filter(Boolean));
  const unmatchedAllocations = allocations.filter((allocation) => allocation.taskId && !taskIds.has(allocation.taskId));
  const noResourceTasks = tasks.filter((task) => !task.assignedResourceId || task.unconstrained === true);
  const missingTaskOffsets = tasks.filter((task) => task.missingOffsets);
  const invalidTaskOffsets = tasks.filter((task) => task.invalidOffsets);
  const missingTaskDates = tasks.filter((task) => task.missingDates);
  const missingAllocationOffsets = allocations.filter((allocation) => allocation.missingOffsets);
  const invalidAllocationOffsets = allocations.filter((allocation) => allocation.invalidOffsets);
  const taskAllocationsByTaskId = groupCount(allocations, (allocation) => allocation.taskId ?? "");
  const allocatedTasksWithoutResourceId = tasks.filter((task) => task.assignedResourceId && !taskAllocationsByTaskId[task.taskId]);

  return [
    checkItem("顶层结构", Object.prototype.hasOwnProperty.call(root, "data") ? "ok" : "warn", "发现 data 节点", "未发现 data 节点，已按根对象兜底读取。"),
    checkItem("返回码", root.code === 0 ? "ok" : "warn", `code=${display(root.code)}，message=${display(root.message)}`, `code=${display(root.code)}，message=${display(root.message)}`),
    checkItem("任务数组", tasks.length > 0 ? "ok" : "error", `tasks[] 共 ${tasks.length} 条。`, "tasks[] 为空或缺失。"),
    checkItem("任务 ID", duplicateTaskIds.length ? "warn" : "ok", "未发现重复 taskId。", `发现 ${duplicateTaskIds.length} 个重复 taskId。`, duplicateTaskIds.slice(0, 20)),
    checkItem("资源分配数组", allocations.length > 0 ? "ok" : "warn", `resourceAllocations[] 共 ${allocations.length} 条。`, "resourceAllocations[] 为空或缺失。"),
    checkItem("资源分配匹配", unmatchedAllocations.length ? "error" : "ok", "所有带 taskId 的资源分配均可匹配 tasks[]。", `${unmatchedAllocations.length} 条资源分配未匹配到 tasks[]。`, unmatchedAllocations.map((item) => `${item.resourceLabel} / ${display(item.taskId)}`).slice(0, 20)),
    checkItem("任务资源字段", noResourceTasks.length ? "warn" : "ok", "所有任务都提供 assignedResourceId 且未标记 unconstrained。", `${noResourceTasks.length} 条任务未提供 assignedResourceId 或标记 unconstrained。`, noResourceTasks.map((task) => task.taskName).slice(0, 20)),
    checkItem("任务偏移字段", missingTaskOffsets.length || invalidTaskOffsets.length ? "warn" : "ok", "所有任务偏移字段完整且未倒挂。", `缺失偏移 ${missingTaskOffsets.length} 条，结束早于开始 ${invalidTaskOffsets.length} 条。`),
    checkItem("任务日期字段", missingTaskDates.length ? "warn" : "ok", "所有任务提供 startDate/endDate。", `${missingTaskDates.length} 条任务缺少 startDate 或 endDate。`),
    checkItem("资源分配偏移", missingAllocationOffsets.length || invalidAllocationOffsets.length ? "warn" : "ok", "所有资源分配偏移字段完整且未倒挂。", `缺失偏移 ${missingAllocationOffsets.length} 条，结束早于开始 ${invalidAllocationOffsets.length} 条。`),
    checkItem("任务与分配覆盖", allocatedTasksWithoutResourceId.length ? "warn" : "ok", "带 assignedResourceId 的任务均可在 resourceAllocations[] 找到记录。", `${allocatedTasksWithoutResourceId.length} 条带 assignedResourceId 的任务未在 resourceAllocations[] 出现。`, allocatedTasksWithoutResourceId.map((task) => task.taskName).slice(0, 20)),
    checkItem("里程碑", milestones.length ? "ok" : "warn", `milestones[] 共 ${milestones.length} 条。`, "milestones[] 为空或缺失。"),
    checkItem("诊断信息", diagnostics.length ? "ok" : "warn", `diagnostics[] 共 ${diagnostics.length} 条。`, "diagnostics[] 为空或缺失。"),
    checkItem("资源建议", resourceRecommendations.length ? "ok" : "warn", `resourceRecommendations[] 共 ${resourceRecommendations.length} 条。`, "resourceRecommendations[] 为空。"),
    checkItem("字段范围", "info", `data 字段：${Object.keys(data).join(", ") || "JSON 未提供"}`, ""),
  ];
}

function checkItem(title, tone, okMessage, issueMessage, details = []) {
  return {
    title,
    tone,
    message: tone === "ok" || tone === "info" ? okMessage : issueMessage,
    details,
  };
}

function renderHtml(review) {
  const dataJson = safeJson(review);
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>固定资源最小工期结果可视化</title>
  <style>
    :root {
      color-scheme: light;
      font-family: "Segoe UI", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      color: #18212f;
      background: #eef2f6;
      font-synthesis: none;
      text-rendering: optimizeLegibility;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-width: 320px;
      min-height: 100vh;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.86), rgba(238,242,246,0.96) 240px),
        #eef2f6;
    }

    button, input { font: inherit; }

    .shell {
      width: min(1680px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 18px 0 28px;
      display: grid;
      gap: 14px;
    }

    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      margin: 0 -16px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      background: rgba(238, 242, 246, 0.92);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(203, 213, 225, 0.72);
    }

    .brand {
      min-width: 0;
      display: grid;
      gap: 3px;
    }

    h1, h2, h3, p { margin: 0; }

    h1 {
      font-size: 22px;
      line-height: 1.25;
      letter-spacing: 0;
      color: #102033;
    }

    h2 {
      font-size: 16px;
      line-height: 1.3;
      letter-spacing: 0;
      color: #102033;
    }

    .muted {
      color: #64748b;
      font-size: 12px;
      line-height: 1.45;
    }

    .source-line {
      min-width: 0;
      max-width: 100%;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .nav {
      flex: 0 0 auto;
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 6px;
    }

    .nav a {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 5px 9px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      background: #fff;
      color: #24364b;
      text-decoration: none;
      font-size: 12px;
      font-weight: 650;
    }

    .notice {
      padding: 10px 12px;
      border: 1px solid #bae6fd;
      border-radius: 8px;
      background: #f0f9ff;
      color: #0c4a6e;
      font-size: 13px;
      line-height: 1.5;
    }

    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }

    .metric {
      min-height: 76px;
      padding: 12px 13px;
      border: 1px solid #dbe4ed;
      border-radius: 8px;
      background: #fff;
      display: grid;
      align-content: center;
      gap: 4px;
    }

    .metric span {
      color: #64748b;
      font-size: 12px;
      line-height: 1.35;
    }

    .metric strong {
      color: #102033;
      font-size: 20px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }

    .panel {
      background: #fff;
      border: 1px solid #dbe4ed;
      border-radius: 8px;
      overflow: hidden;
    }

    .panel-title {
      min-height: 54px;
      padding: 12px 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      border-bottom: 1px solid #edf2f7;
      background: #fbfdff;
    }

    .panel-title > div:first-child {
      min-width: 0;
      display: grid;
      gap: 3px;
    }

    .panel-body {
      padding: 12px 14px 14px;
    }

    .two-column {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 0.55fr);
      gap: 12px;
      align-items: start;
    }

    .check-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .check {
      min-height: 48px;
      padding: 9px 10px;
      border: 1px solid #dbe4ed;
      border-radius: 7px;
      background: #f8fafc;
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
    }

    .check-title {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #334155;
      font-size: 12px;
      font-weight: 750;
      line-height: 1.4;
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: #64748b;
    }

    .check.ok .dot { background: #16a34a; }
    .check.warn .dot { background: #d97706; }
    .check.error .dot { background: #dc2626; }
    .check.info .dot { background: #2563eb; }

    .check.ok { background: #f0fdf4; border-color: #bbf7d0; }
    .check.warn { background: #fffbeb; border-color: #fde68a; }
    .check.error { background: #fff1f2; border-color: #fecdd3; }
    .check.info { background: #eff6ff; border-color: #bfdbfe; }

    .check-message {
      min-width: 0;
      color: #334155;
      font-size: 12px;
      line-height: 1.5;
      overflow-wrap: anywhere;
    }

    .detail-list {
      margin-top: 5px;
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      max-width: 100%;
      padding: 3px 7px;
      border-radius: 6px;
      background: #eef2f7;
      color: #344256;
      font-size: 12px;
      font-weight: 650;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .diagnostics {
      display: grid;
      gap: 7px;
    }

    .diagnostic {
      padding: 9px 10px;
      border: 1px solid #dbe4ed;
      border-radius: 7px;
      background: #f8fafc;
      color: #334155;
      font-size: 13px;
      line-height: 1.45;
    }

    .diagnostic.info { background: #eff6ff; border-color: #bfdbfe; color: #1e3a8a; }
    .diagnostic.warning, .diagnostic.warn { background: #fffbeb; border-color: #fde68a; color: #854d0e; }
    .diagnostic.error { background: #fff1f2; border-color: #fecdd3; color: #9f1239; }

    .table-wrap {
      overflow: auto;
      max-height: 560px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }

    th, td {
      padding: 8px 9px;
      border-bottom: 1px solid #e5edf5;
      text-align: left;
      vertical-align: top;
      white-space: nowrap;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 3;
      background: #f8fafc;
      color: #475569;
      font-weight: 750;
    }

    tbody tr:nth-child(odd) td { background: #fbfdff; }
    tbody tr:hover td { background: #f3f8ff; }

    .plan-table { min-width: 1380px; }
    .milestone-table { min-width: 900px; }

    code {
      color: #475569;
      font-family: Consolas, "Cascadia Mono", monospace;
      font-size: 12px;
    }

    .empty {
      padding: 18px 14px;
      color: #64748b;
      font-size: 13px;
      text-align: center;
    }

    .chart-scroll {
      overflow: auto;
      padding: 12px 14px 16px;
    }

    .gantt,
    .lanes,
    .paths {
      display: grid;
      gap: 7px;
      min-width: 980px;
    }

    .chart-group {
      display: grid;
      gap: 4px;
    }

    .chart-group-title {
      position: sticky;
      left: 0;
      z-index: 2;
      min-height: 28px;
      padding: 5px 8px;
      border: 1px solid #dbe4ed;
      border-radius: 6px;
      background: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      color: #203248;
      font-size: 12px;
      font-weight: 750;
    }

    .gantt-row,
    .lane-row,
    .path-row {
      display: grid;
      grid-template-columns: 260px minmax(720px, 1fr);
      align-items: center;
      gap: 10px;
      min-height: 28px;
    }

    .row-label {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #24364b;
      font-size: 12px;
      font-weight: 650;
    }

    .row-label small {
      margin-left: 6px;
      color: #64748b;
      font-weight: 600;
    }

    .track {
      position: relative;
      height: 24px;
      border-radius: 5px;
      overflow: hidden;
      background:
        repeating-linear-gradient(
          90deg,
          #f8fafc 0,
          #f8fafc calc(10% - 1px),
          #e2e8f0 calc(10% - 1px),
          #e2e8f0 10%
        );
      border: 1px solid #e2e8f0;
    }

    .bar {
      position: absolute;
      top: 3px;
      height: 16px;
      min-width: 6px;
      border-radius: 4px;
      color: #fff;
      box-shadow: 0 1px 4px rgba(15, 23, 42, 0.16);
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      font-size: 11px;
      font-weight: 750;
      line-height: 16px;
      padding: 0 5px;
    }

    .bar.no-time {
      left: 0;
      width: 100%;
      background: repeating-linear-gradient(45deg, #94a3b8, #94a3b8 7px, #64748b 7px, #64748b 14px);
    }

    .path-row {
      min-height: 34px;
      align-items: start;
    }

    .path-sequence {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 0;
      overflow-x: auto;
      padding-bottom: 2px;
      white-space: nowrap;
    }

    .path-step {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      max-width: 240px;
      padding: 4px 8px;
      border-radius: 6px;
      border: 1px solid #dbe4ed;
      background: #f8fafc;
      color: #203248;
      font-size: 12px;
      font-weight: 650;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .path-step:not(:last-child)::after {
      content: ">";
      padding-left: 8px;
      color: #94a3b8;
      font-weight: 750;
    }

    .raw-keys {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }

    @media (max-width: 980px) {
      .shell { width: min(100vw - 18px, 1680px); }
      .topbar { position: static; display: grid; }
      .nav { justify-content: start; }
      .metrics, .check-grid, .two-column { grid-template-columns: 1fr; }
      .panel-title { display: grid; justify-content: stretch; }
      .gantt-row, .lane-row, .path-row { grid-template-columns: 220px minmax(640px, 1fr); }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="topbar">
      <div class="brand">
        <h1>固定资源最小工期结果可视化</h1>
        <span class="muted source-line" id="source-line"></span>
      </div>
      <nav class="nav" aria-label="页面导航">
        <a href="#summary">整体工期</a>
        <a href="#plan">计划表</a>
        <a href="#gantt">甘特图</a>
        <a href="#lanes">资源泳道</a>
        <a href="#paths">资源路径</a>
      </nav>
    </header>

    <section class="notice">
      页面为只读审查快照；展示字段来自输入 JSON，分组、计数、条形宽度和资源路径顺序均由页面按 JSON 字段派生。
    </section>

    <section id="summary" class="metrics" aria-label="整体工期结果"></section>

    <section class="panel" id="checks">
      <div class="panel-title">
        <div>
          <h2>完整性审查</h2>
          <span class="muted">检查任务、资源分配、里程碑、诊断和资源建议的 JSON 覆盖情况</span>
        </div>
      </div>
      <div class="panel-body">
        <div class="check-grid" id="check-grid"></div>
      </div>
    </section>

    <section class="two-column">
      <section class="panel">
        <div class="panel-title">
          <div>
            <h2>诊断信息</h2>
            <span class="muted">直接展示 diagnostics[]</span>
          </div>
        </div>
        <div class="panel-body diagnostics" id="diagnostics"></div>
      </section>
      <section class="panel">
        <div class="panel-title">
          <div>
            <h2>JSON 字段</h2>
            <span class="muted">顶层和 data 字段清单</span>
          </div>
        </div>
        <div class="panel-body">
          <h3 class="muted">Top level</h3>
          <div class="raw-keys" id="top-keys"></div>
          <h3 class="muted" style="margin-top: 12px;">data</h3>
          <div class="raw-keys" id="data-keys"></div>
        </div>
      </section>
    </section>

    <section class="panel" id="milestones">
      <div class="panel-title">
        <div>
          <h2>里程碑与资源建议</h2>
          <span class="muted">直接展示 milestones[] 和 resourceRecommendations[]</span>
        </div>
      </div>
      <div class="panel-body" id="milestone-body"></div>
    </section>

    <section class="panel" id="plan">
      <div class="panel-title">
        <div>
          <h2>计划表</h2>
          <span class="muted">列值来自 tasks[]；工期列由 startOffsetDays/endOffsetDays 派生</span>
        </div>
      </div>
      <div class="table-wrap">
        <table class="plan-table">
          <thead>
            <tr>
              <th>序号</th>
              <th>taskId</th>
              <th>taskName</th>
              <th>workPointId</th>
              <th>startOffsetDays</th>
              <th>endOffsetDays</th>
              <th>工期(派生)</th>
              <th>startDate</th>
              <th>endDate</th>
              <th>assignedResourceId</th>
              <th>assignedResourceLabel</th>
              <th>unconstrained</th>
              <th>甘特分组(派生)</th>
            </tr>
          </thead>
          <tbody id="plan-rows"></tbody>
        </table>
      </div>
    </section>

    <section class="panel" id="gantt">
      <div class="panel-title">
        <div>
          <h2>甘特图</h2>
          <span class="muted">横轴按偏移天数；分组由 taskName 首段派生</span>
        </div>
        <span class="muted" id="timeline-label"></span>
      </div>
      <div class="chart-scroll">
        <div class="gantt" id="gantt-chart"></div>
      </div>
    </section>

    <section class="panel" id="lanes">
      <div class="panel-title">
        <div>
          <h2>资源泳道</h2>
          <span class="muted">横轴按 resourceAllocations[] 的 startOffsetDays/endOffsetDays 展示</span>
        </div>
      </div>
      <div class="chart-scroll">
        <div class="lanes" id="resource-lanes"></div>
      </div>
    </section>

    <section class="panel" id="paths">
      <div class="panel-title">
        <div>
          <h2>资源路径图</h2>
          <span class="muted">按资源分组后，以 startOffsetDays 排序展示 taskName 序列；不推断施工位置</span>
        </div>
      </div>
      <div class="chart-scroll">
        <div class="paths" id="resource-paths"></div>
      </div>
    </section>
  </main>

  <script id="review-data" type="application/json">${dataJson}</script>
  <script>
    (() => {
      const data = JSON.parse(document.getElementById("review-data").textContent);
      const palette = ["#0f766e", "#2563eb", "#b45309", "#7c3aed", "#be123c", "#15803d", "#0891b2", "#a16207", "#4f46e5", "#c2410c"];
      const groupColor = new Map();

      function byId(id) {
        return document.getElementById(id);
      }

      function text(value) {
        if (value === null || value === undefined || value === "") return "JSON 未提供";
        if (typeof value === "boolean") return value ? "true" : "false";
        return String(value);
      }

      function html(value) {
        return text(value)
          .replaceAll("&", "&amp;")
          .replaceAll("<", "&lt;")
          .replaceAll(">", "&gt;")
          .replaceAll('"', "&quot;")
          .replaceAll("'", "&#39;");
      }

      function percent(start, end) {
        if (typeof start !== "number" || typeof end !== "number") return { left: 0, width: 100, noTime: true };
        const timeline = Math.max(1, data.summary.timelineDays || 1);
        return {
          left: Math.max(0, Math.min(100, (start / timeline) * 100)),
          width: Math.max(0.8, Math.min(100, ((end - start) / timeline) * 100)),
          noTime: false,
        };
      }

      function colorFor(key) {
        if (!groupColor.has(key)) {
          groupColor.set(key, palette[groupColor.size % palette.length]);
        }
        return groupColor.get(key);
      }

      function renderMetric(label, value, hint) {
        return '<article class="metric"><span>' + html(label) + '</span><strong>' + html(value) + '</strong>' + (hint ? '<span>' + html(hint) + '</span>' : "") + '</article>';
      }

      function renderSummary() {
        byId("source-line").textContent = data.source.inputPath;
        byId("summary").innerHTML = [
          renderMetric("求解状态", data.summary.solveStatus, "data.solveStatus"),
          renderMetric("总工期", data.summary.objectiveDays === null ? null : data.summary.objectiveDays + " 天", "data.objectiveDays"),
          renderMetric("计划完工日", data.summary.planFinishDate, "data.planFinishDate"),
          renderMetric("最早任务开始", data.summary.derivedPlanStartDate, "由 tasks[].startDate 派生"),
          renderMetric("任务数", data.summary.taskCount + " 项", "tasks[]"),
          renderMetric("资源分配", data.summary.resourceAllocationCount + " 条", "resourceAllocations[]"),
          renderMetric("资源数量", data.summary.resourceCount + " 个", "由 resourceAllocations[].resourceId 派生"),
          renderMetric("里程碑 / 诊断", data.summary.milestoneCount + " / " + data.summary.diagnosticCount, "milestones[] / diagnostics[]"),
        ].join("");
        byId("timeline-label").textContent = "横轴 0-" + text(data.summary.timelineDays) + " 天";
      }

      function renderChecks() {
        byId("check-grid").innerHTML = data.checks.map((item) => {
          const details = Array.isArray(item.details) && item.details.length
            ? '<div class="detail-list">' + item.details.map((detail) => '<span class="pill" title="' + html(detail) + '">' + html(detail) + '</span>').join("") + '</div>'
            : "";
          return '<article class="check ' + html(item.tone) + '">'
            + '<span class="check-title"><span class="dot"></span>' + html(item.title) + '</span>'
            + '<span class="check-message">' + html(item.message) + details + '</span>'
            + '</article>';
        }).join("");
      }

      function renderDiagnostics() {
        byId("diagnostics").innerHTML = data.diagnostics.length
          ? data.diagnostics.map((item) => '<div class="diagnostic ' + html(item.level) + '">' + html(item.message) + '</div>').join("")
          : '<div class="empty">JSON 中 diagnostics[] 为空</div>';
      }

      function renderKeys() {
        byId("top-keys").innerHTML = data.source.topLevelKeys.map((key) => '<span class="pill">' + html(key) + '</span>').join("") || '<span class="muted">JSON 未提供</span>';
        byId("data-keys").innerHTML = data.source.dataKeys.map((key) => '<span class="pill">' + html(key) + '</span>').join("") || '<span class="muted">JSON 未提供</span>';
      }

      function renderMilestones() {
        const milestoneTable = data.milestones.length
          ? '<div class="table-wrap"><table class="milestone-table"><thead><tr><th>milestoneId</th><th>workPointId</th><th>name</th><th>targetDate</th><th>actualFinishDate</th><th>delayDays</th><th>status</th></tr></thead><tbody>'
            + data.milestones.map((item) => '<tr><td><code>' + html(item.milestoneId) + '</code></td><td>' + html(item.workPointId) + '</td><td>' + html(item.name) + '</td><td>' + html(item.targetDate) + '</td><td>' + html(item.actualFinishDate) + '</td><td>' + html(item.delayDays) + '</td><td>' + html(item.status) + '</td></tr>').join("")
            + '</tbody></table></div>'
          : '<div class="empty">JSON 中 milestones[] 为空</div>';
        const recommendations = data.resourceRecommendations.length
          ? '<div class="detail-list" style="margin-top: 12px;">' + data.resourceRecommendations.map((item) => '<span class="pill">' + html(item.value) + '</span>').join("") + '</div>'
          : '<div class="notice" style="margin-top: 12px;">JSON 中 resourceRecommendations[] 为空。</div>';
        byId("milestone-body").innerHTML = milestoneTable + recommendations;
      }

      function renderPlanRows() {
        byId("plan-rows").innerHTML = data.tasks.map((task) => {
          return '<tr>'
            + '<td>' + html(task.index) + '</td>'
            + '<td><code>' + html(task.taskId) + '</code></td>'
            + '<td>' + html(task.taskName) + '</td>'
            + '<td>' + html(task.workPointId) + '</td>'
            + '<td>' + html(task.startOffsetDays) + '</td>'
            + '<td>' + html(task.endOffsetDays) + '</td>'
            + '<td>' + html(task.durationDays === null ? null : task.durationDays + " 天") + '</td>'
            + '<td>' + html(task.startDate) + '</td>'
            + '<td>' + html(task.endDate) + '</td>'
            + '<td><code>' + html(task.assignedResourceId) + '</code></td>'
            + '<td>' + html(task.assignedResourceLabel) + '</td>'
            + '<td>' + html(task.unconstrained) + '</td>'
            + '<td><span class="pill">' + html(task.derivedGroup) + '</span></td>'
            + '</tr>';
        }).join("");
      }

      function renderGantt() {
        byId("gantt-chart").innerHTML = data.ganttGroups.length
          ? data.ganttGroups.map((group) => {
            const rows = group.tasks.map((task) => {
              const position = percent(task.startOffsetDays, task.endOffsetDays);
              const style = position.noTime
                ? ""
                : 'left:' + position.left.toFixed(3) + '%;width:' + position.width.toFixed(3) + '%;background:' + colorFor(group.title) + ';';
              const title = [
                "taskId: " + text(task.taskId),
                "taskName: " + text(task.taskName),
                "计划: " + text(task.startDate) + " 至 " + text(task.endDate),
                "偏移: " + text(task.startOffsetDays) + " 至 " + text(task.endOffsetDays),
                "资源: " + text(task.assignedResourceLabel),
              ].join("\\n");
              return '<div class="gantt-row">'
                + '<div class="row-label" title="' + html(task.taskName) + '">' + html(task.taskName) + '<small>' + html(task.durationDays === null ? "" : task.durationDays + "d") + '</small></div>'
                + '<div class="track"><div class="bar ' + (position.noTime ? "no-time" : "") + '" style="' + html(style) + '" title="' + html(title) + '">' + html(task.durationDays === null ? "" : task.durationDays + "d") + '</div></div>'
                + '</div>';
            }).join("");
            return '<div class="chart-group">'
              + '<div class="chart-group-title"><strong>' + html(group.title) + '</strong><span>' + html(text(group.firstStartDate) + " 至 " + text(group.lastEndDate) + " / " + group.taskCount + "项") + '</span></div>'
              + rows
              + '</div>';
          }).join("")
          : '<div class="empty">JSON 中 tasks[] 为空</div>';
      }

      function renderResourceLanes() {
        byId("resource-lanes").innerHTML = data.resourceGroups.length
          ? data.resourceGroups.map((group) => {
            const bars = group.allocations.map((allocation) => {
              const position = percent(allocation.startOffsetDays, allocation.endOffsetDays);
              const style = position.noTime
                ? ""
                : 'left:' + position.left.toFixed(3) + '%;width:' + position.width.toFixed(3) + '%;background:' + colorFor(group.resourceKey) + ';';
              const title = [
                "resourceId: " + text(allocation.resourceId),
                "resourceLabel: " + text(allocation.resourceLabel),
                "taskId: " + text(allocation.taskId),
                "taskName: " + text(allocation.taskName),
                "偏移: " + text(allocation.startOffsetDays) + " 至 " + text(allocation.endOffsetDays),
                "日期: " + text(allocation.startDateFromTask) + " 至 " + text(allocation.endDateFromTask) + "（由 taskId 关联 tasks[]）",
              ].join("\\n");
              return '<div class="bar ' + (position.noTime ? "no-time" : "") + '" style="' + html(style) + '" title="' + html(title) + '">' + html(allocation.taskName) + '</div>';
            }).join("");
            return '<div class="lane-row">'
              + '<div class="row-label" title="' + html(group.resourceLabel) + '">' + html(group.resourceLabel) + '<small>' + html(group.taskCount + "项") + '</small></div>'
              + '<div class="track">' + bars + '</div>'
              + '</div>';
          }).join("")
          : '<div class="empty">JSON 中 resourceAllocations[] 为空</div>';
      }

      function renderResourcePaths() {
        byId("resource-paths").innerHTML = data.resourceGroups.length
          ? data.resourceGroups.map((group) => {
            const steps = group.allocations.map((allocation) => {
              const title = text(allocation.taskName) + "\\n" + text(allocation.startOffsetDays) + "-" + text(allocation.endOffsetDays) + " 天";
              return '<span class="path-step" title="' + html(title) + '">' + html(allocation.taskName) + '</span>';
            }).join("");
            return '<div class="path-row">'
              + '<div class="row-label" title="' + html(group.resourceLabel) + '">' + html(group.resourceLabel) + '<small>' + html(group.taskCount + "项") + '</small></div>'
              + '<div class="path-sequence">' + steps + '</div>'
              + '</div>';
          }).join("")
          : '<div class="empty">JSON 中 resourceAllocations[] 为空</div>';
      }

      renderSummary();
      renderChecks();
      renderDiagnostics();
      renderKeys();
      renderMilestones();
      renderPlanRows();
      renderGantt();
      renderResourceLanes();
      renderResourcePaths();
    })();
  </script>
</body>
</html>`;
}

function safeJson(value) {
  return JSON.stringify(value)
    .replace(/&/g, "\\u0026")
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

function taskNameGroup(taskName) {
  const name = stringOrNull(taskName) ?? "JSON 未提供 taskName";
  return name.split("-")[0]?.trim() || name;
}

function compareTaskSchedule(left, right) {
  return (left.startOffsetDays ?? 999999) - (right.startOffsetDays ?? 999999)
    || (left.endOffsetDays ?? 999999) - (right.endOffsetDays ?? 999999)
    || left.taskName.localeCompare(right.taskName, "zh-CN")
    || left.index - right.index;
}

function compareAllocationSchedule(left, right) {
  return (left.startOffsetDays ?? 999999) - (right.startOffsetDays ?? 999999)
    || (left.endOffsetDays ?? 999999) - (right.endOffsetDays ?? 999999)
    || left.taskName.localeCompare(right.taskName, "zh-CN")
    || left.index - right.index;
}

function groupCount(items, keyFn) {
  const result = {};
  for (const item of items) {
    const key = keyFn(item);
    if (!key) continue;
    result[key] = (result[key] ?? 0) + 1;
  }
  return result;
}

function duplicates(values) {
  const seen = new Set();
  const repeated = new Set();
  for (const value of values) {
    if (seen.has(value)) {
      repeated.add(value);
    } else {
      seen.add(value);
    }
  }
  return Array.from(repeated);
}

function minString(values) {
  const filtered = values.filter((value) => typeof value === "string" && value.trim());
  return filtered.length ? filtered.sort()[0] : null;
}

function maxString(values) {
  const filtered = values.filter((value) => typeof value === "string" && value.trim());
  return filtered.length ? filtered.sort()[filtered.length - 1] : null;
}

function maxNumber(values) {
  const filtered = values.filter((value) => typeof value === "number" && Number.isFinite(value));
  return filtered.length ? Math.max(...filtered) : null;
}

function minNullableNumber(left, right) {
  if (left === null || left === undefined) return right ?? null;
  if (right === null || right === undefined) return left;
  return Math.min(left, right);
}

function maxNullableNumber(left, right) {
  if (left === null || left === undefined) return right ?? null;
  if (right === null || right === undefined) return left;
  return Math.max(left, right);
}

function minNullableString(left, right) {
  if (!left) return right ?? null;
  if (!right) return left;
  return left <= right ? left : right;
}

function maxNullableString(left, right) {
  if (!left) return right ?? null;
  if (!right) return left;
  return left >= right ? left : right;
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function isRecord(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function numberOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function booleanOrNull(value) {
  if (typeof value === "boolean") return value;
  if (value === "true") return true;
  if (value === "false") return false;
  return null;
}

function display(value) {
  if (value === null || value === undefined || value === "") return "JSON 未提供";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

function displayUnknown(value) {
  if (value === null || value === undefined || value === "") return "JSON 未提供";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
