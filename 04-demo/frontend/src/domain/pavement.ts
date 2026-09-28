import type { ScenarioInput, ProjectMasterWorkpoint, PavementSettings, PavementProcessType, PavementDependencyRule, ResourcePool, GeneratedScheduleInput, Task } from "../contracts";

export const pavementUnits = ["m/天", "m2/天", "m3/天", "t/天"];
export const pavementProcessTypes = ["granular_base", "cement_stabilized_base", "asphalt_course"] as const;
export const emptyPavementSettings = (): PavementSettings => ({ input_kind: "customer", layer_conditions: [], ancillary_steps: [], fixed_sequences: [] });

export function newPavementFleet(id: string): ResourcePool {
  return { id, type: "pavement_paving_crew", label: "新机组", quantity: 0, max_quantity: 0,
    transfer_days: null, enabled: true, resource_mode: "LIMITED", scope_mode: "PROJECT_SHARED",
    authorized_workpoint_ids: null, calendar_id: "continuous", compatible_process_ids: [] };
}

export function togglePavementFleetProcess(pool: ResourcePool, processId: string, selected: boolean): ResourcePool {
  return { ...pool, compatible_process_ids: selected ? [...new Set([...pool.compatible_process_ids, processId])]
    : pool.compatible_process_ids.filter(id => id !== processId) };
}

export function pavementFleetErrors(scenario: Pick<ScenarioInput, "resource_pools" | "process_library">): string[] {
  const known = new Set(scenario.process_library.map(p => p.id));
  return scenario.resource_pools.flatMap(pool => {
    const errors: string[] = [];
    const name = pool.label.trim() || "未命名机组";
    if (!pool.label.trim()) errors.push("请填写机组名称。");
    if (!Number.isInteger(pool.quantity) || Number(pool.quantity) < 0) errors.push(`${name}：数量须为非负整数。`);
    if (pool.compatible_process_ids.some(id => !known.has(id))) errors.push(`${name}：请移除失效工艺并重新选择。`);
    if (pool.enabled && Number(pool.quantity) > 0) {
      if (!pool.compatible_process_ids.length) errors.push(`${name}：至少选择一种适用工艺。`);
      if (pool.transfer_days == null || !Number.isInteger(pool.transfer_days) || pool.transfer_days < 0) errors.push(`${name}：请填写非负整数转场天数。`);
    }
    return errors;
  });
}

export function pavementLayerQuantityT(length: unknown, width: unknown, thickness: unknown, density: unknown): number | null {
  const values = [length, width, thickness, density].map(value =>
    typeof value === "number" || (typeof value === "string" && value.trim()) ? Number(value) : NaN);
  if (values.some((value, i) => !Number.isFinite(value) || (i === 0 ? value < 0 : value <= 0))) return null;
  const quantity = values.reduce((total, value) => total * value, 1);
  return Number.isFinite(quantity) ? quantity : null;
}

export function pavementLayers(scenario: ScenarioInput) {
  return scenario.project.bridges.flatMap(workpoint => workpoint.work_sections.flatMap(section =>
    section.structures.flatMap(structure => structure.components.filter(c => c.enabled).map(component => ({ workpoint, section, structure, component })))));
}

export type PavementDependencyRow = {
  structure_id: string; section_name: string; predecessor_key: string; successor_key: string;
  predecessor_name: string; successor_name: string; default_lag_days: number | null;
  predecessor_id: string; successor_id: string;
  relationship: PavementDependencyRule["relationship"]; lag_days: number | null;
  source: "section" | "project" | "conditions";
};

