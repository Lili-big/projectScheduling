#!/usr/bin/env node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const reviewRoot = path.resolve(__dirname, "..");
const defaultInput = path.join(reviewRoot, "input", "第一版本.json");
const defaultOutput = path.join(reviewRoot, "output", "第一版本.html");

const inputPath = resolveArg(process.argv[2], defaultInput);
const outputPath = resolveArg(process.argv[3], defaultOutput);

const source = JSON.parse(readFileSync(inputPath, "utf8"));
const report = buildReport(source);
const html = renderHtml(report, inputPath);

mkdirSync(path.dirname(outputPath), { recursive: true });
writeFileSync(outputPath, html, "utf8");

console.log(`Generated ${outputPath}`);
console.log(
  `Summary: ${report.summary.workSectionCount} workSection, ${report.summary.structureCount} structures, ${report.summary.taskCount} tasks`,
);

function resolveArg(value, fallback) {
  if (!value) return fallback;
  return path.isAbsolute(value) ? value : path.resolve(process.cwd(), value);
}

function buildReport(json) {
  if (!Array.isArray(json?.data) && Array.isArray(json?.data?.tasks)) {
    return buildScheduleReport(json);
  }

  const roots = Array.isArray(json?.data) ? json.data : Array.isArray(json) ? json : [json];
  const rows = [];
  const taskById = new Map();
  const nodeTypeCounts = {};
  const workSections = new Map();
  const structures = new Map();
  const componentGroups = new Map();
  const components = new Map();

  for (const root of roots) {
    walk(root, {
      workSection: null,
      structure: null,
      componentGroup: null,
      component: null,
    });
  }

  for (const row of rows) {
    const resolved = row.predecessors.map((predecessor) => {
      const found = taskById.get(predecessor.predecessorTaskId);
      return {
        ...predecessor,
        predecessorStructureName: found?.structureName ?? "",
        predecessorComponentName: found?.componentName ?? "",
      };
    });
    row.predecessors = resolved;
    row.predecessorCount = resolved.length;
  }

  return {
    rootName: stringValue(roots[0]?.name),
    sourceCode: json?.code ?? null,
    sourceMessage: json?.message ?? "",
    rows,
    summary: {
      workSectionCount: workSections.size,
      structureCount: structures.size,
      componentGroupCount: componentGroups.size,
      componentCount: components.size,
      taskCount: rows.length,
      totalDurationDays: rows.reduce((total, row) => total + numberOrZero(row.durationDays), 0),
      predecessorLinkCount: rows.reduce((total, row) => total + row.predecessorCount, 0),
      nodeTypeCounts,
      componentTypeCounts: groupCount(rows, (row) => row.componentTypeLabel || row.componentType || ""),
      processCounts: groupCount(rows, (row) => row.processName || ""),
    },
  };

  function walk(node, context) {
    if (!node || typeof node !== "object") return;
    const nodeType = stringValue(node.nodeType);
    if (nodeType) {
      nodeTypeCounts[nodeType] = (nodeTypeCounts[nodeType] ?? 0) + 1;
    }

    const nextContext = { ...context };
    if (nodeType === "workSection") {
      nextContext.workSection = compactNode(node);
      workSections.set(nextContext.workSection.id, nextContext.workSection);
    } else if (nodeType === "side") {
      nextContext.side = compactNode(node);
    } else if (["pier", "abutment", "structure", "topside"].includes(nodeType)) {
      nextContext.structure = compactNode(node);
      structures.set(nextContext.structure.id, nextContext.structure);
    } else if (nodeType === "componentGroup") {
      nextContext.componentGroup = compactNode(node);
      componentGroups.set(nextContext.componentGroup.id, nextContext.componentGroup);
    } else if (nodeType === "component") {
      nextContext.component = compactNode(node);
      components.set(nextContext.component.id, nextContext.component);
    } else if (nodeType === "task") {
      const row = taskRow(node, context);
      rows.push(row);
      taskById.set(row.id, row);
      taskById.set(row.nodeId, row);
    }

    for (const child of arrayValue(node.children)) {
      walk(child, nextContext);
    }
  }
}

