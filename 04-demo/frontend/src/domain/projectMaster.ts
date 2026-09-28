import type {
  ProjectMasterDiffEntry,
  ProjectMasterIssue,
  ProjectMasterSide,
  ProjectMasterWorkpoint,
  ProjectMasterWorkpointType,
} from "../contracts/projectMaster";

export const projectMasterWorkpointTypeLabels: Record<ProjectMasterWorkpointType, string> = {
  pavement: "路面",
  bridge: "桥梁",
  roadbed: "路基",
  tunnel: "隧道",
  culvert: "涵洞",
  interchange: "互通",
  service_area: "服务区",
  station_yard: "场站",
  access_road: "便道",
  other: "其他",
};

export const projectMasterSideLabels: Record<ProjectMasterSide, string> = {
  left: "左幅",
  right: "右幅",
  shared: "共用",
  none: "不适用",
};

export function sortProjectMasterHierarchy(items: ProjectMasterWorkpoint[]): ProjectMasterWorkpoint[] {
  return [...items]
    .sort((a, b) => a.sort_order - b.sort_order || a.workpoint_id.localeCompare(b.workpoint_id))
    .map((workpoint) => ({
      ...workpoint,
      structures: [...workpoint.structures]
        .sort((a, b) => a.sort_order - b.sort_order || a.structure_id.localeCompare(b.structure_id))
        .map((structure) => ({
          ...structure,
          components: [...structure.components].sort(
            (a, b) => a.sort_order - b.sort_order || a.component_id.localeCompare(b.component_id),
          ),
        })),
    }));
}

export function groupProjectMasterDiffs(items: ProjectMasterDiffEntry[]) {
  return {
    added: items.filter((item) => item.change_type === "added"),
    modified: items.filter((item) => item.change_type === "modified"),
    deleted: items.filter((item) => item.change_type === "deleted"),
  };
}

export function projectMasterIssueLocation(issue: ProjectMasterIssue): string {
  return [issue.sheet_name, issue.row_no ? `第 ${issue.row_no} 行` : null, issue.field_name]
    .filter(Boolean)
    .join(" · ");
}
