import { AlertTriangle, CheckCircle2, History, Loader2, Play, RefreshCw, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  adoptAdjustmentProposal,
  generateAdjustmentProposals,
  generateProgressForecast,
  getPlanControlProject,
  saveProgressSnapshot,
} from "../../api/schedulerApi";
import { PanelTitle } from "../../components/common/PanelTitle";
import type {
  AdjustmentComparisonResponse,
  ForecastSchedule,
  PlanControlProjectSummary,
  ProgressEntry,
  ProgressTaskStatus,
  ScenarioInput,
} from "../../types/scheduler";

const statusLabels: Record<ProgressTaskStatus, string> = {
  not_started: "未开始",
  in_progress: "进行中",
  completed: "已完成",
  paused: "暂停",
  cancelled: "取消",
};

const strategyLabels = {
  as_is: "不调整",
  add_bottleneck_resources: "增加瓶颈资源",
  prioritize_critical_tasks: "关键任务优先",
};

function emptyEntry(taskId: string): ProgressEntry {
  return {
    task_id: taskId,
    status: "not_started",
    percent_complete: 0,
    remaining_days: 0,
    remaining_days_source: "none",
    notes: "",
  };
}

export function PlanControlPanel({ scenario }: { scenario: ScenarioInput | null }) {
  const [summary, setSummary] = useState<PlanControlProjectSummary | null>(null);
  const [entries, setEntries] = useState<Record<string, ProgressEntry>>({});
  const [statusDate, setStatusDate] = useState(new Date().toISOString().slice(0, 10));
  const [submittedBy, setSubmittedBy] = useState("本地计划工程师");
  const [correctionReason, setCorrectionReason] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [resourceIncrementLimit, setResourceIncrementLimit] = useState(1);
  const [forecast, setForecast] = useState<ForecastSchedule | null>(null);
  const [adjustments, setAdjustments] = useState<AdjustmentComparisonResponse | null>(null);
  const [pendingAdoptionId, setPendingAdoptionId] = useState<string | null>(null);
  const [busy, setBusy] = useState<"loading" | "saving" | "forecast" | "adjustments" | "adopting" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function reload() {
    if (!scenario) return;
    setBusy("loading");
    setError(null);
    setMessage(null);
    try {
      const next = await getPlanControlProject(scenario.scenario_id);
      setSummary(next);
      setForecast(next.latest_forecast ?? null);
      const restored = Object.fromEntries((next.current_progress_snapshot?.entries ?? []).map((item) => [item.task_id, item]));
      setEntries(restored);
      if (next.current_progress_snapshot) setStatusDate(next.current_progress_snapshot.status_date);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "计划管控数据加载失败");
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    setSummary(null);
    setForecast(null);
    setAdjustments(null);
    setEntries({});
    void reload();
  }, [scenario?.scenario_id]);

  const tasks = summary?.active_plan?.generated_snapshot.schedule_input.tasks ?? [];
  const visibleTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const filtered = keyword
      ? tasks.filter((task) => `${task.name} ${task.structure_name} ${task.process_name}`.toLowerCase().includes(keyword))
      : tasks;
    return filtered.slice((page - 1) * 50, page * 50);
  }, [page, query, tasks]);
  const filteredTaskCount = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return keyword
      ? tasks.filter((task) => `${task.name} ${task.structure_name} ${task.process_name}`.toLowerCase().includes(keyword)).length
      : tasks.length;
  }, [query, tasks]);
  const pageCount = Math.max(1, Math.ceil(filteredTaskCount / 50));

  useEffect(() => {
    setPage(1);
  }, [query, scenario?.scenario_id]);

  function patchEntry(taskId: string, patch: Partial<ProgressEntry>) {
    setEntries((current) => {
      const base = current[taskId] ?? emptyEntry(taskId);
      const next = { ...base, ...patch };
      if (patch.status === "completed") next.percent_complete = 100;
      if (patch.status === "not_started") next.percent_complete = 0;
      return { ...current, [taskId]: next };
    });
  }

  async function handleSave() {
    const plan = summary?.active_plan;
    if (!plan) return;
    setBusy("saving");
    setError(null);
    setMessage(null);
    try {
      const response = await saveProgressSnapshot({
        plan_version_id: plan.plan_version_id,
        status_date: statusDate,
        entries: Object.values(entries),
        submitted_by: submittedBy,
        correction_reason: summary?.current_progress_snapshot ? correctionReason || null : null,
        expected_revision_no: summary?.current_progress_snapshot?.revision_no ?? null,
      });
      setSummary((current) => current ? { ...current, current_progress_snapshot: response.progress_snapshot, latest_forecast: null } : current);
      setForecast(null);
      setAdjustments(null);
      setCorrectionReason("");
      setMessage(`已保存 ${response.progress_snapshot.status_date} 的第 ${response.progress_snapshot.revision_no} 次进度快照。`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "实际进度保存失败");
    } finally {
      setBusy(null);
    }
  }

  async function handleForecast() {
    const plan = summary?.active_plan;
    const snapshot = summary?.current_progress_snapshot;
    if (!plan || !snapshot) return;
    setBusy("forecast");
    setError(null);
    setMessage(null);
    try {
      const next = await generateProgressForecast(plan.plan_version_id, snapshot.progress_snapshot_id);
      setForecast(next);
      setAdjustments(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "滚动预测失败");
    } finally {
      setBusy(null);
    }
  }

  async function handleAdjustments() {
    if (!forecast) return;
    setBusy("adjustments");
    setError(null);
    setMessage(null);
    try {
      const resourceTypes = summary?.active_plan?.resource_plan_snapshot.resource_pools
        .filter((pool) => pool.enabled && (pool.quantity ?? 0) > 0)
        .map((pool) => pool.type) ?? [];
      setAdjustments(await generateAdjustmentProposals(
        forecast.forecast_id,
        Object.fromEntries(resourceTypes.map((resourceType) => [resourceType, resourceIncrementLimit])),
      ));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "调整方案生成失败");
    } finally {
      setBusy(null);
    }
  }

  async function handleAdopt(proposalId: string) {
    const plan = summary?.active_plan;
    if (!plan) return;
    setBusy("adopting");
    setError(null);
    try {
      await adoptAdjustmentProposal(proposalId, {
        confirmed_by: submittedBy,
        adoption_reason: "采用滚动预测调整方案",
        source_plan_fingerprint: plan.input_fingerprint,
      });
      await reload();
      setAdjustments(null);
      setPendingAdoptionId(null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "调整方案采用失败");
      setBusy(null);
    }
  }

  if (!scenario) {
    return <section className="panel full"><PanelTitle title="计划执行与进度" subtitle="请先加载项目" /></section>;
  }

  return (
    <div className="plan-control-page">
      <section className="panel full">
        <PanelTitle
          title="计划执行与进度"
          subtitle={summary?.active_plan ? `${summary.active_plan.project_name} / 第 ${summary.active_plan.version_no} 版` : scenario.project.project_name}
          action={<button className="secondary" type="button" onClick={() => void reload()} disabled={busy !== null}><RefreshCw size={15} />刷新</button>}
        />
        {error && <div className="notice danger">{error}</div>}
        {message && <div className="notice success">{message}</div>}
        {busy === "loading" && <div className="plan-control-empty"><Loader2 className="spin" />正在加载计划版本…</div>}
        {!busy && !summary?.active_plan && (
          <div className="plan-control-empty">
            <History size={28} />
            <strong>尚未确认基准计划</strong>
            <span>请先在“AI 多方案比选”中完成方案求解，并把一个可行方案设为基准计划。</span>
          </div>
        )}
        {summary?.active_plan && (
          <>
            <div className="plan-version-strip">
              <div><span>当前执行版本</span><strong>第 {summary.active_plan.version_no} 版</strong></div>
              <div><span>版本类型</span><strong>{summary.active_plan.version_kind === "baseline" ? "基准计划" : "调整后执行计划"}</strong></div>
              <div><span>确认人</span><strong>{summary.active_plan.confirmed_by}</strong></div>
              <div><span>历史版本</span><strong>{summary.plan_versions.length}</strong></div>
            </div>
            <details className="plan-history">
              <summary>查看计划版本历史</summary>
              {summary.plan_versions.map((version) => (
                <div key={version.plan_version_id}>
                  <strong>第 {version.version_no} 版</strong>
                  <span>{version.status === "active" ? "当前生效" : "历史只读"}</span>
                  <span>{version.confirmed_by} / {new Date(version.confirmed_at).toLocaleString()}</span>
                  <span>{version.confirmation_reason}</span>
                </div>
              ))}
            </details>
          </>
        )}
      </section>

      {summary?.active_plan && (
        <section className="panel full">
          <PanelTitle title="实际进度反馈" subtitle="按状态日期填报；同日再次保存会形成可追溯修订" />
          <div className="plan-control-toolbar">
            <label>状态日期<input type="date" value={statusDate} onChange={(event) => setStatusDate(event.target.value)} /></label>
            <label>填报人<input value={submittedBy} onChange={(event) => setSubmittedBy(event.target.value)} /></label>
            {summary.current_progress_snapshot && <label>更正原因<input value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} placeholder="同日更正必填" /></label>}
            <label>筛选任务<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="结构物、任务或工艺" /></label>
            <button className="primary" type="button" onClick={() => void handleSave()} disabled={busy !== null}>
              {busy === "saving" ? <Loader2 className="spin" size={15} /> : <Save size={15} />}保存进度
            </button>
          </div>
          <div className="progress-entry-table-wrap">
            <table className="progress-entry-table">
              <thead><tr><th>任务</th><th>状态</th><th>完成比例</th><th>已完工程量</th><th>实际开始</th><th>实际完成</th><th>剩余工程量</th><th>实际工效</th><th>人工剩余天数</th><th>恢复日期</th><th>计算结果</th><th>原因/备注</th></tr></thead>
              <tbody>
                {visibleTasks.map((task) => {
                  const entry = entries[task.id] ?? emptyEntry(task.id);
                  return (
                    <tr key={task.id}>
                      <td><strong>{task.name}</strong><small>{task.structure_name} / {task.process_name}</small></td>
                      <td><select value={entry.status} onChange={(event) => patchEntry(task.id, { status: event.target.value as ProgressTaskStatus })}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td>
                      <td><input type="number" min="0" max="100" value={entry.percent_complete} disabled={entry.status === "completed" || entry.status === "not_started"} onChange={(event) => patchEntry(task.id, { percent_complete: Number(event.target.value) })} /></td>
                      <td><input type="number" min="0" max={task.quantity} value={entry.completed_quantity ?? ""} disabled={entry.status !== "in_progress"} onChange={(event) => patchEntry(task.id, { completed_quantity: event.target.value ? Number(event.target.value) : null })} /></td>
                      <td><input type="date" value={entry.actual_start_date ?? ""} disabled={!(["in_progress", "completed", "paused"] as ProgressTaskStatus[]).includes(entry.status)} onChange={(event) => patchEntry(task.id, { actual_start_date: event.target.value || null })} /></td>
                      <td><input type="date" value={entry.actual_finish_date ?? ""} disabled={entry.status !== "completed"} onChange={(event) => patchEntry(task.id, { actual_finish_date: event.target.value || null })} /></td>
                      <td><input type="number" min="0" max={task.quantity} value={entry.remaining_quantity ?? ""} disabled={entry.status !== "in_progress"} onChange={(event) => patchEntry(task.id, { remaining_quantity: event.target.value ? Number(event.target.value) : null })} /></td>
                      <td><input type="number" min="0" step="0.01" value={entry.actual_productivity ?? ""} disabled={entry.status !== "in_progress"} onChange={(event) => patchEntry(task.id, { actual_productivity: event.target.value ? Number(event.target.value) : null })} /></td>
                      <td><input type="number" min="0" value={entry.estimated_remaining_days ?? ""} disabled={!(["in_progress", "paused"] as ProgressTaskStatus[]).includes(entry.status)} onChange={(event) => patchEntry(task.id, { estimated_remaining_days: event.target.value ? Number(event.target.value) : null })} /></td>
                      <td><input type="date" value={entry.expected_resume_date ?? ""} disabled={entry.status !== "paused"} onChange={(event) => patchEntry(task.id, { expected_resume_date: event.target.value || null })} /></td>
                      <td><small>{entry.remaining_days_source === "none" ? "保存后计算" : `${entry.remaining_days} 天 / ${remainingSourceLabel(entry.remaining_days_source)}`}</small></td>
                      <td><input value={entry.reason ?? entry.notes} onChange={(event) => patchEntry(task.id, { reason: event.target.value, notes: event.target.value })} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="progress-pagination">
            <span>共 {filteredTaskCount} 项，每页 50 项</span>
            <button className="secondary" type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>上一页</button>
            <strong>{page} / {pageCount}</strong>
            <button className="secondary" type="button" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)}>下一页</button>
          </div>
          {(summary.current_progress_snapshot?.validation_messages.length ?? 0) > 0 && (
            <div className="notice warning">{summary.current_progress_snapshot?.validation_messages.map((item) => item.message).join("；")}</div>
          )}
        </section>
      )}

      {summary?.current_progress_snapshot && (
        <section className="panel full">
          <PanelTitle
            title="滚动预测与按期风险"
            subtitle={`进度快照：${summary.current_progress_snapshot.status_date} / 修订 ${summary.current_progress_snapshot.revision_no}`}
            action={<button className="primary" type="button" disabled={busy !== null} onClick={() => void handleForecast()}>{busy === "forecast" ? <Loader2 className="spin" size={15} /> : <Play size={15} />}生成滚动预测</button>}
          />
          {forecast ? (
            <>
              <div className={`forecast-risk-card ${forecast.risk_status}`}>
                {forecast.risk_status === "on_track" ? <CheckCircle2 /> : <AlertTriangle />}
                <div><strong>{riskLabel(forecast.risk_status)}</strong><span>预测完成：{String(forecast.metrics.predicted_finish_date ?? "不可用")}；可信度：{forecast.confidence}</span></div>
              </div>
              {forecast.status === "stale" && <div className="notice warning">该预测已因进度或计划输入变化而过期，请重新生成后再比较或采用调整方案。</div>}
              <div className="risk-evidence-list">{forecast.risk_evidence.map((item, index) => <div key={index}>{String(item.message ?? "风险证据")}</div>)}</div>
              <div className="forecast-task-state-table-wrap">
                <table className="forecast-task-state-table">
                  <thead><tr><th>任务</th><th>阶段</th><th>基准日期</th><th>实际日期</th><th>预测日期</th><th>偏差</th></tr></thead>
                  <tbody>{[...forecast.historical_tasks, ...forecast.predicted_tasks].map((item) => (
                    <tr key={`${item.state}-${item.task_id}`}><td>{item.task_name}</td><td>{item.state === "actual" ? "历史实际" : "未来预测"}</td><td>{dateRange(item.baseline_start_date, item.baseline_finish_date)}</td><td>{dateRange(item.actual_start_date, item.actual_finish_date)}</td><td>{dateRange(item.predicted_start_date, item.predicted_finish_date)}</td><td>{item.variance_days == null ? "-" : `${item.variance_days} 天`}</td></tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="adjustment-controls">
                <label>瓶颈资源单类最大增配<input type="number" min="0" max="20" value={resourceIncrementLimit} onChange={(event) => setResourceIncrementLimit(Number(event.target.value))} /></label>
                <button className="secondary" type="button" onClick={() => void handleAdjustments()} disabled={busy !== null || forecast.status === "stale"}>{busy === "adjustments" ? <Loader2 className="spin" size={15} /> : <Play size={15} />}比较调整方案</button>
              </div>
            </>
          ) : <div className="plan-control-empty compact">保存实际进度后生成状态日期之后的剩余计划预测。</div>}
        </section>
      )}

      {adjustments && (
        <section className="panel full">
          <PanelTitle title="调整方案比选" subtitle="每种策略独立求解；推荐结论来自确定性指标" />
          <div className="adjustment-grid">
            {adjustments.proposals.map((proposal) => (
              <article className={`adjustment-card ${proposal.recommended ? "recommended" : ""}`} key={proposal.proposal_id}>
                <header><strong>{strategyLabels[proposal.strategy]}</strong><span>{proposal.status}</span></header>
                <p>{proposal.explanation}</p>
                <dl><div><dt>预计完成</dt><dd>{String(proposal.metrics.predicted_finish_date ?? "不可用")}</dd></div><div><dt>工期偏差</dt><dd>{String(proposal.metrics.finish_variance_days ?? "-")} 天</dd></div><div><dt>迟延里程碑</dt><dd>{String(proposal.metrics.late_milestone_count ?? 0)}</dd></div><div><dt>新增资源</dt><dd>{String(proposal.metrics.added_resource_count ?? 0)}</dd></div><div><dt>演示成本变化</dt><dd>{String(proposal.metrics.demo_cost_change ?? 0)}</dd></div><div><dt>完工改善</dt><dd>{String(proposal.metrics.finish_improvement_days ?? 0)} 天</dd></div></dl>
                {diagnosticText(proposal.diagnostics, "error") && <div className="notice danger">{diagnosticText(proposal.diagnostics, "error")}</div>}
                {diagnosticText(proposal.diagnostics, "warning") && <div className="notice warning">{diagnosticText(proposal.diagnostics, "warning")}</div>}
                {proposal.recommended && <div className="notice success">系统推荐：{proposal.recommendation_reason}</div>}
                {pendingAdoptionId === proposal.proposal_id ? (
                  <div className="adoption-confirm">
                    <span>确认后将形成新活动版本，原版本保留为历史。</span>
                    <button className="primary" type="button" disabled={busy !== null} onClick={() => void handleAdopt(proposal.proposal_id)}>{busy === "adopting" ? <Loader2 className="spin" size={15} /> : <CheckCircle2 size={15} />}确认形成新版本</button>
                    <button className="secondary" type="button" disabled={busy !== null} onClick={() => setPendingAdoptionId(null)}>取消</button>
                  </div>
                ) : (
                  <button className="primary" type="button" disabled={busy !== null || proposal.status !== "feasible"} onClick={() => setPendingAdoptionId(proposal.proposal_id)}><CheckCircle2 size={15} />采用并形成新版本</button>
                )}
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function riskLabel(value: ForecastSchedule["risk_status"]): string {
  return { on_track: "预计按期", at_risk: "存在风险", late: "预计延期", insufficient_data: "数据不足" }[value];
}

function remainingSourceLabel(value: ProgressEntry["remaining_days_source"]): string {
  return { none: "无", baseline: "基准", calculated: "工程量/工效", manual: "人工" }[value];
}

function dateRange(start?: string | null, finish?: string | null): string {
  if (!start && !finish) return "-";
  return `${start ?? "?"} ～ ${finish ?? "?"}`;
}

function diagnosticText(
  diagnostics: Array<{ level: "error" | "warning" | "info"; message: string }>,
  level: "error" | "warning",
): string {
  return diagnostics.filter((item) => item.level === level).map((item) => item.message).join("；");
}
