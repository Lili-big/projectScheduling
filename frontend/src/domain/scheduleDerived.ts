import type { ScheduleResult, ValidationMessage } from "../types/scheduler";
import { scheduleStatusLabels } from "./labels";

export type MetricTone = "ok" | "warn" | "danger" | "neutral";

export type PlanStatusDisplay = {
  label: string;
  tone: MetricTone;
  hint?: string;
  diagnostic?: ValidationMessage;
};

export function derivePlanStatus(result: ScheduleResult | null): PlanStatusDisplay {
  if (!result) {
    return { label: "未求解", tone: "neutral" };
  }

  const isSolved = result.status === "OPTIMAL" || result.status === "FEASIBLE";
  if (!isSolved) {
    return {
      label: scheduleStatusLabels[result.status],
      tone: result.status === "UNKNOWN" ? "warn" : "danger",
    };
  }

  const solveMode = typeof result.objective_breakdown.solve_mode === "string"
    ? result.objective_breakdown.solve_mode
    : result.stats.solve_mode;
  const isShortestDurationMode = !solveMode || solveMode === "shortest_duration_fixed_resources";

  if (!isShortestDurationMode) {
    return { label: scheduleStatusLabels[result.status], tone: "ok" };
  }

  const lateMilestones = result.milestone_results.filter((milestone) => milestone.lateness_days > 0);
  const hardLateCount = lateMilestones.filter((milestone) => milestone.mode === "hard").length;
  const softLateCount = lateMilestones.filter((milestone) => milestone.mode === "soft").length;

  if (hardLateCount > 0) {
    return {
      label: "不可行",
      tone: "danger",
      hint: "硬里程碑未满足",
      diagnostic: {
        level: "error",
        message: `工期不满足硬里程碑要求：${hardLateCount} 个强制里程碑节点未满足。`,
        subject_id: "plan-status-hard-milestone",
      },
    };
  }

  if (softLateCount > 0) {
    return {
      label: "可行",
      tone: "warn",
      hint: "弱节点不满足",
      diagnostic: {
        level: "warning",
        message: `弱节点不满足：${softLateCount} 个提醒里程碑节点未满足。`,
        subject_id: "plan-status-soft-milestone",
      },
    };
  }

  return { label: "可行", tone: "ok", hint: "里程碑均满足" };
}
