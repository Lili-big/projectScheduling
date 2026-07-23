import type {
  ComponentType,
  ProcessTemplate,
  ProjectMasterParameter,
  ProjectMasterWorkpoint,
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
  excludedResourceCatalogTypes,
  keyResourceComponentTypes,
  pileResourceTypeByMethod,
  pileResourceTypeByProcess,
  projectMasterComponentTypeProjection,
  projectMasterUpperStructureResourceComponent,
  standardResourceTypeLabels,
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

export type WorkpointStructureSummaryComponentType =
  | "pile"
  | "cap"
  | "middle_tie_beam"
  | "pier_body"
  | "ground_tie_beam"
  | "cap_beam";

export type ResolvedStructureProcess = {
  identity: string;
  processId: string | null;
  label: string;
  source: "component_explicit" | "structure_explicit" | "unique_default" | "unknown_explicit" | "missing";
};

export type WorkpointStructureSummaryItem = {
  signature: string;
  componentType: WorkpointStructureSummaryComponentType;
  processId: string | null;
  processLabel: string;
  parameterSegments: string[];
  quantity: number;
  unit: string;
  displayText: string;
};

export type WorkpointStructureSummaryGroup = {
  componentType: WorkpointStructureSummaryComponentType;
  label: string;
  sortOrder: number;
  items: WorkpointStructureSummaryItem[];
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
    enabled: isCanonicalLocal ? normalizedQuantity > 0 : pool.enabled,
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
  for (const pool of pools.map(normalizeResourcePoolForWorkspace).sort((left, right) => left.id.localeCompare(right.id))) {
    if (excludedResourceCatalogTypes.has(pool.type)) continue;
    const existing = catalog.get(pool.type);
    catalog.set(pool.type, {
      type: pool.type,
      label: resourceTypeLabel(pool.type, pools),
      defaultCalendarId: pool.calendar_id || existing?.defaultCalendarId || "continuous",
      defaultMaxQuantity: Math.max(existing?.defaultMaxQuantity ?? 0, resourcePoolUsableLimit(pool)),
      applicableProcessIds: Array.from(new Set([...(existing?.applicableProcessIds ?? []), ...pool.compatible_process_ids])).sort(),
    });
  }
  return [...catalog.values()].sort((left, right) => left.type.localeCompare(right.type));
}

const processMethodParameterCodes = new Set([
  "method_id",
  "process_method_id",
  "pile_method",
  "construction_method",
]);

const workpointStructureSummaryDefinitions: ReadonlyArray<{
  componentType: WorkpointStructureSummaryComponentType;
  label: string;
}> = [
  { componentType: "pile", label: "桩基" },
  { componentType: "cap", label: "承台" },
  { componentType: "middle_tie_beam", label: "柱系梁" },
  { componentType: "pier_body", label: "墩身" },
  { componentType: "ground_tie_beam", label: "桩系梁" },
  { componentType: "cap_beam", label: "盖梁" },
];

const workpointStructureSummaryTypes = new Set<WorkpointStructureSummaryComponentType>(
  workpointStructureSummaryDefinitions.map((item) => item.componentType),
);

const summaryPhysicalParameterPriority: Record<string, number> = {
  diameter_m: 1,
  length_m: 2,
  width_m: 3,
  height_m: 4,
  dimensions_m: 5,
};

type NormalizedSummaryParameter = {
  code: string;
  signatureValue: string;
  displayValues: string[];
  unit: string;
};

type NormalizedMetricDimensionExpression = {
  signatureValue: string;
  displayValue: string;
};

function methodIdsFromParameters(parameters: ProjectMasterParameter[]): string[] {
  const methodIds: string[] = [];
  for (const parameter of parameters) {
    if (!processMethodParameterCodes.has(parameter.parameter_code)) continue;
    const values = Array.isArray(parameter.value) ? parameter.value : [parameter.value];
    for (const value of values) {
      const methodId = String(value ?? "").trim();
      if (methodId) methodIds.push(methodId);
    }
  }
  return Array.from(new Set(methodIds));
}

function workpointStructureSummaryComponentType(componentType: string): WorkpointStructureSummaryComponentType | null {
  const projected = workpointStructureSummaryTypes.has(componentType as WorkpointStructureSummaryComponentType)
    ? componentType
    : projectMasterComponentTypeProjection[componentType];
  return projected && workpointStructureSummaryTypes.has(projected as WorkpointStructureSummaryComponentType)
    ? projected as WorkpointStructureSummaryComponentType
    : null;
}

function stableSummaryParameterValue(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "number") return Number.isFinite(value) ? formatSummaryNumber(value) : "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "boolean") return value ? "true" : "false";
  if (Array.isArray(value)) {
    const items = value.map(stableSummaryParameterValue).filter(Boolean);
    return items.length > 0 ? `[${items.join(",")}]` : "";
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => [key, stableSummaryParameterValue(item)] as const)
      .filter(([, item]) => item)
      .sort(([left], [right]) => left.localeCompare(right));
    return entries.length > 0 ? `{${entries.map(([key, item]) => `${key}:${item}`).join(",")}}` : "";
  }
  return String(value).trim();
}

