import type {
  ProcessTemplate,
  ResourceCostType,
  ResourceMode,
  ResourcePool,
  ResourceScopeMode,
  ScenarioInput,
  Task,
  WorkpointResourceOverride,
} from "../contracts";
import {
  defaultResourceTypeByComponent,
  keyResourceComponentTypes,
  pileResourceTypeByMethod,
  pileResourceTypeByProcess,
} from "./constants";
import { resourceCostTypeLabels } from "./constants";

export function applyRequiredResourceTypesToTasks(tasks: Task[], resourcePools: ResourcePool[]): Task[] {
  const poolsByType = new Map<string, ResourcePool[]>();
  for (const pool of resourcePools) poolsByType.set(pool.type, [...(poolsByType.get(pool.type) ?? []), pool]);
  return tasks.map((task) => ({
    ...task,
    compatible_resource_types: requiredResourceTypesForTask(task, poolsByType),
  }));
}

export function requiredResourceTypesForTask(task: Task, poolsByType: Map<string, ResourcePool[]>): string[] {
  const resourceType = defaultResourceTypeForTask(task);
  if (!resourceType) return [];
  const pools = poolsByType.get(resourceType) ?? [];
  if (pools.some(isLimitedResourcePoolAvailable)) return [resourceType];
  if (keyResourceComponentTypes.has(task.component_type)) return [];
  if (pools.some((pool) => resourcePoolMode(pool) === "LIMITED")) return [];
  return [];
}

export function defaultResourceTypeForTask(task: Task): string | null {
  const fallback = task.compatible_resource_types[0] ?? null;
  const processId = task.productivity_rule_id.split(":")[0];
  const methodId = methodIdFromProcessId(processId);
  if (task.component_type === "pile") {
    return pileResourceTypeByProcess[processId] ?? (methodId ? pileResourceTypeByMethod[methodId] : null) ?? fallback;
  }
  return defaultResourceTypeByComponent[task.component_type] ?? fallback;
}

export function methodIdFromProcessId(processId: string): string | null {
  return Object.keys(pileResourceTypeByMethod).find((methodId) => processId.includes(methodId)) ?? null;
}

export function isLimitedResourcePoolAvailable(pool: ResourcePool | undefined): boolean {
  return Boolean(pool && pool.enabled && resourcePoolMode(pool) === "LIMITED" && resourcePoolQuantity(pool) > 0);
}

export function resourcePoolMode(pool: ResourcePool): ResourceMode {
  return pool.resource_mode ?? "LIMITED";
}

export function resourcePoolQuantity(pool: ResourcePool): number {
  return typeof pool.quantity === "number" && Number.isFinite(pool.quantity) ? pool.quantity : 0;
}

export function resourcePoolUsableLimit(pool: ResourcePool): number {
  const maxQuantity = pool.max_quantity;
  if (typeof maxQuantity === "number" && Number.isFinite(maxQuantity)) return maxQuantity;
  return resourcePoolQuantity(pool);
}

export function resourcePoolCostType(pool: ResourcePool): ResourceCostType {
  const costType = pool.cost_type ?? "none";
  return costType in resourceCostTypeLabels ? costType : "none";
}

export function resourcePoolUnitCost(pool: ResourcePool): number {
  return Number.isFinite(Number(pool.incremental_unit_cost)) ? Math.max(0, Number(pool.incremental_unit_cost)) : 0;
}

export function resourcePoolBillingPeriodDays(pool: ResourcePool): number {
  return Number.isFinite(Number(pool.billing_period_days)) ? Math.max(1, Number(pool.billing_period_days)) : 30;
}

const mechanicalPileResourceTypes = new Set(["rotary_drill", "circulation_drill", "impact_drill"]);

export type EffectiveWorkpointResource = {
  workpointId: string;
  enabled: boolean;
  quantity: number;
  maxQuantity: number;
  inheritanceSource: "inherited" | "overridden";
};

export type ResourceCatalogItem = {
  type: string;
  label: string;
  defaultCalendarId: string;
  defaultMaxQuantity: number;
  applicableProcessIds: string[];
};

export const resourceScopeLabels: Record<ResourceScopeMode, string> = {
  PROJECT_SHARED: "项目共享",
  WORKPOINT_EXCLUSIVE: "工点独享",
};

function normalizeResourceScopeMode(value: ResourceScopeMode | undefined): ResourceScopeMode {
  return value === "WORKPOINT_EXCLUSIVE" ? value : "PROJECT_SHARED";
}

function normalizeWorkpointIds(values: string[] | null | undefined): string[] | null {
  if (values == null) return null;
  return Array.from(new Set(values.map((value) => value.trim()).filter(Boolean))).sort();
}

