import type { ScheduleResult, ValidationMessage } from "../types/scheduler";
import { scheduleStatusLabels } from "./labels";

export type MetricTone = "ok" | "warn" | "danger" | "neutral";

export type PlanStatusDisplay = {
  label: string;
  tone: MetricTone;
  hint?: string;
  diagnostic?: ValidationMessage;
};

type TargetAchievementSummary = {
  businessSuccess: boolean;
  targetStatus: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function targetAchievementFromResult(result: ScheduleResult): TargetAchievementSummary | null {
  const raw = result.stats.target_achievement ?? result.objective_breakdown.target_achievement;
  if (!isRecord(raw)) return null;
  return {
    businessSuccess: Boolean(raw.business_success),
    targetStatus: typeof raw.target_status === "string" ? raw.target_status : "",
  };
}

function optimalityHint(result: ScheduleResult): string | undefined {
  if (result.status !== "FEASIBLE") return undefined;
  const target = targetAchievementFromResult(result);
  if (target?.businessSuccess && target.targetStatus !== "unconfirmed") {
    return "目标已达成，未证明最优";
  }
  return "未证明最优";
}

export function derivePlanStatus(result: ScheduleResult | null): PlanStatusDisplay {
  if (!result) {
    return { label: "未求解", tone: "neutral" };
  }

  const isSolved = result.status === "OPTIMAL" || result.status === "FEASIBLE";
  const lateMilestones = result.milestone_results.filter((milestone) => milestone.lateness_days > 0);
  const hardLateCount = lateMilestones.filter((milestone) => milestone.mode === "hard").length;
  const softLateCount = lateMilestones.filter((milestone) => milestone.mode === "soft").length;

  if (!isSolved) {
    return {
      label: scheduleStatusLabels[result.status],
      tone: result.status === "UNKNOWN" ? "warn" : "danger",
      hint: hardLateCount > 0 ? "硬里程碑未满足" : undefined,
      diagnostic: hardLateCount > 0
        ? {
            level: "error",
            message: `工期不满足硬里程碑要求：${hardLateCount} 个强制里程碑节点未满足。`,
            subject_id: "plan-status-hard-milestone",
          }
        : undefined,
    };
  }

  const solveMode = typeof result.objective_breakdown.solve_mode === "string"
    ? result.objective_breakdown.solve_mode
    : result.stats.solve_mode;
  const isShortestDurationMode = !solveMode || solveMode === "shortest_duration_fixed_resources";
  const proofHint = optimalityHint(result);

  if (!isShortestDurationMode) {
    return { label: scheduleStatusLabels[result.status], tone: "ok", hint: proofHint };
  }

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
      hint: proofHint ? `弱节点不满足，${proofHint}` : "弱节点不满足",
      diagnostic: {
        level: "warning",
        message: `弱节点不满足：${softLateCount} 个提醒里程碑节点未满足。`,
        subject_id: "plan-status-soft-milestone",
      },
    };
  }

  return { label: "可行", tone: "ok", hint: proofHint ?? "里程碑均满足" };
}
