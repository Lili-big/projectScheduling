import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const resultDir = path.resolve(scriptDir, "..");
const outputDir = path.resolve(scriptDir, "../../../../.local-data/archive/rebuildable/customer-validation/lugu/project-master");
const bridgePath = "D:/00-1-03-生产产线-24年/02-产品需求/15-2026斑马基建版/03 项目验证/泸古1标/泸古高速TJ-1标桥梁进度统计表4.27(1).xlsx";
const workpointPath = path.resolve(scriptDir, "../../customer-materials/泸古1标架梁工点导入模板.xlsx");
const outputPath = `${resultDir}/泸古TJ-1标统一工点及桥梁结构物导入数据.xlsx`;

const WORKPOINT_COLUMNS = [
  ["workpoint_id", "工点ID"],
  ["workpoint_name", "工点名称"],
  ["workpoint_type", "工点类型"],
  ["alignment_code", "线路编码"],
  ["start_mileage_m", "起点里程(m)"],
  ["end_mileage_m", "终点里程(m)"],
  ["sort_order", "排序号"],
  ["remark", "备注"],
];

const STRUCTURE_COLUMNS = [
  ["structure_id", "结构物ID"],
  ["workpoint_id", "所属工点ID"],
  ["structure_name", "结构物名称"],
  ["structure_category", "结构类别"],
  ["structure_type", "结构类型"],
  ["side", "幅别"],
  ["section_code", "工区编码"],
  ["section_name", "工区名称"],
  ["control_level", "受控级别"],
  ["sort_order", "排序号"],
  ["remark", "备注"],
  ["param.span_index", "跨序号"],
  ["param.span_length_m", "跨径(m)"],
  ["param.bearing_from", "起点墩台"],
  ["param.bearing_to", "终点墩台"],
  ["param.span_expression", "联跨表达式"],
  ["param.main_pier_ids", "主墩ID"],
  ["param.segment_count", "节段数量"],
  ["param.beam_count_per_span", "每跨梁片数"],
];

const COMPONENT_COLUMNS = [
  ["component_id", "构件ID"],
  ["structure_id", "所属结构物ID"],
  ["component_name", "构件名称"],
  ["component_type", "构件类型"],
  ["quantity", "工程量"],
  ["unit", "单位"],
  ["enabled", "是否启用"],
  ["sort_order", "排序号"],
  ["remark", "备注"],
  ["param.diameter_m", "直径(m)"],
  ["param.length_m", "长度(m)"],
  ["param.height_m", "高度(m)"],
  ["param.form", "结构形式"],
];

const BRIDGES = [
  { canonicalName: "联合村1号大桥", progressSheet: "联合村1号中桥", code: "LHC01" },
  { canonicalName: "联合村2号大桥", progressSheet: "联合村2号大桥", code: "LHC02" },
  { canonicalName: "两河口大桥", progressSheet: "两河口大桥", code: "LHK" },
  { canonicalName: "观音岩大桥", progressSheet: "观音岩大桥", code: "GYY" },
  { canonicalName: "观房屋基大桥", progressSheet: "观房屋基大桥", code: "GFWJ" },
  { canonicalName: "永宁河特大桥", progressSheet: "永宁河特大桥", code: "YNH", aggregateUpperBothSides: true },
  { canonicalName: "松树湾大桥", progressSheet: "松树湾大桥", code: "SSW" },
  { canonicalName: "观音溪大桥", progressSheet: "观音溪大桥", code: "GYX" },
  { canonicalName: "七龙咀大桥", progressSheet: "七龙咀大桥", code: "QLZ" },
  { canonicalName: "新屋基大桥", progressSheet: "新屋基大桥", code: "XWJ" },
  { canonicalName: "夏蓉高速1号桥", progressSheet: "夏蓉高速右线1号大桥", code: "XR01" },
  { canonicalName: "夏蓉高速2号桥", progressSheet: "夏蓉高速右线2号大桥", code: "XR02" },
  { canonicalName: "夏蓉高速中桥", progressSheet: "夏蓉高速右线中桥", code: "XRZQ" },
];

const bridgeByCanonicalName = new Map(BRIDGES.map((item) => [item.canonicalName, item]));
const ERROR_TOKENS = new Set(["#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!"]);

function clean(value) {
  if (value === null || value === undefined) return null;
  const text = String(value).replace(/\r/g, "").trim();
  if (!text || ["/", "／", "\\", "-", "—", "——", "无", "null", "None"].includes(text) || ERROR_TOKENS.has(text)) return null;
  return text;
}

