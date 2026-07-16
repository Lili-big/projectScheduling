import type { TaskViewFilters, TaskViewRow } from "../../contracts";
import { componentLabels } from "../../domain/labels";

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