export function pavementDependencyRows(scenario: ScenarioInput, includeDisabled = false): PavementDependencyRow[] {
  const settings = scenario.pavement_settings ?? emptyPavementSettings();
  const rules = settings.dependency_rules ?? [];
  const rows: PavementDependencyRow[] = [];
  for (const workpoint of scenario.project.bridges) for (const section of workpoint.work_sections) for (const structure of section.structures) {
    const counts: Record<string, number> = {};
    let previous: { key: string; name: string; id: string } | null = null;
    let wait: number | null = 0;
    const append = (key: string, name: string, id: string) => {
      if (previous) {
        const matches = rules.filter(r => r.predecessor_key === previous!.key && r.successor_key === key);
        const local = matches.find(r => r.structure_id === structure.id);
        const global = matches.find(r => !r.structure_id);
        const rule = local ?? global;
        rows.push({ structure_id: structure.id, section_name: section.name,
          predecessor_key: previous.key, successor_key: key, predecessor_name: previous.name, successor_name: name,
          predecessor_id: previous.id, successor_id: id,
          default_lag_days: wait, relationship: rule?.relationship ?? "FS", lag_days: rule ? rule.lag_days : wait,
          source: local ? "section" : global ? "project" : "conditions" });
      }
      previous = { key, name, id };
    };
    for (const component of [...structure.components].sort((a, b) => Number(a.properties.layer_order) - Number(b.properties.layer_order) || a.id.localeCompare(b.id))) {
      const occurrence = counts[component.component_type] = (counts[component.component_type] ?? 0) + 1;
      const key = `layer:${component.component_type}:${occurrence}`;
      // The configuration editor can retain disabled layers; task previews use only enabled layers.
      if (!component.enabled && !includeDisabled) continue;
      const prepCounts: Record<string, number> = {};
      for (const step of settings.ancillary_steps.filter(s => s.before_component_id === component.id).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id))) {
        const prepOccurrence = prepCounts[step.kind] = (prepCounts[step.kind] ?? 0) + 1;
        if (step.duration_days === 0) { wait = wait == null ? null : wait + step.wait_after_days; continue; }
        append(`${key}/prep:${step.kind}:${prepOccurrence}`, step.name, `pavement-prep:${step.id}`);
        wait = step.wait_after_days;
      }
      append(key, component.name, `pavement:${component.id}`);
      wait = settings.layer_conditions.find(c => c.component_id === component.id)?.wait_days ?? null;
    }
  }
  return rows;
}

export function setPavementDependencyRule(settings: PavementSettings, rule: PavementDependencyRule, reset = false): PavementSettings {
  const rest = (settings.dependency_rules ?? []).filter(r => !((r.structure_id ?? null) === (rule.structure_id ?? null)
    && r.predecessor_key === rule.predecessor_key && r.successor_key === rule.successor_key));
  return { ...settings, dependency_rules: reset ? rest : [...rest, rule] };
}

export function fillMissingPavementConditions(scenario: ScenarioInput, processType: PavementProcessType, waitDays: number): PavementSettings {
  if (!Number.isInteger(waitDays) || waitDays < 0) throw new Error("等待天数须为非负整数。");
  const current = scenario.pavement_settings ?? emptyPavementSettings();
  const configured = new Set(current.layer_conditions.map(c => c.component_id));
  return { ...current, layer_conditions: [...current.layer_conditions,
    ...pavementLayers(scenario).filter(l => l.component.component_type === processType && !configured.has(l.component.id))
      .map(l => ({ component_id: l.component.id, wait_days: waitDays, accepted_available_date: null, basis_note: "按工艺批量确认等待天数" })),
  ] };
}

export function pavementDuration(quantity: number, unit: string, rate: number, rateUnit: string): number | null {
  return quantity > 0 && rate > 0 && Number.isFinite(quantity) && Number.isFinite(rate) && rateUnit === `${unit}/天`
    ? Math.ceil(quantity / rate) : null;
}

export type PavementTaskRelation = {
  predecessor_id: string; predecessor_name: string;
  relationship: PavementDependencyRule["relationship"]; lag_days: number | null;
  source: string; status: "confirmed" | "pending" | "invalid";
};
export type PavementTaskRow = {
  id: string; componentId: string | null; name: string; task: Task | null;
  process: ScenarioInput["process_library"][number] | null; selectedOptionId: string;
  quantityLabel: string; roadbedDate: string; relations: PavementTaskRelation[];
};

