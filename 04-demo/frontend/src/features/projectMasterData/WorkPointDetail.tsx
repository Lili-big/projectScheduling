import type {
  ProjectMasterComponent,
  ProjectMasterParameter,
  ProjectMasterSide,
  ProjectMasterStructure,
  ProjectMasterWorkpoint,
} from "../../contracts/projectMaster";
import { projectMasterSideLabels, projectMasterWorkpointTypeLabels } from "../../domain/projectMaster";

const SIDE_ORDER: ProjectMasterSide[] = ["left", "right", "shared", "none"];
const STRUCTURE_PARAMETER_LABELS: Record<string, string> = {
  start_chainage: "起点桩号（原文）", end_chainage: "终点桩号（原文）", construction_length_m: "确认净施工长度",
  width_m: "宽度", roadbed_available_date: "路床最早可用日期", quantity_basis_confirmed: "净量依据已确认",
  quantity_basis_note: "净量依据说明", quantity_basis: "数量依据", thickness_m: "厚度（统一m）",
  mileage_start_text: "起点里程",
  mileage_end_text: "终点里程",
  span_index: "跨序号",
  span_length_m: "跨径",
  bearing_from: "起点墩台",
  bearing_to: "终点墩台",
  span_expression: "联跨",
  main_pier_ids: "主墩",
  segment_count: "节段数",
  beam_count_per_span: "每跨梁片",
};

