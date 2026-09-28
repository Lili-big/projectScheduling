import type { GeneratedScheduleInput, PavementWaitInterval, PrecedenceLink, ScheduleResult, ScheduledTask } from "../../contracts";

export function dateAt(start: string, offset: number): string {
  const value = Date.parse(`${start}T00:00:00Z`) + offset * 86400000;
  return Number.isFinite(value) ? new Date(value).toISOString().slice(0, 10) : "—";
}

export function validTaskRange(task: ScheduledTask): boolean {
  return Number.isFinite(task.start_offset) && Number.isFinite(task.end_offset)
    && task.start_offset >= 0 && task.end_offset > task.start_offset;
}

export function taskLabel(task: ScheduledTask): string {
  const prefix = `${task.structure_name} · `;
  return task.name.startsWith(prefix) ? task.name.slice(prefix.length) : task.name;
}

export type PlanGroup = { key: string; name: string; structureId: string; tasks: ScheduledTask[] };
export type PlanLink = { link: PrecedenceLink; from: number; to: number };
export type WaitBand = PavementWaitInterval & { key: string; taskId: string | null };

export function buildPavementPlan(result: ScheduleResult, generated?: GeneratedScheduleInput) {
  const tasks = result.tasks ?? [];
  const byId = new Map(tasks.map(task => [task.id, task]));
  const groupsById = new Map<string, PlanGroup>();
  const ranks = new Map((generated?.schedule_input?.tasks ?? tasks).map((t, i) => [t.id, i]));
  for (const task of [...tasks].sort((a, b) => (ranks.get(a.id) ?? Infinity) - (ranks.get(b.id) ?? Infinity))) {
    const key = JSON.stringify([task.bridge_id ?? "", task.structure_id]);
    if (!groupsById.has(key)) groupsById.set(key, { key, name: task.structure_name, structureId: task.structure_id, tasks: [] });
    groupsById.get(key)!.tasks.push(task);
  }
  const groups = [...groupsById.values()];
  for (const group of groups) group.tasks.sort((a, b) => a.sequence_order - b.sequence_order || a.start_offset - b.start_offset || a.id.localeCompare(b.id));
  const issues: string[] = [];
  const links: PlanLink[] = [];
  if (!generated?.schedule_input?.precedence_links) issues.push("此结果缺少完整工序逻辑数据，暂不显示关系箭线。");
  for (const link of generated?.schedule_input?.precedence_links ?? []) {
    const a = byId.get(link.predecessor_id), b = byId.get(link.successor_id);
    if (!a || !b || !validTaskRange(a) || !validTaskRange(b) || !/^(FS|SS|FF|SF)$/.test(link.relationship)) {
      issues.push("部分工序关系无法匹配有效任务，已保留可读任务。"); continue;
    }
    links.push({ link, from: link.relationship[0] === "F" ? a.end_offset : a.start_offset,
      to: link.relationship[1] === "F" ? b.end_offset : b.start_offset });
  }
  const waits: WaitBand[] = (result.pavement_summary?.wait_intervals ?? []).flatMap((wait, i) => {
    if (!Number.isFinite(wait.start_offset) || !Number.isFinite(wait.end_offset) || wait.start_offset < 0 || wait.end_offset <= wait.start_offset) return [];
    const candidates = tasks.filter(t => t.pavement_context?.source_component_id === wait.source_component_id || t.component_id === wait.source_component_id);
    const matches = wait.reason === "零天配套步骤的附加等待"
      ? candidates.filter(t => t.component_id === wait.source_component_id && t.pavement_context?.task_kind !== "preparation")
      : candidates.filter(t => t.end_offset === wait.start_offset);
    return [{ ...wait, key: `wait-${i}`, taskId: matches.length === 1 ? matches[0].id : null }];
  });
  if (tasks.some(t => !validTaskRange(t))) issues.push("部分任务时间边界无效，仅显示文字详情。");
  const end = Math.max(1, ...tasks.filter(validTaskRange).map(t => t.end_offset), ...waits.map(w => w.end_offset));
  return { groups, links, waits, end, issues: [...new Set(issues)] };
}

