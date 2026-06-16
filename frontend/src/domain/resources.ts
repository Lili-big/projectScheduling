import type { ProcessTemplate, ResourceCostType, ResourceMode, ResourcePool, ScenarioInput, Task } from "../types/scheduler";
import {
  defaultResourceTypeByComponent,
  keyResourceComponentTypes,
  pileResourceTypeByMethod,
  pileResourceTypeByProcess,
} from "./constants";
import { resourceCostTypeLabels } from "./constants";

export function applyRequiredResourceTypesToTasks(tasks: Task[], resourcePools: ResourcePool[]): Task[] {
  const poolsByType = new Map(resourcePools.map((pool) => [pool.type, pool]));
  return tasks.map((task) => ({
    ...task,
    compatible_resource_types: requiredResourceTypesForTask(task, poolsByType),
  }));
}

export function requiredResourceTypesForTask(task: Task, poolsByType: Map<string, ResourcePool>): string[] {
  const resourceType = defaultResourceTypeForTask(task);
  if (!resourceType) return [];
  const pool = poolsByType.get(resourceType);
  if (isLimitedResourcePoolAvailable(pool)) return [resourceType];
  if (keyResourceComponentTypes.has(task.component_type)) return [];
  if (pool && resourcePoolMode(pool) === "LIMITED") return [];
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
  return Boolean(pool && pool.enabled && resourcePoolMode(pool) === "LIMITED" && resourcePoolUsableLimit(pool) > 0);
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

export function normalizeLimitedResourcePool(pool: ResourcePool): ResourcePool {
  const quantity = Math.max(0, resourcePoolQuantity(pool));
  const rawMaxQuantity = typeof pool.max_quantity === "number" && Number.isFinite(pool.max_quantity)
    ? pool.max_quantity
    : quantity;
  return {
    ...pool,
    resource_mode: "LIMITED",
    quantity,
    max_quantity: Math.max(quantity, rawMaxQuantity),
    calendar_id: pool.calendar_id || "continuous",
  };
}

export function normalizeScenarioResourcePools(scenario: ScenarioInput): ScenarioInput {
  return {
    ...scenario,
    resource_pools: scenario.resource_pools.map(normalizeLimitedResourcePool),
  };
}

export function taskResourceTypesLabel(task: Task, resourcePools: ResourcePool[]): string {
  if (!task.compatible_resource_types.length) return "-";
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
