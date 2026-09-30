import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, Save } from "lucide-react";
import type { ScenarioInput } from "../../contracts";
import type { PavementProgressView, PavementProgressRow } from "../../contracts/projectMaster";
import { getPavementProgress, savePavementProgress } from "../../api/projectMasterApi";
import { currentProgressMonth, parseDailyLength, progressCellKey, progressChanges, progressEntryMap, progressError,
  progressGroups, progressMonthDays, progressRequestGate, progressReview, progressTotals, shiftProgressMonth,
  type ProgressDrafts } from "../../domain/pavementProgress";
import "./styles.css";

const format = (n: number | null | undefined) => n == null ? "—" : new Intl.NumberFormat("zh-CN", {maximumFractionDigits: 6}).format(n);
const sideName = {left: "左幅", right: "右幅", shared: "共用", none: "—"};
const columns = ["序号", "分段/幅别", "施工段 / 工序", "起止桩号", "设计总量", "已完量", "剩余量", "宽度", "厚度"];

export function PavementProgressPanel({scenario, projectId, active, onRefreshMaster}: {
  scenario: ScenarioInput; projectId: string; active: boolean; onRefreshMaster: (versionId: string) => Promise<void>;
}) {
  const [view, setView] = useState<PavementProgressView | null>(null);
  const [drafts, setDrafts] = useState<ProgressDrafts>({});
  const [month, setMonth] = useState(currentProgressMonth);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [phase, setPhase] = useState<"loading" | "ready" | "saving" | "error">("loading");
  const [error, setError] = useState("");
  const [savedNotice, setSavedNotice] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [pendingReview, setPendingReview] = useState<Set<string>>(new Set());
  const gate = useMemo(progressRequestGate, [projectId]);
  const latest = useRef({view, drafts, phase, conflict}); latest.current = {view, drafts, phase, conflict};
  const days = useMemo(() => progressMonthDays(month), [month]);
  const groups = useMemo(() => view ? progressGroups(scenario, view) : [], [scenario, view]);
  const entries = useMemo(() => view ? progressEntryMap(view) : new Map<string,number>(), [view]);
  const totals = useMemo(() => view ? progressTotals(view, drafts) : {}, [view, drafts]);
  const dirty = Object.keys(drafts).length > 0;
  const masterMatches = !!view && scenario.project_data_version_id === view.master_version_id;
  const invalid = Object.values(drafts).some(v => !!parseDailyLength(v).error) || Object.values(totals).some(t => !!t.error);
  const editable = phase === "ready" && masterMatches && !conflict && !pendingReview.size;

  async function load() {
    if (latest.current.phase === "saving") return;
    const current = gate.next();
    setPhase("loading"); setError("");
    try {
      const next = await getPavementProgress(projectId);
      if (!current()) return;
      const state = latest.current;
      if (Object.keys(state.drafts).length && (state.conflict || state.view?.revision !== next.revision || state.view?.master_version_id !== next.master_version_id)) {
        setPendingReview(new Set(Object.keys(state.drafts)));
      }
      setView(next); setConflict(false); setPhase("ready");
    } catch (reason) {
      if (current()) {setError(progressError(reason)); setPhase("error");}
    }
  }
  useEffect(() => {
    if (active) void load();
    // Drafts remain mounted when switching menus. Each load checks both versions.
  }, [active, projectId, scenario.project_data_version_id]);
  useEffect(() => () => gate.cancel(), [gate]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {event.preventDefault(); event.returnValue = "";};
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function edit(key: string, text: string) {
    setSavedNotice(false);
    setDrafts(old => {
      const next = {...old}; const parsed = parseDailyLength(text);
      if (!parsed.error && parsed.value === (entries.get(key) ?? null)) delete next[key]; else next[key] = text;
      return next;
    });
  }
  async function save() {
    if (!view || !editable || !dirty || invalid) return;
    const current = gate.next();
    setPhase("saving"); setError(""); setSavedNotice(false);
    try {
      const next = await savePavementProgress(projectId, {expected_master_version_id: view.master_version_id,
        expected_revision: view.revision, cells: progressChanges(view, drafts)});
      if (current()) {setView(next); setDrafts({}); setPhase("ready"); setSavedNotice(true);}
    } catch (reason) {
      if (!current()) return;
      const message = progressError(reason);
      setError(message); setPhase("ready");
      if (/PAVEMENT_PROGRESS_(MASTER_CHANGED|REVISION_CONFLICT)/.test(message)) setConflict(true);
    }
  }
  function resolve(key: string, keep: boolean) {
    if (!keep) setDrafts(old => {const next = {...old}; delete next[key]; return next;});
    setPendingReview(old => {const next = new Set(old); next.delete(key); return next;});
  }
  const review = view ? progressReview(view, drafts).filter(item => pendingReview.has(item.key)) : [];

  function metrics(row: PavementProgressRow | null) {
    const total = row ? totals[row.component_id] : null;
    return <>
      <td className="pp-fixed pp-c4 pp-number">{format(row?.design_length_m)}</td>
      <td className="pp-fixed pp-c5 pp-number">{format(total?.completed)}</td>
      <td className={`pp-fixed pp-c6 pp-number${total?.overrun ? " pp-overrun" : ""}`}>
        {format(total?.remaining)}{total?.overrun ? <small>超量 {format(total.overrun)} m</small> : row?.design_length_m == null && row ? <small>请完善施工长度</small> : null}
        {total?.error && <small role="alert">{total.error}</small>}
      </td>
      <td className="pp-fixed pp-c7 pp-number">{format(row?.width_m)}</td>
      <td className="pp-fixed pp-c8 pp-number">{format(row?.thickness_m)}</td>
    </>;
  }
  function dateCells(row: PavementProgressRow | null, name: string, historical = false) {
    return days.map(day => {
      const key = progressCellKey(row?.component_id ?? name, day);
      const value = drafts[key] ?? (entries.has(key) ? String(entries.get(key)) : "");
      const changed = Object.prototype.hasOwnProperty.call(drafts, key);
      const issue = changed ? parseDailyLength(value).error : null;
      return <td key={day} className={`pp-day${changed ? " pp-dirty" : ""}`}>
        {row && !historical ? <input type="text" inputMode="decimal" value={value} disabled={!editable}
          aria-label={`${row.section_name} / ${name} / ${day} 完成长度（m）`} aria-invalid={!!issue}
          title={issue ?? `${day} · ${name} · 完成长度（m）`} onChange={e => edit(key,e.target.value)} /> : <span>{row && entries.has(key) ? format(entries.get(key)) : "—"}</span>}
        {issue && <small className="pp-cell-error">{issue}</small>}
      </td>;
    });
  }
  function head() {
    return <thead><tr>{columns.map((label,i) => <th key={label} rowSpan={2} scope="col" className={`pp-fixed pp-c${i}`}>
      {label}{i >= 4 && <small>（m）</small>}</th>)}<th colSpan={days.length || 1} className="pp-month-head">{month.replace("-"," 年 ")} 月 · 每日完成长度（m）</th></tr>
      <tr>{days.map(day => <th key={day} scope="col" className="pp-date-head">{Number(day.slice(-2))}日</th>)}</tr></thead>;
  }
  function tableColumns() {
    return <colgroup>{columns.map((_,i) => <col key={i} className={`pp-col${i}`} />)}{days.map(day => <col className="pp-date-col" key={day} />)}</colgroup>;
  }
  return <section className="panel full pp-panel" aria-label="实际进度统计" hidden={!active}>
    <header className="pp-heading"><div><h3>实际进度统计</h3><p>按施工段与工序填报每日完成长度，已完量自动累计全部日期。</p></div>
      <button type="button" onClick={() => void save()} disabled={!editable || !dirty || invalid}><Save size={15} />{phase === "saving" ? "保存中…" : "保存进度"}</button></header>
    <div className="pp-toolbar"><div className="pp-month-switch"><button type="button" aria-label="上个月" onClick={() => setMonth(shiftProgressMonth(month,-1))}><ChevronLeft size={16} /></button>
      <label>填报月份 <input aria-label="填报月份" type="month" min="0001-01" max="9999-12" value={month} onChange={e => {if (progressMonthDays(e.target.value).length) setMonth(e.target.value);}} /></label>
      <button type="button" aria-label="下个月" onClick={() => setMonth(shiftProgressMonth(month,1))}><ChevronRight size={16} /></button>
      <button type="button" onClick={() => setMonth(currentProgressMonth())}>本月</button></div>
      <span className={`pp-save-state${dirty ? " is-dirty" : ""}`} role="status">{phase === "loading" ? "正在读取进度…" : phase === "saving" ? "正在保存…" : dirty ? `${Object.keys(drafts).length} 个日格未保存` : savedNotice ? "已保存" : "累计范围：全部日期"}</span>
      <button type="button" disabled={phase === "saving" || phase === "loading"} onClick={() => void load()}>重新加载{dirty ? "并核对" : ""}</button>
    </div>
    <p className="pp-note">设计总量、宽度和厚度来自项目主数据；仅填写每日量。空白表示未填，填写 0 表示当日未完成。</p>
    {error && <p role="alert" className="notice error">{error}{dirty && " 本地修改已保留。"}</p>}
    {view && !masterMatches && <div className="notice" role="status">项目主数据版本已变化，请先更新当前任务结构后核对进度。 <button disabled={phase === "saving"} onClick={() => void onRefreshMaster(view.master_version_id).catch(reason => setError(progressError(reason)))}>更新主数据</button></div>}
    {conflict && <p className="notice">请点击“重新加载并核对”，查看最新已保存值与本地修改。</p>}
    {!!review.length && <div className="pp-review" role="region" aria-label="核对未保存进度"><h4>核对未保存记录</h4><p>其他页面或主数据已有更新。逐项选择后再保存。</p>
      {review.map(item => <div className="pp-review-row" key={item.key}><span>{item.row ? `${item.row.section_name} / ${item.row.component_name}` : item.componentId} · {item.date}</span>
        <span>已保存：{item.saved == null ? "未填" : format(item.saved)} · 本地：{item.local || "清空"}</span>
        <button type="button" disabled={!item.editable || !!parseDailyLength(item.local).error} onClick={() => resolve(item.key,true)}>保留本地值</button>
        <button type="button" onClick={() => resolve(item.key,false)}>采用已保存值</button>{!item.editable && <small>此工序已停用或移除，不能继续填报。</small>}</div>)}
    </div>}
    {view && <><div className="pp-scroll" role="region" aria-label="实际进度月表，可横向和纵向滚动" tabIndex={0}>
      <table className="pp-table" style={{width: 788 + days.length * 86}} aria-label="施工段工序每日完成长度">{tableColumns()}{head()}<tbody>
        {groups.map((group, index) => {const info=group.rows.find(r=>r.master)?.master; const closed=collapsed.has(group.id);return <Fragment key={group.id}>
          <tr className="pp-group"><td className="pp-fixed pp-c0">{index+1}</td><td className="pp-fixed pp-c1">{info ? sideName[info.side] : "—"}</td>
            <th scope="row" className="pp-fixed pp-c2"><button aria-expanded={!closed} onClick={() => setCollapsed(old=>{const next=new Set(old);if(next.has(group.id))next.delete(group.id);else next.add(group.id);return next;})}>
              {closed ? <ChevronRight size={14}/> : <ChevronDown size={14}/>}<span>{group.name}</span></button></th>
            <td className="pp-fixed pp-c3">{info?.start_chainage ?? "—"}<br/>{info?.end_chainage ?? "—"}</td>{metrics(null)}{days.map(day=><td className="pp-day" key={day}/>)}</tr>
          {!closed && group.rows.map((task,order)=><tr key={task.id} data-component-id={task.componentId ?? undefined}>
            <td className="pp-fixed pp-c0 pp-sub-index">{index+1}.{order+1}</td><td className="pp-fixed pp-c1">{task.master ? sideName[task.master.side] : "—"}</td>
            <th scope="row" className="pp-fixed pp-c2 pp-process">{task.name}</th><td className="pp-fixed pp-c3">{task.master?.start_chainage ?? "—"}<br/>{task.master?.end_chainage ?? "—"}</td>
            {metrics(task.master)}{dateCells(task.master,task.name)}</tr>)}
        </Fragment>;})}
        {!groups.length && <tr><td colSpan={9+days.length} className="pp-empty">当前没有启用工序，请在项目主数据中维护施工段和工序。</td></tr>}
      </tbody></table></div>
      {!!view.historical_rows.length && <details className="pp-history"><summary>历史工序记录 · {view.historical_rows.length} 道工序（只读）</summary>
        <p className="pp-note">保留停用或移除工序的已填进度。已移除工序的尺寸取其历史主数据；重新启用原工序后恢复填报。</p>
        <div className="pp-scroll" role="region" aria-label="历史工序进度" tabIndex={0}><table className="pp-table" style={{width: 788 + days.length * 86}}>{tableColumns()}{head()}<tbody>{view.historical_rows.map((r,i)=><tr key={r.component_id}>
          <td className="pp-fixed pp-c0">{i+1}</td><td className="pp-fixed pp-c1">{sideName[r.side]}</td><th className="pp-fixed pp-c2" scope="row">{r.section_name} / {r.component_name}<small>{r.status === "removed" ? "已移除 · 历史主数据" : "已停用"}</small></th>
          <td className="pp-fixed pp-c3">{r.start_chainage ?? "—"}<br/>{r.end_chainage ?? "—"}</td>{metrics(r)}{dateCells(r,r.component_name,true)}
        </tr>)}</tbody></table></div>
      </details>}
    </>}
    {!view && phase === "loading" && <p className="pp-empty">正在读取项目主数据与每日进度…</p>}
    {invalid && <p role="alert" className="pp-validation">请修正标注的日格后保存；每日量须为非负数，最多3位小数。</p>}
  </section>;
}