export function parseChainage(value: unknown): { prefix: string; metres: number } | null {
  if (typeof value !== "string") return null;
  const match = /^([a-z]*k)\s*(\d+)\s*\+\s*(\d{1,3}(?:\.\d+)?)$/i.exec(value.trim());
  if (!match) return null;
  const metres = Number(match[2]) * 1000 + Number(match[3]);
  return Number.isFinite(metres) ? { prefix: match[1].toUpperCase(), metres } : null;
}

export function formatChainage(prefix: string, metres: number): string {
  const rounded = Math.round(metres);
  return `${prefix}${Math.floor(rounded / 1000)}+${String(rounded % 1000).padStart(3, "0")}`;
}

export type CrewSide = "left" | "right" | "none" | "unknown";
export type VisitLocation = { axisKey: string | null; axisLabel: string; coordinateGroupKey: string | null; groupLabel: string; side: CrewSide; prefix: string; start: number | null; end: number | null; rawStart: string; rawEnd: string; reason: string | null };
export type VisitTransfer = { days: number | null; start?: number; end?: number; issue?: string };
export type CrewVisit = { key: string; ordinal: number; name: string; position: string; tasks: ScheduledTask[]; location: VisitLocation; incomingTransfer: VisitTransfer | null };
export type MileageAxis = { key: string; label: string; prefix: string; min: number; max: number; visits: CrewVisit[] };
export type CrewRoute = { id: string; name: string; visits: CrewVisit[]; axes: MileageAxis[]; issues: string[] };

function visitLocation(tasks: Pick<ScheduledTask, "properties" | "bridge_id" | "pavement_context">[], generated?: GeneratedScheduleInput): VisitLocation {
  const task = tasks[0];
  const rawStart = String(task.properties?.start_chainage ?? "未提供"), rawEnd = String(task.properties?.end_chainage ?? "未提供");
  const side = (/:(left|right|none)$/.exec(task.pavement_context?.position_id ?? "")?.[1] ?? "unknown") as CrewSide;
  const workpoint = generated?.solve_scope && generated.solve_scope.workpoint_id === task.bridge_id ? generated.solve_scope.workpoint_name : null;
  const base = { axisKey: null, axisLabel: "无法按统一里程定位", coordinateGroupKey: null, groupLabel: "", side, prefix: "", start: null, end: null, rawStart, rawEnd };
  const values = tasks.map(t => [parseChainage(t.properties?.start_chainage), parseChainage(t.properties?.end_chainage)] as const);
  if (values.some(([a, b]) => !a || !b)) return { ...base, reason: "桩号缺失或格式无法解析" };
  const [a, b] = values[0];
  if (values.some(([start, end]) => start!.prefix !== end!.prefix)) return { ...base, reason: "起终点跨桩号系列" };
  if (values.some(([start, end]) => start!.prefix !== a!.prefix || start!.metres !== a!.metres || end!.metres !== b!.metres)) return { ...base, reason: "同次到访的工序桩号存在冲突" };
  const sideLabel = { left: "左幅", right: "右幅", none: "不分幅", unknown: "幅别未知" }[side];
  const groupLabel = `${workpoint || task.bridge_id || "工点未知"} · ${a!.prefix} 桩号`;
  return { axisKey: JSON.stringify([task.bridge_id ?? "unknown", a!.prefix, side]), axisLabel: `${groupLabel} · ${sideLabel}`,
    coordinateGroupKey: JSON.stringify([task.bridge_id ?? "unknown", a!.prefix]), groupLabel, side,
    prefix: a!.prefix, start: a!.metres, end: b!.metres, rawStart, rawEnd, reason: null };
}

