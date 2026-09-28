import { useState, type ReactNode } from "react";
import type { GeneratedScheduleInput, ScenarioInput } from "../../contracts";
import { pavementTaskGroups } from "../../domain/pavement";

export function PavementTaskView({ scenario, generated, status, error, onRetry, onSave, dirty, saving, onSelectLayerOption }: {
  scenario: ScenarioInput; generated: GeneratedScheduleInput | null;
  status: "idle" | "loading" | "ready" | "error"; error: string | null;
  onRetry: () => void; onSave: () => void; dirty: boolean; saving: boolean;
  onSelectLayerOption: (componentId: string, optionId: string) => void;
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const groups = pavementTaskGroups(scenario, generated);
  const diagnostics = generated?.validation ?? [];
  const scope = generated?.schedule_input.pavement_handover_scope;
  return <section className="panel full pavement-task-preview">
    <header className="pavement-task-heading"><h2>施工任务 <small>{groups.length}段 · {groups.reduce((n,g) => n+g.rows.length,0)}道工序</small></h2>
      <button disabled={saving || !dirty} onClick={onSave}>{saving ? "保存中…" : "保存工效选择"}{dirty ? "（未保存）" : ""}</button>
    </header>
    {(status === "loading" || status === "idle") && <p role="status">正在按当前设置更新任务…</p>}
    {status === "error" && <p role="alert">任务生成失败：{error} <button onClick={onRetry}>重试</button></p>}
    {scope && <p role="status">本次纳入 {scope.included_section_count} 段 / {scope.included_layer_count} 个结构层 · {scope.pending_policy === "strict_last" || scope.pending_policy === "per_fleet_last" ? `其中 ${scope.pending_sections?.length ?? 0} 段待移交，附条件排程` : `受阻 ${scope.blocked_sections.length} 段`}</p>}
    {!!scope?.pending_sections?.length && <p>{scope.pending_policy === "per_fleet_last" ? "各机组完成自身正常段任务后，再施工待移交段。" : scope.pending_policy === "strict_last" ? "历史任务按其他施工段全部工序完成后安排待移交段，请重新生成任务以使用按机组后置规则。" : "待移交段为附条件安排。"}以届时完成路床移交为前提。</p>}
    {!!scope?.blocked_sections.length && <details open><summary>受阻施工段（未排程）</summary><table aria-label="受阻施工段"><thead><tr><th>施工段</th><th>受阻原因</th></tr></thead><tbody>{scope.blocked_sections.map(s => <tr key={s.structure_id}><th scope="row">{s.section_name}</th><td>{s.reason}</td></tr>)}</tbody></table></details>}
    {!groups.length ? <p>{scope?.blocked_sections.length ? "暂无可开工施工段" : "暂无启用的结构层，请在项目主数据中配置。"}</p> : <div className="table-wrap"><table aria-label="施工任务清单">
      <thead><tr><th>工序</th><th>计量工程量</th><th>工效方案</th><th>工效（每套）</th><th>工期（天）</th><th>前置工序</th><th>逻辑关系</th></tr></thead>
      {groups.map(group => <tbody key={group.id}>
        <tr className="pavement-task-group"><th colSpan={7}><button aria-expanded={!collapsed.has(group.id)} onClick={() => setCollapsed(current => { const next=new Set(current); if(next.has(group.id)) next.delete(group.id); else next.add(group.id); return next; })}>
          {collapsed.has(group.id) ? "▸" : "▾"} {group.name} <small>{group.rows.length}道工序</small>
        </button>{group.pendingHandover && <small className="pavement-task-pending">待移交·附条件排程：{group.pendingHandover.reason}</small>}</th></tr>
        {!collapsed.has(group.id) && group.rows.map(row => <tr key={row.id}>
          <th scope="row">{row.name}{status === "ready" && !row.task && <small className="pavement-task-pending">待完善</small>}</th>
          <td className="pavement-task-quantity">{row.quantityLabel}</td>
          <td>{row.componentId ? <select disabled={saving} aria-label={`${group.name} / ${row.name}工效方案`} value={row.selectedOptionId} onChange={e => onSelectLayerOption(row.componentId!, e.target.value)}>
            <option value="">继承主数据 / 默认方案</option>
            {row.selectedOptionId && !row.process?.productivity_options?.some(o => o.id === row.selectedOptionId) && <option value={row.selectedOptionId}>失效方案（请重新选择）</option>}
            {row.process?.productivity_options?.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select> : "固定工期"}</td>
          <td>{row.task && row.componentId ? `${row.task.properties?.productivity_value} ${row.task.properties?.productivity_unit}` : row.componentId ? "待完善" : "—"}</td>
          <td className="pavement-task-duration">{row.task?.duration_days ?? (status === "loading" ? "计算中" : "待完善")}</td>
          <td>{row.relations.length ? row.relations.map((r,i) => <div key={i}>{r.predecessor_name}</div>) : <span>路床移交：{row.roadbedDate}</span>}</td>
          <td>{row.relations.length ? row.relations.map((r,i) => <div key={i} title={r.source}>{r.relationship}+{r.lag_days ?? "N"}{r.lag_days == null ? "（待确认）" : "天"}{r.status === "invalid" ? " · 关系无效" : r.status === "pending" && r.lag_days != null ? " · 待生成确认" : ""}</div>) : "—"}</td>
        </tr>)}
      </tbody>)}
    </table></div>}
    {!!diagnostics.length && <details className="pavement-task-diagnostics"><summary>待完善与诊断（{diagnostics.length}项）</summary><ul>{diagnostics.map((d,i) => <li key={i}>{d.message}{d.subject_id ? `（${d.subject_id}）` : ""}</li>)}</ul></details>}
  </section>;
}

type TaskViewWorkspaceProps = {
  children: ReactNode;
  displayStatus?: "loading" | "ready" | "error";
  onRetry?: () => void;
};

export function TaskViewWorkspace({
  children,
  displayStatus = "ready",
  onRetry,
}: TaskViewWorkspaceProps) {
  if (displayStatus === "loading") {
    return (
      <div className="task-view-grid">
        <section className="panel full">
          <div className="task-view-empty" role="status">
            <strong>正在加载权威项目主数据</strong>
            <span>全部工点名称就绪后将一次性展示任务清单。</span>
          </div>
        </section>
      </div>
    );
  }

  if (displayStatus === "error") {
    return (
      <div className="task-view-grid">
        <section className="panel full">
          <div className="task-view-empty" role="alert">
            <strong>权威项目主数据暂不可用</strong>
            <span>任务数据已保留，请重试加载名称映射。</span>
            <button className="secondary" type="button" onClick={onRetry}>重试</button>
          </div>
        </section>
      </div>
    );
  }

  return <div className="task-view-grid">{children}</div>;
}