function numeric(value) {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = clean(value);
  if (!text) return null;
  const normalized = text.replace(/,/g, "").replace(/^φ/i, "");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function round(value, digits = 3) {
  if (value === null || value === undefined) return null;
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

function mileageToMeters(value) {
  const text = clean(value);
  if (!text) return null;
  const match = text.match(/(\d+)\+(\d+(?:\.\d+)?)/);
  if (!match) return null;
  const sign = text.startsWith("-") ? -1 : 1;
  return round(sign * (Number(match[1]) * 1000 + Number(match[2])), 3);
}

function mileagePrefix(value) {
  const text = clean(value)?.replace(/^-/, "");
  if (!text) return null;
  const match = text.match(/^([A-Za-z][A-Za-z0-9]*?)(?=\d+\+)/);
  return match ? match[1].toUpperCase() : null;
}

function sideFromText(value) {
  const text = clean(value) ?? "";
  if (text.includes("左幅") || text === "左") return "left";
  if (text.includes("右幅") || text === "右") return "right";
  return null;
}

function sideCode(side) {
  return side === "left" ? "L" : side === "right" ? "R" : side === "shared" ? "S" : "N";
}

function sideName(side) {
  return side === "left" ? "左幅" : side === "right" ? "右幅" : side === "shared" ? "共用" : "不适用";
}

function normalizeWorkpointName(value) {
  return (clean(value) ?? "")
    .replace(/^(左幅|右幅)/, "")
    .replace(/（(?:前段预制梁|中段现浇连续梁|后段预制梁)）$/, "")
    .trim();
}

function roadbedDescriptor(value) {
  return normalizeWorkpointName(value).replace(/（[^（）]*[～~][^（）]*）$/, "").trim();
}

function roadbedRouteToken(descriptor) {
  if (descriptor.includes("B1匝道")) return "B1";
  if (descriptor.includes("B匝道")) return "B";
  if (descriptor.includes("A匝道")) return "A";
  return "MAIN";
}

function parallelNumber(value) {
  const match = (clean(value) ?? "").match(/P(\d+)/i);
  return match ? Number(match[1]) : 999;
}

function truncate(text, max = 500) {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

async function extractWorkbook(path) {
  const input = await FileBlob.load(path);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const inspection = await workbook.inspect({ kind: "sheet", include: "id,name,range", maxChars: 30000 });
  const sheets = inspection.ndjson
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => JSON.parse(line))
    .filter((entry) => entry.kind === "sheet")
    .map((entry) => {
      const worksheet = workbook.resolve(entry.id);
      return { name: entry.name, values: worksheet.getUsedRange(false).values };
    });
  return new Map(sheets.map((sheet) => [sheet.name, sheet]));
}

function createWorkpoints(workpointSheet) {
  const groups = new Map();
  const rows = workpointSheet.values;
  for (let index = 1; index < rows.length; index += 1) {
    const row = rows[index];
    const sourceRow = index + 1;
    const rawName = clean(row[0]);
    const rawType = clean(row[1]);
    if (!rawName || !rawType) continue;
    const side = sideFromText(row[2]) ?? sideFromText(rawName);
    const parallel = clean(row[4]) ?? "P999";
    const normalizedName = normalizeWorkpointName(rawName);
    let kind;
    let key;
    let descriptor = normalizedName;
    let config = null;

    if (rawType.includes("桥") || rawType.includes("梁")) {
      kind = "bridge";
      config = bridgeByCanonicalName.get(normalizedName);
      if (!config) throw new Error(`工点表第 ${sourceRow} 行桥梁未配置映射：${normalizedName}`);
      key = `bridge:${config.code}`;
      descriptor = config.canonicalName;
    } else if (rawType.includes("路基")) {
      kind = "roadbed";
      descriptor = roadbedDescriptor(rawName);
      key = `roadbed:${parallel}:${roadbedRouteToken(descriptor)}`;
    } else if (rawType.includes("隧道")) {
      kind = "tunnel";
      key = `tunnel:${descriptor}`;
    } else {
      kind = "other";
      key = `other:${parallel}:${descriptor}`;
    }

    if (!groups.has(key)) {
      groups.set(key, { key, kind, descriptor, parallel, config, sourceRows: [] });
    }
    groups.get(key).sourceRows.push({
      sourceRow,
      rawName,
      rawType,
      side,
      lineTag: clean(row[2]),
      lineOrder: numeric(row[3]),
      parallel,
      startMileage: clean(row[5]),
      endMileage: clean(row[6]),
      beamCount: numeric(row[7]),
      spanCount: numeric(row[8]),
    });
  }

  const ordered = [...groups.values()].sort((a, b) => {
    const groupDiff = parallelNumber(a.parallel) - parallelNumber(b.parallel);
    if (groupDiff) return groupDiff;
    const priority = { roadbed: 1, tunnel: 2, bridge: 3, other: 4 };
    const typeDiff = priority[a.kind] - priority[b.kind];
    if (typeDiff) return typeDiff;
    return a.descriptor.localeCompare(b.descriptor, "zh-CN");
  });

  const usedRoadbedIds = new Map();
  const tunnelIds = new Map([["白咀岩隧道", "BJY"], ["寨子山隧道", "ZZS"]]);
  for (let index = 0; index < ordered.length; index += 1) {
    const item = ordered[index];
    if (item.kind === "bridge") {
      item.workpointId = `WP-BR-${item.config.code}`;
      item.workpointName = item.config.canonicalName;
    } else if (item.kind === "tunnel") {
      item.workpointId = `WP-TN-${tunnelIds.get(item.descriptor) ?? String(index + 1).padStart(3, "0")}`;
      item.workpointName = item.descriptor;
    } else if (item.kind === "roadbed") {
      const route = roadbedRouteToken(item.descriptor);
      const base = `WP-RD-${item.parallel}-${route}`;
      const count = (usedRoadbedIds.get(base) ?? 0) + 1;
      usedRoadbedIds.set(base, count);
      item.workpointId = count === 1 ? base : `${base}-${count}`;
      item.workpointName = item.descriptor === "路基" ? `路基段（${item.parallel}）` : item.descriptor;
    } else {
      item.workpointId = `WP-OT-${String(index + 1).padStart(3, "0")}`;
      item.workpointName = item.descriptor;
    }
    item.sortOrder = index + 1;
    const starts = item.sourceRows.map((row) => mileageToMeters(row.startMileage)).filter((value) => value !== null);
    const ends = item.sourceRows.map((row) => mileageToMeters(row.endMileage)).filter((value) => value !== null);
    item.startMileageM = starts.length ? Math.min(...starts) : null;
    item.endMileageM = ends.length ? Math.max(...ends) : null;
    item.alignmentCode = [...new Set(item.sourceRows.flatMap((row) => [mileagePrefix(row.startMileage), mileagePrefix(row.endMileage)]).filter(Boolean))].join("/") || null;
    item.expectedSides = [...new Set(item.sourceRows.map((row) => row.side).filter(Boolean))];
    item.expectedBySide = Object.fromEntries(item.expectedSides.map((side) => {
      const rowsForSide = item.sourceRows.filter((row) => row.side === side);
      return [side, {
        beamCount: rowsForSide.reduce((sum, row) => sum + (row.beamCount ?? 0), 0),
        listedSpanCount: rowsForSide.reduce((sum, row) => sum + (row.spanCount ?? 0), 0),
      }];
    }));
    const sideMileage = item.sourceRows.map((row) => `${sideName(row.side)} ${row.startMileage ?? "?"}～${row.endMileage ?? "?"}`).join("；");
    const aliasNote = item.config && item.config.progressSheet !== item.config.canonicalName ? `；桥梁结构表名称“${item.config.progressSheet}”` : "";
    item.remark = truncate(`来源：架梁工点导入模板第${item.sourceRows.map((row) => row.sourceRow).join("/")}行；${sideMileage}${aliasNote}`);
  }
  return ordered;
}

function findColumn(topHeaders, predicate) {
  for (let index = 0; index < topHeaders.length; index += 1) {
    const text = clean(topHeaders[index]) ?? "";
    if (predicate(text)) return index;
  }
  return -1;
}

function supportToken(name) {
  const normalized = (clean(name) ?? "").replace(/\s+/g, "").replace(/(左幅|右幅)/g, "");
  const match = normalized.match(/(\d+[A-Za-z]?)#/);
  const number = match ? match[1].toUpperCase() : normalized.replace(/\W/g, "").slice(0, 8);
  return { normalized, number, isAbutment: /桥台|台/.test(normalized) };
}

function addAggregatedComponent(map, kind, values) {
  if (!values.quantity || values.quantity <= 0) return;
  const key = [kind, values.diameter ?? "", values.length ?? "", values.height ?? "", values.form ?? ""].join("|");
  const existing = map.get(key);
  if (existing) {
    existing.quantity = round(existing.quantity + values.quantity, 3);
  } else {
    map.set(key, { kind, ...values });
  }
}

function projectedSubstructureComponentType(structureType, componentType) {
  return structureType === "bridge_abutment" && componentType !== "pile" ? "abutment_body" : componentType;
}

function parseSpecialStructures(specialSheet) {
  const result = [];
  let current = null;
  for (let index = 2; index < specialSheet.values.length; index += 1) {
    const row = specialSheet.values[index];
    const bridgeName = clean(row[0]);
    const description = clean(row[1]);
    if (bridgeName) current = { bridgeName: bridgeName.replace(/\s+/g, ""), description: description ?? "", sourceRow: index + 1 };
    if (!current) continue;
    const task = clean(row[2]);
    const segmentMatch = task?.match(/(\d+)个节段施工/);
    if (!segmentMatch) continue;
    const expressionMatch = current.description.match(/[（(]([0-9.+]+)[）)]\s*m/i);
    if (!expressionMatch) continue;
    result.push({
      bridgeName: current.bridgeName,
      side: current.description.includes("左") ? "left" : current.description.includes("右") ? "right" : "both",
      expression: expressionMatch[1],
      lengths: expressionMatch[1].split("+").map(Number),
      segmentCount: Number(segmentMatch[1]),
      sourceRows: [current.sourceRow, index + 1],
    });
  }
  return result;
}

function findSequence(entries, lengths, occupied) {
  for (let start = 0; start <= entries.length - lengths.length; start += 1) {
    let matches = true;
    for (let offset = 0; offset < lengths.length; offset += 1) {
      if (occupied.has(start + offset) || Math.abs(entries[start + offset].length - lengths[offset]) > 0.001) {
        matches = false;
        break;
      }
    }
    if (matches) return start;
  }
  return -1;
}

function buildSupportLabels(supports, entryCount) {
  const labels = supports.map((support) => support.displayName);
  if (labels.length === entryCount + 1) return labels;
  if (labels.length === entryCount && labels.length) {
    const first = supportToken(labels[0]);
    const firstNumber = Number.parseInt(first.number, 10);
    if (Number.isFinite(firstNumber) && firstNumber > 0) labels.unshift(`${firstNumber - 1}#接口`);
    else labels.push(`${labels.length}#接口`);
  }
  while (labels.length < entryCount + 1) labels.push(`${labels.length}#接口`);
  return labels.slice(0, entryCount + 1);
}

function rowFromObject(columns, object) {
  return columns.map(([code]) => object[code] ?? null);
}

function parseBridge(config, sheet, workpoint, specialDefinitions, structureObjects, componentObjects, quality) {
  const values = sheet.values;
  const topHeaders = values[1] ?? [];
  const indices = {
    support: 3,
    position: 4,
    pile: findColumn(topHeaders, (text) => text === "桩基"),
    cap: findColumn(topHeaders, (text) => /^承台\s*$/.test(text)),
    baseTie: findColumn(topHeaders, (text) => text.includes("桩/承台系梁")),
    pier: findColumn(topHeaders, (text) => text === "墩柱"),
    columnTie: findColumn(topHeaders, (text) => text.startsWith("柱系梁")),
    spacer: findColumn(topHeaders, (text) => text.startsWith("隔板")),
    capBeam: findColumn(topHeaders, (text) => text.includes("盖梁/台帽")),
    upper: findColumn(topHeaders, (text) => text === "上部结构"),
  };
  if ([indices.pile, indices.pier, indices.capBeam, indices.upper].some((index) => index < 0)) {
    throw new Error(`桥梁表“${sheet.name}”缺少必要结构列。`);
  }

  const defaultSide = config.progressSheet.includes("右线") ? "right" : workpoint.expectedSides.length === 1 ? workpoint.expectedSides[0] : null;
  const supportMap = new Map();
  const supportOrder = { left: [], right: [] };
  const upperEntries = { left: [], right: [] };
  let currentSupport = null;
  let currentSide = defaultSide;
  let totalSection = false;

  for (let rowIndex = 3; rowIndex < values.length; rowIndex += 1) {
    const row = values[rowIndex];
    const rawSupport = clean(row[indices.support]);
    const rawPosition = clean(row[indices.position]);
    if (rawPosition?.includes("共计") || clean(row[0])?.includes("共计")) totalSection = true;
    if (totalSection) continue;
    const explicitSide = sideFromText(rawPosition) ?? sideFromText(rawSupport);
    if (explicitSide) currentSide = explicitSide;
    else if (defaultSide) currentSide = defaultSide;
    if (rawSupport) currentSupport = rawSupport;
    if (!currentSupport || !["left", "right"].includes(currentSide) || !currentSupport.includes("#")) continue;

    const token = supportToken(currentSupport);
    const key = `${currentSide}|${token.normalized}`;
    if (!supportMap.has(key)) {
      const support = {
        key,
        side: currentSide,
        displayName: token.normalized,
        token,
        rows: [],
        firstRow: rowIndex + 1,
      };
      supportMap.set(key, support);
      supportOrder[currentSide].push(support);
    }
    supportMap.get(key).rows.push({ row, sourceRow: rowIndex + 1 });

    const upperLength = numeric(row[indices.upper]);
    if (upperLength !== null) {
      upperEntries[currentSide].push({
        length: upperLength,
        quantity: numeric(row[indices.upper + 1]),
        supportKey: key,
        supportName: token.normalized,
        sourceRow: rowIndex + 1,
      });
    }
  }

  const supportIdBySideAndName = new Map();
  for (const side of ["left", "right"]) {
    for (let orderIndex = 0; orderIndex < supportOrder[side].length; orderIndex += 1) {
      const support = supportOrder[side][orderIndex];
      const structureType = support.token.isAbutment ? "bridge_abutment" : "bridge_pier";
      const supportKind = support.token.isAbutment ? "AB" : "PI";
      const structureId = `ST-${config.code}-${sideCode(side)}-${supportKind}${support.token.number}`;
      support.structureId = structureId;
      supportIdBySideAndName.set(`${side}|${support.displayName}`, structureId);
      const sourceRows = support.rows.map((entry) => entry.sourceRow);
      structureObjects.push({
        structure_id: structureId,
        workpoint_id: workpoint.workpointId,
        structure_name: `${sideName(side)}${support.displayName}`,
        structure_category: "substructure",
        structure_type: structureType,
        side,
        section_code: `TJ1-${config.code}-${sideCode(side)}`,
        section_name: `${workpoint.workpointName}${sideName(side)}`,
        control_level: null,
        sort_order: orderIndex + 1,
        remark: truncate(`来源：桥梁进度表“${sheet.name}”第${Math.min(...sourceRows)}-${Math.max(...sourceRows)}行；已排除资源、工效和计划时间列。`),
      });

      const aggregated = new Map();
      for (const entry of support.rows) {
        const row = entry.row;
        const pileNo = clean(row[indices.pile]);
        if (pileNo) addAggregatedComponent(aggregated, "pile", { quantity: 1, diameter: numeric(row[indices.pile + 1]), length: numeric(row[indices.pile + 2]), height: null, form: null });
        if (indices.cap >= 0 && clean(row[indices.cap])) addAggregatedComponent(aggregated, "cap", { quantity: numeric(row[indices.cap + 1]) ?? 1, diameter: null, length: null, height: null, form: clean(row[indices.cap]) });
        if (indices.baseTie >= 0 && clean(row[indices.baseTie])) addAggregatedComponent(aggregated, "baseTie", { quantity: numeric(row[indices.baseTie + 1]) ?? 1, diameter: null, length: null, height: null, form: clean(row[indices.baseTie]) });
        if (indices.pier >= 0 && (numeric(row[indices.pier]) !== null || numeric(row[indices.pier + 2]) !== null)) addAggregatedComponent(aggregated, "pier", { quantity: numeric(row[indices.pier + 3]) ?? 1, diameter: numeric(row[indices.pier]), length: null, height: numeric(row[indices.pier + 2]), form: clean(row[indices.pier + 1]) });
        if (indices.columnTie >= 0 && clean(row[indices.columnTie])) addAggregatedComponent(aggregated, "columnTie", { quantity: numeric(row[indices.columnTie + 1]) ?? 1, diameter: null, length: null, height: null, form: clean(row[indices.columnTie]) });
        if (indices.spacer >= 0 && numeric(row[indices.spacer])) addAggregatedComponent(aggregated, "spacer", { quantity: numeric(row[indices.spacer]), diameter: null, length: null, height: null, form: "隔板" });
        if (indices.capBeam >= 0 && clean(row[indices.capBeam])) addAggregatedComponent(aggregated, "capBeam", { quantity: numeric(row[indices.capBeam + 1]) ?? 1, diameter: null, length: null, height: null, form: clean(row[indices.capBeam]) });
      }

      let componentOrder = 1;
      for (const component of aggregated.values()) {
        const definitions = {
          pile: ["桩基", "pile", "根"],
          cap: ["承台", "cap", "个"],
          baseTie: ["桩/承台系梁", "tie_beam", "个"],
          pier: ["墩柱", "pier_body", "根"],
          columnTie: ["柱系梁", "tie_beam", "个"],
          spacer: ["隔板", "other", "个"],
          capBeam: [structureType === "bridge_abutment" ? "台帽" : "盖梁", "cap_beam", "个"],
        };
        const [label, sourceType, unit] = definitions[component.kind];
        const type = projectedSubstructureComponentType(structureType, sourceType);
        componentObjects.push({
          component_id: `CP-${structureId.replace(/^ST-/, "")}-${String(componentOrder).padStart(2, "0")}`,
          structure_id: structureId,
          component_name: component.form ? `${label}（${component.form}）` : label,
          component_type: type,
          quantity: component.quantity,
          unit,
          enabled: "是",
          sort_order: componentOrder,
          remark: `来源：桥梁进度表“${sheet.name}”${sideName(side)}${support.displayName}。`,
          "param.diameter_m": component.diameter,
          "param.length_m": component.length,
          "param.height_m": component.height,
          "param.form": component.form,
        });
        componentOrder += 1;
      }
    }
  }

  if (config.aggregateUpperBothSides && upperEntries.left.length && !upperEntries.right.length) {
    upperEntries.right = upperEntries.left.map((entry) => ({ ...entry, quantity: entry.quantity && entry.quantity > 1 ? entry.quantity / 2 : entry.quantity, replicatedFrom: "left" }));
    upperEntries.left = upperEntries.left.map((entry) => ({ ...entry, quantity: entry.quantity && entry.quantity > 1 ? entry.quantity / 2 : entry.quantity }));
    quality.notes.push(`${sheet.name}上部结构原表按两幅合计填在左幅区，已依据工点表左右幅梁片数等量拆分，并复用相同跨径序列。`);
  }

  const specialForBridge = specialDefinitions.filter((definition) => definition.bridgeName === sheet.name.replace(/\s+/g, ""));
  const castDefinitions = config.code === "XR02"
    ? [
        { side: "right", expression: "31+37.2+32", lengths: [31, 37.2, 32] },
        { side: "right", expression: "21.5+21.5", lengths: [21.5, 21.5] },
      ]
    : [];

  for (const side of workpoint.expectedSides) {
    const entries = upperEntries[side];
    if (!entries?.length) {
      quality.errors.push(`${sheet.name}${sideName(side)}缺少上部结构跨径数据。`);
      continue;
    }
    const supports = supportOrder[side];
    const labels = buildSupportLabels(supports, entries.length);
    const occupied = new Set();
    const units = [];
    const continuous = specialForBridge.filter((definition) => definition.side === side || definition.side === "both");
    for (const definition of continuous) {
      const start = findSequence(entries, definition.lengths, occupied);
      if (start < 0) {
        quality.errors.push(`${sheet.name}${sideName(side)}未找到连续刚构跨径 ${definition.expression}。`);
        continue;
      }
      definition.lengths.forEach((_, offset) => occupied.add(start + offset));
      units.push({ kind: "continuous", start, ...definition });
    }
    for (const definition of castDefinitions.filter((item) => item.side === side)) {
      const start = findSequence(entries, definition.lengths, occupied);
      if (start < 0) {
        quality.errors.push(`${sheet.name}${sideName(side)}未找到现浇箱梁跨径 ${definition.expression}。`);
        continue;
      }
      definition.lengths.forEach((_, offset) => occupied.add(start + offset));
      units.push({ kind: "cast", start, ...definition });
    }

    let upperOrder = 1;
    for (let spanIndex = 0; spanIndex < entries.length; spanIndex += 1) {
      if (occupied.has(spanIndex)) continue;
      const entry = entries[spanIndex];
      const structureId = `ST-${config.code}-${sideCode(side)}-SP${String(spanIndex + 1).padStart(3, "0")}`;
      const from = labels[spanIndex];
      const to = labels[spanIndex + 1];
      structureObjects.push({
        structure_id: structureId,
        workpoint_id: workpoint.workpointId,
        structure_name: `${sideName(side)}第${spanIndex + 1}跨（${from}～${to}）`,
        structure_category: "superstructure",
        structure_type: "simple_span",
        side,
        section_code: `TJ1-${config.code}-${sideCode(side)}`,
        section_name: `${workpoint.workpointName}${sideName(side)}`,
        control_level: null,
        sort_order: 1000 + spanIndex + 1,
        remark: truncate(`来源：桥梁进度表“${sheet.name}”第${entry.sourceRow}行上部结构；已排除资源和计划时间。${entry.replicatedFrom ? "原表为两幅合计，本行由左幅跨径序列拆分。" : ""}`),
        "param.span_index": spanIndex + 1,
        "param.span_length_m": entry.length,
        "param.bearing_from": from,
        "param.bearing_to": to,
        "param.beam_count_per_span": entry.quantity,
      });
      if (entry.quantity && entry.quantity > 0) {
        componentObjects.push({
          component_id: `CP-${config.code}-${sideCode(side)}-SP${String(spanIndex + 1).padStart(3, "0")}-BEAM`,
          structure_id: structureId,
          component_name: `${entry.length}m预制T梁`,
          component_type: "precast_beam",
          quantity: entry.quantity,
          unit: "片",
          enabled: "是",
          sort_order: 1,
          remark: `来源：桥梁进度表“${sheet.name}”第${entry.sourceRow}行。`,
          "param.length_m": entry.length,
          "param.form": "预制T梁",
        });
      }
      upperOrder += 1;
    }

    const simpleBeamTotal = entries.reduce((sum, entry, index) => occupied.has(index) ? sum : sum + (entry.quantity ?? 0), 0);
    const expectedBeamTotal = workpoint.expectedBySide[side]?.beamCount ?? 0;
    if (Math.abs(simpleBeamTotal - expectedBeamTotal) > 0.001) {
      quality.errors.push(`${workpoint.workpointName}${sideName(side)}预制梁数量不一致：工点表 ${expectedBeamTotal} 片，结构表映射 ${simpleBeamTotal} 片。`);
    }

    for (const [unitIndex, unit] of units.sort((a, b) => a.start - b.start).entries()) {
      const end = unit.start + unit.lengths.length - 1;
      const from = labels[unit.start];
      const to = labels[end + 1];
      const structureType = unit.kind === "continuous" ? "continuous_unit" : "cast_in_place_unit";
      const token = unit.kind === "continuous" ? "CU" : "CI";
      const structureId = `ST-${config.code}-${sideCode(side)}-${token}${String(unitIndex + 1).padStart(2, "0")}`;
      const intermediateLabels = labels.slice(unit.start + 1, end + 1);
      const mainPierIds = unit.kind === "continuous"
        ? intermediateLabels.map((label) => supportIdBySideAndName.get(`${side}|${label}`)).filter(Boolean).join("|")
        : null;
      const sourceRows = entries.slice(unit.start, end + 1).map((entry) => entry.sourceRow);
      structureObjects.push({
        structure_id: structureId,
        workpoint_id: workpoint.workpointId,
        structure_name: `${sideName(side)}${unit.kind === "continuous" ? "连续刚构联" : "现浇箱梁联"}（${unit.expression}）`,
        structure_category: "superstructure",
        structure_type: structureType,
        side,
        section_code: `TJ1-${config.code}-${sideCode(side)}`,
        section_name: `${workpoint.workpointName}${sideName(side)}`,
        control_level: unit.kind === "continuous" ? "关键控制结构" : null,
        sort_order: 1000 + unit.start + 1,
        remark: truncate(`来源：桥梁进度表“${sheet.name}”第${sourceRows.join("/")}行${unit.kind === "continuous" ? `及“特殊结构物施工工艺”第${unit.sourceRows.join("/")}行` : ""}；仅保留结构参数。`),
        "param.span_index": unit.start + 1,
        "param.span_length_m": round(unit.lengths.reduce((sum, value) => sum + value, 0), 3),
        "param.bearing_from": from,
        "param.bearing_to": to,
        "param.span_expression": unit.expression,
        "param.main_pier_ids": mainPierIds,
        "param.segment_count": unit.segmentCount ?? null,
      });
      componentObjects.push({
        component_id: `CP-${config.code}-${sideCode(side)}-${token}${String(unitIndex + 1).padStart(2, "0")}`,
        structure_id: structureId,
        component_name: unit.kind === "continuous" ? `${unit.segmentCount}个连续刚构节段` : `现浇箱梁（${unit.expression}）`,
        component_type: unit.kind === "continuous" ? "cast_in_place_continuous_beam" : "cast_in_place_box_beam",
        quantity: unit.kind === "continuous" ? unit.segmentCount : 1,
        unit: unit.kind === "continuous" ? "段" : "联",
        enabled: "是",
        sort_order: 1,
        remark: unit.kind === "continuous" ? "节段数量来自特殊结构物施工工艺表；未导入工期及资源信息。" : "联跨表达式来自桥梁结构统计及逐桥明细。",
        "param.form": unit.expression,
      });
    }
  }
}

function assertQuality(workpoints, structures, components, quality) {
  const duplicateCheck = (items, key, label) => {
    const seen = new Set();
    for (const item of items) {
      if (seen.has(item[key])) quality.errors.push(`${label}ID重复：${item[key]}`);
      seen.add(item[key]);
    }
  };
  duplicateCheck(workpoints, "workpoint_id", "工点");
  duplicateCheck(structures, "structure_id", "结构物");
  duplicateCheck(components, "component_id", "构件");
  const workpointIds = new Set(workpoints.map((item) => item.workpoint_id));
  const structureIds = new Set(structures.map((item) => item.structure_id));
  for (const structure of structures) if (!workpointIds.has(structure.workpoint_id)) quality.errors.push(`结构物 ${structure.structure_id} 的父工点不存在。`);
  for (const component of components) if (!structureIds.has(component.structure_id)) quality.errors.push(`构件 ${component.component_id} 的父结构物不存在。`);
  for (const row of [...workpoints, ...structures, ...components]) {
    for (const value of Object.values(row)) if (ERROR_TOKENS.has(String(value))) quality.errors.push(`输出数据残留公式错误值：${value}`);
  }
  if (workpoints.filter((item) => item.workpoint_type === "bridge").length !== BRIDGES.length) quality.errors.push("桥梁工点数量不是预期的13座。 ");
  if (quality.errors.length) throw new Error(`数据映射校验失败：\n- ${quality.errors.join("\n- ")}`);
}

function styleDataSheet(sheet, columns, rowCount, widths, validations) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(2);
  const lastColumn = String.fromCharCode(64 + columns.length);
  sheet.getRange(`A1:${lastColumn}1`).format = {
    fill: "#0F4C5C",
    font: { bold: true, color: "#FFFFFF" },
    verticalAlignment: "center",
    wrapText: true,
    borders: { bottom: { style: "medium", color: "#0B3641" } },
  };
  sheet.getRange(`A2:${lastColumn}2`).format = {
    fill: "#D9EEF2",
    font: { bold: true, color: "#12343B" },
    verticalAlignment: "center",
    wrapText: true,
    borders: { bottom: { style: "thin", color: "#9CC5CE" } },
  };
  sheet.getRange(`A3:${lastColumn}${rowCount + 2}`).format = {
    font: { color: "#1F2937" },
    verticalAlignment: "center",
    borders: { insideHorizontal: { style: "thin", color: "#E5E7EB" } },
  };
  sheet.getRange(`A1:${lastColumn}2`).format.rowHeight = 28;
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, Math.max(rowCount + 2, 3), 1).format.columnWidth = width;
  });
  for (const validation of validations) {
    sheet.getRange(`${validation.column}3:${validation.column}${Math.max(rowCount + 2, 500)}`).dataValidation = {
      rule: { type: "list", values: validation.values },
    };
  }
}