export function buildCrewRoutes(result: ScheduleResult, generated?: GeneratedScheduleInput): CrewRoute[] {
  const byCrew = new Map<string, ScheduledTask[]>();
  for (const task of result.tasks ?? []) if (task.assigned_resource_id) {
    const tasks = byCrew.get(task.assigned_resource_id) ?? [];
    tasks.push(task); byCrew.set(task.assigned_resource_id, tasks);
  }
  return [...byCrew].map(([id, tasks]) => {
    tasks.sort((a, b) => a.start_offset - b.start_offset || a.end_offset - b.end_offset || a.id.localeCompare(b.id));
    const issues: string[] = [];
    if (tasks.some(t => !validTaskRange(t))) issues.push("部分作业时间无效，当前序号仅供查看，无法确认完整施工顺序。");
    if (tasks.some((t, i) => tasks.slice(0, i).some(prior => prior.end_offset > t.start_offset))) issues.push("该机组存在重叠作业，当前序号仅按开始时间列示，无法确认唯一施工顺序。");
    const visits: CrewVisit[] = [];
    for (const task of tasks) {
      const position = task.pavement_context?.position_id || JSON.stringify([task.bridge_id, task.structure_id]);
      const last = visits[visits.length - 1];
      if (last?.position === position) last.tasks.push(task);
      else visits.push({ key: JSON.stringify([id, task.id]), ordinal: visits.length + 1, name: task.structure_name, position, tasks: [task], location: {} as VisitLocation, incomingTransfer: null });
    }
    const resource = generated?.schedule_input?.resources?.find(r => r.id === id);
    const axes = new Map<string, MileageAxis>();
    visits.forEach((visit, i) => {
      visit.location = visitLocation(visit.tasks, generated);
      if (i > 0) {
        const a = visits[i - 1].tasks[visits[i - 1].tasks.length - 1], b = visit.tasks[0];
        const matches = (result.pavement_summary?.transfers ?? []).filter(t => t.resource_id === id && t.from_task_id === a.id && t.to_task_id === b.id);
        const transfer = matches[0];
        if (transfer && validTaskRange(a) && validTaskRange(b) && Number.isFinite(transfer.start_offset) && Number.isFinite(transfer.end_offset)
          && transfer.start_offset >= a.end_offset && transfer.end_offset >= transfer.start_offset && transfer.end_offset <= b.start_offset
          && matches.every(t => t.start_offset === transfer.start_offset && t.end_offset === transfer.end_offset)) {
          visit.incomingTransfer = { days: transfer.end_offset - transfer.start_offset, start: transfer.start_offset, end: transfer.end_offset };
        } else if (transfer) {
          visit.incomingTransfer = { days: null, issue: "转场记录越界或冲突，无法确认转场耗时" };
        } else {
          const samePosition = !!a.pavement_context?.position_id && a.pavement_context.position_id === b.pavement_context?.position_id;
          visit.incomingTransfer = { days: samePosition || resource?.transfer_days === 0 ? 0 : null };
        }
      }
      const location = visit.location;
      if (location.axisKey != null && location.start != null && location.end != null) {
        const min = Math.min(location.start, location.end), max = Math.max(location.start, location.end);
        if (!axes.has(location.axisKey)) axes.set(location.axisKey, { key: location.axisKey, label: location.axisLabel, prefix: location.prefix, min, max, visits: [] });
        const axis = axes.get(location.axisKey)!;
        axis.min = Math.min(axis.min, min); axis.max = Math.max(axis.max, max); axis.visits.push(visit);
      }
    });
    return { id, name: tasks[0].assigned_resource_name || id, visits, axes: [...axes.values()], issues };
  });
}

export type CrewFlowSection = { key: string; name: string; side: "left" | "right"; start: number; end: number; rawStart: string; rawEnd: string };
export type CrewFlowGroup = { key: string; label: string; prefix: string; min: number; max: number; sections: CrewFlowSection[] };
export type CrewFlowVisit = CrewVisit & { start: number | null; end: number | null; xStart: number | null; xEnd: number | null; xAnchor: number | null; unlocatedReason: string | null };
export type CrewFlowEdge = { key: string; from: CrewFlowVisit; to: CrewFlowVisit; kind: "same-side" | "cross-side" | "external" | "unlocated" | "invalid"; reason: string | null };

