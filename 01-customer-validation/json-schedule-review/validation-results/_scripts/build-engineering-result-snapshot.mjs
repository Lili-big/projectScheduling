#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..", "..");
const defaultInput = path.join(root, "customer-materials", "固定资源最小工期结果.v1.json");
const defaultOutputDir = path.join(root, "validation-results");

const inputPath = resolvePath(process.argv[2], defaultInput);
const outputDir = resolvePath(process.argv[3], defaultOutputDir);
const json = JSON.parse(readFileSync(inputPath, "utf8"));
const report = buildReport(json);

mkdirSync(outputDir, { recursive: true });
const reportPath = path.join(outputDir, "固定资源最小工期结果.v1.report.json");
const htmlPath = path.join(outputDir, "固定资源最小工期结果.v1.html");
writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");
writeFileSync(htmlPath, renderHtml(report, inputPath), "utf8");

console.log(`Report: ${reportPath}`);
console.log(`HTML: ${htmlPath}`);
console.log(
  `Summary: ${display(report.solveStatus)}, ${display(report.objectiveDays)} days, ${report.taskCount} tasks, ${report.resourceAllocationCount} allocations`,
);

function resolvePath(value, fallback) {
  if (!value) return fallback;
  return path.isAbsolute(value) ? value : path.resolve(process.cwd(), value);
}

function buildReport(source) {
  const rootObject = isRecord(source) ? source : {};
  const data = isRecord(rootObject.data) ? rootObject.data : rootObject;
  const tasks = arrayValue(data.tasks);
  const allocations = arrayValue(data.resourceAllocations);
  const milestones = arrayValue(data.milestones);
  const diagnostics = arrayValue(data.diagnostics);
  const recommendations = arrayValue(data.resourceRecommendations);
  const taskIds = new Set(tasks.map((task) => stringOrNull(task?.taskId)).filter(Boolean));
  const unmatchedAllocations = allocations.filter((allocation) => {
    const taskId = stringOrNull(allocation?.taskId);
    return taskId && !taskIds.has(taskId);
  });
  const noResourceTasks = tasks.filter((task) => !stringOrNull(task?.assignedResourceId) || task?.unconstrained === true);
  const invalidTaskTime = tasks.filter((task) => {
    const start = numberOrNull(task?.startOffsetDays);
    const end = numberOrNull(task?.endOffsetDays);
    return start !== null && end !== null && end < start;
  });
  const missingTaskTime = tasks.filter(
    (task) => numberOrNull(task?.startOffsetDays) === null || numberOrNull(task?.endOffsetDays) === null,
  );
  const resourcePaths = buildResourcePaths(allocations);

  return {
    sourceFile: inputPath,
    code: rootObject.code ?? null,
    message: rootObject.message ?? null,
    rawDataKeys: Object.keys(data),
    solveStatus: data.solveStatus ?? null,
    objectiveDays: data.objectiveDays ?? null,
    planFinishDate: data.planFinishDate ?? null,
    taskCount: tasks.length,
    resourceAllocationCount: allocations.length,
    milestoneCount: milestones.length,
    diagnosticCount: diagnostics.length,
    resourceRecommendationCount: recommendations.length,
    unmatchedAllocationCount: unmatchedAllocations.length,
    noResourceTaskCount: noResourceTasks.length,
    invalidTaskTimeCount: invalidTaskTime.length,
    missingTaskTimeCount: missingTaskTime.length,
    diagnostics: diagnostics.map(String),
    milestones: milestones.map((milestone) => ({
      milestoneId: milestone?.milestoneId ?? null,
      name: milestone?.name ?? null,
      targetDate: milestone?.targetDate ?? null,
      actualFinishDate: milestone?.actualFinishDate ?? null,
      delayDays: milestone?.delayDays ?? null,
      status: milestone?.status ?? null,
    })),
    resourcePaths,
    sampleTasks: tasks.slice(0, 20).map((task) => ({
      taskId: task?.taskId ?? null,
      taskName: task?.taskName ?? null,
      startOffsetDays: task?.startOffsetDays ?? null,
      endOffsetDays: task?.endOffsetDays ?? null,
      startDate: task?.startDate ?? null,
      endDate: task?.endDate ?? null,
      assignedResourceLabel: task?.assignedResourceLabel ?? null,
      unconstrained: task?.unconstrained ?? null,
    })),
  };
}

function buildResourcePaths(allocations) {
  const groups = new Map();
  for (const allocation of allocations) {
    const key = stringOrNull(allocation?.resourceId) ?? stringOrNull(allocation?.resourceLabel) ?? "JSON 未提供";
    const current = groups.get(key) ?? {
      resourceId: stringOrNull(allocation?.resourceId),
      resourceLabel: stringOrNull(allocation?.resourceLabel) ?? key,
      taskCount: 0,
      tasks: [],
    };
    current.taskCount += 1;
    current.tasks.push({
      taskId: allocation?.taskId ?? null,
      taskName: allocation?.taskName ?? null,
      startOffsetDays: allocation?.startOffsetDays ?? null,
      endOffsetDays: allocation?.endOffsetDays ?? null,
    });
    groups.set(key, current);
  }

  return Array.from(groups.values())
    .map((item) => ({
      ...item,
      tasks: item.tasks.sort((left, right) => (numberOrNull(left.startOffsetDays) ?? 999999) - (numberOrNull(right.startOffsetDays) ?? 999999)),
    }))
    .sort((left, right) => String(left.resourceLabel).localeCompare(String(right.resourceLabel), "zh-CN"));
}