function normalizedOverride(override: WorkpointResourceOverride): WorkpointResourceOverride | null {
  const workpointId = override.workpoint_id.trim();
  if (!workpointId) return null;
  const normalized: WorkpointResourceOverride = { workpoint_id: workpointId };
  if (override.enabled != null) normalized.enabled = Boolean(override.enabled);
  if (override.quantity != null) normalized.quantity = normalizeResourceQuantity(override.quantity);
  if (override.max_quantity != null) normalized.max_quantity = normalizeResourceQuantity(override.max_quantity);
  return Object.keys(normalized).length > 1 ? normalized : null;
}

function normalizeWorkpointOverrides(values: WorkpointResourceOverride[] | undefined): WorkpointResourceOverride[] {
  const byWorkpoint = new Map<string, WorkpointResourceOverride>();
  for (const value of values ?? []) {
    const normalized = normalizedOverride(value);
    if (normalized) byWorkpoint.set(normalized.workpoint_id, normalized);
  }
  return [...byWorkpoint.values()].sort((left, right) => left.workpoint_id.localeCompare(right.workpoint_id));
}

function normalizeResourceQuantity(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) ? Math.max(0, Math.trunc(number)) : 0;
}

function normalizedParallelRuleDescription(pool: ResourcePool): string {
  if (mechanicalPileResourceTypes.has(pool.type)) {
    return "机械桩基资源：按同桥同幅同墩同工艺形成墩组，组内由同一台设备负责；不再配置并行上限。";
  }
  if (pool.type === "manual_pile_team") {
    return "人工挖孔班组：不进入机械钻机墩组规则，按班组数量和资源互斥排程。";
  }
  return String(pool.parallel_rule_description ?? "");
}

export function normalizeResourcePoolForWorkspace(pool: ResourcePool): ResourcePool {
  const resourceMode = resourcePoolMode(pool);
  const quantity = resourceMode === "LIMITED" ? normalizeResourceQuantity(pool.quantity) : pool.quantity;
  const normalizedQuantity = typeof quantity === "number" ? quantity : 0;
  const maxQuantity = resourceMode === "LIMITED"
    ? Math.max(normalizedQuantity, normalizeResourceQuantity(pool.max_quantity ?? normalizedQuantity))
    : pool.max_quantity;
  const scopeMode = normalizeResourceScopeMode(pool.scope_mode);
  const workpointId = typeof pool.workpoint_id === "string" && pool.workpoint_id.trim() ? pool.workpoint_id.trim() : null;
  const isCanonicalLocal = scopeMode === "WORKPOINT_EXCLUSIVE" && workpointId !== null;
  return {
    ...pool,
    resource_mode: resourceMode,
    scope_mode: scopeMode,
    workpoint_id: scopeMode === "PROJECT_SHARED" ? null : workpointId,
    quantity,
    max_quantity: maxQuantity,
    authorized_workpoint_ids: isCanonicalLocal ? null : normalizeWorkpointIds(pool.authorized_workpoint_ids),
    workpoint_overrides: isCanonicalLocal ? [] : normalizeWorkpointOverrides(pool.workpoint_overrides),
    calendar_id: pool.calendar_id || "continuous",
    same_structure_resource_binding: Boolean(pool.same_structure_resource_binding),
    parallel_rule_description: normalizedParallelRuleDescription(pool),
  };
}

export function isWorkpointLocalPool(pool: ResourcePool): boolean {
  return (pool.scope_mode ?? "PROJECT_SHARED") === "WORKPOINT_EXCLUSIVE" && Boolean(pool.workpoint_id?.trim());
}

export function localResourcePoolsForWorkpoint(pools: ResourcePool[], workpointId: string): ResourcePool[] {
  return pools
    .map(normalizeResourcePoolForWorkspace)
    .filter((pool) => isWorkpointLocalPool(pool) && pool.workpoint_id === workpointId)
    .sort((left, right) => left.type.localeCompare(right.type) || left.id.localeCompare(right.id));
}

export function sharedResourcePools(pools: ResourcePool[]): ResourcePool[] {
  return pools
    .map(normalizeResourcePoolForWorkspace)
    .filter((pool) => (pool.scope_mode ?? "PROJECT_SHARED") === "PROJECT_SHARED")
    .sort((left, right) => left.type.localeCompare(right.type) || left.id.localeCompare(right.id));
}

type WorkpointLocalResourceInput = Pick<ResourcePool, "id" | "type" | "label" | "quantity" | "max_quantity" | "enabled">
  & Partial<Pick<ResourcePool, "calendar_id" | "compatible_process_ids">>;

