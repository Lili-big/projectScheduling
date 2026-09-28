import type { ScenarioSolveResult } from "./scheduler";

export type PavementSolveEvent = { sequence: number; elapsed_seconds: number } & (
  | { type: "started"; time_budget_seconds: number }
  | { type: "solution"; solution_kind: "initial" | "improvement"; solved: ScenarioSolveResult }
  | { type: "complete"; solved: ScenarioSolveResult }
  | { type: "error"; code: string; message: string }
);
export type PavementLiveStatus = "idle" | "running" | "complete" | "interrupted";
