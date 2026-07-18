import type { ProjectMasterWorkpoint, TaskViewFilters, TaskViewRow, WorkSectionSide } from "../../contracts";
import { componentLabels, sideLabels } from "../../domain/labels";

export type TaskViewProjectMasterMaps = {
  bridges: Map<string, { name: string; order: number }>;
  sections: Map<string, { name: string; order: number; sideLabel: string }>;
};

export const taskViewNameUnavailable = "名称不可用";

export function buildProjectMasterTaskViewMaps(workpoints: ProjectMasterWorkpoint[]): TaskViewProjectMasterMaps {
  const bridges = new Map<string, { name: string; order: number }>();
  const sections = new Map<string, { name: string; order: number; sideLabel: string }>();

  for (const workpoint of workpoints) {
    bridges.set(workpoint.workpoint_id, {
      name: workpoint.workpoint_name.trim() || taskViewNameUnavailable,
      order: workpoint.sort_order,
    });
    for (const structure of workpoint.structures) {
      if (!structure.section_code) continue;
      // Keep the display lookup aligned with project_master/scheduling_adapter.py.
      const side: WorkSectionSide = structure.side === "left" || structure.side === "right"
        ? structure.side
        : "none";
      const sectionId = `${structure.section_code}:${side}`;
      const current = sections.get(sectionId);
      if (current && current.order <= structure.sort_order) continue;
      sections.set(sectionId, {
        name: structure.section_name?.trim() || taskViewNameUnavailable,
        order: structure.sort_order,
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