export function upsertWorkpointLocalResource(
  pools: ResourcePool[],
  workpointId: string,
  input: WorkpointLocalResourceInput,
): ResourcePool[] {
  const existing = pools.find((pool) => isWorkpointLocalPool(pool) && pool.workpoint_id === workpointId && pool.type === input.type);
  const next = normalizeResourcePoolForWorkspace({
    ...(existing ?? {}),
    ...input,
    id: existing?.id ?? input.id,
    resource_mode: "LIMITED",
    scope_mode: "WORKPOINT_EXCLUSIVE",
    workpoint_id: workpointId,
    authorized_workpoint_ids: null,
    workpoint_overrides: [],
    calendar_id: input.calendar_id ?? existing?.calendar_id ?? "continuous",
    compatible_process_ids: input.compatible_process_ids ?? existing?.compatible_process_ids ?? [],
  });
  return [...pools.filter((pool) => pool.id !== next.id && pool !== existing), next]
    .map(normalizeResourcePoolForWorkspace)
    .sort((left, right) => left.id.localeCompare(right.id));
}

export function removeResourcePoolById(pools: ResourcePool[], poolId: string): ResourcePool[] {
  return pools.filter((pool) => pool.id !== poolId).map(normalizeResourcePoolForWorkspace);
}

export function upsertResourcePoolById(pools: ResourcePool[], poolId: string, patch: Partial<ResourcePool>): ResourcePool[] {
  return pools.map((pool) => pool.id === poolId
    ? normalizeResourcePoolForWorkspace({ ...pool, ...patch, id: pool.id })
    : normalizeResourcePoolForWorkspace(pool));
}

export function resourceCatalogProjection(processes: ProcessTemplate[], pools: ResourcePool[]): ResourceCatalogItem[] {
  const catalog = new Map<string, ResourceCatalogItem>();
  for (const process of processes) {
    const type = defaultResourceTypeForProcess(process);
    if (!type || excludedResourceCatalogTypes.has(type)) continue;
    const existing = catalog.get(type);
    catalog.set(type, {
      type,
      label: existing?.label ?? resourceTypeLabel(type, pools),
      defaultCalendarId: existing?.defaultCalendarId ?? "continuous",
      defaultMaxQuantity: existing?.defaultMaxQuantity ?? 0,
      applicableProcessIds: Array.from(new Set([...(existing?.applicableProcessIds ?? []), process.id])).sort(),
    });
  }
  for (const pool of pools.map(normalizeResourcePoolForWorkspace)) {
    if (excludedResourceCatalogTypes.has(pool.type)) continue;
    const existing = catalog.get(pool.type);
    catalog.set(pool.type, {
      type: pool.type,
      label: pool.label || existing?.label || pool.type,
      defaultCalendarId: pool.calendar_id || existing?.defaultCalendarId || "continuous",
      defaultMaxQuantity: Math.max(existing?.defaultMaxQuantity ?? 0, resourcePoolUsableLimit(pool)),
      applicableProcessIds: Array.from(new Set([...(existing?.applicableProcessIds ?? []), ...pool.compatible_process_ids])).sort(),
    });
  }
  return [...catalog.values()].sort((left, right) => left.type.localeCompare(right.type));
}

const excludedResourceCatalogTypes = new Set(["girder_erector", "beam_yard", "beam_yard_production_line"]);

export function effectiveWorkpointResource(pool: ResourcePool, workpointId: string): EffectiveWorkpointResource {
  const normalized = normalizeResourcePoolForWorkspace(pool);
  const override = normalized.workpoint_overrides?.find((item) => item.workpoint_id === workpointId);
  const quantity = override?.quantity ?? resourcePoolQuantity(normalized);
  const maxQuantity = Math.max(quantity, override?.max_quantity ?? resourcePoolUsableLimit(normalized));
  return {
    workpointId,
    enabled: override?.enabled ?? normalized.enabled,
    quantity,
    maxQuantity,
    inheritanceSource: override ? "overridden" : "inherited",
  };
}

export function setWorkpointResourceOverride(
  pool: ResourcePool,
  workpointId: string,
  patch: Omit<Partial<WorkpointResourceOverride>, "workpoint_id">,
): ResourcePool {
  const normalized = normalizeResourcePoolForWorkspace(pool);
  const current = normalized.workpoint_overrides?.find((item) => item.workpoint_id === workpointId) ?? { workpoint_id: workpointId };
  const next = normalizedOverride({ ...current, ...patch, workpoint_id: workpointId });
  const remaining = (normalized.workpoint_overrides ?? []).filter((item) => item.workpoint_id !== workpointId);
  return normalizeResourcePoolForWorkspace({
    ...normalized,
    workpoint_overrides: next ? [...remaining, next] : remaining,
  });
}

export function restoreWorkpointResourceInheritance(pool: ResourcePool, workpointId: string): ResourcePool {
  return normalizeResourcePoolForWorkspace({
    ...pool,
    workpoint_overrides: (pool.workpoint_overrides ?? []).filter((item) => item.workpoint_id !== workpointId),
  });
}