function summaryParameterDisplayValues(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap(summaryParameterDisplayValues);
  const normalized = stableSummaryParameterValue(value);
  return normalized ? [normalized] : [];
}

function normalizedMetricDimensionExpression(value: unknown): NormalizedMetricDimensionExpression | null {
  if (typeof value !== "string") return null;
  const match = value.trim().match(
    /^((?:\d+(?:\.\d+)?(?:\s*\/\s*\d+(?:\.\d+)?)*)(?:\s*[*xX×]\s*(?:\d+(?:\.\d+)?(?:\s*\/\s*\d+(?:\.\d+)?)*))+)(?:\s*m)?(.*)$/i,
  );
  if (!match) return null;
  const suffix = match[2].trim();
  if (suffix && !/^[（(].*[）)]$/.test(suffix)) return null;
  const expression = match[1]
    .replace(/\s*[*xX×]\s*/g, "×")
    .replace(/\s*\/\s*/g, "/");
  const normalizedSuffix = suffix.replace(/\s+/g, "");
  return {
    signatureValue: `${expression}m${normalizedSuffix}`,
    displayValue: `${expression}m${suffix}`,
  };
}

function normalizedSummaryParameters(parameters: ProjectMasterParameter[]): NormalizedSummaryParameter[] {
  return parameters
    .filter((parameter) => !processMethodParameterCodes.has(parameter.parameter_code))
    .map((parameter) => {
      const metricDimension = ["dimensions_m", "form"].includes(parameter.parameter_code)
        ? normalizedMetricDimensionExpression(parameter.value)
        : null;
      return {
        code: parameter.parameter_code,
        signatureValue: metricDimension?.signatureValue ?? stableSummaryParameterValue(parameter.value),
        displayValues: metricDimension ? [metricDimension.displayValue] : summaryParameterDisplayValues(parameter.value),
        unit: metricDimension ? "" : parameter.unit?.trim() || (parameter.parameter_code.endsWith("_m") ? "m" : ""),
      };
    })
    .filter((parameter) => parameter.signatureValue)
    .sort((left, right) => (
      left.code.localeCompare(right.code)
      || left.signatureValue.localeCompare(right.signatureValue)
      || left.unit.localeCompare(right.unit)
    ));
}

function summaryDiagnosticParameter(code: string, signatureValue: string, displayValue: string): NormalizedSummaryParameter {
  return { code, signatureValue, displayValues: [displayValue], unit: "" };
}