function buildScheduleReport(json) {
  const data = json?.data && typeof json.data === "object" ? json.data : {};
  const tasks = arrayValue(data.tasks);
  const taskById = new Map();
  const rows = tasks.map(scheduleTaskRow);
  for (const row of rows) {
    taskById.set(row.id, row);
    taskById.set(row.nodeId, row);
  }
  for (const row of rows) {
    row.predecessors = row.predecessors.map((predecessor) => {
      const found = taskById.get(predecessor.predecessorTaskId);
      return {
        ...predecessor,
        predecessorStructureName: found?.structureName ?? "",
        predecessorComponentName: found?.componentName ?? "",
      };
    });
    row.predecessorCount = row.predecessors.length;
  }

  const workPointIds = new Set(rows.map((row) => row.workSectionId).filter(Boolean));
  const sides = new Set(rows.map((row) => row.sideName).filter(Boolean));
  const structures = new Set(rows.map((row) => row.structureKey).filter(Boolean));
  const componentGroups = new Set(rows.map((row) => row.componentGroupName).filter(Boolean));
  const totalDurationDays = rows.reduce((total, row) => total + numberOrZero(row.durationDays), 0);
  const predecessorLinkCount = rows.reduce((total, row) => total + row.predecessorCount, 0);

  return {
    viewKind: "schedule",
    rootName: stringValue(data.solveStatus),
    sourceCode: json?.code ?? null,
    sourceMessage: json?.message ?? "",
    rows,
    summary: {
      workSectionCount: workPointIds.size,
      structureCount: structures.size,
      componentGroupCount: componentGroups.size,
      componentCount: rows.length,
      taskCount: rows.length,
      totalDurationDays,
      predecessorLinkCount,
      nodeTypeCounts: {},
      scheduleCounts: {
        "data/tasks": rows.length,
        "data/precedences": arrayValue(data.precedences).length,
        "data/resourceAllocations": arrayValue(data.resourceAllocations).length,
        "data/continuousBeamResults": arrayValue(data.continuousBeamResults).length,
        "derived/side": sides.size,
        "derived/structure": structures.size,
      },
      componentTypeCounts: groupCount(rows, (row) => row.componentTypeLabel || row.componentType || ""),
      processCounts: groupCount(rows, (row) => row.processName || ""),
    },
  };

  function scheduleTaskRow(task) {
    const taskName = stringValue(task?.taskName);
    const taskId = stringValue(task?.taskId);
    const derived = deriveScheduleTask(taskName);
    const startOffset = numberOrNull(task?.startOffsetDays);
    const endOffset = numberOrNull(task?.endOffsetDays);
    const durationDays = startOffset !== null && endOffset !== null ? endOffset - startOffset : null;
    const predecessors = normalizePredecessors(task?.predecessors);
    const row = {
      id: taskId,
      nodeId: taskId,
      taskName,
      workSectionId: stringValue(task?.workPointId),
      workSectionName: stringValue(task?.workPointId),
      sideId: derived.sideName,
      sideName: derived.sideName,
      structureId: derived.structureName,
      structureName: derived.structureName,
      structureKey: [stringValue(task?.workPointId), derived.sideName, derived.structureName].join(":"),
      structureNodeType: derived.structureNodeType,
      structureOrder: supportOrder(derived.structureName),
      componentGroupId: derived.componentGroupName,
      componentGroupName: derived.componentGroupName,
      componentId: derived.componentName,
      componentName: derived.componentName,
      componentType: derived.componentType,
      componentTypeLabel: derived.componentTypeLabel,
      processName: derived.processName,
      productivityOptionName: "",
      quantity: null,
      quantityLabel: "",
      durationDays,
      durationFormula: "",
      resourceLabel: stringValue(task?.assignedResourceLabel),
      resourceType: stringValue(task?.assignedResourceId),
      methodId: "",
      bindingSource: "",
      processTemplateId: "",
      productivityOptionId: "",
      startOffsetDays: startOffset,
      endOffsetDays: endOffset,
      startDate: stringValue(task?.startDate),
      endDate: stringValue(task?.endDate),
      unconstrained: task?.unconstrained === undefined ? "" : String(task.unconstrained),
      predecessorCount: predecessors.length,
      predecessors,
    };
    row.searchText = [
      row.workSectionName,
      row.sideName,
      row.structureName,
      row.componentGroupName,
      row.componentName,
      row.componentType,
      row.componentTypeLabel,
      row.taskName,
      row.processName,
      row.resourceLabel,
      row.resourceType,
      row.startDate,
      row.endDate,
    ].join(" ").toLowerCase();
    return row;
  }
}

function deriveScheduleTask(taskName) {
  const sideName = deriveSideName(taskName);
  const componentTypeLabel = deriveComponentTypeLabel(taskName);
  const componentType = componentTypeLabel;
  const processName = deriveScheduleProcessName(taskName, componentTypeLabel);
  const structure = deriveScheduleStructureName(taskName);
  return {
    sideName,
    structureName: structure.name,
    structureNodeType: structure.nodeType,
    componentGroupName: componentTypeLabel,
    componentName: taskName,
    componentType,
    componentTypeLabel,
    processName,
  };
}

function deriveSideName(value) {
  const text = stringValue(value);
  if (text.includes("左幅")) return "左幅";
  if (text.includes("右幅")) return "右幅";
  return "";
}