function renderHtml(report, sourcePath) {
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>固定资源最小工期结果 v1</title>
  <style>
    body { margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: #eef2f6; color: #18212f; }
    main { padding: 24px; display: grid; gap: 16px; }
    section { background: #fff; border: 1px solid #dbe4ed; border-radius: 8px; overflow: hidden; }
    h1, h2 { margin: 0; }
    .title { padding: 16px; display: grid; gap: 6px; }
    .title span { color: #64748b; font-size: 12px; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(160px, 1fr)); gap: 12px; }
    .metric { min-height: 74px; padding: 14px; border: 1px solid #dbe4ed; border-radius: 8px; background: #fff; }
    .metric span { display: block; color: #64748b; font-size: 12px; }
    .metric strong { display: block; margin-top: 6px; font-size: 20px; }
    .body { padding: 14px 16px 16px; }
    .check { min-height: 34px; padding: 8px 10px; border: 1px solid #e2e8f0; border-radius: 7px; background: #f8fafc; display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
    .check.warn { background: #fffbeb; border-color: #fde68a; }
    .check.error { background: #fff1f2; border-color: #fecdd3; }
    .check strong { min-width: 120px; color: #475569; font-size: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 12px; }
    th, td { padding: 8px 9px; border-bottom: 1px solid #e2e8f0; text-align: left; white-space: nowrap; }
    th { background: #f8fafc; color: #475569; }
    .path { margin-bottom: 8px; display: grid; grid-template-columns: 180px minmax(0, 1fr); gap: 10px; align-items: center; }
    .steps { display: flex; gap: 6px; overflow-x: auto; white-space: nowrap; }
    .step { padding: 4px 7px; border-radius: 5px; background: #eef6f6; color: #0f766e; font-size: 12px; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <section>
      <div class="title">
        <h1>固定资源最小工期结果 v1</h1>
        <span>${escapeHtml(sourcePath)}</span>
      </div>
    </section>
    <div class="metrics">
      ${metric("状态", report.solveStatus)}
      ${metric("总工期", report.objectiveDays === null ? null : `${report.objectiveDays} 天`)}
      ${metric("完工日期", report.planFinishDate)}
      ${metric("任务/分配", `${report.taskCount} / ${report.resourceAllocationCount}`)}
    </div>
    <section>
      <div class="title"><h2>完整性检查</h2><span>字段只来自 JSON 和展示派生统计</span></div>
      <div class="body">
        ${check("任务", `tasks[] 共 ${report.taskCount} 条。`, report.taskCount ? "" : "error")}
        ${check("资源分配", `resourceAllocations[] 共 ${report.resourceAllocationCount} 条。`, report.resourceAllocationCount ? "" : "warn")}
        ${check("分配匹配", `${report.unmatchedAllocationCount} 条资源分配未匹配到任务。`, report.unmatchedAllocationCount ? "error" : "")}
        ${check("无资源任务", `${report.noResourceTaskCount} 条任务未提供资源或标记 unconstrained。`, report.noResourceTaskCount ? "warn" : "")}
        ${check("时间字段", `缺失 ${report.missingTaskTimeCount} 条，倒挂 ${report.invalidTaskTimeCount} 条。`, report.missingTaskTimeCount || report.invalidTaskTimeCount ? "warn" : "")}
        ${check("里程碑/诊断", `${report.milestoneCount} / ${report.diagnosticCount}`, report.milestoneCount && report.diagnosticCount ? "" : "warn")}
      </div>
    </section>
    <section>
      <div class="title"><h2>计划表样例</h2><span>前 20 条任务</span></div>
      <div class="body">
        <table>
          <thead><tr><th>任务</th><th>开始偏移</th><th>结束偏移</th><th>开始日期</th><th>结束日期</th><th>资源</th><th>不受资源约束</th></tr></thead>
          <tbody>${report.sampleTasks.map((task) => `<tr><td>${escapeHtml(display(task.taskName))}</td><td>${escapeHtml(display(task.startOffsetDays))}</td><td>${escapeHtml(display(task.endOffsetDays))}</td><td>${escapeHtml(display(task.startDate))}</td><td>${escapeHtml(display(task.endDate))}</td><td>${escapeHtml(display(task.assignedResourceLabel))}</td><td>${escapeHtml(display(task.unconstrained))}</td></tr>`).join("")}</tbody>
        </table>
      </div>
    </section>
    <section>
      <div class="title"><h2>资源路径</h2><span>按资源分组并按开始偏移排序</span></div>
      <div class="body">
        ${report.resourcePaths.map((pathItem) => `<div class="path"><strong>${escapeHtml(display(pathItem.resourceLabel))}</strong><div class="steps">${pathItem.tasks.map((task) => `<span class="step">${escapeHtml(display(task.taskName ?? task.taskId))}</span>`).join("")}</div></div>`).join("")}
      </div>
    </section>
  </main>
</body>
</html>`;
}

function metric(label, value) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(display(value))}</strong></div>`;
}

function check(title, message, level) {
  return `<div class="check ${level}"><strong>${escapeHtml(title)}</strong><span>${escapeHtml(message)}</span></div>`;
}

function display(value) {
  if (value === null || value === undefined || value === "") return "JSON 未提供";
  if (typeof value === "boolean") return value ? "是" : "否";
  return String(value);
}

function stringOrNull(value) {
  if (value === null || value === undefined || value === "") return null;
  return String(value);
}

function numberOrNull(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function arrayValue(value) {
  return Array.isArray(value) ? value : [];
}

function isRecord(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