function summaryParametersForComponent(
  componentType: WorkpointStructureSummaryComponentType,
  parameters: NormalizedSummaryParameter[],
): NormalizedSummaryParameter[] {
  if (componentType === "pile") {
    const diameters = parameters.filter((parameter) => parameter.code === "diameter_m");
    return diameters.length > 0
      ? diameters
      : [summaryDiagnosticParameter("__pile_diameter_missing", "missing", "桩径未提供")];
  }
  if (componentType !== "pier_body") return parameters;

  const diameters = parameters.filter((parameter) => parameter.code === "diameter_m");
  const dimensions = parameters.filter((parameter) => parameter.code === "dimensions_m");
  if (diameters.length > 0 && dimensions.length > 0) {
    const conflictIdentity = JSON.stringify(
      [...diameters, ...dimensions].map((parameter) => [parameter.code, parameter.signatureValue, parameter.unit]),
    );
    return [summaryDiagnosticParameter("__pier_section_conflict", conflictIdentity, "截面尺寸冲突")];
  }
  if (diameters.length > 0) return diameters;
  if (dimensions.length > 0) return dimensions;
  return [summaryDiagnosticParameter("__pier_section_missing", "missing", "截面尺寸未提供")];
}

function summaryParameterSegments(
  componentType: WorkpointStructureSummaryComponentType,
  parameters: NormalizedSummaryParameter[],
): string[] {
  const physical = parameters
    .filter((parameter) => parameter.code in summaryPhysicalParameterPriority)
    .sort((left, right) => (
      summaryPhysicalParameterPriority[left.code] - summaryPhysicalParameterPriority[right.code]
      || left.signatureValue.localeCompare(right.signatureValue)
    ))
    .flatMap((parameter) => parameter.displayValues.map((value) => ({
      text: parameter.code === "diameter_m" ? `φ${value}` : value,
      unit: parameter.unit,
    })));
  const segments: string[] = [];
  if (physical.length > 0) {
    const commonUnit = physical[0].unit && physical.every((item) => item.unit === physical[0].unit)
      ? physical[0].unit
      : "";
    segments.push(commonUnit
      ? `${physical.map((item) => item.text).join("×")}${commonUnit}`
      : physical.map((item) => `${item.text}${item.unit}`).join("×"));
  }

  const forms = parameters
    .filter((parameter) => parameter.code === "form")
    .flatMap((parameter) => parameter.displayValues.map((value) => `${value}${parameter.unit}`));
  segments.push(...forms);

  const other = parameters
    .filter((parameter) => !(parameter.code in summaryPhysicalParameterPriority) && parameter.code !== "form")
    .flatMap((parameter) => parameter.displayValues.map((value) => `${value}${parameter.unit}`));
  segments.push(...other);
  if (segments.length === 0 && componentType === "pile") return [];
  return segments;
}

function resolveStructureProcess(
  componentType: WorkpointStructureSummaryComponentType,
  componentParameters: ProjectMasterParameter[],
  structureParameters: ProjectMasterParameter[],
  processes: ProcessTemplate[],
): ResolvedStructureProcess {
  const componentMethodId = [...methodIdsFromParameters(componentParameters)].sort()[0] ?? null;
  const structureMethodId = componentMethodId ? null : [...methodIdsFromParameters(structureParameters)].sort()[0] ?? null;
  const explicitMethodId = componentMethodId ?? structureMethodId;
  const candidates = processes
    .filter((process) => process.component_type === componentType)
    .sort((left, right) => left.id.localeCompare(right.id));
  if (explicitMethodId) {
    const matched = candidates.find((process) => process.id === explicitMethodId || process.method_id === explicitMethodId);
    if (matched) {
      return {
        identity: `process:${matched.id}`,
        processId: matched.id,
        label: matched.process_name.trim() || matched.id,
        source: componentMethodId ? "component_explicit" : "structure_explicit",
      };
    }
    return {
      identity: `unknown:${explicitMethodId}`,
      processId: null,
      label: `工艺未识别（${explicitMethodId}）`,
      source: "unknown_explicit",
    };
  }
  const defaults = candidates.filter((process) => process.is_default);
  if (defaults.length === 1) {
    return {
      identity: `process:${defaults[0].id}`,
      processId: defaults[0].id,
      label: defaults[0].process_name.trim() || defaults[0].id,
      source: "unique_default",
    };
  }
  return { identity: "missing", processId: null, label: "工艺未指定", source: "missing" };
}

