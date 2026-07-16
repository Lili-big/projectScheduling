import type { CriticalNodeForecast, ForecastSchedule, ProgressEntry } from "../../contracts";
import type { ProgressWorkflowStep } from "./progressWorkflow";

export function riskLabel(value: ForecastSchedule["risk_status"]): string {
  return { on_track: "预计按期", at_risk: "临近风险", late: "预计延期", insufficient_data: "无法判断" }[value];
}

export function workflowStepStatusLabel(step: ProgressWorkflowStep): string {
  return { blocked: "未解锁", ready: "可执行", running: "执行中", complete: "已完成", failed: "需处理", stale: "待更新" }[step.status];
}

export function executionSummaryItems(forecast: ForecastSchedule): Array<{ label: string; value: string | number }> {
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

export function executionStateLabel(
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

export function criticalNodeStatusLabel(value: CriticalNodeForecast["status"]): string {
  return { on_track: "预计按期", at_risk: "临近风险", late: "预计延期", insufficient_data: "无法判断" }[value];
}

export function criticalNodeDateSourceLabel(value: CriticalNodeForecast["date_source"]): string {
  return { actual: "历史实绩", predicted: "未来预测", combined: "实绩＋预测", unavailable: "不可用" }[value];
}

export function criticalNodeVarianceLabel(node: CriticalNodeForecast): string {
  if (node.variance_days == null || node.buffer_days == null) return "-";
  if (node.variance_days > 0) return `延期 ${node.variance_days} 天`;
  if (node.buffer_days === 0) return "无剩余缓冲";
  return `缓冲 ${node.buffer_days} 天`;
}

export function remainingSourceLabel(value: ProgressEntry["remaining_days_source"]): string {
  return { none: "无", baseline: "基准", calculated: "工程量/工效", manual: "人工" }[value];
}

export function dateRange(start?: string | null, finish?: string | null): string {
  if (!start && !finish) return "-";
  return `${start ?? "?"} ～ ${finish ?? "?"}`;
}