function writeDataSheet(sheet, columns, objects, widths, validations) {
  const rows = objects.map((object) => rowFromObject(columns, object));
  sheet.getRangeByIndexes(0, 0, 1, columns.length).values = [columns.map(([code]) => code)];
  sheet.getRangeByIndexes(1, 0, 1, columns.length).values = [columns.map(([, label]) => label)];
  if (rows.length) sheet.getRangeByIndexes(2, 0, rows.length, columns.length).values = rows;
  styleDataSheet(sheet, columns, rows.length, widths, validations);
  return rows;
}

await fs.mkdir(outputDir, { recursive: true });
const [bridgeSheets, workpointSheets] = await Promise.all([extractWorkbook(bridgePath), extractWorkbook(workpointPath)]);
const workpointSource = workpointSheets.get("工点");
if (!workpointSource) throw new Error("未找到工点工作表。 ");
const workpointGroups = createWorkpoints(workpointSource);
const workpointByBridgeName = new Map(workpointGroups.filter((item) => item.kind === "bridge").map((item) => [item.workpointName, item]));
const quality = { errors: [], notes: [], exclusions: ["钻机/模板/塔吊/电梯等资源字段", "施工工效与施工持续时间", "计划开始/完成时间", "完成进度及汇总表公式错误值"] };
const structureObjects = [];
const componentObjects = [];

