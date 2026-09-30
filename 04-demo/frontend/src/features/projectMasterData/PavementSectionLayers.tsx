import { useEffect, useState } from "react";
import type { PavementLayerEdit, ProjectMasterStructure } from "../../contracts/projectMaster";
import { pavementLayerQuantityT } from "../../domain/pavement";

const processNames = { granular_base: "碎石", cement_stabilized_base: "水稳", asphalt_course: "沥青" };
type LayerRow = Omit<PavementLayerEdit, "thickness_m" | "density_t_m3"> & { key: string; thickness: string; density: string };
const tonnageFormat = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });
const validDimension = (value: string) => !value.trim() || (Number.isFinite(Number(value)) && Number(value) > 0);

export function PavementSectionLayers({ section, readOnly, onSave, onDirtyChange }: {
  section: ProjectMasterStructure;
  readOnly: boolean;
  onSave?: (sectionId: string, layers: PavementLayerEdit[]) => Promise<void>;
  onDirtyChange?: (key: string, dirty: boolean) => void;
}) {
  const initialRows = (): LayerRow[] => [...section.components].sort((a, b) => a.sort_order - b.sort_order).map(c => ({
    key: c.component_id, component_id: c.component_id, name: c.component_name,
    process_type: c.component_type as PavementLayerEdit["process_type"], enabled: c.enabled,
    thickness: String(c.parameters.find(p => p.parameter_code === "thickness_m")?.value ?? ""),
    density: String(c.parameters.find(p => p.parameter_code === "density_t_m3")?.value ?? ""),
  }));
  const [rows, setRows] = useState(initialRows);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { onDirtyChange?.(`${section.structure_id}:layers`, dirty || busy); }, [onDirtyChange, section.structure_id, dirty, busy]);
  useEffect(() => () => onDirtyChange?.(`${section.structure_id}:layers`, false), [onDirtyChange, section.structure_id]);
  const length = section.parameters.find(p => p.parameter_code === "construction_length_m")?.value;
  const width = section.parameters.find(p => p.parameter_code === "width_m")?.value;
  const valid = rows.length > 0 && rows.every(r => r.name.trim() && validDimension(r.thickness) && validDimension(r.density));
  function change(next: LayerRow[]) { setRows(next); setDirty(true); setError(""); }
  function patch(key: string, values: Partial<LayerRow>) { change(rows.map(r => r.key === key ? { ...r, ...values } : r)); }
  function move(index: number, offset: number) { const next = [...rows]; [next[index], next[index + offset]] = [next[index + offset], next[index]]; change(next); }
  async function save() {
    if (!valid || !onSave) return;
    setBusy(true); setError("");
    try {
      await onSave(section.structure_id, rows.map(r => ({ component_id: r.component_id, name: r.name.trim(), process_type: r.process_type, thickness_m: r.thickness.trim() ? Number(r.thickness) : null, density_t_m3: r.density.trim() ? Number(r.density) : null, enabled: r.enabled })));
      setDirty(false);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <section className="pavement-section-editor" aria-label={`${section.structure_name}结构层`}>
    <header><h4>{section.structure_name} · 结构层</h4><span>{readOnly ? "历史版本，只读" : dirty ? "未保存" : "已保存"}</span></header>
    {error && <p role="alert">{error}</p>}
    <fieldset disabled={readOnly || busy}>
      <table aria-label="结构层明细"><thead><tr><th>层序</th><th>启用</th><th>结构层名称</th><th>工艺</th><th>厚度（m）</th><th>密度（t/m³）</th><th title="工程量 = 施工长度 × 宽度 × 厚度 × 密度">工程量（t）</th>{!readOnly && <th>调整</th>}</tr></thead>
        <tbody>{rows.map((r, i) => {
          const quantity = pavementLayerQuantityT(length, width, r.thickness, r.density);
          return <tr key={r.key}>
          <td>{i + 1}</td><td><input type="checkbox" aria-label={`第${i + 1}层启用`} checked={r.enabled} onChange={e => patch(r.key, { enabled: e.target.checked })} /></td>
          <td><input aria-label={`第${i + 1}层名称`} maxLength={100} value={r.name} onChange={e => patch(r.key, { name: e.target.value })} /></td>
          <td><select aria-label={`第${i + 1}层工艺`} value={r.process_type} onChange={e => patch(r.key, { process_type: e.target.value as LayerRow["process_type"] })}>
            {Object.entries(processNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select></td>
          <td><input type="number" min="0.001" step="any" aria-label={`第${i + 1}层厚度`} placeholder="待填写" value={r.thickness} onChange={e => patch(r.key, { thickness: e.target.value })} /></td>
          <td><input type="number" min="0.001" step="any" aria-label={`第${i + 1}层密度`} placeholder="待填写" value={r.density} onChange={e => patch(r.key, { density: e.target.value })} /></td>
          <td className="numeric">{quantity == null ? "—" : tonnageFormat.format(quantity)}</td>
          {!readOnly && <td className="pavement-section-layer-actions"><button disabled={i === 0} aria-label={`上移第${i + 1}层`} onClick={() => move(i, -1)}>上移</button><button disabled={i === rows.length - 1} aria-label={`下移第${i + 1}层`} onClick={() => move(i, 1)}>下移</button><button disabled={rows.length === 1} aria-label={`删除第${i + 1}层`} onClick={() => change(rows.filter(row => row.key !== r.key))}>删除</button></td>}
        </tr>; })}</tbody>
      </table>
      {!readOnly && <footer><button disabled={rows.length >= 30} onClick={() => change([...rows, { key: crypto.randomUUID(), component_id: null, name: "沥青面层", process_type: "asphalt_course", thickness: "", density: "", enabled: true }])}>添加结构层</button>
        <button className="primary" disabled={!dirty || !valid} onClick={() => void save()}>{busy ? "正在保存…" : "保存本段"}</button>
        <button disabled={!dirty} onClick={() => { setRows(initialRows()); setDirty(false); setError(""); }}>撤销修改</button>
      </footer>}
    </fieldset>
  </section>;
}