/** Fixed across crew/visit selection: only a new result/input snapshot can change the domains. */
export function buildCrewFlowScene(result: ScheduleResult, generated?: GeneratedScheduleInput) {
  const groupsByKey = new Map<string, CrewFlowGroup>();
  for (const task of [...(generated?.schedule_input?.tasks ?? []), ...(result.tasks ?? [])]) {
    const l = visitLocation([task], generated);
    if (!l.coordinateGroupKey || l.start == null || l.end == null) continue;
    const min = Math.min(l.start, l.end), max = Math.max(l.start, l.end);
    let group = groupsByKey.get(l.coordinateGroupKey);
    if (group) { group.min = Math.min(group.min, min); group.max = Math.max(group.max, max); }
    else { group = { key: l.coordinateGroupKey, label: l.groupLabel, prefix: l.prefix, min, max, sections: [] }; groupsByKey.set(l.coordinateGroupKey, group); }
    if (l.side === "left" || l.side === "right") {
      const key = task.pavement_context?.position_id || JSON.stringify([task.bridge_id, task.structure_id]);
      const section = { key, name: task.structure_name.split("·")[0].trim(), side: l.side, start: min, end: max, rawStart: l.rawStart, rawEnd: l.rawEnd };
      const existing = group.sections.findIndex(s => s.key === key);
      if (existing < 0) group.sections.push(section); else group.sections[existing] = section;
    }
  }
  const groups = [...groupsByKey.values()].sort((a, b) => a.key.localeCompare(b.key));
  const timeEnd = Math.max(1, ...(result.tasks ?? []).filter(validTaskRange).map(t => t.end_offset));
  const routes = buildCrewRoutes(result, generated).map(route => {
    const visits: CrewFlowVisit[] = route.visits.map(visit => {
      const l = visit.location, group = l.coordinateGroupKey ? groupsByKey.get(l.coordinateGroupKey) : undefined;
      const validTime = visit.tasks.every(validTaskRange);
      const unlocatedReason = l.reason ?? (l.side === "none" ? "不分幅，未投到左右幅" : l.side === "unknown" ? "幅别未知，未投到左右幅" : !validTime ? "作业时间无效" : null);
      const x = (value: number) => group!.max === group!.min ? .5 : (value - group!.min) / (group!.max - group!.min);
      const xStart = !unlocatedReason && group ? x(Math.min(l.start!, l.end!)) : null;
      const xEnd = !unlocatedReason && group ? x(Math.max(l.start!, l.end!)) : null;
      return { ...visit, start: validTime ? visit.tasks[0].start_offset : null,
        end: validTime ? Math.max(...visit.tasks.map(t => t.end_offset)) : null,
        xStart, xEnd, xAnchor: xStart == null || xEnd == null ? null : (xStart + xEnd) / 2, unlocatedReason };
    });
    // Keep every adjacent pair, including non-drawable ones, so missing visits can never be skipped.
    const edges: CrewFlowEdge[] = visits.slice(1).map((to, i) => {
      const from = visits[i];
      let kind: CrewFlowEdge["kind"], reason: string | null = null;
      if (route.issues.length) { kind = "invalid"; reason = "作业时间异常，无法确认流转顺序"; }
      else if (from.unlocatedReason || to.unlocatedReason) { kind = "unlocated"; reason = from.unlocatedReason || to.unlocatedReason; }
      else if (from.location.coordinateGroupKey !== to.location.coordinateGroupKey) { kind = "external"; reason = "跨工点或桩号系列，通过前后到访查看"; }
      else kind = from.location.side === to.location.side ? "same-side" : "cross-side";
      return { key: JSON.stringify([route.id, from.key, to.key]), from, to, kind, reason };
    });
    return { ...route, visits, edges };
  });
  return { groups, routes, timeEnd, sourceNote: generated?.schedule_input?.tasks ? null : "缺少同次生成输入，里程范围按本结果全部任务显示。" };
}

