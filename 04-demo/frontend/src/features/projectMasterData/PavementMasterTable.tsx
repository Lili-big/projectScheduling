import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { getProjectMasterWorkpoint, listProjectMasterWorkpoints, initializePavementLayers, savePavementSectionLayers, savePavementHandover } from "../../api/projectMasterApi";
import type { PavementLayerEdit, ProjectMasterParameter, ProjectMasterWorkpoint, SavePavementHandoverRequest } from "../../contracts/projectMaster";
import { projectMasterSideLabels, sortProjectMasterHierarchy } from "../../domain/projectMaster";
import { pavementLayerQuantityT, pavementHandover } from "../../domain/pavement";
import { PavementSectionLayers } from "./PavementSectionLayers";
import { PavementSectionHandover } from "./PavementSectionHandover";

export function PavementMasterBrowser({ versionId, editable, onVersionSaved, expandedSectionId, onExpand, onDirtyChange }: {
  versionId: string; editable: boolean; onVersionSaved: (versionId: string) => Promise<void>;
  expandedSectionId: string | null | undefined; onExpand: (id: string | null) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const [items, setItems] = useState<ProjectMasterWorkpoint[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const dirtyEditors = useRef(new Set<string>());
  const reportDirty = useCallback((key: string, dirty: boolean) => {
    if (dirty) dirtyEditors.current.add(key); else dirtyEditors.current.delete(key);
    onDirtyChange?.(dirtyEditors.current.size > 0);
  }, [onDirtyChange]);

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    async function load() {
      const details: ProjectMasterWorkpoint[] = [];
      for (let page = 1; ; page++) {
        const result = await listProjectMasterWorkpoints(versionId, { page, pageSize: 200, workpointType: "pavement" });
        if (cancelled) return;
        details.push(...await Promise.all(result.items.map(item => getProjectMasterWorkpoint(versionId, item.workpoint_id))));
        if (cancelled) return;
        if (details.length >= result.total || result.items.length === 0) break;
      }
      if (editable && details.some(w => w.structures.some(s => s.components.length === 0))) {
        const initialized = await initializePavementLayers(versionId);
        if (cancelled) return;
        if (initialized.version_id !== versionId) { await onVersionSaved(initialized.version_id); return; }
      }
      setItems(details);
    }
    void load().catch(reason => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : String(reason));
    });
    return () => { cancelled = true; };
  }, [versionId, attempt, editable]);

  if (error) return <section className="panel full pavement-master-state" role="alert">
    <p>施工段读取失败：{error}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>重新加载</button>
  </section>;
  if (!items) return <section className="panel full pavement-master-state" role="status">正在读取施工段…</section>;
  return <PavementMasterTable workpoints={items} readOnly={!editable} expandedSectionId={expandedSectionId} onExpand={onExpand} onDirtyChange={reportDirty} onSaveLayers={async (sectionId, layers) => {
    const saved = await savePavementSectionLayers(versionId, sectionId, layers);
    await onVersionSaved(saved.version_id);
    if (saved.version_id === versionId) setAttempt(value => value + 1);
  }} onSaveHandover={async (sectionId, values) => {
    const saved = await savePavementHandover(versionId, sectionId, values);
    await onVersionSaved(saved.version_id);
    if (saved.version_id === versionId) setAttempt(value => value + 1);
  }} />;
}

const numberFormat = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 });
const tonnageFormat = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });
const layerTypeLabels: Record<string, string> = {
  granular_base: "碎石", cement_stabilized_base: "水稳", asphalt_course: "沥青",
};
const parameterLabels: Record<string, string> = {
  thickness_m: "厚度", layer_order: "层序", construction_length_m: "施工长度", width_m: "宽度",
  quantity_basis: "工程量依据", quantity_basis_confirmed: "净量依据已确认", quantity_basis_note: "净量依据说明",
  start_chainage: "起点桩号", end_chainage: "终点桩号", roadbed_available_date: "路床移交日期",
};

function parameterValue(parameters: ProjectMasterParameter[], code: string): unknown {
  return parameters.find(parameter => parameter.parameter_code === code)?.value;
}