export function WorkPointDetail({ workpoint, loading }: { workpoint: ProjectMasterWorkpoint | null; loading: boolean }) {
  if (loading) return <section className="project-master-detail project-master-empty">正在读取工点结构…</section>;
  if (!workpoint) return <section className="project-master-detail project-master-empty">从左侧选择一个工点查看结构物与构件参数</section>;
  const sideGroups = groupStructuresBySide(workpoint.structures);
  return (
    <section className="project-master-detail" aria-label="工点明细">
      <div className="project-master-detail-heading">
        <div>
          <span>{projectMasterWorkpointTypeLabels[workpoint.workpoint_type]}</span>
          <h3>{workpoint.workpoint_name}</h3>
          <p className="project-master-detail-summary">
            起点 {formatMileage(workpoint.start_mileage_m)} · 终点 {formatMileage(workpoint.end_mileage_m)} · {workpoint.structures.length} 个结构物
          </p>
        </div>
        <b className={workpoint.schedule_support !== "not_supported" ? "supported" : "unsupported"}>
          {workpoint.schedule_support === "pavement_supported" ? "支持路面排程" : workpoint.schedule_support === "bridge_supported" ? "支持桥梁排程" : "当前不参与排程"}
        </b>
      </div>
      {workpoint.workpoint_type === "pavement" && workpoint.remark && <p>{workpoint.remark}</p>}
      <div className="project-master-structure-list">
        {sideGroups.map(({ side, structures }) => (
          <section className="project-master-side-group" key={side}>
            <header className="project-master-side-heading">
              <b>{projectMasterSideLabels[side]}</b>
              <small>{structures.length} 个结构单元</small>
            </header>
            <div className="project-master-side-structures">
              {structures.map((structure) => (
                <article key={structure.structure_id}>
                  <header className="project-master-structure-heading">
                    <strong>{displayStructureName(structure)}</strong>
                  </header>
                  {workpoint.workpoint_type === "pavement" && structure.remark && <p>{structure.remark}</p>}
                  {structure.parameters.length > 0 && (
                    <div className="project-master-parameter-grid">
                      {structure.parameters.map((parameter) => (
                        <div key={parameter.parameter_code}>
                          <span>{STRUCTURE_PARAMETER_LABELS[parameter.parameter_code] || "结构参数"}</span>
                          <strong>{formatParameterValue(parameter)}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="project-master-components">
                    {workpoint.workpoint_type === "pavement" && structure.components.length === 0 && <p>该施工段尚未配置结构层，补齐层序、厚度和工程量单位后可生成施工任务。</p>}
                    {structure.components.map((component) => {
                      const parameterSummary = component.parameters
                        .map((parameter) => formatComponentParameter(component, parameter))
                        .filter((item): item is string => Boolean(item));
                      return (
                        <div className="project-master-component-row" key={component.component_id}>
                          <span className="project-master-component-main">
                            <strong>{displayComponentName(component)}</strong>
                            {parameterSummary.length > 0 && <small>{parameterSummary.join(" · ")}</small>}
                          </span>
                          <b>{formatQuantity(component.quantity)} {component.unit}</b>
                        </div>
                      );
                    })}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function groupStructuresBySide(structures: ProjectMasterStructure[]) {
  return SIDE_ORDER
    .map((side) => ({ side, structures: structures.filter((structure) => structure.side === side) }))
    .filter((group) => group.structures.length > 0);
}

function displayStructureName(structure: ProjectMasterStructure): string {
  return structure.structure_name
    .replace(/^(左幅|右幅|共用)/, "")
    .replace(/(左幅|右幅)$/, "")
    .trim();
}

function displayComponentName(component: ProjectMasterComponent): string {
  return component.component_name.replace(/[（(][\d.\s*×xX]+[）)]$/, "").trim();
}

function formatComponentParameter(component: ProjectMasterComponent, parameter: ProjectMasterParameter): string | null {
  const rawValue = parameter.value == null ? "" : String(parameter.value);
  if (parameter.parameter_code === "form" && component.component_name.includes(rawValue)) {
    if (!isDimensionValue(rawValue)) return null;
  }
  const label = componentParameterLabel(component.component_type, parameter.parameter_code);
  return label ? `${label} ${formatParameterValue(parameter)}` : null;
}

function componentParameterLabel(componentType: string, parameterCode: string): string | null {
  if (parameterCode === "diameter_m") {
    if (componentType === "pile") return "桩径";
    if (componentType === "pier_body") return "截面直径";
    return "直径";
  }
  if (parameterCode === "length_m") {
    if (componentType === "pile") return "桩长";
    if (componentType === "precast_beam") return "梁长";
    return "长度";
  }
  if (parameterCode === "height_m") return "高度";
  if (parameterCode === "form") {
    if (["cap", "tie_beam", "cap_beam"].includes(componentType)) return "尺寸";
    if (["precast_beam", "cast_in_place_box_beam", "cast_in_place_continuous_beam"].includes(componentType)) return "结构形式";
    return "构造形式";
  }
  return STRUCTURE_PARAMETER_LABELS[parameterCode] || "参数";
}

function formatParameterValue(parameter: ProjectMasterParameter): string {
  const rawValue = parameter.value == null ? "—" : typeof parameter.value === "boolean" ? (parameter.value ? "是" : "否") : String(parameter.value);
  if (parameter.parameter_code === "quantity_basis") {
    return rawValue === "entered" ? "人工确认工程量" : rawValue === "geometric" ? "按几何尺寸计算" : rawValue;
  }
  if (parameter.parameter_code === "form" && isDimensionValue(rawValue)) {
    return `${rawValue.replace(/\s*[*×xX]\s*/g, " × ")} m`;
  }
  const defaultUnit = parameter.parameter_code.endsWith("_m") ? "m" : parameter.parameter_code === "beam_count_per_span" ? "片" : "";
  const unit = parameter.unit || defaultUnit;
  return `${rawValue}${unit ? ` ${unit}` : ""}`;
}

function isDimensionValue(value: string): boolean {
  return /^\d+(?:\.\d+)?(?:\s*[*×xX]\s*\d+(?:\.\d+)?)+$/.test(value.trim());
}

function formatQuantity(value: number): string {
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 3 });
}

function formatMileage(value?: number | null): string {
  return value == null ? "—" : `${value.toLocaleString()} m`;
}