for (const workpoint of workpointGroups) {
  if (!["roadbed", "tunnel"].includes(workpoint.kind)) continue;
  const structureType = workpoint.kind === "roadbed" ? "roadbed_section" : "tunnel_body";
  const category = workpoint.kind === "roadbed" ? "earthwork" : "tunnel_body";
  for (const [sideIndex, source] of workpoint.sourceRows.entries()) {
    if (!source.side) continue;
    structureObjects.push({
      structure_id: `ST-${workpoint.workpointId.replace(/^WP-/, "")}-${sideCode(source.side)}`,
      workpoint_id: workpoint.workpointId,
      structure_name: `${workpoint.workpointName}${sideName(source.side)}`,
      structure_category: category,
      structure_type: structureType,
      side: source.side,
      section_code: null,
      section_name: null,
      control_level: null,
      sort_order: sideIndex + 1,
      remark: truncate(`来源：架梁工点导入模板第${source.sourceRow}行；线路${source.lineTag ?? ""}，里程${source.startMileage ?? "?"}～${source.endMileage ?? "?"}。`),
    });
  }
}

const specialSheet = bridgeSheets.get("特殊结构物施工工艺");
if (!specialSheet) throw new Error("未找到“特殊结构物施工工艺”工作表。 ");
const specialDefinitions = parseSpecialStructures(specialSheet);

