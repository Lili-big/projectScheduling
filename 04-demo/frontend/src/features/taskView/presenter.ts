import type { TaskViewDisplayWorkpoint, TaskViewFilters, TaskViewRow, WorkSectionSide } from "../../contracts";
import { componentLabels, sideLabels } from "../../domain/labels";

export type TaskViewProjectMasterMaps = {
  bridges: Map<string, { name: string; order: number }>;
  sections: Map<string, { name: string; order: number; sideLabel: string }>;
};

export const taskViewNameUnavailable = "名称不可用";

export function buildProjectMasterTaskViewMaps(workpoints: TaskViewDisplayWorkpoint[]): TaskViewProjectMasterMaps {
  const bridges = new Map<string, { name: string; order: number }>();
  const sections = new Map<string, { name: string; order: number; sideLabel: string }>();

  for (const workpoint of workpoints) {
    bridges.set(workpoint.workpoint_id, {
      name: workpoint.workpoint_name.trim() || taskViewNameUnavailable,
      order: workpoint.sort_order,
    });
    for (const section of workpoint.work_sections) {
      const side: WorkSectionSide = section.side === "left" || section.side === "right"
        ? section.side
        : "none";
      const current = sections.get(section.work_section_id);
      if (current && current.order <= section.sort_order) continue;
      sections.set(section.work_section_id, {
        name: section.work_section_name?.trim() || taskViewNameUnavailable,
        order: section.sort_order,
        sideLabel: sideLabels[side],
      });
    }
  }

  return { bridges, sections };
}

export function filterTaskViewRows(rows: TaskViewRow[], filters: TaskViewFilters): TaskViewRow[] {
  const structureNeedle = filters.structureText.trim().toLowerCase();
  const processNeedle = filters.processText.trim().toLowerCase();
  return rows.filter((row) => {
    if (structureNeedle && !row.searchText.includes(structureNeedle)) return false;
    if (!processNeedle) return true;
    return `${row.task.process_name} ${componentLabels[row.task.component_type]}`.toLowerCase().includes(processNeedle);
  });
}

export function groupTaskRowsByStructure(rows: TaskViewRow[]): Map<string, TaskViewRow[]> {
  const groups = new Map<string, TaskViewRow[]>();
  for (const row of rows) {
    const key = `${row.task.bridge_id ?? "-"}:${row.task.work_section_id ?? "-"}:${row.parentStructureId}`;
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return groups;
}
