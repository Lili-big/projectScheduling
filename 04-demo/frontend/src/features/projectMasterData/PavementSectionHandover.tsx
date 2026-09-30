import { useEffect, useState } from "react";
import type { ProjectMasterStructure, SavePavementHandoverRequest } from "../../contracts/projectMaster";
import { pavementHandover } from "../../domain/pavement";

export function PavementSectionHandover({ section, readOnly, onSave, onDirtyChange }: {
  section: ProjectMasterStructure; readOnly: boolean;
  onSave?: (sectionId: string, values: SavePavementHandoverRequest) => Promise<void>;
  onDirtyChange?: (key: string, dirty: boolean) => void;
}) {
  const initial = pavementHandover(Object.fromEntries(section.parameters.map(p => [p.parameter_code, p.value])));
  const [status, setStatus] = useState(initial.status);
  const [date, setDate] = useState(initial.date);
  const [note, setNote] = useState(String(section.parameters.find(p => p.parameter_code === "roadbed_handover_note")?.value ?? ""));
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { onDirtyChange?.(`${section.structure_id}:handover`, dirty || busy); }, [onDirtyChange, section.structure_id, dirty, busy]);
  useEffect(() => () => onDirtyChange?.(`${section.structure_id}:handover`, false), [onDirtyChange, section.structure_id]);
  const invalid = pavementHandover({roadbed_handover_status:status, roadbed_available_date:date}).invalid;
  async function save() {
    if (!onSave || invalid) return;
    setBusy(true); setError("");
    try {
      await onSave(section.structure_id, {status:status as SavePavementHandoverRequest["status"], available_date:date || null, note, created_by:"本地计划工程师"});
      setDirty(false);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <section className="pavement-handover-editor" aria-label={`${section.structure_name}路床移交`}>
    <fieldset disabled={readOnly || busy}>
      <label>路床移交 <select aria-label="路床移交状态" value={status} onChange={e => {setStatus(e.target.value); if(e.target.value !== "dated") setDate(""); setDirty(true);}}>
        <option value="dated">指定日期</option><option value="handed_over">已移交</option><option value="pending">移交待定</option>
      </select></label>
      {status === "dated" && <label>移交日期 <input aria-label="路床移交日期" type="date" required value={date} onChange={e => {setDate(e.target.value); setDirty(true);}} /></label>}
      <label className="pavement-handover-note">{status === "pending" ? "受阻原因" : "说明"} <input aria-label="路床移交说明" maxLength={1000} value={note} placeholder={status === "pending" ? "移交日期未定，暂不可开工" : "选填"} onChange={e => {setNote(e.target.value); setDirty(true);}} /></label>
      {!readOnly && <button disabled={!dirty || invalid} onClick={() => void save()}>{busy ? "保存中…" : "保存移交条件"}</button>}
      {!readOnly && <button disabled={!dirty} onClick={() => {setStatus(initial.status); setDate(initial.date); setNote(String(section.parameters.find(p => p.parameter_code === "roadbed_handover_note")?.value ?? "")); setDirty(false); setError("");}}>撤销移交修改</button>}
    </fieldset>
    {status === "handed_over" && <span>最早按计划开始日安排施工</span>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