for (const config of BRIDGES) {
  const sheet = bridgeSheets.get(config.progressSheet);
  const workpoint = workpointByBridgeName.get(config.canonicalName);
  if (!sheet) quality.errors.push(`缺少桥梁明细工作表：${config.progressSheet}`);
  if (!workpoint) quality.errors.push(`缺少桥梁工点：${config.canonicalName}`);
  if (sheet && workpoint) parseBridge(config, sheet, workpoint, specialDefinitions, structureObjects, componentObjects, quality);
}

const workpointObjects = workpointGroups.map((item) => ({
  workpoint_id: item.workpointId,
  workpoint_name: item.workpointName,
  workpoint_type: item.kind,
  alignment_code: item.alignmentCode,
  start_mileage_m: item.startMileageM,
  end_mileage_m: item.endMileageM,
  sort_order: item.sortOrder,
  remark: item.remark,
}));

structureObjects.sort((a, b) => {
  const workpointDiff = workpointObjects.findIndex((item) => item.workpoint_id === a.workpoint_id) - workpointObjects.findIndex((item) => item.workpoint_id === b.workpoint_id);
  if (workpointDiff) return workpointDiff;
  const sideDiff = ["left", "right", "shared", "none"].indexOf(a.side) - ["left", "right", "shared", "none"].indexOf(b.side);
  if (sideDiff) return sideDiff;
  return a.sort_order - b.sort_order || a.structure_id.localeCompare(b.structure_id);
});
const structurePosition = new Map(structureObjects.map((item, index) => [item.structure_id, index]));
componentObjects.sort((a, b) => (structurePosition.get(a.structure_id) ?? 999999) - (structurePosition.get(b.structure_id) ?? 999999) || a.sort_order - b.sort_order);
assertQuality(workpointObjects, structureObjects, componentObjects, quality);