// Identity comes from current master data; calculated values only come from this generation.
export function pavementTaskGroups(scenario: ScenarioInput, generated: GeneratedScheduleInput | null) {
  const settings = scenario.pavement_settings ?? emptyPavementSettings();
  const tasks = new Map((generated?.schedule_input.tasks ?? []).map(t => [t.id, t]));
  const links = generated?.schedule_input.precedence_links ?? [];
  const expected = pavementDependencyRows(scenario);
  const layers = pavementLayers(scenario);
  const graphInvalid = generated?.validation.some(v => v.level === "error" && v.code === "PAVEMENT_LOGIC_CYCLE") ?? false;
  const blockedIds = new Set(generated?.schedule_input.pavement_handover_scope?.blocked_sections.map(s => s.structure_id) ?? []);
  const blockedComponents = new Set(generated?.schedule_input.pavement_handover_scope?.blocked_sections.flatMap(s => s.component_ids) ?? []);
  const pendingSections = generated?.schedule_input.pavement_handover_scope?.pending_sections ?? [];
  const groups: { id: string; name: string; rows: PavementTaskRow[]; pendingHandover: (typeof pendingSections)[number] | null }[] = [];
  for (const workpoint of scenario.project.bridges) for (const section of workpoint.work_sections) for (const structure of section.structures) {
    if (blockedIds.has(structure.id)) continue;
    const rows: PavementTaskRow[] = [];
    const append = (id: string, component: typeof structure.components[number], preparationName?: string) => {
      const task = tasks.get(id) ?? null;
      const override = scenario.task_overrides?.[component.id];
      const method = override?.method_id || component.method_id;
      const matches = scenario.process_library.filter(p => p.component_type === component.component_type && (!method || p.method_id === method));
      const process = preparationName ? null : (scenario.process_library.find(p => p.id === task?.pavement_context?.process_id)
        ?? matches.find(p => p.is_default) ?? matches[0] ?? null);
      const optionId = preparationName ? "" : override?.productivity_option_id || component.productivity_option_id
        || task?.productivity_rule_id || process?.productivity_options?.find(o => o.is_default)?.id || process?.productivity_options?.[0]?.id || "";
      const relations: PavementTaskRelation[] = expected.filter(r => r.successor_id === id).map(r => {
        const edge = links.find(l => l.predecessor_id === r.predecessor_id && l.successor_id === id && l.source_rule_id === "pavement_layer_condition");
        const confirmed = !!edge && !!task && tasks.has(r.predecessor_id) && r.lag_days != null
          && edge.relationship === r.relationship && edge.lag_days === r.lag_days;
        return { predecessor_id: r.predecessor_id, predecessor_name: r.predecessor_name,
          relationship: r.relationship, lag_days: r.lag_days, source: r.source === "section" ? "分段调整" : r.source === "project" ? "统一配置" : "原有条件",
          status: graphInvalid ? "invalid" : confirmed ? "confirmed" : "pending" };
      });
      for (const sequence of settings.fixed_sequences) {
        const eligible = sequence.component_ids.filter(cid => !blockedComponents.has(cid));
        for (let i=1; i<eligible.length; i++) {
        if (`pavement:${eligible[i]}` !== id) continue;
        const predecessorId = `pavement:${eligible[i-1]}`;
        const layer = layers.find(l => l.component.id === eligible[i-1]);
        const edge = links.find(l => l.predecessor_id === predecessorId && l.successor_id === id && l.source_rule_id !== "pavement_layer_condition");
        relations.push({ predecessor_id: predecessorId, predecessor_name: layer ? `${layer.section.name} / ${layer.component.name}` : eligible[i-1],
          relationship: edge?.relationship ?? "FS", lag_days: edge?.lag_days ?? 0, source: "固定跨段顺序",
          status: !layer || graphInvalid ? "invalid" : edge && task && tasks.has(predecessorId) ? "confirmed" : "pending" });
      }}
      rows.push({ id, componentId: preparationName ? null : component.id, name: preparationName ?? component.name,
        task, process, selectedOptionId: optionId, relations,
        quantityLabel: task?.quantity_label ?? (preparationName ? "固定工期" : `${component.quantity}${component.properties.unit ?? ""}`),
        roadbedDate: pavementHandover(component.properties).label });
    };
    for (const component of [...structure.components].filter(c => c.enabled).sort((a,b) => Number(a.properties.layer_order)-Number(b.properties.layer_order) || a.id.localeCompare(b.id))) {
      for (const step of settings.ancillary_steps.filter(s => s.before_component_id === component.id && s.duration_days > 0).sort((a,b) => a.order-b.order || a.id.localeCompare(b.id))) {
        append(`pavement-prep:${step.id}`, component, step.name);
      }
      append(`pavement:${component.id}`, component);
    }
    if (rows.length) groups.push({ id: `${workpoint.id}:${structure.id}`, name: section.name, rows,
      pendingHandover: pendingSections.find(s => s.structure_id === structure.id) ?? null });
  }
  return groups;
}

