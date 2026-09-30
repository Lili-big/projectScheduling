import type { ScenarioInput, ScenarioSolveResult, PavementSolveEvent, PavementLiveStatus } from "../../contracts";
import { scenarioFingerprintForSolve } from "./scenarioWorkflow";

type ScenarioNormalizer = (scenario: ScenarioInput) => ScenarioInput;
type ScenarioSolver = (scenario: ScenarioInput, workpointId?: string | null) => Promise<ScenarioSolveResult>;

export type PavementLiveState = {
  status: PavementLiveStatus;
  solved: ScenarioSolveResult | null;
  error: string | null;
  sequence: number;
  elapsed: number;
  timeBudgetSeconds: number | null;
};
type PavementStream = (scenario: ScenarioInput, scope: string | null, publish: (event: unknown) => void, signal: AbortSignal) => Promise<void>;

type PavementIdleStream = (scenario: ScenarioInput, scope: string | null, baseline: ScenarioSolveResult,
  publish: (event: unknown) => void, signal: AbortSignal, timeBudgetSeconds?: number) => Promise<void>;

export function parsePavementSolveBudget(draft: string): number | null {
  const seconds = Number(draft);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export function canOptimizePavementIdle(solved: ScenarioSolveResult | null, matchesInput: boolean, busy: boolean) {
  return !!(matchesInput && !busy && solved && ["FEASIBLE", "OPTIMAL"].includes(solved.result.status)
    && solved.result.objective_days && solved.result.pavement_summary?.input_fingerprint
    && solved.generated?.schedule_input?.pavement_handover_scope?.pending_policy === "per_fleet_last");
}

export function createPavementSolveController(stream: PavementStream, idleStream?: PavementIdleStream) {
  let token = 0;
  let controller: AbortController | null = null;
  return {
    cancel() { token++; controller?.abort(); controller = null; },
    async request(scenario: ScenarioInput, scope: string | null, publish: (state: PavementLiveState) => void,
      baseline?: ScenarioSolveResult, timeBudgetSeconds?: number) {
      let requestScenario = scenario;
      if (timeBudgetSeconds !== undefined) {
        if (!Number.isFinite(timeBudgetSeconds) || timeBudgetSeconds <= 0) throw new Error("请输入大于 0 的有效秒数。");
        // Budget changes do not alter the business input or the baseline's full identity.
        const originalBudget = baseline?.generated?.schedule_input?.time_limit_seconds;
        if (baseline && (originalBudget == null || !Number.isFinite(originalBudget) || originalBudget <= 0)) {
          throw new Error("基准方案缺少有效求解时限，请重新求解。");
        }
        requestScenario = {...scenario, time_limit_seconds: baseline ? originalBudget! : timeBudgetSeconds};
      }
      const current = ++token;
      controller?.abort();
      const requestController = new AbortController();
      controller = requestController;
      let terminal = false, receivedSolution = false;
      let idleIdentity: string | null = null;
      const cap = baseline?.result.objective_days;
      const inputFingerprint = baseline?.result.pavement_summary?.input_fingerprint;
      const taskTiming = (plan: ScenarioSolveResult) => JSON.stringify((plan.result.tasks ?? []).map(t =>
        [t.id, t.start_offset, t.end_offset, t.assigned_resource_id]).sort((a,b) => String(a[0]).localeCompare(String(b[0]))));
      let state: PavementLiveState = { status: "running", solved: baseline ?? null, error: null, sequence: 0, elapsed: 0, timeBudgetSeconds: null };
      publish(state);
      try {
        const receive = (raw: unknown) => {
          if (current !== token) return;
          const event = raw as PavementSolveEvent;
          if (!event || !Number.isInteger(event.sequence) || event.sequence <= state.sequence || terminal
            || !Number.isFinite(event.elapsed_seconds) || event.elapsed_seconds < state.elapsed
            || (state.sequence === 0 && event.type !== "started")) throw new Error("实时求解事件顺序异常，本次优化未完成。");
          state = { ...state, sequence: event.sequence, elapsed: event.elapsed_seconds };
          if (event.type === "started") {
            if (event.sequence !== 1 || !Number.isFinite(event.time_budget_seconds) || event.time_budget_seconds <= 0
              || timeBudgetSeconds !== undefined && event.time_budget_seconds !== timeBudgetSeconds) {
              throw new Error("实时求解启动数据无效。");
            }
            state = { ...state, timeBudgetSeconds: event.time_budget_seconds };
          } else if (event.type === "solution" || event.type === "complete") {
            const solved = event.solved;
            if (!solved?.result) throw new Error("实时求解方案数据不完整。");
            const valid = solved.result.status === "FEASIBLE" || solved.result.status === "OPTIMAL";
            const days = solved.result.objective_days;
            const previous = state.solved?.result.objective_days;
            if (valid && (!Number.isInteger(days) || days == null || days <= 0
              || !baseline && previous != null && (days > previous || event.type === "solution" && days === previous))) {
              throw new Error("实时方案工期异常，保留上一次合法方案。");
            }
            if (valid && baseline) {
              const meta = solved.result.pavement_idle_optimization;
              const nonnegative = (n: unknown) => typeof n === "number" && Number.isInteger(n) && n >= 0;
              if (!meta || !cap || !days || days > cap || meta.makespan_cap_days !== cap
                || meta.goal !== "min_idle_with_makespan_cap" || meta.metric !== "fleet_internal_idle_v1"
                || meta.baseline_input_fingerprint !== inputFingerprint
                || solved.result.pavement_summary?.input_fingerprint !== inputFingerprint
                || solved.result.pavement_summary?.construction_finish_offset !== days
                || ![meta.baseline_idle_days,meta.final_idle_days,meta.improvement_idle_days,
                    meta.baseline_transfer_days,meta.final_transfer_days].every(nonnegative)
                || meta.final_idle_days > meta.baseline_idle_days
                || meta.improvement_idle_days !== meta.baseline_idle_days - meta.final_idle_days
                || event.type === "solution" && meta.proved_optimal) {
                throw new Error("窝工方案指标或工期上限异常，保留上一次合法方案。");
              }
              const identity = JSON.stringify([cap,inputFingerprint,meta.baseline_idle_days,meta.baseline_transfer_days]);
              if (!receivedSolution) {
                if (event.type !== "solution" || meta.final_idle_days !== meta.baseline_idle_days
                  || days !== cap || taskTiming(solved) !== taskTiming(baseline)) throw new Error("窝工优化基准不一致。");
                const known = baseline.result.pavement_idle_optimization;
                if (known && (known.final_idle_days !== meta.baseline_idle_days || known.final_transfer_days !== meta.baseline_transfer_days)) {
                  throw new Error("窝工优化基准指标不一致。");
                }
                idleIdentity = identity;
              } else {
                const lastIdle = state.solved?.result.pavement_idle_optimization?.final_idle_days;
                if (identity !== idleIdentity || lastIdle == null || meta.final_idle_days > lastIdle
                  || event.type === "solution" && meta.final_idle_days === lastIdle) throw new Error("窝工方案未改善或基准已变化。");
              }
            }
            if (event.type === "solution") {
              if (!valid || solved.result.status !== "FEASIBLE"
                || event.solution_kind !== (receivedSolution ? "improvement" : "initial")) throw new Error("实时方案状态无效。");
              receivedSolution = true;
              state = { ...state, solved };
            } else {
              terminal = true;
              if (!valid && state.solved) {
                state = { ...state, status: "interrupted", error: solved.diagnostics.map(d => d.message).join("；") || "最终结果与已收到方案不一致，优化未完成。" };
              } else state = { ...state, status: "complete", solved };
            }
          } else if (event.type === "error") {
            terminal = true;
            state = { ...state, status: "interrupted", error: event.message || "本次优化失败。" };
          } else throw new Error("无法识别实时求解事件。");
          publish(state);
        };
        if (baseline) {
          if (!idleStream) throw new Error("窝工优化接口不可用。");
          await idleStream(requestScenario, scope, baseline, receive, requestController.signal, timeBudgetSeconds);
        } else await stream(requestScenario, scope, receive, requestController.signal);
        if (current !== token) return;
        if (!terminal) throw new Error("实时连接已中断，本次优化未完成；保留最后收到的方案。");
      } catch (reason) {
        if (current === token) {
          state = { ...state, status: "interrupted", error: reason instanceof Error ? reason.message : String(reason) };
          publish(state);
        }
      } finally {
        if (current === token) controller = null;
      }
    },
  };
}

export async function solveScenarioWorkflow(
  scenario: ScenarioInput,
  normalize: ScenarioNormalizer,
  solve: ScenarioSolver,
  workpointId: string | null = null,
): Promise<{ solved: ScenarioSolveResult; scenario: ScenarioInput; fingerprint: string }> {
  const normalizedScenario = normalize(scenario);
  return {
    solved: await solve(normalizedScenario, workpointId),
    scenario: normalizedScenario,
    fingerprint: scenarioFingerprintForSolve(normalizedScenario, workpointId),
  };
}

export function fallbackTargetDaysForScenario(
  scenarioFingerprint: string,
  resultFingerprint: string | null,
  result: ScenarioSolveResult | null,
): number | null {
  return resultFingerprint === scenarioFingerprint ? result?.result.objective_days ?? null : null;
}