const workbook = Workbook.create();
const guide = workbook.worksheets.add("填写说明");
const workpointSheet = workbook.worksheets.add("工点信息");
const structureSheet = workbook.worksheets.add("结构物信息");
const componentSheet = workbook.worksheets.add("构件参数");

writeDataSheet(
  workpointSheet,
  WORKPOINT_COLUMNS,
  workpointObjects,
  [23, 30, 14, 14, 16, 16, 10, 70],
  [{ column: "C", values: ["bridge", "roadbed", "tunnel", "culvert", "interchange", "service_area", "station_yard", "access_road", "other"] }],
);
writeDataSheet(
  structureSheet,
  STRUCTURE_COLUMNS,
  structureObjects,
  [28, 23, 34, 18, 24, 12, 20, 24, 18, 10, 66, 12, 14, 18, 18, 26, 34, 14, 16],
  [
    { column: "D", values: ["substructure", "superstructure", "earthwork", "tunnel_body", "drainage", "ancillary", "other"] },
    { column: "E", values: ["bridge_abutment", "bridge_pier", "simple_span", "cast_in_place_unit", "continuous_unit", "roadbed_section", "tunnel_body", "culvert_body", "other"] },
    { column: "F", values: ["left", "right", "shared", "none"] },
  ],
);
writeDataSheet(
  componentSheet,
  COMPONENT_COLUMNS,
  componentObjects,
  [34, 28, 36, 30, 12, 10, 12, 10, 64, 12, 12, 12, 30],
  [
    { column: "D", values: ["pile", "cap", "tie_beam", "pier_body", "abutment_body", "cap_beam", "precast_beam", "cast_in_place_box_beam", "cast_in_place_continuous_beam", "other"] },
    { column: "G", values: ["是", "否"] },
  ],
);