/** Schematic section columns and repeat-visit rows; sequence comes only from the route, never these pixels. */
export function crewSequenceLayout(group: CrewFlowGroup, visits: CrewFlowVisit[], spacing = 1) {
  const sections = {
    left: group.sections.filter(s => s.side === "left").sort((a, b) => a.start - b.start || a.end - b.end || a.key.localeCompare(b.key)),
    right: group.sections.filter(s => s.side === "right").sort((a, b) => a.start - b.start || a.end - b.end || a.key.localeCompare(b.key)),
  };
  const columns = Math.max(1, sections.left.length, sections.right.length);
  const width = Math.max(900, 96 * columns + 88), columnWidth = (width - 88) / columns;
  const counts = new Map<string, number>(), rows = { left: 0, right: 0 };
  const placed = visits.filter(v => v.location.coordinateGroupKey === group.key && !v.unlocatedReason).flatMap(visit => {
    const side = visit.location.side;
    if (side !== "left" && side !== "right") return [];
    const column = sections[side].findIndex(s => s.key === visit.position);
    if (column < 0) return [];
    const row = counts.get(visit.position) ?? 0;
    counts.set(visit.position, row + 1); rows[side] = Math.max(rows[side], row + 1);
    return [{ visit, side, column, row }];
  });
  const rowGap = 64 * spacing, leftBase = 30 + Math.max(1, rows.left) * rowGap;
  const rightHeader = leftBase + 80, rightBase = rightHeader + 56;
  const nodes = new Map(placed.map(p => [p.visit.key, { x: 64 + (p.column + .5) * columnWidth,
    y: p.side === "left" ? leftBase - 34 - p.row * rowGap : rightBase + 34 + p.row * rowGap, row: p.row }]));
  return { sections, nodes, width, columnWidth, leftBase, rightHeader, rightBase,
    height: rightBase + Math.max(1, rows.right) * rowGap + 30 };
}

export type ResourceTimeSegment = {
  key: string; kind: "work" | "transfer" | "idle" | "unknown"; start: number; end: number;
  task?: ScheduledTask; from?: ScheduledTask; to?: ScheduledTask;
};
export type ResourceTimelineRow = {
  id: string; name: string; segments: ResourceTimeSegment[]; tasks: ScheduledTask[]; issues: string[];
  periodStart: number | null; periodEnd: number | null; workDays: number | null;
  transferDays: number | null; idleDays: number | null; workRate: number | null;
  longestIdle: ResourceTimeSegment | null;
};

function occupiedDays(intervals: { start: number; end: number }[]): number {
  let end = -Infinity, total = 0;
  for (const interval of [...intervals].sort((a, b) => a.start - b.start)) {
    total += Math.max(0, interval.end - Math.max(end, interval.start));
    end = Math.max(end, interval.end);
  }
  return total;
}

