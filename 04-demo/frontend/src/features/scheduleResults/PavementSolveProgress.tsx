import { useEffect, useState } from "react";
import type { PavementLiveStatus } from "../../contracts";

export type PavementProgress = { startedAt: number | null; timeBudgetSeconds: number | null; goal?: "makespan" | "idle" };

export function pavementProgressText(hasPlan: boolean, waited: number, budget: number | null, goal: "makespan" | "idle" = "makespan") {
  if (budget != null && waited >= budget) return "正在等待计算结果收尾";
  if (goal === "idle") return "正在保持工期上限、减少资源窝工，发现改善即更新";
  return hasPlan ? "持续优化中，发现更短工期即更新" : "正在寻找可行方案，找到后立即显示";
}

export function PavementSolveProgress({ status, progress, hasPlan, improvementCount }: {
  status?: PavementLiveStatus; progress?: PavementProgress; hasPlan: boolean; improvementCount?: number | null;
}) {
  const startedAt = progress?.startedAt ?? null;
  const [now, setNow] = useState(() => performance.now());
  useEffect(() => {
    if (status !== "running" || startedAt == null) return;
    setNow(performance.now());
    const timer = window.setInterval(() => setNow(performance.now()), 250);
    return () => window.clearInterval(timer);
  }, [status, startedAt]);
  if (status !== "running") return null;
  const waited = startedAt == null ? 0 : Math.max(0, (now - startedAt) / 1000);
  const budget = progress?.timeBudgetSeconds ?? null;
  return <div className="pavement-solve-progress" aria-label="求解进行中">
    <span className="pavement-activity" aria-hidden="true" />
    <div><strong role="status">{pavementProgressText(hasPlan, waited, budget, progress?.goal)}</strong>
      <div className="pavement-progress-facts">
        {startedAt != null && <span>已等待 {waited.toFixed(1)} 秒</span>}
        {budget != null && <span>计算预算 {budget} 秒</span>}
        {improvementCount != null && <span>已改善 {improvementCount} 次</span>}
      </div>
    </div>
  </div>;
}
