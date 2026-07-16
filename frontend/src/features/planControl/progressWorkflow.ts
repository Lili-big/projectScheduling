import type { ForecastSchedule, ProgressEntry, ProgressSnapshot, Task } from "../../contracts";

export type ProgressEntryIssue = {
  task_id: string;
  field: keyof ProgressEntry | null;
  severity: "error" | "warning";
  code: string;
  message: string;
};

export type ProgressWorkflowStepStatus = "blocked" | "ready" | "running" | "complete" | "failed" | "stale";

export type ProgressWorkflowStep = {
  step: "progress" | "reschedule" | "warning";
  status: ProgressWorkflowStepStatus;
  title: string;
  message: string;
  referenceId: string | null;
};

export type ProgressWorkflowState = {
  activePlan: boolean;
  snapshot: ProgressSnapshot | null;
  forecast: ForecastSchedule | null;
  dirty: boolean;
  busy: "loading" | "saving" | "forecast" | "adjustments" | "adopting" | null;
  failedStep?: "progress" | "reschedule" | null;
};

const quantityTolerance = (total: number) => Math.max(0.000001, Math.abs(total) * 0.000000001);

function isIsoLocalDate(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return false;
  const parsed = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return parsed.getUTCFullYear() === Number(match[1])
    && parsed.getUTCMonth() === Number(match[2]) - 1
    && parsed.getUTCDate() === Number(match[3]);
}

export function validateProgressEntry(entry: ProgressEntry, task: Task, statusDate: string): ProgressEntryIssue[] {
  const issues: ProgressEntryIssue[] = [];
  const error = (field: keyof ProgressEntry | null, code: string, message: string) => {
    issues.push({ task_id: task.id, field, severity: "error", code, message });
  };
  const warning = (field: keyof ProgressEntry | null, code: string, message: string) => {
    issues.push({ task_id: task.id, field, severity: "warning", code, message });
  };

  if (!isIsoLocalDate(statusDate)) {
    error(null, "invalid_status_date", "状态日期格式无效。");
    return issues;
  }
  for (const [field, value] of [
    ["actual_start_date", entry.actual_start_date],
    ["actual_finish_date", entry.actual_finish_date],
  ] as const) {
    if (value && value > statusDate) error(field, "actual_date_after_status", "实际日期不能晚于状态日期。");
  }
  if (entry.actual_start_date && entry.actual_finish_date && entry.actual_finish_date < entry.actual_start_date) {
    error("actual_finish_date", "finish_before_start", "实际完成日期不能早于实际开始日期。");
  }

  if (Number.isFinite(task.quantity) && task.quantity > 0) {
    const completed = entry.completed_quantity;
    const remaining = entry.remaining_quantity;
    if (completed != null && (completed < 0 || completed > task.quantity + quantityTolerance(task.quantity))) {
      error("completed_quantity", "completed_quantity_out_of_range", "实际已完工程量超出计划总工程量。");
    }
    if (remaining != null && (remaining < 0 || remaining > task.quantity + quantityTolerance(task.quantity))) {
      error("remaining_quantity", "remaining_quantity_out_of_range", "剩余工程量超出计划总工程量。");
    }
    if (completed != null && remaining != null && Math.abs(completed + remaining - task.quantity) > quantityTolerance(task.quantity)) {
      error(null, "quantity_sum_mismatch", "实际已完工程量与剩余工程量之和必须等于计划总工程量。");
    }
  }

  if (entry.status === "not_started") {
    if (entry.actual_start_date || entry.actual_finish_date || entry.percent_complete !== 0) {
      error(null, "not_started_has_actual", "未开始任务不能填写实际日期或完成比例。");
    }
  } else if (entry.status === "in_progress") {
    if (!entry.actual_start_date) error("actual_start_date", "missing_actual_start", "进行中任务必须填写实际开始日期。");
    if (!(entry.percent_complete > 0 && entry.percent_complete < 100)) {
      error("percent_complete", "invalid_in_progress_percent", "进行中任务完成比例必须大于 0 且小于 100%。");
    }
    const canCalculate = entry.remaining_quantity != null && entry.actual_productivity != null && entry.actual_productivity > 0;
    if (!canCalculate && !(entry.estimated_remaining_days != null && entry.estimated_remaining_days > 0)) {
      error("estimated_remaining_days", "missing_remaining_duration", "进行中任务缺少实际工效或人工预计剩余天数。");
    }
  } else if (entry.status === "completed") {
    if (!entry.actual_start_date) error("actual_start_date", "missing_actual_start", "已完成任务必须填写实际开始日期。");
    if (!entry.actual_finish_date) error("actual_finish_date", "missing_actual_finish", "已完成任务必须填写实际完成日期。");
    if (entry.percent_complete !== 100) error("percent_complete", "invalid_completed_percent", "已完成任务完成比例必须为 100%。");
  } else if (entry.status === "paused") {
    if (!entry.actual_start_date) error("actual_start_date", "missing_actual_start", "暂停任务必须填写实际开始日期。");
    if (!(entry.reason ?? "").trim()) error("reason", "missing_pause_reason", "暂停任务必须填写暂停原因。");
    if (!(entry.estimated_remaining_days != null && entry.estimated_remaining_days > 0)) {
      error("estimated_remaining_days", "missing_remaining_duration", "暂停任务必须填写人工预计剩余天数。");
    }
    if (!entry.expected_resume_date) {
      warning("expected_resume_date", "missing_resume_date", "尚未填写恢复日期；可以保存现场事实，但暂不能生成确定性未来排程。");
    } else if (entry.expected_resume_date < statusDate) {
      error("expected_resume_date", "resume_before_status", "恢复日期不能早于状态日期。");
    }
  } else if (entry.status === "cancelled") {
    if (entry.percent_complete >= 100) error("percent_complete", "invalid_cancelled_percent", "取消任务完成比例必须小于 100%。");
    if (!(entry.reason ?? "").trim()) error("reason", "missing_cancel_reason", "取消任务必须填写取消原因。");
  }
  return issues;
}

