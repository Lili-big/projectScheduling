import type {
  GeneratedScheduleInput,
  ProjectMasterWorkpoint,
  Resource,
  ResourcePool,
  ScheduleResult,
  ValidationMessage,
} from "../../contracts";
import { effectiveWorkpointResource, resourcePoolQuantity, resourceScopeLabels } from "../../domain/resources";
import { scheduleStatusLabels } from "../../domain/labels";

export const projectSharedTransferNotice = "项目共享资源在允许工点间互斥流转，转场时间 0 天、转场成本 0。使用先后由求解器确定。";

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
