import type {
  GeneratedScheduleInput,
  ProjectMasterWorkpoint,
  Resource,
  ResourcePool,
  ScheduleResult,
  SolveScope,
  ValidationMessage,
} from "../../contracts";
import { effectiveWorkpointResource, resourcePoolQuantity, resourceScopeLabels } from "../../domain/resources";
import { scheduleStatusLabels } from "../../domain/labels";

export const projectSharedTransferNotice = "项目共享资源在允许工点间互斥流转，转场时间 0 天、转场成本 0。使用先后由求解器确定。";

export function solveScopeLabel(scope: SolveScope | null | undefined): string {
  if (!scope || scope.mode === "ALL") return "全部工点";
  const name = scope.workpoint_name?.trim() || "未命名工点";
  return `单工点试算：${name}（${scope.workpoint_id ?? "未知 ID"}）`;
}

export type ResourceScopeResultRow = {
  key: string;
  resourceLabel: string;
  scopeLabel: string;
  workpointLabel: string;
  currentQuantity: number | null;
  recommendedQuantity: number | null;
};

export type ResourceScopeResult = {
  rows: ResourceScopeResultRow[];
  showProjectSharedNotice: boolean;
  notice: string;
};

type ResourceScopeResultInput = {
  generated: GeneratedScheduleInput | null;
  result: ScheduleResult | null;
  resourcePools: ResourcePool[];
  workpoints: Array<Pick<ProjectMasterWorkpoint, "workpoint_id" | "workpoint_name">>;
};

export function formatScheduleStatus(value: unknown): string {
  if (typeof value === "string" && Object.prototype.hasOwnProperty.call(scheduleStatusLabels, value)) {
    return scheduleStatusLabels[value as ScheduleResult["status"]];
  }
  return value == null ? "-" : String(value);
}

export function scheduleResultSummary(result: ScheduleResult | null) {
  return result
    ? { status: formatScheduleStatus(result.status), days: result.objective_days, tasks: result.tasks.length }
    : { status: "-", days: null, tasks: 0 };
}

export function summarizeDiagnostics(diagnostics: ValidationMessage[]) {
  return diagnostics.reduce(
    (summary, item) => ({ ...summary, [item.level]: summary[item.level] + 1 }),
    { error: 0, warning: 0, info: 0 },
  );
}

export function objectiveBreakdownEntries(result: ScheduleResult | null): Array<[string, unknown]> {
  return Object.entries(result?.objective_breakdown ?? {}).sort(([left], [right]) => left.localeCompare(right));
}

export type UnifiedSolvePresentation = {
  mode: "fixed" | "minimum" | "legacy";
  objectiveText: string;
  diagnosticText: string;
  businessStatus: string;
  solverStatus: string;
  maxTargetDelayDays: string;
  solverCalls: string;
  globalSearchStatus: string;
  candidateSummary: string;
  verificationStatus: string;
  retryStatus: string;
  sourceNotice: string;
};

const targetStatusLabels: Record<string, string> = {
  met: "目标已满足",
  not_met: "已证明目标未满足",
  unconfirmed: "目标尚未确认",
  infeasible: "物理不可行",
};