function formatSummaryNumber(value: number): string {
  return Object.is(value, -0) ? "0" : String(value);
}

function summaryDisplayText(item: Omit<WorkpointStructureSummaryItem, "displayText">): string {
  const details = [item.processLabel, ...item.parameterSegments].filter(Boolean).join("-");
  return `${details || "参数/工艺未提供"}×${formatSummaryNumber(item.quantity)}${item.unit}`;
}

function projectedProjectMasterComponentType(structureType: string, componentType: string): ComponentType | null {
  if (structureType === "bridge_abutment") {
    return componentType === "pile" ? "pile" : "abutment_body";
  }
  return projectMasterComponentTypeProjection[componentType] ?? null;
}

function processesForProjectedComponent(
  componentType: ComponentType,
  explicitMethodIds: string[],
  processes: ProcessTemplate[],
): ProcessTemplate[] {
  const candidates = processes.filter((process) => process.component_type === componentType);
  if (explicitMethodIds.length > 0) {
    return explicitMethodIds
      .map((methodId) => candidates.find((process) => process.id === methodId || process.method_id === methodId) ?? null)
      .filter((process): process is ProcessTemplate => process !== null);
  }
  const defaults = candidates.filter((process) => process.is_default);
  return defaults.length === 1 ? defaults : [];
}

export function workpointResourceTypeProjection(
  workpoint: ProjectMasterWorkpoint,
  processes: ProcessTemplate[],
): string[] {
  const resourceTypes = new Set<string>();
  const addComponentResources = (componentType: ComponentType, explicitMethodIds: string[]) => {
    for (const process of processesForProjectedComponent(componentType, explicitMethodIds, processes)) {
      const resourceType = defaultResourceTypeForProcess(process);
      if (resourceType && !excludedResourceCatalogTypes.has(resourceType)) resourceTypes.add(resourceType);
    }
  };

  for (const structure of workpoint.structures) {
    const structureMethodIds = methodIdsFromParameters(structure.parameters);
    const upperComponentType = projectMasterUpperStructureResourceComponent[structure.structure_type];
    if (upperComponentType) addComponentResources(upperComponentType, structureMethodIds);

    for (const component of structure.components) {
      if (!component.enabled) continue;
      const componentType = projectedProjectMasterComponentType(structure.structure_type, component.component_type);
      if (!componentType) continue;
      const componentMethodIds = methodIdsFromParameters(component.parameters);
      addComponentResources(componentType, componentMethodIds.length > 0 ? componentMethodIds : structureMethodIds);
    }
  }

  return [...resourceTypes].sort((left, right) => left.localeCompare(right));
}