export function resourcePoolScopeIssues(pool: ResourcePool, authoritativeWorkpointIds: string[]): string[] {
  const authoritative = new Set(authoritativeWorkpointIds);
  const normalized = normalizeResourcePoolForWorkspace(pool);
  const referenced = [
    ...(normalized.workpoint_id ? [normalized.workpoint_id] : []),
    ...(pool.authorized_workpoint_ids ?? []),
    ...(pool.workpoint_overrides ?? []).map((item) => item.workpoint_id),
  ];
  const issues = new Set<string>();
  if (normalized.scope_mode === "PROJECT_SHARED" && normalized.authorized_workpoint_ids?.length === 0) {
    issues.add("共享池至少选择一个可流转工点，或选择全部工点");
  }
  if (isWorkpointLocalPool(normalized) && !authoritative.has(normalized.workpoint_id ?? "")) {
    issues.add("工点资源不属于当前项目主数据版本");
  }
  if (referenced.some((workpointId) => !authoritative.has(workpointId))) {
    issues.add("配置包含当前项目主数据版本之外的工点");
  }
  const overrideIds = (pool.workpoint_overrides ?? []).map((item) => item.workpoint_id);
  if (new Set(overrideIds).size !== overrideIds.length) issues.add("同一工点存在重复覆盖");
  return [...issues];
}

export function resourcePoolsScopeIssues(pools: ResourcePool[], authoritativeWorkpointIds: string[]): string[] {
  const issues = pools.flatMap((pool) => resourcePoolScopeIssues(pool, authoritativeWorkpointIds));
  const ids = pools.map((pool) => pool.id);
  if (new Set(ids).size !== ids.length) issues.push("资源池 ID 重复");
  const localKeys = pools.filter(isWorkpointLocalPool).map((pool) => `${pool.workpoint_id}\u0000${pool.type}`);
  if (new Set(localKeys).size !== localKeys.length) issues.push("同一工点同一资源类型只能维护一条本地记录");
  return Array.from(new Set(issues));
}

export function resourcePoolsSemanticFingerprint(pools: ResourcePool[]): string {
  return JSON.stringify(
    pools
      .map(normalizeResourcePoolForWorkspace)
      .sort((left, right) => left.id.localeCompare(right.id))
      .map((pool) => ({
        id: pool.id,
        type: pool.type,
        resource_mode: pool.resource_mode,
        scope_mode: pool.scope_mode,
        workpoint_id: pool.workpoint_id ?? null,
        quantity: pool.quantity,
        max_quantity: pool.max_quantity,
        authorized_workpoint_ids: pool.authorized_workpoint_ids,
        workpoint_overrides: pool.workpoint_overrides,
        calendar_id: pool.calendar_id,
        enabled: pool.enabled,
        compatible_process_ids: [...pool.compatible_process_ids].sort(),
        cost_type: pool.cost_type,
        incremental_unit_cost: pool.incremental_unit_cost,
        billing_period_days: pool.billing_period_days,
        same_structure_resource_binding: pool.same_structure_resource_binding,
      })),
  );
}

export function normalizeLimitedResourcePool(pool: ResourcePool): ResourcePool {
  return normalizeResourcePoolForWorkspace({ ...pool, resource_mode: "LIMITED" });
}

export function normalizeScenarioResourcePools(scenario: ScenarioInput): ScenarioInput {
  return {
    ...scenario,
    resource_pools: scenario.resource_pools.map(normalizeResourcePoolForWorkspace),
  };
}

export function taskResourceTypesLabel(task: Task, resourcePools: ResourcePool[]): string {
  if (!task.compatible_resource_types.length) return "默认充足";
  return resourceTypesLabel(task.compatible_resource_types, resourcePools, " / ");
}

export function processResourceLabel(process: ProcessTemplate, resourcePools: ResourcePool[]): string {
  const resourceType = defaultResourceTypeForProcess(process);
  if (!resourceType) return "";
  return resourceTypeLabel(resourceType, resourcePools);
}

export function resourceTypeLabel(resourceType: string, resourcePools: ResourcePool[]): string {
  return resourcePools.find((pool) => pool.type === resourceType)?.label ?? resourceType;
}

export function resourceTypesLabel(resourceTypes: string[], resourcePools: ResourcePool[], separator = "、"): string {
  if (!resourceTypes.length) return "-";
  return resourceTypes.map((type) => resourceTypeLabel(type, resourcePools)).join(separator);
}

export function defaultResourceTypeForProcess(process: ProcessTemplate): string | null {
  if (process.component_type === "pile") {
    return (
      pileResourceTypeByProcess[process.id]
      ?? (process.method_id ? pileResourceTypeByMethod[process.method_id] : null)
      ?? process.resource_type
      ?? null
    );
  }
  return defaultResourceTypeByComponent[process.component_type] ?? null;
}