export function validateProgressEntries(
  entries: Record<string, ProgressEntry>,
  tasks: Task[],
  statusDate: string,
): ProgressEntryIssue[] {
  return tasks.flatMap((task) => validateProgressEntry(entries[task.id] ?? emptyEntry(task.id), task, statusDate));
}

export function hasUnsavedProgressChanges(
  entries: Record<string, ProgressEntry>,
  snapshot: ProgressSnapshot | null,
  statusDate: string,
): boolean {
  if (!snapshot) return Object.keys(entries).length > 0;
  if (snapshot.status_date !== statusDate) return true;
  const current = Object.values(entries).sort((a, b) => a.task_id.localeCompare(b.task_id));
  const saved = [...snapshot.entries].sort((a, b) => a.task_id.localeCompare(b.task_id));
  return JSON.stringify(current) !== JSON.stringify(saved);
}

export function deriveProgressWorkflowSteps(state: ProgressWorkflowState): ProgressWorkflowStep[] {
  const snapshot = state.snapshot;
  const forecast = state.forecast;
  const progressStatus: ProgressWorkflowStepStatus = !state.activePlan
    ? "blocked"
    : state.busy === "saving"
      ? "running"
      : state.failedStep === "progress"
        ? "failed"
        : snapshot && !state.dirty
          ? "complete"
          : "ready";
  const rescheduleStatus: ProgressWorkflowStepStatus = !snapshot
    ? "blocked"
    : state.dirty
      ? "stale"
      : state.busy === "forecast"
        ? "running"
        : state.failedStep === "reschedule" || forecast?.status === "failed" || forecast?.status === "infeasible"
          ? "failed"
          : forecast?.status === "stale"
            ? "stale"
            : forecast
              ? "complete"
              : "ready";
  const warningStatus: ProgressWorkflowStepStatus = !forecast
    ? "blocked"
    : state.dirty || forecast.status === "stale"
      ? "stale"
      : forecast.status === "feasible"
        ? "complete"
        : "failed";
  return [
    {
      step: "progress",
      status: progressStatus,
      title: "保存实际进度",
      message: progressStatus === "complete"
        ? `已形成 ${snapshot?.status_date} / 修订 ${snapshot?.revision_no} 的进度快照。`
        : progressStatus === "blocked"
          ? "请先确认一个活动基准计划。"
          : state.dirty && snapshot
            ? "存在未保存修改，后续结论暂不更新。"
            : "填写并保存状态日期下的现场实绩。",
      referenceId: snapshot?.progress_snapshot_id ?? null,
    },
    {
      step: "reschedule",
      status: rescheduleStatus,
      title: "锁定实绩并重排剩余计划",
      message: !snapshot
        ? "保存有效进度快照后解锁。"
        : state.dirty
          ? "请先保存本次进度修改。"
          : forecast?.status === "failed" || forecast?.status === "infeasible"
            ? "当前快照未获得可执行的剩余计划，请根据诊断补充数据后重试。"
            : forecast
              ? "已基于当前快照完成剩余计划重排。"
            : "锁定历史实绩，按当前资源和既定顺序预测剩余计划。",
      referenceId: forecast?.forecast_id ?? null,
    },
    {
      step: "warning",
      status: warningStatus,
      title: "查看关键节点预警与调整",
      message: !forecast
        ? "完成剩余计划重排后生成节点预警。"
        : warningStatus === "stale"
          ? "进度输入已变化，请重新重排。"
          : "查看项目完工和强制里程碑风险，并进入调整方案。",
      referenceId: forecast?.forecast_id ?? null,
    },
  ];
}

export function planControlErrorMessage(error: unknown, action: "load" | "save" | "forecast" | "adjustments"): string {
  const fallback = {
    load: "计划管控数据加载失败。",
    save: "实际进度保存失败，尚未形成进度快照。",
    forecast: "剩余计划重排失败，未生成新的关键节点结论。",
    adjustments: "调整方案生成失败。",
  }[action];
  if (!(error instanceof Error)) return fallback;
  const message = error.message.trim();
  if (/failed to fetch|networkerror|network request failed/i.test(message)) {
    return `${fallback} 后端服务当前不可达，请检查服务后重试。`;
  }
  if (/修订|已被更新|冲突/.test(message)) return `${message} 请刷新后基于最新修订继续。`;
  return message || fallback;
}

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