guide.showGridLines = false;
guide.freezePanes.freezeRows(2);
guide.getRange("A1:B6").values = [
  ["template_version", "1.0"],
  ["definition_version", "project-master/v1"],
  ["导入语义", "当前项目完整主数据快照；工点 → 结构物 → 构件参数。"],
  ["桥梁口径", "一座物理桥梁只维护一个工点；左右幅作为结构物 side 属性。"],
  ["来源文件", "工点来自《泸古1标架梁工点导入模板》；桥梁结构来自《泸古高速TJ-1标桥梁进度统计表4.27(1)》。"],
  ["排除字段", quality.exclusions.join("；")],
];
guide.getRange("A8:D8").merge();
guide.getRange("A8:D8").values = [["泸古 TJ-1 标统一主数据摘要"]];
guide.getRange("A9:B14").values = [
  ["指标", "数量"],
  ["工点总数", null],
  ["桥梁工点", null],
  ["结构物总数", null],
  ["构件总数", null],
  ["数据映射错误", 0],
];
guide.getRange("B10").formulas = [["=COUNTA('工点信息'!A3:A2000)"]];
guide.getRange("B11").formulas = [["=COUNTIF('工点信息'!C3:C2000,\"bridge\")"]];
guide.getRange("B12").formulas = [["=COUNTA('结构物信息'!A3:A5000)"]];
guide.getRange("B13").formulas = [["=COUNTA('构件参数'!A3:A10000)"]];
guide.getRange("A16:D16").merge();
guide.getRange("A16:D16").values = [["映射说明与已核对差异"]];
const notes = [
  "1. 联合村1号桥：工点表名称为“联合村1号大桥”，桥梁结构表名称为“联合村1号中桥”；工点名称按工点表保留，备注记录别名。",
  "2. 永宁河特大桥上部结构原表以14片/跨汇总左右幅；按工点表左右幅各112片拆分为7片/跨，跨径序列保持一致。",
  "3. 两河口大桥连续刚构节段数16、永宁河特大桥连续刚构节段数22，均取自“特殊结构物施工工艺”表。",
  "4. 夏蓉高速2号桥前5跨依据桥梁表识别为两联现浇箱梁，后3跨为25m预制T梁。",
  "5. 所有原始资源、工效、计划时间、进度及错误公式均未写入本主数据文件。",
];
guide.getRange(`A17:D${16 + notes.length}`).values = notes.map((note) => [note, null, null, null]);
for (let index = 17; index <= 16 + notes.length; index += 1) guide.getRange(`A${index}:D${index}`).merge();

