import { componentLabels, sideLabels } from "./labels";
import { findComponent, findStructure, findWorkSection, isComponentType } from "./projectTree";
import type { MilestoneConstraint, MilestoneResult, ScenarioInput } from "../contracts";

export function milestoneStatusClass(milestone: MilestoneResult): string {
  if (milestone.status !== "late") return milestone.status;
  return milestone.mode === "hard" ? "late-hard" : "late-soft";
}

export function scopeLabel(milestone: MilestoneConstraint, scenario: ScenarioInput): string {
  const project = scenario.project;
  if (milestone.scope_type === "project") {
    return "全部桥梁/工点 · 全部下部结构及上部现浇结构";
  }

  if (milestone.scope_type === "bridge") {
    const bridge = project.bridges.find((item) => item.id === milestone.scope_id) ?? project.bridges[0];
    return bridge ? `${bridge.name} · 全部下部结构及上部现浇结构` : "全桥 · 全部下部结构及上部现浇结构";
  }

  if (milestone.scope_type === "work_section") {
    const section = findWorkSection(project, milestone.scope_id ?? "");
    if (!section) return "指定工点 · 全部下部结构及上部现浇结构";
    if (section.side && section.side !== "none") {
      return `${sideLabels[section.side]} · 全部下部结构及上部现浇结构`;
    }
    return `${section.name} · 全部下部结构及上部现浇结构`;
  }

  if (milestone.scope_type === "structure") {
    const found = findStructure(project, milestone.scope_id ?? "");
    return found ? `${found.structure.support_no ?? found.structure.name} · 全部下部结构` : "指定墩台 · 全部下部结构";
  }

  if (milestone.scope_type === "component") {
    if (isComponentType(milestone.scope_id)) {
      return `全部${componentLabels[milestone.scope_id]}`;
    }
    const found = findComponent(project, milestone.scope_id ?? "");
    if (found) {
      const location = found.structure.support_no ?? found.structure.name;
      return `${location} · ${componentLabels[found.component.component_type]}`;
    }
    return "指定构件";
  }

  return "-";
}
