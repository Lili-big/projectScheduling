import { useEffect, useId, useMemo, useState } from "react";
import type { GeneratedScheduleInput, ScheduleResult, ScheduledTask } from "../../contracts";
import { shiftSplitText } from "../../domain/pavement";
import { buildPavementPlan, dateAt, taskLabel, validTaskRange } from "./pavementViewModel";

const ROW = 40;
const WIDTH = 920;
const GUTTER = 14;
const colors: Record<string, string> = { granular_base: "#64748b", cement_stabilized_base: "#0d9488", asphalt_course: "#3b82f6", pavement_preparation: "#a78bfa" };

export function PavementPlanTimeline({ result, generated, pendingIds = [] }: {
  result: ScheduleResult; generated?: GeneratedScheduleInput; pendingIds?: string[];
}) {
  const plan = useMemo(() => buildPavementPlan(result, generated), [result, generated]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [showLinks, setShowLinks] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const arrowId = useId();
  const selected = result.tasks.find(t => t.id === selectedId);
  useEffect(() => { if (selectedId && !selected) setSelectedId(null); }, [selectedId, selected]);
  const rows = plan.groups.flatMap(group => [{ key: group.key, group, task: null as ScheduledTask | null },
    ...(collapsed.has(group.key) ? [] : group.tasks.map(task => ({ key: task.id, group, task })))]);
  const indices = new Map(rows.flatMap((row, i) => row.task ? [[row.task.id, i] as const] : []));
  const visibleLinks = plan.links.filter(e => indices.has(e.link.predecessor_id) && indices.has(e.link.successor_id));
  const x = (day: number) => GUTTER + day / plan.end * (WIDTH - GUTTER * 2);
  const pct = (day: number) => x(day) / WIDTH * 100;
  const ticks = Array.from({ length: 9 }, (_, i) => Math.round(i * plan.end / 8)).filter((d, i, all) => all.indexOf(d) === i);
  const detailLinks = selected ? plan.links.filter(e => e.link.predecessor_id === selected.id || e.link.successor_id === selected.id) : [];
  const detailWaits = selected ? plan.waits.filter(w => w.taskId === selected.id) : [];
  const unlocatedWaits = plan.waits.filter(w => !w.taskId);
  const regimes = generated?.schedule_input.shift_regimes ?? [];
  const dayOffset = (day: string) => Math.round((Date.parse(day) - Date.parse(result.plan_start_date)) / 86400000);
  const doubleBands = regimes.filter(r => r.shifts === 2).map(r => ({
    key: r.start_date, start: Math.max(0, dayOffset(r.start_date)),
    end: Math.min(plan.end, r.end_date ? dayOffset(r.end_date) + 1 : plan.end),
  })).filter(band => band.end > band.start);
  const toggle = (key: string) => setCollapsed(old => { const next = new Set(old); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  return <section className="pv-section" aria-label="施工计划表格与横道图">
    <div className="pv-section-heading"><div><h3>施工计划</h3><p>施工段 / 工序 · 按日历时间查看施工与衔接</p></div>
      <div className="pv-controls"><button type="button" onClick={() => setCollapsed(new Set())}>全部展开</button>
        <button type="button" onClick={() => setCollapsed(new Set(plan.groups.map(g => g.key)))}>全部收起</button>
        <label><input type="checkbox" checked={showLinks} onChange={e => setShowLinks(e.target.checked)} />工序逻辑</label></div>
    </div>
    <div className="pv-legend"><span><i className="pv-key-work" />施工</span><span><i className="pv-key-wait" />工艺等待（不占主机组）</span>
      {!!doubleBands.length && <span><i className="pv-key-double" />双班区间（日产出×2）</span>}<span>→ 工序逻辑关系</span><span>点击工序查看详情</span></div>
    {plan.issues.map(issue => <p className="pv-note" key={issue}>{issue}</p>)}
    {!rows.length ? <p className="pv-empty">暂无可展示任务。</p> : <div className="pv-plan-scroll" tabIndex={0} aria-label="施工计划，可横向及纵向滚动">
      <div className="pv-plan-grid" role="treegrid" aria-label="施工段与工序计划" aria-rowcount={rows.length + 1} aria-colcount={6}>
        <div className="pv-plan-header" role="row"><div className="pv-cells">{["施工段 / 工序", "开始日期", "完成日期", "天数", "机组"].map(label => <span role="columnheader" key={label}>{label}</span>)}</div>
          <div className="pv-calendar" role="columnheader" aria-label="日历时间轴">{ticks.map(d => <span key={d} style={{ left: `${pct(d)}%` }}>{dateAt(result.plan_start_date, d).slice(5)}</span>)}</div></div>
        <div className="pv-plan-body">
          <div className="pv-link-layer" aria-hidden="true"><svg width="100%" height={rows.length * ROW} viewBox={`0 0 ${WIDTH} ${rows.length * ROW}`} preserveAspectRatio="none">
            <defs><marker id={arrowId} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L8 4 L0 8 Z" fill="context-stroke" /></marker></defs>
            {doubleBands.map(band => <rect key={band.key} x={x(band.start)} width={Math.max(1, x(band.end) - x(band.start))} y="0" height={rows.length * ROW} fill="#f59e0b" opacity={0.12} />)}
            {ticks.map(day => <line key={day} x1={x(day)} x2={x(day)} y1="0" y2={rows.length * ROW} stroke="#dfe7ef" strokeDasharray="2 4" />)}
            {showLinks && visibleLinks.map(({ link, from, to }) => {
              const y1 = indices.get(link.predecessor_id)! * ROW + ROW / 2, y2 = indices.get(link.successor_id)! * ROW + ROW / 2;
              const x1 = x(from), x2 = x(to), midY = y1 + (y2 > y1 ? ROW / 2 - 3 : -ROW / 2 + 3);
              const startOut = x1 + (link.relationship[0] === "F" ? 8 : -8);
              const endIn = x2 + (link.relationship[1] === "F" ? 8 : -8);
              const active = selected && (link.predecessor_id === selected.id || link.successor_id === selected.id);
              return <path key={link.id} data-link-id={link.id} d={`M${x1},${y1} H${startOut} V${midY} H${endIn} V${y2} H${x2}`} fill="none" stroke={active ? "#ea580c" : "#64748b"} strokeWidth={active ? 2 : 1.2} opacity={selected && !active ? .15 : .85} markerEnd={`url(#${arrowId})`} />;
            })}
          </svg></div>
          {rows.map(({ key, group, task }) => {
            if (!task) {
              const groupTasks = group.tasks.filter(validTaskRange);
              return <div key={key} className="pv-plan-row pv-parent-row" role="row" aria-level={1} aria-expanded={!collapsed.has(key)}>
                <div className="pv-parent-cells" role="gridcell"><button type="button" aria-expanded={!collapsed.has(key)} onClick={() => toggle(key)} title={group.name}>
                  <span aria-hidden="true">{collapsed.has(key) ? "▸" : "▾"}</span> {group.name}</button>
                  <span className="pv-parent-count">{group.tasks.length} 道工序{pendingIds.includes(group.structureId) && " · 待移交"}</span></div>
                <div className="pv-parent-track" role="gridcell">{groupTasks.length > 0 && <span>{dateAt(result.plan_start_date, Math.min(...groupTasks.map(t => t.start_offset)))} ～ {dateAt(result.plan_start_date, Math.max(...groupTasks.map(t => t.end_offset)) - 1)}</span>}</div>
              </div>;
            }
            const valid = validTaskRange(task) && dateAt(result.plan_start_date, task.start_offset) !== "—";
            return <div key={key} className={`pv-plan-row ${selected?.id === task.id ? "is-selected" : ""}`} role="row" aria-level={2} aria-selected={selected?.id === task.id} data-task-id={task.id}>
              <div className="pv-cells"><div role="gridcell" className="pv-task-cell"><button type="button" className="pv-task-label" title={task.name} onClick={() => setSelectedId(task.id)}>{taskLabel(task)}{task.pavement_context?.task_kind === "preparation" && "（配套）"}</button></div>
                <span role="gridcell">{task.start_date}</span><span role="gridcell">{task.finish_date}</span><span role="gridcell">{task.end_offset - task.start_offset}</span><span role="gridcell" title={task.assigned_resource_name ?? "辅助资源未约束"}>{task.assigned_resource_name ?? "辅助资源未约束"}</span></div>
              <div className="pv-track" role="gridcell">
                {plan.waits.filter(w => w.taskId === task.id).map(w => <button type="button" key={w.key} className="pv-wait-band" style={{ left: `${pct(w.start_offset)}%`, width: `${pct(w.end_offset) - pct(w.start_offset)}%` }} title={`${w.reason} · ${w.end_offset - w.start_offset} 天；不占主机组`} aria-label={`${taskLabel(task)}：${w.reason} ${w.end_offset - w.start_offset} 天`} onClick={() => setSelectedId(task.id)} />)}
                {valid && <button type="button" className="pv-work-bar" data-task-bar={task.id} style={{ left: `${pct(task.start_offset)}%`, width: `${pct(task.end_offset) - pct(task.start_offset)}%`, backgroundColor: colors[task.component_type] ?? "#0d9488" }} title={`${task.name}\n${task.start_date} ～ ${task.finish_date} · ${task.end_offset - task.start_offset}天${regimes.length ? `（${shiftSplitText(task.start_offset, task.end_offset, regimes, result.plan_start_date)}）` : ""}`} aria-label={`${task.name}，${task.start_date}至${task.finish_date}`} onClick={() => setSelectedId(task.id)} />}
              </div>
            </div>;
          })}
        </div>
      </div>
    </div>}
    {showLinks && visibleLinks.length < plan.links.length && <p className="pv-note">部分关系连接到已收起工序，展开施工段后可查看。</p>}
    {selected && <div className="pv-task-detail" aria-label="选中工序详情"><strong>{selected.name}</strong><p>{selected.start_date} ～ {selected.finish_date} · {selected.end_offset - selected.start_offset} 天{!!regimes.length && `（${shiftSplitText(selected.start_offset, selected.end_offset, regimes, result.plan_start_date)}）`} · {selected.assigned_resource_name ?? "辅助资源未约束"}</p>
      {detailLinks.map(({ link }) => <p key={link.id}>{taskLabel(result.tasks.find(t => t.id === link.predecessor_id)!)} → {taskLabel(result.tasks.find(t => t.id === link.successor_id)!)}：{link.relationship} {link.lag_days >= 0 ? "+" : ""}{link.lag_days} 天{link.max_finish_gap_days != null && `；最大完成间隔 ${link.max_finish_gap_days} 天`}{link.severity === "warning" && "（提醒关系）"}</p>)}
      {detailWaits.map(w => <p key={w.key}>{w.reason}：{dateAt(result.plan_start_date, w.start_offset)} ～ {dateAt(result.plan_start_date, w.end_offset - 1)}，{w.end_offset - w.start_offset} 天；期间主机组可去其他段施工。</p>)}
      {!detailWaits.length && <p className="pv-note">本工序没有可定位的技术等待。横道之间的空白不自动视为养生或转场。</p>}
    </div>}
    {unlocatedWaits.length > 0 && <details><summary>未能定位到单个工序的等待（{unlocatedWaits.length}）</summary>{unlocatedWaits.map(w => <p key={w.key}>{w.source_component_id} · {w.reason} · {dateAt(result.plan_start_date, w.start_offset)} ～ {dateAt(result.plan_start_date, w.end_offset - 1)}</p>)}</details>}
  </section>;
}