export function unifiedSolvePresentation(result: ScheduleResult | null): UnifiedSolvePresentation | null {
  if (!result) return null;
  const stats = asRecord(result.stats);
  const breakdown = asRecord(result.objective_breakdown);
  const solveMode = String(stats.solve_mode ?? breakdown.solve_mode ?? "");
  const source = String(stats.schedule_source ?? breakdown.schedule_source ?? "");
  const verification = asRecord(stats.minimum_resource_verification ?? breakdown.minimum_resource_verification);
  const target = asRecord(stats.target_achievement ?? breakdown.target_achievement);
  const isMinimum = solveMode === "min_resources_fixed_duration" || Object.keys(verification).length > 0;
  const isUnified = solveMode === "unified_fixed_resource"
    || Array.isArray(stats.objective_priority)
    || isMinimum;
  const targetStatus = String(target.target_status ?? "");
  const recommendations = Array.isArray(stats.recommended_resource_counts)
    ? stats.recommended_resource_counts.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    : [];
  const candidateSummary = recommendations.length
    ? recommendations.map((item) => `${String(item.label ?? item.resource_pool_id ?? "资源")} ${Number(item.recommended_quantity ?? 0)}`).join("；")
    : "无全局候选";
  const candidateFound = verification.candidate_found === true;
  const candidateVerified = verification.candidate_verified === true;

  return {
    mode: isMinimum ? "minimum" : isUnified ? "fixed" : "legacy",
    objectiveText: isMinimum
      ? "全局搜索先最小化资源总数，同数时再最小化总工期；随后按候选资源执行一次详细排程。"
      : "最大目标延期优先，总工期其次。",
    diagnosticText: "资源空闲与连续性仅作求解后诊断，不参与固定资源或固定工期目标。",
    businessStatus: targetStatusLabels[targetStatus] ?? (targetStatus || "未评估"),
    solverStatus: formatScheduleStatus(target.solver_status ?? result.status),
    maxTargetDelayDays: typeof target.max_target_delay_days === "number" ? `${target.max_target_delay_days} 天` : "未提供",
    solverCalls: isMinimum
      ? `全局 ${Number(stats.global_search_call_count ?? 0)} 次 / 详细 ${Number(verification.detail_solver_call_count ?? 0)} 次`
      : `${Number(stats.solver_call_count ?? 0)} 次`,
    globalSearchStatus: isMinimum ? formatScheduleStatus(stats.global_search_status ?? "未运行") : "不适用",
    candidateSummary: isMinimum ? candidateSummary : "不适用",
    verificationStatus: isMinimum
      ? candidateVerified ? "详细排程已验证目标满足" : candidateFound ? "尚未通过详细排程确认" : "未形成候选"
      : "不适用",
    retryStatus: isUnified
      ? (stats.resource_expansion_attempted === true || verification.retry_attempted === true ? "发生了资源调整" : "未自动增配、未重搜、未重试")
      : "历史结果按原始字段展示",
    sourceNotice: isUnified
      ? `结果来源：${source || "统一求解"}`
      : `历史求解口径：${source || "来源字段缺失"}；按原始事实兼容展示。`,
  };
}

function asRecord(value: unknown): Record<string, any> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, any> : {};
}

export function buildResourceScopeResult({
  generated,
  result,
  resourcePools,
  workpoints,
}: ResourceScopeResultInput): ResourceScopeResult {
  const resources = generated?.schedule_input.resources ?? [];
  const tasksById = new Map((generated?.schedule_input.tasks ?? []).map((task) => [task.id, task]));
  const allocationsByResource = new Map<string, string[]>();
  for (const allocation of result?.resource_allocations ?? []) {
    const current = allocationsByResource.get(allocation.resource_id) ?? [];
    current.push(allocation.task_id);
    allocationsByResource.set(allocation.resource_id, current);
  }
  const workpointNames = new Map(workpoints.map((workpoint) => [workpoint.workpoint_id, workpoint.workpoint_name]));
  const poolsById = new Map(resourcePools.map((pool) => [pool.id, pool]));
  const recommendations = resourceScopeDiagnosticGroups(result);
  const groups = groupResourcesByEffectivePool(resources);

  const rows = groups.map((group): ResourceScopeResultRow => {
    const resource = group.resources[0];
    const pool = resource.pool_id ? poolsById.get(resource.pool_id) : undefined;
    const workpointId = resource.scope_mode === "WORKPOINT_EXCLUSIVE" ? resource.exclusive_workpoint_id ?? null : null;
    const recommendation = recommendations.find((item) => (
      item.resourcePoolId === resource.pool_id
      && (resource.scope_mode === "PROJECT_SHARED"
        ? item.workpointId === null
        : item.workpointId === workpointId)
    ));
    return {
      key: group.key,
      resourceLabel: pool?.label ?? resource.pool_label ?? resource.name,
      scopeLabel: resource.scope_mode ? resourceScopeLabels[resource.scope_mode] : "作用域不可用",
      workpointLabel: resourceWorkpointLabel(group.resources, allocationsByResource, tasksById, workpointNames),
      currentQuantity: recommendation?.currentQuantity ?? currentQuantity(pool, workpointId),
      recommendedQuantity: recommendation?.recommendedQuantity ?? null,
    };
  });

  return {
    rows,
    showProjectSharedNotice: resources.some((resource) => resource.scope_mode === "PROJECT_SHARED"),
    notice: projectSharedTransferNotice,
  };
}