guide.getRange("A1:B2").format = { fill: "#0F4C5C", font: { bold: true, color: "#FFFFFF" }, borders: { preset: "outside", style: "thin", color: "#0B3641" } };
guide.getRange("A3:B6").format = { fill: "#EEF7F8", wrapText: true, borders: { insideHorizontal: { style: "thin", color: "#D7E7EA" } } };
guide.getRange("A8:D8").format = { fill: "#0F4C5C", font: { bold: true, color: "#FFFFFF", size: 14 }, horizontalAlignment: "left", verticalAlignment: "center" };
guide.getRange("A9:B9").format = { fill: "#D9EEF2", font: { bold: true, color: "#12343B" } };
guide.getRange("A10:B14").format = { borders: { insideHorizontal: { style: "thin", color: "#E5E7EB" } } };
guide.getRange("A16:D16").format = { fill: "#D9EEF2", font: { bold: true, color: "#12343B" } };
guide.getRange(`A17:D${16 + notes.length}`).format = { wrapText: true, verticalAlignment: "top", borders: { insideHorizontal: { style: "thin", color: "#E5E7EB" } } };
guide.getRange("A1:A30").format.columnWidth = 30;
guide.getRange("B1:B30").format.columnWidth = 80;
guide.getRange("C1:D30").format.columnWidth = 24;
guide.getRange("A8:D8").format.rowHeight = 32;
guide.getRange(`A17:D${16 + notes.length}`).format.rowHeight = 38;

workpointSheet.getRange(`E3:F${workpointObjects.length + 2}`).format.numberFormat = "0.000";
workpointSheet.getRange(`G3:G${workpointObjects.length + 2}`).format.numberFormat = "0";
structureSheet.getRange(`J3:J${structureObjects.length + 2}`).format.numberFormat = "0";
structureSheet.getRange(`L3:L${structureObjects.length + 2}`).format.numberFormat = "0";
structureSheet.getRange(`M3:M${structureObjects.length + 2}`).format.numberFormat = "0.000";
componentSheet.getRange(`E3:E${componentObjects.length + 2}`).format.numberFormat = "0.###";
componentSheet.getRange(`H3:H${componentObjects.length + 2}`).format.numberFormat = "0";
componentSheet.getRange(`J3:L${componentObjects.length + 2}`).format.numberFormat = "0.000";

const inspectionParts = [];
for (const request of [
  { kind: "region", sheetId: "填写说明", range: "A1:D22" },
  { kind: "region", sheetId: "工点信息", range: `A1:H${Math.min(workpointObjects.length + 2, 20)}` },
  { kind: "region", sheetId: "结构物信息", range: `A1:S${Math.min(structureObjects.length + 2, 20)}` },
  { kind: "region", sheetId: "构件参数", range: `A1:M${Math.min(componentObjects.length + 2, 20)}` },
  { kind: "formula", sheetId: "填写说明", range: "A1:D22" },
]) {
  const inspection = await workbook.inspect({ ...request, maxChars: 12000, tableMaxRows: 20, tableMaxCols: 20 });
  inspectionParts.push(inspection.ndjson);
}
await fs.writeFile(`${outputDir}/泸古TJ-1标统一主数据_inspect.ndjson`, inspectionParts.join("\n"), "utf8");

const previewRanges = {
  "填写说明": "A1:D22",
  "工点信息": `A1:H${Math.min(workpointObjects.length + 2, 42)}`,
  "结构物信息": `A1:S${Math.min(structureObjects.length + 2, 42)}`,
  "构件参数": `A1:M${Math.min(componentObjects.length + 2, 42)}`,
};
for (const [sheetName, range] of Object.entries(previewRanges)) {
  const preview = await workbook.render({ sheetName, range, scale: 0.8, format: "png" });
  await fs.writeFile(`${outputDir}/preview-${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
const report = {
  outputPath,
  sourceFiles: { workpoints: workpointPath, bridgeStructures: bridgePath },
  counts: {
    workpoints: workpointObjects.length,
    bridgeWorkpoints: workpointObjects.filter((item) => item.workpoint_type === "bridge").length,
    roadbedWorkpoints: workpointObjects.filter((item) => item.workpoint_type === "roadbed").length,
    tunnelWorkpoints: workpointObjects.filter((item) => item.workpoint_type === "tunnel").length,
    structures: structureObjects.length,
    components: componentObjects.length,
  },
  quality,
  generatedAt: new Date().toISOString(),
};
await fs.writeFile(`${resultDir}/泸古TJ-1标统一主数据_mapping-report.json`, JSON.stringify(report, null, 2), "utf8");
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