export function withPavementMaster(scenario: ScenarioInput, items: ProjectMasterWorkpoint[], versionId: string): ScenarioInput {
  return { ...scenario, project_data_version_id: versionId, project: { ...scenario.project,
    bridges: items.filter(w => w.workpoint_type === "pavement").map(w => ({
      id: w.workpoint_id, name: w.workpoint_name, order: w.sort_order, workpoint_type: "pavement", import_source: {},
      work_sections: w.structures.map(s => ({ id: s.structure_id, name: s.structure_name, order: s.sort_order,
        side: s.side === "left" || s.side === "right" ? s.side : "none", upper_structures: [],
        structures: [{ id: s.structure_id, name: s.structure_name, order: s.sort_order, structure_type: "pavement_section",
          properties: Object.fromEntries(s.parameters.filter(p => ["roadbed_handover_status", "roadbed_available_date", "roadbed_handover_note"].includes(p.parameter_code)).map(p => [p.parameter_code, p.value])),
          components: [...s.components].sort((a,b) => a.sort_order - b.sort_order).filter(c => pavementProcessTypes.includes(c.component_type as typeof pavementProcessTypes[number])).map(c => ({
            id: c.component_id, name: c.component_name, component_type: c.component_type as typeof pavementProcessTypes[number],
            quantity: c.quantity, quantity_label: `${c.quantity}${c.unit}`, enabled: c.enabled,
            properties: { ...Object.fromEntries(s.parameters.map(p => [p.parameter_code, p.value])),
              ...Object.fromEntries(c.parameters.map(p => [p.parameter_code, p.value])),
              ...Object.fromEntries(["roadbed_handover_status", "roadbed_available_date", "roadbed_handover_note"].map(key => [key, s.parameters.find(p => p.parameter_code === key)?.value ?? null])),
              unit: c.unit, layer_order: c.sort_order },
          })) }],
      })),
    })),
  }};
}
export function pavementHandover(properties: Record<string, unknown>) {
  const date = String(properties.roadbed_available_date || "");
  const status = String(properties.roadbed_handover_status || (date ? "dated" : "pending"));
  const validDate = /^\d{4}-\d{2}-\d{2}$/.test(date) && Number.isFinite(Date.parse(date)) && new Date(date).toISOString().slice(0,10) === date;
  const invalid = !["dated", "handed_over", "pending"].includes(status) || (status === "dated" ? !validDate : !!date);
  const note = String(properties.roadbed_handover_note || (status === "pending" ? properties.roadbed_handover_status ? "移交日期未定，暂不可开工" : "尚未明确移交条件" : ""));
  return { status, date, note, invalid, label: invalid ? "移交条件无效" : status === "dated" ? date : status === "handed_over" ? "已移交（按计划开始日）" : "移交待定" };
}