function groupResourcesByEffectivePool(resources: Resource[]): Array<{ key: string; resources: Resource[] }> {
  const groups = new Map<string, Resource[]>();
  for (const resource of resources) {
    const key = JSON.stringify([
      resource.pool_id ?? null,
      resource.scope_mode ?? null,
      resource.exclusive_workpoint_id ?? null,
    ]);
    groups.set(key, [...(groups.get(key) ?? []), resource]);
  }
  return [...groups].map(([key, groupedResources]) => ({ key, resources: groupedResources }));
}

function resourceWorkpointLabel(
  resources: Resource[],
  allocationsByResource: Map<string, string[]>,
  tasksById: Map<string, { bridge_id?: string | null }>,
  workpointNames: Map<string, string>,
): string {
  const resource = resources[0];
  if (!resource.scope_mode) return "工点信息不可用";
  const allocatedWorkpointIds = resources.flatMap((item) => (
    allocationsByResource.get(item.id) ?? []
  )).map((taskId) => tasksById.get(taskId)?.bridge_id).filter((value): value is string => Boolean(value));
  const workpointIds = resource.scope_mode === "WORKPOINT_EXCLUSIVE"
    ? [resource.exclusive_workpoint_id].filter((value): value is string => Boolean(value))
    : allocatedWorkpointIds.length ? allocatedWorkpointIds : resource.eligible_workpoint_ids;
  const normalizedIds = Array.from(new Set(workpointIds)).sort();
  if (!normalizedIds.length) return "尚未分配";
  const names = normalizedIds.map((workpointId) => workpointNames.get(workpointId)?.trim()).filter(Boolean) as string[];
  return names.length === normalizedIds.length ? names.join("、") : "工点信息不可用";
}

function currentQuantity(pool: ResourcePool | undefined, workpointId: string | null): number | null {
  if (!pool) return null;
  return workpointId ? effectiveWorkpointResource(pool, workpointId).quantity : resourcePoolQuantity(pool);
}

function resourceScopeDiagnosticGroups(result: ScheduleResult | null): Array<{
  resourcePoolId: string;
  workpointId: string | null;
  currentQuantity: number;
  recommendedQuantity: number;
}> {
  const diagnostics = result?.stats?.resource_scope_diagnostics;
  if (!diagnostics || typeof diagnostics !== "object") return [];
  const raw = (diagnostics as Record<string, unknown>).groups;
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const item = value as Record<string, unknown>;
    const resourcePoolId = typeof item.source_pool_id === "string" ? item.source_pool_id : "";
    const currentQuantity = item.current_quantity;
    const recommendedQuantity = item.recommended_quantity;
    if (
      !resourcePoolId
      || typeof currentQuantity !== "number"
      || !Number.isFinite(currentQuantity)
      || typeof recommendedQuantity !== "number"
      || !Number.isFinite(recommendedQuantity)
    ) return [];
    return [{
      resourcePoolId,
      workpointId: typeof item.workpoint_id === "string" ? item.workpoint_id : null,
      currentQuantity,
      recommendedQuantity,
    }];
  });
}