function numberValue(parameters: ProjectMasterParameter[], code: string): number | null {
  const value = parameterValue(parameters, code);
  if (typeof value !== "number" && typeof value !== "string") return null;
  if (typeof value === "string" && !value.trim()) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function textValue(parameters: ProjectMasterParameter[], code: string): string {
  const value = parameterValue(parameters, code);
  return value == null || value === "" ? "—" : String(value);
}

function formatNumber(value: number | null): string {
  return value == null ? "—" : numberFormat.format(value);
}

function formatParameter(parameter: ProjectMasterParameter): string {
  let value = parameter.value == null ? "—" : String(parameter.value);
  if (typeof parameter.value === "boolean") value = parameter.value ? "是" : "否";
  if (parameter.parameter_code === "quantity_basis") value = value === "entered" ? "人工确认" : value === "geometric" ? "几何计算" : value;
  const unit = parameter.unit || (parameter.parameter_code.endsWith("_m") ? "m" : "");
  return `${parameterLabels[parameter.parameter_code] || parameter.parameter_code}：${value}${unit ? ` ${unit}` : ""}`;
}

export function PavementMasterTable({ workpoints, readOnly = true, expandedSectionId, onExpand, onSaveLayers, onSaveHandover, onDirtyChange }: {
  workpoints: ProjectMasterWorkpoint[]; readOnly?: boolean; expandedSectionId?: string | null;
  onExpand?: (id: string | null) => void; onSaveLayers?: (sectionId: string, layers: PavementLayerEdit[]) => Promise<void>;
  onSaveHandover?: (sectionId: string, values: SavePavementHandoverRequest) => Promise<void>;
  onDirtyChange?: (key: string, dirty: boolean) => void;
}) {
  const sortedWorkpoints = sortProjectMasterHierarchy(workpoints);
  const rows = sortedWorkpoints.flatMap(workpoint => workpoint.structures
    .map(structure => ({ workpoint, structure, length: numberValue(structure.parameters, "construction_length_m") })));
  if (!rows.length) return <section className="panel full pavement-master-state">当前版本暂无路面施工段，请导入包含施工段的路面主数据。</section>;

  const totalLength = rows.reduce((sum, row) => sum + (row.length ?? 0), 0);
  const missingLength = rows.filter(row => row.length == null).length;
  const layers = rows.flatMap(row => row.structure.components
    .map(component => ({ ...row, component })));
  const multipleWorkpoints = workpoints.length > 1;
  const expanded = expandedSectionId === undefined ? rows[0]?.structure.structure_id : expandedSectionId;

  return <section className="panel full pavement-master" aria-label="路面施工段主数据">
    <header className="pavement-master-heading">
      <h3>施工段明细</h3>
      <p><strong>{rows.length}</strong> 个施工段<span>·</span>{missingLength ? "已填写长度" : "施工总长度"} <strong>{numberFormat.format(totalLength)}</strong> m</p>
    </header>
    <div className="pavement-master-scroll" role="region" aria-label="施工段明细表，可横向滚动" tabIndex={0}>
      <table className="pavement-master-table" aria-label="施工段明细">
        <thead><tr>
          {onExpand && <th scope="col" className="pavement-section-toggle-cell" aria-label="展开或收起结构层" />}
          <th scope="col">序号</th>{multipleWorkpoints && <th scope="col">所属工点</th>}
          <th scope="col">分段</th><th scope="col">段落桩号</th>
          <th scope="col" className="numeric">施工长度（m）</th>
          <th scope="col" className="numeric">宽度（m）</th>
          <th scope="col">路床移交 / 受阻原因</th>
        </tr></thead>
        <tbody>{rows.map(({ workpoint, structure, length }, index) => {
          const width = numberValue(structure.parameters, "width_m");
          const handover = pavementHandover(Object.fromEntries(structure.parameters.map(p => [p.parameter_code, p.value])));
          return <Fragment key={`${workpoint.workpoint_id}/${structure.structure_id}`}><tr>
            {onExpand && <td className="pavement-section-toggle-cell"><button type="button" className="pavement-section-toggle" title={expanded === structure.structure_id ? "收起结构层" : "展开结构层"} aria-expanded={expanded === structure.structure_id} aria-label={`${expanded === structure.structure_id ? "收起" : "展开"}${structure.structure_name}结构层`} onClick={() => onExpand(expanded === structure.structure_id ? null : structure.structure_id)}>{expanded === structure.structure_id ? <ChevronDown size={16} aria-hidden="true" /> : <ChevronRight size={16} aria-hidden="true" />}</button></td>}
            <td className="pavement-master-sequence">{index + 1}</td>
            {multipleWorkpoints && <td>{workpoint.workpoint_name}</td>}
            <th scope="row">{structure.section_name || structure.structure_name || projectMasterSideLabels[structure.side]}</th>
            <td className="pavement-master-chainage" title={structure.remark || undefined}>{textValue(structure.parameters, "start_chainage")}–{textValue(structure.parameters, "end_chainage")}</td>
            <td className={`numeric${length == null ? " unconfirmed" : ""}`}>{formatNumber(length)}</td>
            <td className={`numeric${width == null ? " unconfirmed" : ""}`}>{formatNumber(width)}</td>
            <td className="pavement-master-date">{handover.label}{handover.status === "pending" && `：${handover.note}`}</td>
          </tr>{onExpand && expanded === structure.structure_id && <tr className="pavement-section-detail-row"><td colSpan={multipleWorkpoints ? 8 : 7}>
            <PavementSectionHandover section={structure} readOnly={readOnly} onSave={onSaveHandover} onDirtyChange={onDirtyChange} />
            <PavementSectionLayers section={structure} readOnly={readOnly} onSave={onSaveLayers} onDirtyChange={onDirtyChange} />
          </td></tr>}</Fragment>;
        })}</tbody>
      </table>
    </div>
    {!onExpand && layers.length > 0 && <>
      <header className="pavement-master-heading pavement-master-layer-heading"><h3>结构层明细</h3><p>{layers.length} 个结构层</p></header>
      <div className="pavement-master-scroll" role="region" aria-label="结构层明细表，可横向滚动" tabIndex={0}>
        <table className="pavement-master-table" aria-label="结构层明细">
          <thead><tr>{multipleWorkpoints && <th scope="col">所属工点</th>}<th scope="col">施工段</th><th scope="col">层序</th><th scope="col">结构层</th><th scope="col">工艺类型</th><th scope="col" className="numeric">厚度（m）</th><th scope="col" className="numeric">密度（t/m³）</th><th scope="col" className="numeric">工程量（t）</th><th scope="col">状态</th><th scope="col">参数与说明</th></tr></thead>
          <tbody>{layers.map(({ workpoint, structure, length, component }) => {
            const quantity = pavementLayerQuantityT(length, numberValue(structure.parameters, "width_m"), numberValue(component.parameters, "thickness_m"), numberValue(component.parameters, "density_t_m3"));
            return <tr key={`${workpoint.workpoint_id}/${structure.structure_id}/${component.component_id}`}>
            {multipleWorkpoints && <td>{workpoint.workpoint_name}</td>}<th scope="row">{structure.structure_name}</th><td>{component.sort_order}</td>
            <td>{component.component_name}</td><td>{layerTypeLabels[component.component_type] || component.component_type}</td>
            <td className="numeric">{formatNumber(numberValue(component.parameters, "thickness_m"))}</td>
            <td className="numeric">{formatNumber(numberValue(component.parameters, "density_t_m3"))}</td>
            <td className="numeric">{quantity == null ? "—" : tonnageFormat.format(quantity)}</td><td>{component.enabled ? "启用" : "停用"}</td>
            <td className="pavement-master-layer-notes">{component.parameters.filter(p => !["thickness_m", "density_t_m3"].includes(p.parameter_code)).map(p => <div key={p.parameter_code}>{formatParameter(p)}</div>)}{component.remark}</td>
          </tr>; })}</tbody>
        </table>
      </div>
    </>}
  </section>;
}
