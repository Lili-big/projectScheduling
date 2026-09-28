import { findComponent } from "./projectTree";
import type { ScenarioInput, Task, TaskOverride } from "../contracts";

export function scenarioWithTaskProcessPatch(scenario: ScenarioInput, task: Task, patch: TaskOverride): ScenarioInput {
  const componentId = task.component_id ?? task.id;
  if (scenario.engineering_domain === "pavement") return scenarioWithTaskOverridePatch(scenario, componentId, patch);
  if (findComponent(scenario.project, componentId)) {
    return scenarioWithComponentPatch(scenario, componentId, patch);
  }
  return scenarioWithTaskOverridePatch(scenario, task.id, patch);
}

export function scenarioWithComponentPatch(scenario: ScenarioInput, componentId: string, patch: TaskOverride): ScenarioInput {
  return {
    ...scenario,
    project: {
      ...scenario.project,
      bridges: scenario.project.bridges.map((bridge) => ({
        ...bridge,
        work_sections: bridge.work_sections.map((section) => ({
          ...section,
          structures: section.structures.map((structure) => ({
            ...structure,
            components: structure.components.map((component) =>
              component.id === componentId ? { ...component, ...patch } : component,
            ),
          })),
        })),
      })),
    },
  };
}

export function scenarioWithTaskOverridePatch(scenario: ScenarioInput, taskId: string, patch: TaskOverride): ScenarioInput {
  const overrides = { ...(scenario.task_overrides ?? {}) };
  const nextOverride = compactTaskOverride({ ...(overrides[taskId] ?? {}), ...patch });
  if (nextOverride) {
    overrides[taskId] = nextOverride;
  } else {
    delete overrides[taskId];
  }
  return { ...scenario, task_overrides: overrides };
}

export function compactTaskOverride(override: TaskOverride): TaskOverride | null {
  const next: TaskOverride = {};
  if (override.method_id !== undefined && override.method_id !== null) {
    next.method_id = override.method_id;
  }
  if (override.productivity_option_id !== undefined && override.productivity_option_id !== null) {
    next.productivity_option_id = override.productivity_option_id;
  }
  return next.method_id !== undefined || next.productivity_option_id !== undefined ? next : null;
}
