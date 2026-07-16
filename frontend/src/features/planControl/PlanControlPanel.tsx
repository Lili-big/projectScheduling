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
import { GirderProgressEditor } from "../girderPlanning/GirderProgressEditor";
import {
  applyActualDateStatusDefaults,
  buildPlannedTaskDatesById,
  formatLocalDate,
  markActualDateFieldManual,
  recomputeSuggestedActualDates,
  type ActualDateSuggestionState,
} from "./progressDateDefaults";
import {
  deriveProgressWorkflowSteps,
  hasUnsavedProgressChanges,
  planControlErrorMessage,
  validateProgressEntries,
  type ProgressWorkflowStep,
} from "./progressWorkflow";
import type {
  AdjustmentComparisonResponse,
  CriticalNodeForecast,
  ForecastSchedule,
  GirderProgressImportPreview,
  GirderExecutionActual,
  GirderMachineActual,
  PassageActual,
  PlanControlProjectSummary,
  ProgressEntry,
  ProgressTaskStatus,
  ScenarioInput,
  Task,
  YardInventoryActual,
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

type ProgressQuantityView = {
  entry: ProgressEntry;
  status: "valid" | "derived" | "conflict" | "unavailable";
  message: string | null;
};

type ProgressQuantityDraft = {
  percentComplete?: string;
  completedQuantity?: string;
};

const percentTolerance = 0.011;

function roundQuantity(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function roundPercent(value: number): number {
  return Math.round(value * 100) / 100;
}

function validTotalQuantity(task: Task): boolean {
  return Number.isFinite(task.quantity) && task.quantity > 0;
}

function taskQuantityUnit(task: Task): string {
  return task.quantity_label.trim().match(/(m³|m²|m|个|根|块|段|联|榀|孔|座|台|处|套|节)$/)?.[1] ?? "";
}

function quantityTolerance(totalQuantity: number): number {
  return Math.max(0.000001, Math.abs(totalQuantity) * 0.000000001);
}

function deriveProgressQuantityView(task: Task, source?: ProgressEntry): ProgressQuantityView {
  const entry = source ? { ...source } : emptyEntry(task.id);
  if (!validTotalQuantity(task)) {
    return {
      entry: { ...entry, completed_quantity: null, remaining_quantity: null },
      status: "unavailable",
      message: "计划总工程量无效，数量联动已停用。",
    };
  }

  const totalQuantity = task.quantity;
  const suppliedCompleted = entry.completed_quantity;
  const suppliedRemaining = entry.remaining_quantity;
  let completedQuantity = suppliedCompleted;
  let remainingQuantity = suppliedRemaining;
  let derived = false;

  if (completedQuantity == null && remainingQuantity == null) {
    completedQuantity = totalQuantity * entry.percent_complete / 100;
    remainingQuantity = totalQuantity - completedQuantity;
    derived = source !== undefined;
  } else if (completedQuantity == null) {
    completedQuantity = totalQuantity - (remainingQuantity ?? 0);
    derived = true;
  } else if (remainingQuantity == null) {
    remainingQuantity = totalQuantity - completedQuantity;
    derived = true;
  }

  const normalizedCompletedQuantity = completedQuantity ?? totalQuantity * entry.percent_complete / 100;
  const normalizedRemainingQuantity = remainingQuantity ?? totalQuantity - normalizedCompletedQuantity;
  const expectedPercent = roundPercent((normalizedCompletedQuantity / totalQuantity) * 100);
  const hasConflict =
    !Number.isFinite(normalizedCompletedQuantity) ||
    !Number.isFinite(normalizedRemainingQuantity) ||
    normalizedCompletedQuantity < 0 ||
    normalizedRemainingQuantity < 0 ||
    normalizedCompletedQuantity > totalQuantity + quantityTolerance(totalQuantity) ||
    normalizedRemainingQuantity > totalQuantity + quantityTolerance(totalQuantity) ||
    Math.abs(entry.percent_complete - expectedPercent) > percentTolerance ||
    Math.abs(normalizedCompletedQuantity + normalizedRemainingQuantity - totalQuantity) > quantityTolerance(totalQuantity);

  return {
    entry: {
      ...entry,
      completed_quantity: roundQuantity(normalizedCompletedQuantity),
      remaining_quantity: roundQuantity(normalizedRemainingQuantity),
    },
    status: hasConflict ? "conflict" : derived ? "derived" : "valid",
    message: hasConflict
      ? "历史进度的比例、已完量和剩余量不一致，请更正后保存新修订。"
      : derived
        ? "历史进度缺少工程量，当前仅按已有值派生展示。"
        : null,
  };
}

function entryForStatus(task: Task, entry: ProgressEntry, status: ProgressTaskStatus): ProgressEntry {
  const totalQuantity = validTotalQuantity(task) ? task.quantity : null;
  if (status === "not_started") {
    return {
      ...entry,
      status,
      actual_start_date: null,
      actual_finish_date: null,
      percent_complete: 0,
      completed_quantity: totalQuantity === null ? null : 0,
      remaining_quantity: totalQuantity,
      actual_productivity: null,
      estimated_remaining_days: null,
      expected_resume_date: null,
      reason: null,
    };
  }
  if (status === "completed") {
    return {
      ...entry,
      status,
      percent_complete: 100,
      completed_quantity: totalQuantity,
      remaining_quantity: totalQuantity === null ? null : 0,
      actual_productivity: null,
      estimated_remaining_days: null,
      expected_resume_date: null,
      reason: null,
    };
  }
  if (entry.status === "not_started" || entry.status === "completed") {
    return {
      ...entry,
      status,
      actual_finish_date: null,
      percent_complete: 0,
      completed_quantity: totalQuantity === null ? null : 0,
      remaining_quantity: totalQuantity,
    };
  }
  return { ...entry, status, actual_finish_date: null };
}

export function PlanControlPanel({ scenario }: { scenario: ScenarioInput | null }) {
  const [summary, setSummary] = useState<PlanControlProjectSummary | null>(null);
  const [entries, setEntries] = useState<Record<string, ProgressEntry>>({});
  const [yardInventoryActuals, setYardInventoryActuals] = useState<YardInventoryActual[]>([]);
  const [girderExecutionActuals, setGirderExecutionActuals] = useState<GirderExecutionActual[]>([]);
  const [girderMachineActuals, setGirderMachineActuals] = useState<GirderMachineActual[]>([]);
  const [passageActuals, setPassageActuals] = useState<PassageActual[]>([]);
  const [quantityDrafts, setQuantityDrafts] = useState<Record<string, ProgressQuantityDraft>>({});
  const [actualDateSuggestions, setActualDateSuggestions] = useState<Record<string, ActualDateSuggestionState>>({});
  const [statusDate, setStatusDate] = useState(formatLocalDate);
  const [submittedBy, setSubmittedBy] = useState("本地计划工程师");
  const [correctionReason, setCorrectionReason] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [resourceIncrementLimit, setResourceIncrementLimit] = useState(1);
  const [forecast, setForecast] = useState<ForecastSchedule | null>(null);
  const [adjustments, setAdjustments] = useState<AdjustmentComparisonResponse | null>(null);
  const [pendingAdoptionId, setPendingAdoptionId] = useState<string | null>(null);
  const [busy, setBusy] = useState<"loading" | "saving" | "forecast" | "adjustments" | "adopting" | null>(null);
  const [failedStep, setFailedStep] = useState<"progress" | "reschedule" | null>(null);
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
      setYardInventoryActuals(next.current_progress_snapshot?.yard_inventory_actuals ?? []);
      setGirderExecutionActuals(next.current_progress_snapshot?.girder_execution_actuals ?? []);
      setGirderMachineActuals(next.current_progress_snapshot?.girder_machine_actuals ?? []);
      setPassageActuals(next.current_progress_snapshot?.passage_actuals ?? []);
      setQuantityDrafts({});
      setActualDateSuggestions({});
      setStatusDate(next.current_progress_snapshot?.status_date ?? formatLocalDate());
      setFailedStep(null);
    } catch (exc) {
      setError(planControlErrorMessage(exc, "load"));
    } finally {
      setBusy(null);
    }
  }

  useEffect(() => {
    setSummary(null);
    setForecast(null);
    setAdjustments(null);
    setEntries({});
    setYardInventoryActuals([]);
    setGirderExecutionActuals([]);
    setGirderMachineActuals([]);
    setPassageActuals([]);
    setQuantityDrafts({});
    setActualDateSuggestions({});
    setStatusDate(formatLocalDate());
    setFailedStep(null);
    void reload();
  }, [scenario?.scenario_id]);

  const tasks = summary?.active_plan?.generated_snapshot.schedule_input.tasks ?? [];
  const scheduledTasks = summary?.active_plan?.schedule_result_snapshot.tasks;
  const plannedDatesByTaskId = useMemo(
    () => buildPlannedTaskDatesById(scheduledTasks ?? []),
    [scheduledTasks],
  );
  const visibleTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const filtered = keyword
      ? tasks.filter((task) => `${task.id} ${task.name} ${task.structure_name} ${task.process_name}`.toLowerCase().includes(keyword))
      : tasks;
    return filtered.slice((page - 1) * 50, page * 50);
  }, [page, query, tasks]);
  const filteredTaskCount = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return keyword
      ? tasks.filter((task) => `${task.id} ${task.name} ${task.structure_name} ${task.process_name}`.toLowerCase().includes(keyword)).length
      : tasks.length;
  }, [query, tasks]);
  const pageCount = Math.max(1, Math.ceil(filteredTaskCount / 50));

  useEffect(() => {
    setPage(1);
  }, [query, scenario?.scenario_id]);

  const quantityIssueCount = useMemo(
    () => tasks.filter((task) => {
      const status = deriveProgressQuantityView(task, entries[task.id]).status;
      return status === "conflict" || status === "unavailable";
    }).length,
    [entries, tasks],
  );
  const progressIssues = useMemo(
    () => validateProgressEntries(entries, tasks, statusDate),
    [entries, statusDate, tasks],
  );
  const progressErrors = useMemo(
    () => progressIssues.filter((item) => item.severity === "error"),
    [progressIssues],
  );
  const progressWarnings = useMemo(
    () => progressIssues.filter((item) => item.severity === "warning"),
    [progressIssues],
  );
  const issuesByTask = useMemo(() => {
    const grouped: Record<string, typeof progressIssues> = {};
    for (const issue of progressIssues) (grouped[issue.task_id] ??= []).push(issue);
    return grouped;
  }, [progressIssues]);
  const hasUnsavedChanges = useMemo(
    () => hasUnsavedProgressChanges(entries, summary?.current_progress_snapshot ?? null, statusDate),
    [entries, statusDate, summary?.current_progress_snapshot],
  );
  const workflowSteps = useMemo(
    () => deriveProgressWorkflowSteps({
      activePlan: Boolean(summary?.active_plan),
      snapshot: summary?.current_progress_snapshot ?? null,
      forecast,
      dirty: hasUnsavedChanges,
      busy,
      failedStep,
    }),
    [busy, failedStep, forecast, hasUnsavedChanges, summary?.active_plan, summary?.current_progress_snapshot],
  );
  const currentForecast = hasUnsavedChanges ? null : forecast;

  function patchEntry(task: Task, patch: Partial<ProgressEntry>) {
    if (patch.status) {
      patchTaskStatus(task, patch.status);
      return;
    }
    setEntries((current) => {
      const base = deriveProgressQuantityView(task, current[task.id]).entry;
      const next = { ...base, ...patch };
      return { ...current, [task.id]: next };
    });
  }

  function patchTaskStatus(task: Task, status: ProgressTaskStatus) {
    setQuantityDrafts((current) => {
      const next = { ...current };
      delete next[task.id];
      return next;
    });
    const base = deriveProgressQuantityView(task, entries[task.id]).entry;
    const normalized = entryForStatus(task, base, status);
    const result = applyActualDateStatusDefaults(
      normalized,
      status,
      plannedDatesByTaskId[task.id],
      statusDate,
      formatLocalDate(),
      actualDateSuggestions[task.id],
    );
    setEntries((current) => ({ ...current, [task.id]: result.entry }));
    setActualDateSuggestions((current) => ({ ...current, [task.id]: result.suggestion }));
  }

  function patchActualDate(
    task: Task,
    field: "actual_start_date" | "actual_finish_date",
    value: string | null,
  ) {
    setActualDateSuggestions((current) => ({
      ...current,
      [task.id]: markActualDateFieldManual(current[task.id], field),
    }));
    patchEntry(task, field === "actual_start_date" ? { actual_start_date: value } : { actual_finish_date: value });
  }

  function patchStatusDate(nextStatusDate: string) {
    const today = formatLocalDate();
    const nextEntries = { ...entries };
    const nextSuggestions = { ...actualDateSuggestions };
    for (const [taskId, suggestion] of Object.entries(actualDateSuggestions)) {
      const currentEntry = entries[taskId];
      if (!currentEntry) continue;
      const result = recomputeSuggestedActualDates(
        currentEntry,
        suggestion,
        plannedDatesByTaskId[taskId],
        nextStatusDate,
        today,
      );
      nextEntries[taskId] = result.entry;
      nextSuggestions[taskId] = result.suggestion;
    }
    setStatusDate(nextStatusDate);
    setEntries(nextEntries);
    setActualDateSuggestions(nextSuggestions);
  }

  function applyGirderProgressImport(preview: GirderProgressImportPreview) {
    setYardInventoryActuals(preview.yard_inventory_actuals);
    setGirderExecutionActuals(preview.girder_execution_actuals);
    setGirderMachineActuals(preview.girder_machine_actuals);
    setPassageActuals(preview.passage_actuals);
    setMessage(`已导入架梁实绩：库存 ${preview.yard_inventory_actuals.length} 条、架梁 ${preview.girder_execution_actuals.length} 条、通道 ${preview.passage_actuals.length} 条。保存进度后才会进入滚动联算。`);
  }

  function patchPercentComplete(task: Task, rawValue: string) {
    setQuantityDrafts((current) => ({ ...current, [task.id]: { percentComplete: rawValue } }));
    if (rawValue === "") return;
    const value = Number(rawValue);
    if (!Number.isFinite(value)) return;
    const percentComplete = value;
    setEntries((current) => {
      const base = deriveProgressQuantityView(task, current[task.id]).entry;
      const completedQuantity = validTotalQuantity(task)
        ? roundQuantity(task.quantity * percentComplete / 100)
        : null;
      return {
        ...current,
        [task.id]: {
          ...base,
          percent_complete: roundPercent(percentComplete),
          completed_quantity: completedQuantity,
          remaining_quantity: completedQuantity === null ? null : roundQuantity(task.quantity - completedQuantity),
        },
      };
    });
  }

  function patchCompletedQuantity(task: Task, rawValue: string) {
    if (!validTotalQuantity(task)) return;
    setQuantityDrafts((current) => ({ ...current, [task.id]: { completedQuantity: rawValue } }));
    if (rawValue === "") return;
    const value = Number(rawValue);
    if (!Number.isFinite(value)) return;
    const completedQuantity = value;
    setEntries((current) => {
      const base = deriveProgressQuantityView(task, current[task.id]).entry;
      return {
        ...current,
        [task.id]: {
          ...base,
          percent_complete: roundPercent(completedQuantity / task.quantity * 100),
          completed_quantity: roundQuantity(completedQuantity),
          remaining_quantity: roundQuantity(task.quantity - completedQuantity),
        },
      };
    });
  }

  async function handleSave() {
    const plan = summary?.active_plan;
    if (!plan) return;
    if (progressErrors.length > 0) {
      setFailedStep("progress");
      setError(`有 ${progressErrors.length} 项阻断问题，请先按任务行提示修正后再保存。`);
      return;
    }
    const incompleteTaskId = Object.entries(quantityDrafts).find(([, draft]) =>
      draft.percentComplete === "" || draft.completedQuantity === ""
    )?.[0];
    if (incompleteTaskId) {
      const taskName = tasks.find((task) => task.id === incompleteTaskId)?.name ?? incompleteTaskId;
      setError(`任务 ${taskName} 的实际完成比例或实际已完工程量已清空，请补充有效值后再保存。`);
      setFailedStep("progress");
      return;
    }
    setBusy("saving");
    setError(null);
    setMessage(null);
    setFailedStep(null);
    try {
      const response = await saveProgressSnapshot({
        plan_version_id: plan.plan_version_id,
        status_date: statusDate,
        entries: Object.values(entries),
        submitted_by: submittedBy,
        correction_reason: summary?.current_progress_snapshot ? correctionReason || null : null,
        expected_revision_no: summary?.current_progress_snapshot?.revision_no ?? null,
        yard_inventory_actuals: yardInventoryActuals,
        girder_execution_actuals: girderExecutionActuals,
        girder_machine_actuals: girderMachineActuals,
        passage_actuals: passageActuals,
      });
      setEntries(Object.fromEntries(response.progress_snapshot.entries.map((item) => [item.task_id, item])));
      setQuantityDrafts({});
      setActualDateSuggestions({});
      setSummary((current) => current ? { ...current, current_progress_snapshot: response.progress_snapshot, latest_forecast: null } : current);
      setForecast(null);
      setAdjustments(null);
      setCorrectionReason("");
      setFailedStep(null);
      setMessage(`已保存 ${response.progress_snapshot.status_date} 的第 ${response.progress_snapshot.revision_no} 次进度快照。`);
    } catch (exc) {
      setFailedStep("progress");
      setError(planControlErrorMessage(exc, "save"));
    } finally {
      setBusy(null);
    }
  }

  async function handleForecast() {
    const plan = summary?.active_plan;
    const snapshot = summary?.current_progress_snapshot;
    if (!plan || !snapshot) return;
    if (hasUnsavedChanges) {
      setFailedStep("reschedule");
      setError("存在未保存的进度修改，请先保存进度快照，再锁定实绩并重排剩余计划。");
      return;
    }
    setBusy("forecast");
    setError(null);
    setMessage(null);
    setFailedStep(null);
    try {
      const next = await generateProgressForecast(plan.plan_version_id, snapshot.progress_snapshot_id);
      setForecast(next);
      setAdjustments(null);
      setFailedStep(next.status === "failed" || next.status === "infeasible" ? "reschedule" : null);
    } catch (exc) {
      setFailedStep("reschedule");
      setError(planControlErrorMessage(exc, "forecast"));
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
      setError(planControlErrorMessage(exc, "adjustments"));
    } finally {
      setBusy(null);
    }
  }

  function focusCriticalNode(node: CriticalNodeForecast) {
    const taskId = node.related_task_ids[0];
    if (!taskId) return;
    setQuery(taskId);
    setPage(1);
    window.setTimeout(() => document.getElementById("progress-entry-panel")?.scrollIntoView({ behavior: "smooth" }), 0);
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
            <div className="plan-integration-reference" aria-label="统一排程版本引用">
              <span>项目数据版本：{summary.active_plan.project_data_version_id ?? "未关联"}</span>
              <span>方案版本：{summary.active_plan.scenario_version_id ?? "未关联"}</span>
              <span>联合快照：{summary.active_plan.integrated_snapshot_id ?? "未关联"}</span>
            </div>
            {summary.active_plan.scenario_snapshot.girder_planning?.enabled && !summary.active_plan.integrated_snapshot_id && (
              <div className="notice warning">当前计划启用了架梁专项，但没有统一联合计算快照；请返回架梁专项完成联合计算后重新发布基线。</div>
            )}
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
        <section className="panel full progress-workflow-panel" aria-label="实际进度闭环步骤">
          <PanelTitle title="实际进度三步闭环" subtitle="先保存现场事实，再锁定实绩重排，最后查看关键节点风险并采取行动" />
          <div className="progress-workflow-steps">
            {workflowSteps.map((step, index) => (
              <article className={`progress-workflow-step ${step.status}`} key={step.step}>
                <div className="progress-workflow-step-index">{index + 1}</div>
                <div><strong>{step.title}</strong><span>{workflowStepStatusLabel(step)}</span><p>{step.message}</p></div>
              </article>
            ))}
          </div>
        </section>
      )}

      {summary?.active_plan && (
        <section className="panel full" id="progress-entry-panel">
          <PanelTitle title="实际进度反馈" subtitle="按状态日期填报；同日再次保存会形成可追溯修订" />
          <div className="plan-control-toolbar">
            <label>状态日期<input type="date" value={statusDate} onChange={(event) => patchStatusDate(event.target.value)} /></label>
            <label>填报人<input value={submittedBy} onChange={(event) => setSubmittedBy(event.target.value)} /></label>
            {summary.current_progress_snapshot && <label>更正原因<input value={correctionReason} onChange={(event) => setCorrectionReason(event.target.value)} placeholder="同日更正必填" /></label>}
            <label>筛选任务<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="结构物、任务或工艺" /></label>
            <button className="primary" type="button" onClick={() => void handleSave()} disabled={busy !== null || progressErrors.length > 0}>
              {busy === "saving" ? <Loader2 className="spin" size={15} /> : <Save size={15} />}保存进度
            </button>
          </div>
          <GirderProgressEditor
            yardActuals={yardInventoryActuals}
            executionActuals={girderExecutionActuals}
            machineActuals={girderMachineActuals}
            passageActuals={passageActuals}
            onImported={applyGirderProgressImport}
          />
          {quantityIssueCount > 0 && (
            <div className="notice warning">
              有 {quantityIssueCount} 个任务的计划总工程量不可用或历史进度数量不一致；请按行提示核验后再保存。
            </div>
          )}
          {progressErrors.length > 0 && <div className="notice danger">有 {progressErrors.length} 项阻断问题，请按任务行提示修正后保存。</div>}
          {progressWarnings.length > 0 && <div className="notice warning">有 {progressWarnings.length} 项数据质量提醒；可以保存现场事实，但可能无法生成确定性未来排程。</div>}
          {hasUnsavedChanges && summary.current_progress_snapshot && <div className="notice warning">当前表格存在未保存修改，上一轮重排和节点预警暂不作为当前结论。</div>}
          <div className="progress-entry-table-wrap">
            <table className="progress-entry-table">
              <thead><tr><th>任务</th><th>状态</th><th>总工程量</th><th>实际完成比例</th><th>实际已完工程量</th><th>剩余工程量</th><th>实际开始</th><th>实际完成</th><th>实际工效</th><th>人工剩余天数</th><th>恢复日期</th><th>计算结果</th><th>原因/备注</th></tr></thead>
              <tbody>
                {visibleTasks.map((task) => {
                  const quantityView = deriveProgressQuantityView(task, entries[task.id]);
                  const entry = quantityView.entry;
                  const quantityDraft = quantityDrafts[task.id];
                  const plannedDates = plannedDatesByTaskId[task.id];
                  const dateSuggestion = actualDateSuggestions[task.id];
                  const quantityUnit = taskQuantityUnit(task);
                  const physicalProgressEditable = !(["completed", "not_started"] as ProgressTaskStatus[]).includes(entry.status);
                  const quantityInputEnabled = physicalProgressEditable && validTotalQuantity(task);
                  const taskIssues = issuesByTask[task.id] ?? [];
                  return (
                    <tr key={task.id} className={taskIssues.some((item) => item.severity === "error") || quantityView.status === "conflict" ? "quantity-conflict-row" : undefined}>
                      <td>
                        <strong>{task.name}</strong>
                        <small>{task.structure_name} / {task.process_name}</small>
                        <small className={`planned-task-dates ${plannedDates?.isValid ? "valid" : "unavailable"}`}>
                          {plannedDates?.isValid
                            ? `计划：${plannedDates.plannedStartDate} 至 ${plannedDates.plannedFinishDate}`
                            : plannedDates?.message ?? "计划日期不可用，需人工填写实际日期。"}
                        </small>
                        {quantityView.message && <small className={`quantity-status ${quantityView.status}`}>{quantityView.message}</small>}
                        {taskIssues.map((issue) => <small className={`progress-entry-issue ${issue.severity}`} key={`${issue.code}-${issue.field}`}>{issue.message}</small>)}
                      </td>
                      <td><select value={entry.status} onChange={(event) => patchEntry(task, { status: event.target.value as ProgressTaskStatus })}>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td>
                      <td><span className="quantity-readonly total" title={`计划任务数量：${task.quantity}`}>{task.quantity_label}</span></td>
                      <td><div className="quantity-input-with-unit"><input type="number" min="0" max={physicalProgressEditable ? "99.99" : "100"} step="0.01" value={quantityDraft?.percentComplete ?? entry.percent_complete} disabled={!physicalProgressEditable} onChange={(event) => patchPercentComplete(task, event.target.value)} /><span>%</span></div></td>
                      <td><div className="quantity-input-with-unit"><input type="number" min="0" max={task.quantity} step="any" value={quantityDraft?.completedQuantity ?? entry.completed_quantity ?? ""} disabled={!quantityInputEnabled} onChange={(event) => patchCompletedQuantity(task, event.target.value)} />{quantityUnit && <span>{quantityUnit}</span>}</div></td>
                      <td><span className="quantity-readonly">{entry.remaining_quantity ?? "—"}{entry.remaining_quantity != null ? quantityUnit : ""}</span></td>
                      <td>
                        <div className="actual-date-field">
                          <input type="date" value={entry.actual_start_date ?? ""} disabled={!(["in_progress", "completed", "paused"] as ProgressTaskStatus[]).includes(entry.status)} onChange={(event) => patchActualDate(task, "actual_start_date", event.target.value || null)} />
                          {dateSuggestion?.actualStartSuggested && entry.actual_start_date && <small className="actual-date-suggestion" title="根据计划日期和状态日期生成，保存前可以修改">系统建议，保存前可修改</small>}
                        </div>
                      </td>
                      <td>
                        <div className="actual-date-field">
                          <input type="date" value={entry.actual_finish_date ?? ""} disabled={entry.status !== "completed"} onChange={(event) => patchActualDate(task, "actual_finish_date", event.target.value || null)} />
                          {dateSuggestion?.actualFinishSuggested && entry.actual_finish_date && <small className="actual-date-suggestion" title="根据计划日期和状态日期生成，保存前可以修改">系统建议，保存前可修改</small>}
                        </div>
                      </td>
                      <td><input type="number" min="0" step="0.01" value={entry.actual_productivity ?? ""} disabled={entry.status !== "in_progress"} onChange={(event) => patchEntry(task, { actual_productivity: event.target.value ? Number(event.target.value) : null })} /></td>
                      <td><input type="number" min="0" value={entry.estimated_remaining_days ?? ""} disabled={!(["in_progress", "paused"] as ProgressTaskStatus[]).includes(entry.status)} onChange={(event) => patchEntry(task, { estimated_remaining_days: event.target.value ? Number(event.target.value) : null })} /></td>
                      <td><input type="date" value={entry.expected_resume_date ?? ""} disabled={entry.status !== "paused"} onChange={(event) => patchEntry(task, { expected_resume_date: event.target.value || null })} /></td>
                      <td><small>{entry.remaining_days_source === "none" ? "保存后计算" : `${entry.remaining_days} 天 / ${remainingSourceLabel(entry.remaining_days_source)}`}</small></td>
                      <td><input value={entry.reason ?? entry.notes} onChange={(event) => patchEntry(task, { reason: event.target.value, notes: event.target.value })} /></td>
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

      {summary?.active_plan && (
        <section className="panel full">
          <PanelTitle
            title="锁定实绩、重排与关键节点预警"
            subtitle={summary.current_progress_snapshot ? `进度快照：${summary.current_progress_snapshot.status_date} / 修订 ${summary.current_progress_snapshot.revision_no}` : "保存有效进度快照后执行剩余计划重排"}
            action={<button className="primary" type="button" disabled={busy !== null || !summary.current_progress_snapshot || hasUnsavedChanges} onClick={() => void handleForecast()}>{busy === "forecast" ? <Loader2 className="spin" size={15} /> : <Play size={15} />}锁定实绩并重排剩余计划</button>}
          />
          {!summary.current_progress_snapshot && <div className="plan-control-empty compact">步骤 2 尚未解锁：请先完成并保存实际进度。</div>}
          {summary.current_progress_snapshot && hasUnsavedChanges && <div className="notice warning">当前进度存在未保存修改。保存后才能重新锁定实绩并重排；上一轮节点预警暂不作为当前结论。</div>}
          {currentForecast ? (
            <>
              <div className="forecast-execution-summary">
                {executionSummaryItems(currentForecast).map((item) => <div key={item.label}><span>{item.label}</span><strong>{item.value}</strong></div>)}
              </div>
              <div className={`forecast-risk-card ${currentForecast.risk_status}`}>
                {currentForecast.risk_status === "on_track" ? <CheckCircle2 /> : <AlertTriangle />}
                <div><strong>{riskLabel(currentForecast.risk_status)}</strong><span>预测完成：{String(currentForecast.metrics.predicted_finish_date ?? "不可用")}；可信度：{currentForecast.confidence}</span></div>
              </div>
              {currentForecast.status === "stale" && <div className="notice warning">该预测已因进度或计划输入变化而过期，请重新生成后再比较或采用调整方案。</div>}
              <div className="risk-evidence-list">{currentForecast.risk_evidence.map((item, index) => <div key={index}>{String(item.message ?? "风险证据")}</div>)}</div>
              <div className="critical-node-section">
                <div className="critical-node-heading"><div><strong>关键节点预警</strong><span>项目完工及强制里程碑优先展示；节点日期综合历史实际与未来预测。</span></div></div>
                {(currentForecast.critical_nodes?.length ?? 0) > 0 ? (
                  <div className="critical-node-table-wrap">
                    <table className="critical-node-table">
                      <thead><tr><th>节点</th><th>状态</th><th>目标日期</th><th>实际/预测日期</th><th>日期来源</th><th>偏差/缓冲</th><th>主要依据</th><th>行动</th></tr></thead>
                      <tbody>{currentForecast.critical_nodes.map((node) => (
                        <tr className={node.status} key={node.node_id}>
                          <td><strong>{node.name}</strong><small>{node.node_type === "project_finish" ? "项目完工" : node.mode === "hard" ? "强制里程碑" : "一般里程碑"}</small></td>
                          <td><span className={`critical-node-status ${node.status}`}>{criticalNodeStatusLabel(node.status)}</span></td>
                          <td>{node.target_date}</td><td>{node.evaluated_date ?? "无法判断"}</td><td>{criticalNodeDateSourceLabel(node.date_source)}</td>
                          <td>{criticalNodeVarianceLabel(node)}</td>
                          <td><div className="critical-node-evidence">{node.evidence.map((item, index) => <span key={`${item.type}-${index}`}>{item.message}</span>)}</div></td>
                          <td><button className="link-button" type="button" disabled={node.related_task_ids.length === 0} onClick={() => focusCriticalNode(node)}>定位任务</button></td>
                        </tr>
                      ))}</tbody>
                    </table>
                  </div>
                ) : <div className="plan-control-empty compact">该历史预测没有结构化节点结果，请基于当前快照重新重排。</div>}
              </div>
              <div className="forecast-task-state-table-wrap">
                <table className="forecast-task-state-table">
                  <thead><tr><th>任务</th><th>锁定/重排状态</th><th>基准日期</th><th>实际日期</th><th>预测日期</th><th>资源</th><th>偏差</th></tr></thead>
                  <tbody>{[...currentForecast.historical_tasks, ...currentForecast.predicted_tasks].map((item) => (
                    <tr key={`${item.state}-${item.task_id}`}><td>{item.task_name}</td><td>{executionStateLabel(item.execution_state, item.state)}</td><td>{dateRange(item.baseline_start_date, item.baseline_finish_date)}</td><td>{dateRange(item.actual_start_date, item.actual_finish_date)}</td><td>{dateRange(item.predicted_start_date, item.predicted_finish_date)}</td><td>{item.assigned_resource_type ?? "-"}</td><td>{item.variance_days == null ? "-" : `${item.variance_days} 天`}</td></tr>
                  ))}</tbody>
                </table>
              </div>
              <div className="adjustment-controls">
                <label>瓶颈资源单类最大增配<input type="number" min="0" max="20" value={resourceIncrementLimit} onChange={(event) => setResourceIncrementLimit(Number(event.target.value))} /></label>
                <button className="secondary" type="button" onClick={() => void handleAdjustments()} disabled={busy !== null || currentForecast.status !== "feasible"}>{busy === "adjustments" ? <Loader2 className="spin" size={15} /> : <Play size={15} />}查看调整方案</button>
              </div>
            </>
          ) : summary.current_progress_snapshot && !hasUnsavedChanges ? <div className="plan-control-empty compact">步骤 2 已解锁：点击“锁定实绩并重排剩余计划”，生成状态日期之后的当前趋势计划和关键节点预警。</div> : null}
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
  return { on_track: "预计按期", at_risk: "临近风险", late: "预计延期", insufficient_data: "无法判断" }[value];
}

function workflowStepStatusLabel(step: ProgressWorkflowStep): string {
  return {
    blocked: "未解锁",
    ready: "可执行",
    running: "执行中",
    complete: "已完成",
    failed: "需处理",
    stale: "待更新",
  }[step.status];
}

function executionSummaryItems(forecast: ForecastSchedule): Array<{ label: string; value: string | number }> {
  const summary = forecast.execution_summary;
  if (!summary) return [{ label: "历史预测", value: "请重新重排" }];
  return [
    { label: "已完成锁定", value: summary.completed_locked_count },
    { label: "进行中剩余", value: summary.in_progress_remaining_count },
    { label: "暂停待恢复", value: summary.paused_remaining_count },
    { label: "未开始重排", value: summary.not_started_future_count },
    { label: "取消待确认", value: summary.cancelled_excluded_count },
    { label: "资源与顺序", value: summary.resource_policy === "baseline_fixed" ? "原资源 / 既定顺序" : "瓶颈资源增配" },
  ];
}

function executionStateLabel(
  value: ForecastSchedule["historical_tasks"][number]["execution_state"],
  fallbackState: ForecastSchedule["historical_tasks"][number]["state"],
): string {
  if (!value) return fallbackState === "actual" ? "历史实际" : "未来预测";
  return {
    completed_locked: "已完成 · 实绩锁定",
    cancelled_excluded: "已取消 · 依赖待确认",
    in_progress_remaining: "进行中 · 仅排剩余工作",
    paused_remaining: "暂停 · 按恢复日期续排",
    not_started_future: "未开始 · 状态日后重排",
  }[value];
}

function criticalNodeStatusLabel(value: CriticalNodeForecast["status"]): string {
  return { on_track: "预计按期", at_risk: "临近风险", late: "预计延期", insufficient_data: "无法判断" }[value];
}

function criticalNodeDateSourceLabel(value: CriticalNodeForecast["date_source"]): string {
  return { actual: "历史实绩", predicted: "未来预测", combined: "实绩＋预测", unavailable: "不可用" }[value];
}

function criticalNodeVarianceLabel(node: CriticalNodeForecast): string {
  if (node.variance_days == null || node.buffer_days == null) return "-";
  if (node.variance_days > 0) return `延期 ${node.variance_days} 天`;
  if (node.buffer_days === 0) return "无剩余缓冲";
  return `缓冲 ${node.buffer_days} 天`;
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
