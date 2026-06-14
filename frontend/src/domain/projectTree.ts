import { componentLabels } from "./labels";
import type { ComponentModel, ComponentType, ProjectModel, StructureModel, WorkSection } from "../types/scheduler";

export function findWorkSection(project: ProjectModel, sectionId: string): WorkSection | null {
  for (const bridge of project.bridges) {
    const section = bridge.work_sections.find((item) => item.id === sectionId);
    if (section) return section;
  }
  return null;
}

export function findStructure(project: ProjectModel, structureId: string): { section: WorkSection; structure: StructureModel } | null {
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      const structure = section.structures.find((item) => item.id === structureId);
      if (structure) return { section, structure };
    }
  }
  return null;
}

export function findComponent(project: ProjectModel, componentId: string): { section: WorkSection; structure: StructureModel; component: ComponentModel } | null {
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      for (const structure of section.structures) {
        const component = structure.components.find((item) => item.id === componentId);
        if (component) return { section, structure, component };
      }
    }
  }
  return null;
}

export function isComponentType(value: string | null | undefined): value is ComponentType {
  return Boolean(value && Object.prototype.hasOwnProperty.call(componentLabels, value));
}