export function workpointStructureSummaryProjection(
  workpoint: ProjectMasterWorkpoint,
  processes: ProcessTemplate[],
): WorkpointStructureSummaryGroup[] {
  const summaries = new Map<WorkpointStructureSummaryComponentType, Map<string, WorkpointStructureSummaryItem>>();
  for (const structure of workpoint.structures) {
    for (const component of structure.components) {
      const componentType = workpointStructureSummaryComponentType(component.component_type);
      const quantity = Number(component.quantity);
      if (!componentType || !component.enabled || !Number.isFinite(quantity) || quantity <= 0) continue;
      const normalizedParameters = summaryParametersForComponent(
        componentType,
        normalizedSummaryParameters(component.parameters),
      );
      const process = resolveStructureProcess(componentType, component.parameters, structure.parameters, processes);
      const unit = component.unit.trim();
      const signature = JSON.stringify([
        componentType,
        normalizedParameters.map((parameter) => [parameter.code, parameter.signatureValue, parameter.unit]),
        process.identity,
        unit,
      ]);
      const bySignature = summaries.get(componentType) ?? new Map<string, WorkpointStructureSummaryItem>();
      const existing = bySignature.get(signature);
      if (existing) {
        const next = { ...existing, quantity: existing.quantity + quantity };
        next.displayText = summaryDisplayText(next);
        bySignature.set(signature, next);
      } else {
        const itemWithoutDisplay = {
          signature,
          componentType,
          processId: process.processId,
          processLabel: process.label,
          parameterSegments: summaryParameterSegments(componentType, normalizedParameters),
          quantity,
          unit,
        };
        bySignature.set(signature, { ...itemWithoutDisplay, displayText: summaryDisplayText(itemWithoutDisplay) });
      }
      summaries.set(componentType, bySignature);
    }
  }

  return workpointStructureSummaryDefinitions.flatMap((definition, index) => {
    const items = [...(summaries.get(definition.componentType)?.values() ?? [])]
      .sort((left, right) => left.signature.localeCompare(right.signature));
    return items.length > 0 ? [{ ...definition, sortOrder: index + 1, items }] : [];
  });
}

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

export function mergeAiWorkpointResourcePools(
  existingPools: ResourcePool[],
  additions: ResourcePool[],
): ResourcePool[] {
  if (additions.length === 0) return existingPools;
  const existingIds = new Set(existingPools.map((pool) => pool.id));
  const existingLocalKeys = new Set(
    existingPools
      .filter(isWorkpointLocalPool)
      .map((pool) => `${pool.workpoint_id}\u0000${pool.type}`),
  );
  const additionIds = new Set<string>();
  const additionKeys = new Set<string>();
  const normalizedAdditions: ResourcePool[] = [];
  for (const addition of additions) {
    const normalized = normalizeResourcePoolForWorkspace(addition);
    const key = `${normalized.workpoint_id ?? ""}\u0000${normalized.type}`;
    const quantity = resourcePoolQuantity(normalized);
    const maxQuantity = resourcePoolUsableLimit(normalized);
    if (
      !isWorkpointLocalPool(normalized)
      || !normalized.workpoint_id
      || normalized.resource_mode !== "LIMITED"
      || quantity < 1
      || maxQuantity < quantity
      || !normalized.enabled
    ) {
      throw new Error("AI 推荐包含非法的工点资源，未应用任何变更。");
    }
    if (
      existingIds.has(normalized.id)
      || existingLocalKeys.has(key)
      || additionIds.has(normalized.id)
      || additionKeys.has(key)
    ) {
      throw new Error("AI 推荐与当前资源配置冲突，未应用任何变更。");
    }
    additionIds.add(normalized.id);
    additionKeys.add(key);
    normalizedAdditions.push(normalized);
  }
  return [...existingPools, ...normalizedAdditions];
}

export function normalizeLimitedResourcePool(pool: ResourcePool): ResourcePool {
  return normalizeResourcePoolForWorkspace({ ...pool, resource_mode: "LIMITED" });
}

export function normalizeScenarioResourcePools(scenario: ScenarioInput): ScenarioInput {
  return {
    ...scenario,
    resource_pools: scenario.resource_pools
      .map(normalizeResourcePoolForWorkspace)
      .filter(isWorkpointLocalPool),
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
  const configuredChineseLabel = resourcePools
    .filter((pool) => pool.type === resourceType)
    .sort((left, right) => left.id.localeCompare(right.id))
    .map((pool) => pool.label.trim())
    .find((label) => /[\u3400-\u9fff]/u.test(label));
  return configuredChineseLabel ?? standardResourceTypeLabels[resourceType] ?? "未命名资源";
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
  return defaultResourceTypeByComponent[process.component_type] ?? process.resource_type ?? null;
}