/** Uses only the result and its matching input snapshot, never the current resource configuration. */
export function buildResourceTimeline(result: ScheduleResult, generated?: GeneratedScheduleInput) {
  const tasks = result.tasks ?? [];
  const resources = generated?.schedule_input?.resources ?? [];
  const ids = new Set([...resources.filter(r => r.enabled).map(r => r.id),
    ...tasks.flatMap(t => t.assigned_resource_id ? [t.assigned_resource_id] : [])]);
  const finish = result.pavement_summary?.construction_finish_offset;
  const axisEnd = Math.max(1, ...(Number.isFinite(finish) && finish! > 0 ? [finish!] : []), ...tasks.filter(validTaskRange).map(t => t.end_offset));
  const rows: ResourceTimelineRow[] = [...ids].map(id => {
    const resource = resources.find(r => r.id === id);
    const assigned = tasks.filter(t => t.assigned_resource_id === id);
    const valid = assigned.filter(validTaskRange).sort((a, b) => a.start_offset - b.start_offset || a.end_offset - b.end_offset || a.id.localeCompare(b.id));
    const issues: string[] = [];
    const invalidWork = valid.length !== assigned.length;
    const overlap = valid.some((t, i) => valid.slice(0, i).some(a => a.end_offset > t.start_offset));
    if (invalidWork) issues.push("部分作业时间无效，无法完整评估作业率和空闲。");
    if (overlap) issues.push("同一机组存在重叠作业，无法评估作业率和空闲。");
    const segments: ResourceTimeSegment[] = valid.map(task => ({ key: `${id}:work:${task.id}`, kind: "work", start: task.start_offset, end: task.end_offset, task }));
    // Identical duplicate transfer records do not double-count occupied days.
    const transfers = [...new Map((result.pavement_summary?.transfers ?? []).filter(t => t.resource_id === id)
      .map(t => [JSON.stringify([t.from_task_id, t.to_task_id, t.start_offset, t.end_offset]), t])).values()];
    const used = new Set<typeof transfers[number]>();
    let incompleteTransfer = false;
    for (let i = 1; i < valid.length; i++) {
      const from = valid[i - 1], to = valid[i];
      const matches = transfers.filter(t => t.from_task_id === from.id && t.to_task_id === to.id);
      matches.forEach(t => used.add(t));
      const transfer = matches[0];
      const validTransfer = matches.length === 1 && Number.isFinite(transfer.start_offset) && Number.isFinite(transfer.end_offset)
        && transfer.start_offset >= from.end_offset && transfer.end_offset >= transfer.start_offset && transfer.end_offset <= to.start_offset;
      const samePosition = !!from.pavement_context?.position_id && from.pavement_context.position_id === to.pavement_context?.position_id;
      const zeroTransfer = matches.length === 0 && (samePosition || resource?.transfer_days === 0);
      const known = validTransfer || zeroTransfer;
      if (!known) {
        incompleteTransfer = true;
        issues.push(matches.length ? "转场记录存在重复冲突或时间越界，空闲统计暂不可用。" : "部分转场信息不足，未作业空档不能确定为闲置。");
      }
      const addGap = (start: number, end: number, part: string) => {
        if (end > start) segments.push({ key: `${id}:gap:${from.id}:${to.id}:${part}`, kind: known ? "idle" : "unknown", start, end, from, to });
      };
      if (validTransfer) {
        addGap(from.end_offset, transfer.start_offset, "before");
        if (transfer.end_offset > transfer.start_offset) segments.push({ key: `${id}:transfer:${from.id}:${to.id}`, kind: "transfer", start: transfer.start_offset, end: transfer.end_offset, from, to });
        addGap(transfer.end_offset, to.start_offset, "after");
      } else addGap(from.end_offset, to.start_offset, "between");
    }
    if (transfers.some(t => !used.has(t))) {
      incompleteTransfer = true;
      issues.push("部分转场无法匹配相邻作业，空闲统计暂不可用。");
    }
    if (invalidWork || overlap || transfers.some(t => !used.has(t))) {
      for (const segment of segments) if (segment.kind === "idle") segment.kind = "unknown";
    }
    const periodStart = valid.length ? valid[0].start_offset : null;
    const periodEnd = valid.length ? Math.max(...valid.map(t => t.end_offset)) : null;
    const workDays = !valid.length || invalidWork ? null : occupiedDays(segments.filter(s => s.kind === "work"));
    const reliable = !!valid.length && !invalidWork && !overlap && !incompleteTransfer;
    const idle = segments.filter(s => s.kind === "idle");
    const longestIdle = reliable ? [...idle].sort((a, b) => b.end - b.start - (a.end - a.start) || a.start - b.start)[0] ?? null : null;
    return { id, name: assigned.find(t => t.assigned_resource_name)?.assigned_resource_name || resource?.name || id,
      tasks: assigned, segments: segments.sort((a, b) => a.start - b.start || a.end - b.end), issues: [...new Set(issues)],
      periodStart, periodEnd, workDays, transferDays: reliable ? occupiedDays(segments.filter(s => s.kind === "transfer")) : null,
      idleDays: reliable ? occupiedDays(idle) : null, longestIdle,
      workRate: reliable && workDays != null ? workDays / (periodEnd! - periodStart!) * 100 : null };
  });
  return { rows, axisEnd, unassignedCount: tasks.filter(t => !t.assigned_resource_id).length };
}
