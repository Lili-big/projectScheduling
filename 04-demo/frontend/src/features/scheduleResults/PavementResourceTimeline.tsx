import { useMemo, useRef, useState } from "react";
import type { GeneratedScheduleInput, ScheduleResult } from "../../contracts";
import { buildResourceTimeline, dateAt, taskLabel, type ResourceTimeSegment } from "./pavementViewModel";

const labels = { work: "作业", transfer: "转场", idle: "期间空闲", unknown: "未作业（信息不足）" };

export function PavementResourceTimeline({ result, generated }: { result: ScheduleResult; generated?: GeneratedScheduleInput }) {
  const timeline = useMemo(() => buildResourceTimeline(result, generated), [result, generated]);
  const [filterId, setFilterId] = useState("");
  const [selection, setSelection] = useState<{ resourceId: string; key: string | null } | null>(null);
  const nodes = useRef(new Map<string, HTMLButtonElement>());
  const filter = timeline.rows.some(r => r.id === filterId) ? filterId : "";
  const rows = filter ? timeline.rows.filter(r => r.id === filter) : timeline.rows;
  const selectedRow = rows.find(r => r.id === selection?.resourceId) ?? rows[0];
  const selected = selectedRow?.segments.find(s => s.key === selection?.key) ?? selectedRow?.segments[0];
  const ticks = [...new Set(Array.from({ length: 7 }, (_, i) => Math.floor((timeline.axisEnd - 1) * i / 6)))];
  const percent = (day: number) => 100 * day / timeline.axisEnd;
  const dates = (start: number, end: number) => `${dateAt(result.plan_start_date, start)} ～ ${dateAt(result.plan_start_date, end - 1)}`;
  const days = (value: number | null) => value == null ? "—" : `${value} 天`;
  const describe = (s: ResourceTimeSegment) => `${labels[s.kind]} · ${dates(s.start, s.end)} · ${s.end - s.start} 天${s.task ? ` · ${s.task.structure_name} / ${taskLabel(s.task)}` : ""}`;
  const select = (resourceId: string, key: string | null, focus = false) => {
    setSelection({ resourceId, key });
    if (key && focus) {
      const node = nodes.current.get(key);
      node?.scrollIntoView({ block: "nearest", inline: "center" });
      node?.focus({ preventScroll: true });
    }
  };
  return <section className="pv-section pv-resource-timeline" aria-label="机组作业与空闲">
    <div className="pv-section-heading"><div><h3>机组作业与空闲</h3><p>每套机组一行 · 横轴为日期 · 查看作业间空档，辅助判断窝工</p></div>
      <label className="pv-crew-picker">资源 <select aria-label="筛选资源横道图" value={filter} onChange={e => setFilterId(e.target.value)}>
        <option value="">全部机组</option>{timeline.rows.map(r => <option key={r.id} value={r.id}>{r.name}</option>)}
      </select></label>
    </div>
    <div className="pv-legend">{Object.entries(labels).map(([kind, name]) => <span key={kind}><i className={`pv-resource-key is-${kind}`} />{name}</span>)}<span><i className="pv-resource-key is-outside" />作业期外</span></div>
    {!rows.length ? <p className="pv-empty">本方案没有可展示的机组资源。</p> : <>
      <div className="pv-resource-scroll" tabIndex={0} aria-label="资源日期横道图，可横向滚动">
        <div className="pv-resource-grid">
          <div className="pv-resource-header"><div className="pv-resource-name">机组 / 期间作业率</div><div className="pv-resource-track">
            {ticks.map((day, i) => <span className={`pv-resource-tick tick-${i === 0 ? "first" : i === ticks.length - 1 ? "last" : "middle"}`} key={day} style={{ left: `${percent(day)}%` }}>{dateAt(result.plan_start_date, day)}</span>)}
          </div></div>
          {rows.map(row => <div className={`pv-resource-row ${selectedRow?.id === row.id ? "is-selected" : ""}`} key={row.id} data-resource-row={row.id}>
            <button type="button" className="pv-resource-name" onClick={() => select(row.id, null)} aria-pressed={selectedRow?.id === row.id} title={row.name}>
              <strong>{row.name}</strong><small>{row.workRate == null ? "—" : `${row.workRate.toFixed(1)}%`} · {row.tasks.length} 道工序</small>
            </button>
            <div className="pv-resource-track">
              {ticks.map(day => <i className="pv-resource-gridline" key={day} style={{ left: `${percent(day)}%` }} />)}
              {row.periodStart != null && row.periodEnd != null && <div className="pv-resource-period" style={{ left: `${percent(row.periodStart)}%`, width: `${percent(row.periodEnd - row.periodStart)}%` }} />}
              {row.segments.map(segment => <button type="button" key={segment.key} ref={node => { if (node) nodes.current.set(segment.key, node); else nodes.current.delete(segment.key); }}
                className={`pv-resource-bar is-${segment.kind} ${selected?.key === segment.key ? "is-selected" : ""}`} aria-label={`${row.name} · ${describe(segment)}`} title={describe(segment)}
                aria-pressed={selected?.key === segment.key} onClick={() => select(row.id, segment.key)}
                style={{ left: `${percent(segment.start)}%`, width: `${percent(segment.end - segment.start)}%` }}>
                {percent(segment.end - segment.start) >= 5 && <span>{labels[segment.kind]} {segment.end - segment.start}天</span>}
              </button>)}
              {!row.segments.length && <span className="pv-resource-empty">{row.tasks.length ? "作业时间无效，详见下方提示" : "无分配任务"}</span>}
            </div>
          </div>)}
        </div>
      </div>
      {selectedRow && <div className="pv-resource-detail" aria-label="资源时间详情">
        <div className="pv-section-heading"><strong>{selectedRow.name}</strong><button type="button" className="pv-resource-locate" disabled={!selectedRow.longestIdle} onClick={() => select(selectedRow.id, selectedRow.longestIdle!.key, true)}>定位最长空闲</button></div>
        <div className="pv-resource-stats">
          <span>作业<b>{days(selectedRow.workDays)}</b></span><span>转场<b>{days(selectedRow.transferDays)}</b></span><span>期间空闲<b>{days(selectedRow.idleDays)}</b></span>
          <span>最长空闲<b>{selectedRow.idleDays == null ? "—" : days(selectedRow.longestIdle ? selectedRow.longestIdle.end - selectedRow.longestIdle.start : 0)}</b></span>
          <span>期间作业率<b>{selectedRow.workRate == null ? "—" : `${selectedRow.workRate.toFixed(1)}%`}</b></span>
        </div>
        <p className="pv-note">{selectedRow.periodStart == null ? "无有效作业期" : `分析期：${dates(selectedRow.periodStart, selectedRow.periodEnd!)}（${selectedRow.periodEnd! - selectedRow.periodStart}天）`}</p>
        {selectedRow.issues.map(issue => <p className="pv-resource-issue" key={issue}>{issue}</p>)}
        {!!selectedRow.tasks.length && !selectedRow.segments.length && <p>{selectedRow.tasks.map(t => `${t.structure_name} / ${taskLabel(t)}`).join("；")}</p>}
        {selected && <div className="pv-resource-selection" aria-live="polite"><strong>{describe(selected)}</strong>
          {selected.from && <p>前一作业：{selected.from.structure_name} / {taskLabel(selected.from)}</p>}
          {selected.to && <p>后一作业：{selected.to.structure_name} / {taskLabel(selected.to)}</p>}
          {selected.kind === "unknown" && <p>转场或作业记录不完整，不能将这段空档直接视为窝工。</p>}
        </div>}
      </div>}
    </>}
    {timeline.unassignedCount > 0 && <p className="pv-note">{timeline.unassignedCount} 道工序未标明机组，未计入资源图。</p>}
    <p className="pv-note">期间作业率 = 作业天数 ÷ 首次开工至最后完工的天数。首作业前、末作业后不计期间空闲；养生等待不占机组。空闲原因需结合工序前置关系和移交条件判断。</p>
  </section>;
}