function deriveScheduleStructureName(value) {
  const text = stringValue(value);
  const continuousT = text.match(/(\d+[#号]墩\s*T构|\d+号墩T构)/);
  if (continuousT) return { name: continuousT[1], nodeType: "topside" };
  const continuousSpan = text.match(/(\d+[-－]\d+号墩(?:边跨|中跨)?(?:直线段|合拢段)?)/);
  if (continuousSpan) return { name: continuousSpan[1], nodeType: "topside" };
  const support = text.match(/^(\d+号[墩台])/);
  if (support) return { name: support[1], nodeType: "pier" };
  return { name: "", nodeType: "" };
}

function deriveComponentTypeLabel(value) {
  const text = stringValue(value);
  if (text.includes("连续梁") || text.includes("T构") || text.includes("边跨") || text.includes("中跨")) return "连续梁";
  if (text.includes("扩大基础")) return "扩大基础";
  if (text.includes("桥台")) return "桥台";
  if (text.includes("桩基")) return "桩基";
  if (text.includes("承台")) return "承台";
  if (text.includes("墩身")) return "墩身";
  if (text.includes("盖梁")) return "盖梁";
  return "";
}

function deriveScheduleProcessName(value, componentTypeLabel) {
  const text = stringValue(value);
  if (text.includes("0号块")) return "0号块";
  if (text.includes("标准段")) return "标准段";
  if (text.includes("边跨直线段")) return "边跨直线段";
  if (text.includes("边跨合拢段")) return "边跨合拢段";
  if (text.includes("中跨合拢段")) return "中跨合拢段";
  return componentTypeLabel;
}

function taskRow(node, context) {
  const payload = node.payload && typeof node.payload === "object" ? node.payload : {};
  const predecessors = normalizePredecessors(payload.predecessors);
  const workSection = context.workSection ?? {};
  const side = context.side ?? {};
  const structure = context.structure ?? {};
  const componentGroup = context.componentGroup ?? {};
  const component = context.component ?? {};
  const componentType = stringValue(payload.componentType);
  const componentTypeLabel = stringValue(payload.componentTypeLabel) || componentType;
  const id = stringValue(payload.taskId) || stringValue(node.id);
  const row = {
    id,
    nodeId: stringValue(node.id) || id,
    taskName: stringValue(node.name) || id,
    workSectionId: stringValue(workSection.id),
    workSectionName: stringValue(workSection.name),
    sideId: stringValue(side.id),
    sideName: stringValue(side.name),
    structureId: stringValue(structure.id),
    structureName: stringValue(structure.name),
    structureNodeType: stringValue(structure.nodeType),
    structureOrder: supportOrder(structure.name),
    componentGroupId: stringValue(componentGroup.id),
    componentGroupName: stringValue(componentGroup.name),
    componentId: stringValue(component.id),
    componentName: stringValue(component.name),
    componentType,
    componentTypeLabel,
    processName: stringValue(payload.processName),
    productivityOptionName: stringValue(payload.productivityOptionName),
    quantity: numberOrNull(payload.quantity),
    quantityLabel: stringValue(payload.quantityLabel) || displayNumber(payload.quantity),
    durationDays: numberOrNull(payload.durationDays),
    durationFormula: stringValue(payload.durationFormula),
    resourceLabel: stringValue(payload.resourceLabel),
    resourceType: stringValue(payload.resourceType) || "",
    methodId: stringValue(payload.methodId),
    bindingSource: stringValue(payload.bindingSource),
    processTemplateId: stringValue(payload.processTemplateId),
    productivityOptionId: stringValue(payload.productivityOptionId),
    predecessorCount: predecessors.length,
    predecessors,
  };
  row.searchText = [
    row.workSectionName,
    row.sideName,
    row.structureName,
    row.componentGroupName,
    row.componentName,
    row.componentType,
    row.componentTypeLabel,
    row.taskName,
    row.processName,
    row.productivityOptionName,
    row.resourceLabel,
    row.durationFormula,
  ].join(" ").toLowerCase();
  return row;
}

function normalizePredecessors(value) {
  return arrayValue(value).map((item, index) => ({
    linkId: stringValue(item?.linkId),
    predecessorTaskId: stringValue(item?.predecessorTaskId),
    predecessorTaskName: stringValue(item?.predecessorTaskName) || stringValue(item?.predecessorTaskId),
    relationship: stringValue(item?.relationship),
    lagDays: numberOrNull(item?.lagDays),
    ruleId: stringValue(item?.ruleId),
  }));
}

function compactNode(node) {
  return {
    id: stringValue(node.id),
    name: stringValue(node.name),
    nodeType: stringValue(node.nodeType),
    parentId: stringValue(node.parentId),
  };
}

function renderHtml(report, inputPath) {
  const dataJson = safeJson(report);
  const labels = report.viewKind === "schedule"
    ? {
      structureMode: "derived/structure",
      processMode: "derived/processName",
      structureFilter: "data/tasks/taskName data/tasks/workPointId",
      structurePlaceholder: "data/tasks/taskName data/tasks/workPointId",
      processFilter: "data/tasks/taskName data/tasks/assignedResourceLabel",
      processPlaceholder: "data/tasks/taskName data/tasks/assignedResourceLabel",
      groupTitle: "data/tasks",
    }
    : {
      structureMode: "nodeType/name",
      processMode: "payload/processName",
      structureFilter: "nodeType/name",
      structurePlaceholder: "data/name children/name payload/taskId",
      processFilter: "payload/processName payload/componentTypeLabel",
      processPlaceholder: "payload/processName payload/componentType payload/resourceLabel",
      groupTitle: "nodeType=task",
    };
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${escapeHtml(report.rootName)}</title>
  <style>
    :root {
      font-family: Inter, "Segoe UI", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
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
      background: #eef2f6;
    }

    button, input {
      font: inherit;
    }

    button {
      border: 0;
      border-radius: 6px;
      height: 34px;
      padding: 0 12px;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      cursor: pointer;
    }

    input {
      border: 1px solid #cbd5e1;
      border-radius: 5px;
      height: 30px;
      padding: 0 8px;
      background: #fff;
      color: #18212f;
    }

    code {
      color: #475569;
      background: #f1f5f9;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      padding: 2px 5px;
      white-space: normal;
      overflow-wrap: anywhere;
    }

    .page {
      min-height: 100vh;
      padding: 16px;
      display: grid;
      gap: 12px;
    }

    .panel {
      min-width: 0;
      border: 1px solid #dbe4ed;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 1px 2px rgb(15 23 42 / 4%);
      overflow: hidden;
    }

    .panel-title {
      padding: 14px 16px;
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      border-bottom: 1px solid #edf2f7;
    }

    .panel-title > div:first-child {
      min-width: 0;
      display: grid;
      gap: 4px;
    }

    .panel-title h1,
    .panel-title h2 {
      margin: 0;
      color: #0f2742;
      line-height: 1.2;
    }

    .panel-title h1 { font-size: 20px; }
    .panel-title h2 { font-size: 16px; }

    .panel-title span {
      color: #64748b;
      font-size: 12px;
      line-height: 1.45;
    }

    .title-actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 10px;
      flex-wrap: wrap;
    }

    .segmented {
      display: inline-flex;
      padding: 3px;
      border-radius: 8px;
      background: #e7eef6;
      gap: 2px;
    }

    .segmented button {
      height: 28px;
      border-radius: 6px;
      background: transparent;
      color: #475569;
    }

    .segmented button.active {
      background: #fff;
      color: #0f4c81;
      box-shadow: 0 1px 2px rgb(15 23 42 / 10%);
      font-weight: 700;
    }

    .summary-grid {
      padding: 12px;
      display: grid;
      grid-template-columns: repeat(6, minmax(120px, 1fr));
      gap: 10px;
    }

    .metric {
      min-width: 0;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 10px 12px;
      background: #f8fafc;
      display: grid;
      gap: 4px;
    }

    .metric strong {
      color: #0f2742;
      font-size: 20px;
      line-height: 1.15;
    }

    .metric span {
      color: #64748b;
      font-size: 12px;
    }

    .filters {
      padding: 12px;
      display: grid;
      grid-template-columns: repeat(2, minmax(220px, 1fr));
      gap: 12px;
      border-top: 1px solid #edf2f7;
    }

    .filters label {
      min-width: 0;
      color: #475569;
      font-size: 12px;
      display: grid;
      gap: 5px;
    }

    .filters input {
      width: 100%;
      min-width: 0;
    }

    .task-view-groups {
      display: grid;
      gap: 12px;
      padding: 12px;
    }

    .task-view-parent-group,
    .task-view-group {
      min-width: 0;
      border: 1px solid #dbe4ed;
      border-radius: 8px;
      overflow: hidden;
      background: #fff;
    }

    .task-view-group.nested {
      border-color: #e2e8f0;
    }

    .task-view-parent-title,
    .task-view-group-title {
      width: 100%;
      height: auto;
      min-height: 40px;
      padding: 9px 12px;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      border-radius: 0;
      border-bottom: 1px solid #edf2f7;
      background: #f8fafc;
      color: inherit;
      text-align: left;
    }

    .task-view-parent-title {
      background: #eef8f8;
    }

    .task-view-group-heading {
      min-width: 0;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      overflow: hidden;
    }

    .chevron {
      width: 0;
      flex: 0 0 auto;
      overflow: hidden;
    }

    .task-view-parent-title strong,
    .task-view-group-title strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: #0f2742;
    }

    .task-view-parent-title > span:last-child,
    .task-view-group-title > span:last-child {
      flex: 0 0 auto;
      color: #64748b;
      font-size: 12px;
      white-space: nowrap;
    }

    .task-view-child-groups {
      padding: 10px;
      display: grid;
      gap: 10px;
      background: #f8fafc;
    }

    .table-wrap {
      overflow: auto;
      max-height: 560px;
    }

    table {
      width: 100%;
      min-width: 0;
      table-layout: fixed;
      border-collapse: collapse;
      font-size: 11px;
    }

    th,
    td {
      border-bottom: 1px solid #edf2f7;
      padding: 6px 6px;
      text-align: left;
      vertical-align: top;
      line-height: 1.25;
      overflow-wrap: anywhere;
      word-break: break-word;
    }

    th {
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #475569;
      font-weight: 700;
      white-space: normal;
    }

    tbody tr:hover {
      background: #f8fafc;
    }

    .tag,
    .text-pill,
    .side-tag {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 7px;
      border-radius: 5px;
      max-width: 100%;
      white-space: normal;
      overflow-wrap: anywhere;
    }

    .tag {
      background: #eaf4ff;
      color: #0f4c81;
      font-weight: 700;
    }

    .text-pill {
      background: #f8fafc;
      color: #334155;
    }

    .side-tag {
      background: #ecfeff;
      color: #0f766e;
      font-weight: 700;
    }

    .duration-expression {
      max-width: none;
      color: #475569;
      font-size: 12px;
      line-height: 1.35;
      white-space: normal;
    }

    .predecessor-count {
      height: auto;
      padding: 0;
      border: 0;
      background: transparent;
      color: #2563eb;
      font-weight: 700;
      text-decoration: underline;
      text-underline-offset: 3px;
    }

    .predecessor-zero {
      color: #64748b;
    }

    .predecessor-popover {
      position: fixed;
      z-index: 1000;
      overflow: auto;
      overscroll-behavior: contain;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 18px 46px rgb(15 23 42 / 20%);
      white-space: normal;
      display: none;
    }

    .predecessor-list {
      padding: 8px;
      display: grid;
      gap: 6px;
    }

    .predecessor-item {
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 7px 10px;
      background: #fff;
    }

    .predecessor-item-title {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }

    .predecessor-identity {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 6px;
      overflow: hidden;
    }

    .predecessor-structure {
      flex: 0 0 auto;
      color: #0f2742;
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }

    .predecessor-identity strong {
      min-width: 0;
      flex: 1 1 auto;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .predecessor-relation-token {
      flex: 0 0 auto;
      padding: 1px 5px;
      border-radius: 5px;
      background: #ecfeff;
      color: #0f766e;
      font-size: 11px;
      font-weight: 700;
    }

    .empty {
      padding: 34px;
      color: #64748b;
      text-align: center;
    }

    @media (max-width: 900px) {
      .page { padding: 10px; }
      .panel-title { align-items: flex-start; flex-direction: column; }
      .summary-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
      .filters { grid-template-columns: 1fr; }
      .task-view-parent-title,
      .task-view-group-title { align-items: flex-start; flex-direction: column; }
      .task-view-parent-title > span:last-child,
      .task-view-group-title > span:last-child { white-space: normal; }
    }
  </style>
</head>
<body>
  <div class="page">
    <section class="panel">
      <div class="panel-title">
        <div>
          <h1>${escapeHtml(report.rootName)}</h1>
          <span id="sourceLine"></span>
        </div>
        <div class="title-actions">
          <span class="text-pill" id="filteredSummary"></span>
          <div class="segmented">
            <button class="active" type="button" data-mode="structure">${escapeHtml(labels.structureMode)}</button>
            <button type="button" data-mode="process">${escapeHtml(labels.processMode)}</button>
          </div>
        </div>
      </div>
      <div class="summary-grid" id="summaryGrid"></div>
      <div class="filters">
        <label>
          ${escapeHtml(labels.structureFilter)}
          <input id="structureFilter" placeholder="${escapeHtml(labels.structurePlaceholder)}" />
        </label>
        <label>
          ${escapeHtml(labels.processFilter)}
          <input id="processFilter" placeholder="${escapeHtml(labels.processPlaceholder)}" />
        </label>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <div>
          <h2>${escapeHtml(labels.groupTitle)}</h2>
          <span id="groupSubtitle"></span>
        </div>
      </div>
      <div class="task-view-groups" id="groups"></div>
    </section>
  </div>

  <div class="predecessor-popover" id="predecessorPopover" role="dialog"></div>

  <script>
    const report = ${dataJson};
    const rows = report.rows;
    const rowsById = new Map(rows.flatMap((row) => [[row.id, row], [row.nodeId, row]]));
    const state = {
      mode: "structure",
      structureFilter: "",
      processFilter: "",
      collapsed: new Set(),
    };

    const groupsEl = document.getElementById("groups");
    const summaryGridEl = document.getElementById("summaryGrid");
    const sourceLineEl = document.getElementById("sourceLine");
    const filteredSummaryEl = document.getElementById("filteredSummary");
    const groupSubtitleEl = document.getElementById("groupSubtitle");
    const structureFilterEl = document.getElementById("structureFilter");
    const processFilterEl = document.getElementById("processFilter");
    const popoverEl = document.getElementById("predecessorPopover");
    let closePopoverTimer = null;
    let pinnedPredecessorRowId = null;

    sourceLineEl.textContent = "code:" + String(report.sourceCode ?? "") + " message:" + String(report.sourceMessage ?? "");
    renderSummary();
    render();

    document.querySelectorAll("[data-mode]").forEach((button) => {
      button.addEventListener("click", () => {
        state.mode = button.dataset.mode;
        document.querySelectorAll("[data-mode]").forEach((item) => {
          item.classList.toggle("active", item === button);
        });
        closePopover();
        render();
      });
    });

    structureFilterEl.addEventListener("input", () => {
      state.structureFilter = structureFilterEl.value.trim().toLowerCase();
      closePopover();
      render();
    });

    processFilterEl.addEventListener("input", () => {
      state.processFilter = processFilterEl.value.trim().toLowerCase();
      closePopover();
      render();
    });

    groupsEl.addEventListener("click", (event) => {
      const collapseButton = event.target.closest("[data-collapse-key]");
      if (collapseButton) {
        const key = collapseButton.dataset.collapseKey;
        if (state.collapsed.has(key)) state.collapsed.delete(key);
        else state.collapsed.add(key);
        closePopover();
        render();
        return;
      }

      const predecessorButton = event.target.closest(".predecessor-count");
      if (predecessorButton) {
        event.stopPropagation();
        const rowId = predecessorButton.dataset.rowId;
        if (pinnedPredecessorRowId === rowId) {
          closePopover();
        } else {
          pinnedPredecessorRowId = rowId;
          showPredecessorPopover(rowId, predecessorButton);
        }
      }
    });

    groupsEl.addEventListener("mouseover", (event) => {
      const button = event.target.closest(".predecessor-count");
      if (!button) return;
      clearPopoverTimer();
      showPredecessorPopover(button.dataset.rowId, button);
    });

    groupsEl.addEventListener("mouseout", (event) => {
      const button = event.target.closest(".predecessor-count");
      if (!button || pinnedPredecessorRowId) return;
      schedulePopoverClose();
    });

    groupsEl.addEventListener("focusin", (event) => {
      const button = event.target.closest(".predecessor-count");
      if (!button) return;
      showPredecessorPopover(button.dataset.rowId, button);
    });

    popoverEl.addEventListener("mouseenter", clearPopoverTimer);
    popoverEl.addEventListener("mouseleave", () => {
      if (!pinnedPredecessorRowId) schedulePopoverClose();
    });
    popoverEl.addEventListener("wheel", (event) => {
      event.stopPropagation();
    }, { passive: true });

    document.addEventListener("click", (event) => {
      if (event.target.closest(".predecessor-count") || event.target.closest("#predecessorPopover")) return;
      closePopover();
    });

    window.addEventListener("resize", closePopover);
    window.addEventListener("scroll", (event) => {
      if (popoverEl.contains(event.target)) return;
      closePopover();
    }, true);

    function renderSummary() {
      const metrics = report.viewKind === "schedule" ? [
        ["data/tasks", report.summary.scheduleCounts["data/tasks"] || 0],
        ["data/precedences", report.summary.scheduleCounts["data/precedences"] || 0],
        ["data/resourceAllocations", report.summary.scheduleCounts["data/resourceAllocations"] || 0],
        ["data/continuousBeamResults", report.summary.scheduleCounts["data/continuousBeamResults"] || 0],
        ["derived/side", report.summary.scheduleCounts["derived/side"] || 0],
        ["derived/structure", report.summary.scheduleCounts["derived/structure"] || 0],
        ["endOffsetDays-startOffsetDays", report.summary.totalDurationDays],
        ["data/tasks/predecessors", report.summary.predecessorLinkCount],
      ] : [
        ["nodeType=workSection", report.summary.nodeTypeCounts.workSection || 0],
        ["nodeType=side", report.summary.nodeTypeCounts.side || 0],
        ["nodeType=pier", report.summary.nodeTypeCounts.pier || 0],
        ["nodeType=topside", report.summary.nodeTypeCounts.topside || 0],
        ["nodeType=component", report.summary.nodeTypeCounts.component || 0],
        ["nodeType=task", report.summary.nodeTypeCounts.task || 0],
        ["payload/durationDays", report.summary.totalDurationDays],
        ["payload/predecessors", report.summary.predecessorLinkCount],
      ];
      summaryGridEl.innerHTML = metrics.map(([label, value]) => (
        '<div class="metric"><strong>' + escapeHtml(value) + '</strong><span>' + escapeHtml(label) + '</span></div>'
      )).join("");
    }

    function render() {
      const list = filteredRows();
      filteredSummaryEl.textContent = list.length + " / " + rows.length;
      groupSubtitleEl.textContent = state.mode === "structure"
        ? (report.viewKind === "schedule" ? "derived/structure" : "nodeType/name")
        : (report.viewKind === "schedule" ? "derived/processName" : "payload/processName");

      if (!list.length) {
        groupsEl.innerHTML = "";
        return;
      }

      groupsEl.innerHTML = state.mode === "structure"
        ? renderStructureMode(list)
        : renderProcessMode(list);
    }

    function filteredRows() {
      return rows.filter((row) => {
        if (state.structureFilter && !row.searchText.includes(state.structureFilter)) return false;
        if (state.processFilter) {
          const processText = [
            row.processName,
            row.componentType,
            row.componentTypeLabel,
            row.componentGroupName,
            row.resourceLabel,
          ].join(" ").toLowerCase();
          if (!processText.includes(state.processFilter)) return false;
        }
        return true;
      });
    }

    function renderStructureMode(list) {
      const parents = new Map();
      for (const row of list) {
        const parentKey = row.workSectionId || row.workSectionName;
        if (!parents.has(parentKey)) {
          parents.set(parentKey, {
            key: "parent:" + parentKey,
            title: row.workSectionName,
            rows: [],
            sides: new Map(),
          });
        }
        const parent = parents.get(parentKey);
        parent.rows.push(row);
        const sideKey = row.sideId || row.sideName;
        if (!parent.sides.has(sideKey)) {
          parent.sides.set(sideKey, {
            key: "side:" + parentKey + ":" + sideKey,
            title: row.sideName,
            rows: [],
            groups: new Map(),
          });
        }
        const side = parent.sides.get(sideKey);
        side.rows.push(row);
        const groupKey = row.structureId || row.structureName;
        if (!side.groups.has(groupKey)) {
          side.groups.set(groupKey, {
            key: "structure:" + parentKey + ":" + sideKey + ":" + groupKey,
            title: row.structureName,
            rows: [],
            nodeType: row.structureNodeType,
            order: row.structureOrder,
          });
        }
        side.groups.get(groupKey).rows.push(row);
      }

      return Array.from(parents.values()).map((parent) => {
        const collapsed = state.collapsed.has(parent.key);
        const sides = Array.from(parent.sides.values()).sort((left, right) => sideOrder(left.title) - sideOrder(right.title) || left.title.localeCompare(right.title, "zh-Hans-CN"));
        return [
          '<div class="task-view-parent-group">',
          renderGroupTitle(parent.key, parent.title, groupSummary(parent.rows, groupSummaryBase() + ":" + sides.length), collapsed, "task-view-parent-title"),
          collapsed ? "" : '<div class="task-view-child-groups">' + sides.map(renderSideGroup).join("") + '</div>',
          '</div>',
        ].join("");
      }).join("");
    }

    function renderSideGroup(side) {
      const collapsed = state.collapsed.has(side.key);
      const groups = Array.from(side.groups.values()).sort((left, right) => (
        structureNodeTypeOrder(left.nodeType) - structureNodeTypeOrder(right.nodeType)
        || left.order - right.order
        || left.title.localeCompare(right.title, "zh-Hans-CN")
      ));
      return [
        '<div class="task-view-group nested">',
        renderGroupTitle(side.key, side.title, groupSummary(side.rows, groupSummaryBase() + ":" + groups.length), collapsed, "task-view-group-title"),
        collapsed ? "" : '<div class="task-view-child-groups">' + groups.map((group) => renderTaskGroup(group, true)).join("") + '</div>',
        '</div>',
      ].join("");
    }

    function renderProcessMode(list) {
      const groups = new Map();
      for (const row of list) {
        const key = (row.componentType || row.componentTypeLabel) + ":" + row.processName;
        const title = [row.componentTypeLabel || row.componentType, row.processName].filter(Boolean).join(" ");
        if (!groups.has(key)) {
          groups.set(key, {
            key: "process:" + key,
            title,
            order: componentTypeOrder(row),
            rows: [],
          });
        }
        groups.get(key).rows.push(row);
      }

      return Array.from(groups.values())
        .sort((left, right) => (
          left.order - right.order
          || left.title.localeCompare(right.title, "zh-Hans-CN")
        ))
        .map((group) => renderTaskGroup(group, false))
        .join("");
    }

    function renderTaskGroup(group, nested) {
      const collapsed = state.collapsed.has(group.key);
      return [
        '<div class="task-view-group' + (nested ? " nested" : "") + '">',
        renderGroupTitle(group.key, group.title, groupSummary(group.rows), collapsed, "task-view-group-title"),
        collapsed ? "" : '<div class="table-wrap">' + renderTable(group.rows) + '</div>',
        '</div>',
      ].join("");
    }

    function renderGroupTitle(key, title, subtitle, collapsed, className) {
      return [
        '<button class="' + className + '" type="button" data-collapse-key="' + escapeAttr(key) + '">',
        '<span class="task-view-group-heading"><span class="chevron"></span><strong>' + escapeHtml(title) + '</strong></span>',
        '<span>' + escapeHtml(subtitle) + '</span>',
        '</button>',
      ].join("");
    }

    function renderTable(list) {
      const sorted = [...list].sort(compareRows);
      if (report.viewKind === "schedule") return renderScheduleTable(sorted);

      return [
        '<table><colgroup>',
        '<col style="width:7%"><col style="width:5%"><col style="width:6%"><col style="width:6%"><col style="width:6%"><col style="width:7%"><col style="width:12%"><col style="width:6%"><col style="width:6%"><col style="width:6%"><col style="width:4%"><col style="width:16%"><col style="width:8%"><col style="width:5%">',
        '</colgroup><thead><tr>',
        '<th>data/<wbr>name</th><th>children/<wbr>name</th><th>children/<wbr>children/<wbr>name</th><th>children/<wbr>children/<wbr>children/<wbr>name</th><th>children/<wbr>children/<wbr>children/<wbr>children/<wbr>name</th><th>payload/<wbr>componentTypeLabel</th><th>name</th><th>payload/<wbr>processName</th><th>payload/<wbr>productivityOptionName</th><th>payload/<wbr>quantityLabel</th><th>payload/<wbr>durationDays</th><th>payload/<wbr>durationFormula</th><th>payload/<wbr>resourceLabel payload/<wbr>resourceType</th><th>payload/<wbr>predecessors</th>',
        '</tr></thead><tbody>',
        sorted.map(renderRow).join(""),
        '</tbody></table>',
      ].join("");
    }

    function renderScheduleTable(sorted) {
      return [
        '<table><colgroup>',
        '<col style="width:8%"><col style="width:6%"><col style="width:7%"><col style="width:8%"><col style="width:8%"><col style="width:18%"><col style="width:6%"><col style="width:6%"><col style="width:6%"><col style="width:6%"><col style="width:9%"><col style="width:7%"><col style="width:5%">',
        '</colgroup><thead><tr>',
        '<th>data/tasks/<wbr>workPointId</th><th>derived/<wbr>side</th><th>derived/<wbr>structure</th><th>derived/<wbr>componentType</th><th>derived/<wbr>processName</th><th>data/tasks/<wbr>taskName</th><th>data/tasks/<wbr>startOffsetDays</th><th>data/tasks/<wbr>endOffsetDays</th><th>data/tasks/<wbr>startDate</th><th>data/tasks/<wbr>endDate</th><th>data/tasks/<wbr>assignedResourceLabel data/tasks/<wbr>assignedResourceId</th><th>endOffsetDays-startOffsetDays</th><th>data/tasks/<wbr>predecessors</th>',
        '</tr></thead><tbody>',
        sorted.map(renderScheduleRow).join(""),
        '</tbody></table>',
      ].join("");
    }

    function renderScheduleRow(row) {
      return [
        '<tr>',
        '<td>' + escapeHtml(row.workSectionName) + '</td>',
        '<td><span class="side-tag">' + escapeHtml(row.sideName) + '</span></td>',
        '<td><span class="side-tag">' + escapeHtml(row.structureName) + '</span></td>',
        '<td><span class="tag">' + escapeHtml(row.componentTypeLabel || row.componentType || "") + '</span></td>',
        '<td><span class="text-pill">' + escapeHtml(row.processName) + '</span></td>',
        '<td>' + escapeHtml(row.taskName) + '</td>',
        '<td>' + escapeHtml(row.startOffsetDays ?? "") + '</td>',
        '<td>' + escapeHtml(row.endOffsetDays ?? "") + '</td>',
        '<td>' + escapeHtml(row.startDate) + '</td>',
        '<td>' + escapeHtml(row.endDate) + '</td>',
        '<td>' + escapeHtml(row.resourceLabel || "") + (row.resourceType ? '<br><code>' + escapeHtml(row.resourceType) + '</code>' : '') + '</td>',
        '<td>' + escapeHtml(row.durationDays ?? "") + '</td>',
        '<td>' + renderPredecessorCell(row) + '</td>',
        '</tr>',
      ].join("");
    }

    function compareRows(left, right) {
      const continuous = compareContinuousBeamRows(left, right);
      if (continuous !== null) return continuous;
      return structureNodeTypeOrder(left.structureNodeType) - structureNodeTypeOrder(right.structureNodeType)
        || left.structureOrder - right.structureOrder
        || left.structureName.localeCompare(right.structureName, "zh-Hans-CN")
        || sideOrder(left.sideName) - sideOrder(right.sideName)
        || left.sideName.localeCompare(right.sideName, "zh-Hans-CN")
        || componentTypeOrder(left) - componentTypeOrder(right)
        || left.componentGroupName.localeCompare(right.componentGroupName, "zh-Hans-CN")
        || left.componentName.localeCompare(right.componentName, "zh-Hans-CN")
        || left.taskName.localeCompare(right.taskName, "zh-Hans-CN");
    }

    function compareContinuousBeamRows(left, right) {
      if (!isContinuousBeamRow(left) || !isContinuousBeamRow(right)) {
        return null;
      }
      const leftKey = continuousBeamSortKey(left);
      const rightKey = continuousBeamSortKey(right);
      return leftKey.mainPier - rightKey.mainPier
        || leftKey.processOrder - rightKey.processOrder
        || leftKey.blockOrder - rightKey.blockOrder
        || left.componentName.localeCompare(right.componentName, "zh-Hans-CN")
        || left.taskName.localeCompare(right.taskName, "zh-Hans-CN");
    }

    function isContinuousBeamRow(row) {
      return row.componentType === "cast_in_place_continuous_beam"
        || row.componentType === "连续梁"
        || row.componentTypeLabel === "连续梁"
        || row.componentTypeLabel === "现浇连续梁";
    }

    function continuousBeamSortKey(row) {
      const text = [row.structureName, row.componentName, row.taskName, row.processName].join(" ");
      return {
        mainPier: continuousBeamMainPier(text),
        processOrder: continuousBeamProcessOrder(text, row.processName),
        blockOrder: continuousBeamBlockOrder(text),
      };
    }

    function continuousBeamMainPier(text) {
      const tShape = text.match(/(\d+)[#号]墩\s*T构/);
      if (tShape) return Number(tShape[1]);
      const range = text.match(/(\d+)[-－](\d+)号墩/);
      if (range) {
        const first = Number(range[1]);
        const second = Number(range[2]);
        const structureRange = String(text).match(/第(\d+)[-－](\d+)跨/);
        if (text.includes("边跨") && structureRange) {
          const start = Number(structureRange[1]);
          const end = Number(structureRange[2]);
          if (first < start) return start;
          if (second >= end) return end - 1;
        }
        return first;
      }
      const sideSpan = text.match(/(\d+)号墩边跨/);
      if (sideSpan) {
        const pier = Number(sideSpan[1]);
        const structureRange = String(text).match(/第(\d+)[-－](\d+)跨/);
        if (structureRange) {
          const start = Number(structureRange[1]);
          const end = Number(structureRange[2]);
          if (pier <= start) return start;
          if (pier >= end) return end - 1;
        }
        return pier;
      }
      return Number.MAX_SAFE_INTEGER;
    }

    function continuousBeamProcessOrder(text, processName) {
      const value = [text, processName].join(" ");
      if (value.includes("0号块")) return 0;
      if (value.includes("标准块") || value.includes("标准段")) return 1;
      if (value.includes("边跨直线段") || value.includes("直线段")) return 2;
      if (value.includes("边跨合拢段")) return 3;
      if (value.includes("中跨合拢段")) return 4;
      if (value.includes("合拢段")) return 4;
      return Number.MAX_SAFE_INTEGER;
    }

    function continuousBeamBlockOrder(text) {
      if (text.includes("0号块")) return 0;
      const match = text.match(/T构[-－](\d+)('?|′)?号块/);
      if (!match) {
        if (text.includes("左侧")) return 0;
        if (text.includes("右侧")) return 1;
        return 0;
      }
      return Number(match[1]) * 2 + (match[2] ? 1 : 0);
    }

    function renderRow(row) {
      return [
        '<tr>',
        '<td>' + escapeHtml(row.workSectionName) + '</td>',
        '<td><span class="side-tag">' + escapeHtml(row.sideName) + '</span></td>',
        '<td><span class="side-tag">' + escapeHtml(row.structureName) + '</span></td>',
        '<td>' + escapeHtml(row.componentGroupName) + '</td>',
        '<td>' + escapeHtml(row.componentName) + '</td>',
        '<td><span class="tag">' + escapeHtml(row.componentTypeLabel || row.componentType || "") + '</span></td>',
        '<td>' + escapeHtml(row.taskName) + '</td>',
        '<td><span class="text-pill">' + escapeHtml(row.processName) + '</span></td>',
        '<td>' + escapeHtml(row.productivityOptionName || "") + '</td>',
        '<td>' + escapeHtml(row.quantityLabel || "") + '</td>',
        '<td>' + escapeHtml(row.durationDays ?? "") + '</td>',
        '<td class="duration-expression">' + escapeHtml(row.durationFormula || "") + '</td>',
        '<td>' + escapeHtml(row.resourceLabel || "") + (row.resourceType ? '<br><code>' + escapeHtml(row.resourceType) + '</code>' : '') + '</td>',
        '<td>' + renderPredecessorCell(row) + '</td>',
        '</tr>',
      ].join("");
    }

    function renderPredecessorCell(row) {
      if (!row.predecessors.length) return '<span class="predecessor-zero">0</span>';
      return '<button class="predecessor-count" type="button" data-row-id="' + escapeAttr(row.id) + '">' + row.predecessors.length + '</button>';
    }

    function componentTypeOrder(row) {
      const order = {
        pile: 0,
        cap: 1,
        pier_body: 2,
        cap_beam: 3,
      };
      return order[row.componentType] ?? Number.MAX_SAFE_INTEGER;
    }

    function sideOrder(value) {
      const text = String(value ?? "");
      if (text.includes("左")) return 0;
      if (text.includes("右")) return 1;
      return Number.MAX_SAFE_INTEGER;
    }

    function structureNodeTypeOrder(value) {
      const order = {
        abutment: 0,
        pier: 1,
        structure: 2,
        topside: 3,
      };
      return order[value] ?? Number.MAX_SAFE_INTEGER;
    }

    function showPredecessorPopover(rowId, anchor) {
      const row = rowsById.get(rowId);
      if (!row || !row.predecessors.length) return;
      clearPopoverTimer();
      popoverEl.innerHTML = predecessorPopoverHtml(row);
      const margin = 12;
      const width = Math.min(420, Math.max(300, window.innerWidth - margin * 2));
      const maxHeight = Math.min(380, Math.max(180, window.innerHeight - margin * 2));
      const rect = anchor.getBoundingClientRect();
      const left = Math.min(Math.max(margin, rect.right - width), Math.max(margin, window.innerWidth - width - margin));
      const belowTop = rect.bottom + 8;
      const top = belowTop + Math.min(maxHeight, 260) > window.innerHeight - margin && rect.top > window.innerHeight / 2
        ? Math.max(margin, rect.top - maxHeight - 8)
        : Math.min(belowTop, Math.max(margin, window.innerHeight - 140));
      Object.assign(popoverEl.style, {
        display: "block",
        width: width + "px",
        maxHeight: maxHeight + "px",
        left: left + "px",
        top: top + "px",
      });
    }

    function predecessorPopoverHtml(row) {
      return '<div class="predecessor-list">' + row.predecessors.map((item) => {
        const structure = item.predecessorStructureName || "";
        const name = item.predecessorTaskName || item.predecessorTaskId || "";
        const token = [
          item.relationship,
          item.lagDays === null ? "" : item.lagDays,
        ].filter((value) => value !== "").join("+");
        return [
          '<div class="predecessor-item">',
          '<div class="predecessor-item-title">',
          '<div class="predecessor-identity">',
          '<span class="predecessor-structure">' + escapeHtml(structure) + '</span>',
          '<strong title="' + escapeAttr(name) + '">' + escapeHtml(name) + '</strong>',
          '</div>',
          '<span class="predecessor-relation-token">' + escapeHtml(token) + '</span>',
          '</div>',
          '<div style="margin-top:6px;color:#64748b;font-size:12px;">ruleId:' + escapeHtml(item.ruleId || "") + ' linkId:' + escapeHtml(item.linkId || "") + '</div>',
          '</div>',
        ].join("");
      }).join("") + '</div>';
    }

    function schedulePopoverClose() {
      clearPopoverTimer();
      closePopoverTimer = window.setTimeout(closePopover, 160);
    }

    function clearPopoverTimer() {
      if (closePopoverTimer) {
        window.clearTimeout(closePopoverTimer);
        closePopoverTimer = null;
      }
    }

    function closePopover() {
      clearPopoverTimer();
      pinnedPredecessorRowId = null;
      popoverEl.style.display = "none";
      popoverEl.innerHTML = "";
    }

    function groupSummary(list, prefix) {
      const structureCount = new Set(list.map((row) => row.structureId || row.structureName)).size;
      const duration = list.reduce((total, row) => total + (Number(row.durationDays) || 0), 0);
      const base = prefix || groupSummaryBase() + ":" + structureCount;
      if (report.viewKind === "schedule") {
        return base + " data/tasks/taskId:" + list.length + " endOffsetDays-startOffsetDays:" + duration;
      }
      return base + " payload/taskId:" + list.length + " payload/durationDays:" + duration;
    }

    function groupSummaryBase() {
      return report.viewKind === "schedule" ? "derived/structure" : "nodeType/name";
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[char]);
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/\\n/g, " ");
    }
  </script>
</body>
</html>`;
}

function groupCount(rows, getKey) {
  const counts = {};
  for (const row of rows) {
    const key = getKey(row);
    counts[key] = (counts[key] ?? 0) + 1;
  }
  return counts;
}

function arrayValue(value) {
  if (Array.isArray(value)) return value;
  if (value === null || value === undefined) return [];
  return [value];
}

function stringValue(value) {
  if (value === null || value === undefined) return "";
  return String(value).trim();
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function numberOrZero(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : 0;
}

function displayNumber(value) {
  const number = numberOrNull(value);
  if (number === null) return "";
  return Number.isInteger(number) ? String(number) : String(Number(number.toFixed(4)));
}

function supportOrder(value) {
  const text = stringValue(value);
  const match = text.match(/(?:第)?(\d+)(?:[-－~至]\d+)?(?:跨|号|#)?/);
  if (!match) return Number.MAX_SAFE_INTEGER;
  return Number(match[1]);
}

function safeJson(value) {
  return JSON.stringify(value).replace(/</g, "\\u003c");
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[char]);
}
