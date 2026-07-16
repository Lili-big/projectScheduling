import { useEffect, useMemo, useState } from "react";

import {
  confirmGirderSpecialty,
  createPlanningScenarioVersion,
  previewGirderPlanning,
  solveIntegratedSchedule,
  validateGirderPlanning,
} from "../../api/girderPlanningApi";
import { listProjectMasterGirderWorkpoints } from "../../api/projectMasterApi";
import type {
  FieldConflict,
  GirderImportPreview,
  GirderPlanningConfig,
  GirderPlanningReadiness,
  GirderPlanningResult,
  IntegratedCalculationSnapshot,
  GirderWorkPoint,
  PlanningScenarioVersion,
  ScenarioInput,
  SourceEvidence,
  ValidationMessage,
} from "../../contracts";
import { normalizeGirderPlanningConfig, withGirderPlanningConfig } from "./adapter";
import { GirderDiagnostics } from "./GirderDiagnostics";
import { GirderResultPanel } from "./GirderResultPanel";
import { RouteEditor } from "./RouteEditor";
import { YardMachineEditor } from "./YardMachineEditor";

type ImportPreview = Pick<GirderImportPreview, "workpoints" | "source_evidence" | "field_conflicts" | "diagnostics">;

export function GirderPlanningPanel({
  scenario,
  onScenarioChange,
  onIntegratedSnapshot,
}: {
  scenario: ScenarioInput;
  onScenarioChange: (next: ScenarioInput) => void;
  onIntegratedSnapshot?: (snapshot: IntegratedCalculationSnapshot | null) => void;
}) {
  const config = useMemo(() => normalizeGirderPlanningConfig(scenario), [scenario]);
  const [scenarioVersion, setScenarioVersion] = useState<PlanningScenarioVersion | null>(null);
  const [preview, setPreview] = useState<ImportPreview>({ workpoints: [], source_evidence: [], field_conflicts: [], diagnostics: [] });
  const [readiness, setReadiness] = useState<GirderPlanningReadiness | null>(null);
  const [girderResult, setGirderResult] = useState<GirderPlanningResult | null>(null);
  const [integratedSnapshot, setIntegratedSnapshot] = useState<IntegratedCalculationSnapshot | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const versionId = scenario.project_data_version_id;
    if (!versionId) {
      setPreview({ workpoints: [], source_evidence: [], field_conflicts: [], diagnostics: [] });
      return;
    }
    setBusy("derive-workpoints");
    void listProjectMasterGirderWorkpoints(versionId)
      .then((workpoints) => setPreview({ workpoints, source_evidence: [], field_conflicts: [], diagnostics: [] }))
      .catch((caught) => setError(caught instanceof Error ? caught.message : String(caught)))
      .finally(() => setBusy(null));
  }, [scenario.project_data_version_id]);

  function updateConfig(next: GirderPlanningConfig) {
    setScenarioVersion(null);
    setReadiness(null);
    setIntegratedSnapshot(null);
    onIntegratedSnapshot?.(null);
    onScenarioChange(withGirderPlanningConfig(scenario, next));
  }

  async function run(action: string, callback: () => Promise<void>) {
    setBusy(action);
    setError(null);
    try { await callback(); } catch (caught) { setError(caught instanceof Error ? caught.message : String(caught)); } finally { setBusy(null); }
  }

  async function saveScenarioVersion() {
    if (!scenario.project_data_version_id) { setError("请先在“项目主数据”确认一个版本。"); return; }
    await run("scenario", async () => {
      const saved = await createPlanningScenarioVersion({ scenario: withGirderPlanningConfig(scenario, config), project_data_version_id: scenario.project_data_version_id!, girder_planning: config, expected_latest_version_no: scenarioVersion?.version_no ?? null, created_by: "本地计划工程师" });
      setScenarioVersion(saved);
      setReadiness(null);
    });
  }

  async function validateCurrent() {
    if (!scenarioVersion) return;
    await run("validate", async () => setReadiness(await validateGirderPlanning(scenarioVersion.scenario_version_id, scenarioVersion.input_fingerprint)));
  }

  async function confirmSpecialty() {
    if (!scenarioVersion || readiness?.status === "blocking") return;
    await run("confirm-specialty", async () => setScenarioVersion(await confirmGirderSpecialty(scenarioVersion.scenario_version_id, { expected_input_fingerprint: scenarioVersion.input_fingerprint, confirmed_by: "架梁专业工程师", confirmation_reason: "专项配置与路线已复核" })));
  }

  async function previewCurrent() {
    if (!scenarioVersion) return;
    await run("preview", async () => setGirderResult(await previewGirderPlanning(scenarioVersion.scenario_version_id, scenarioVersion.input_fingerprint)));
  }

  async function solveCurrent() {
    if (!scenarioVersion || scenarioVersion.status !== "specialty_confirmed") {
      setError("请先完成架梁专项专业确认。");
      return;
    }
    await run("integrated", async () => {
      const snapshot = await solveIntegratedSchedule({ scenario_version_id: scenarioVersion.scenario_version_id, expected_input_fingerprint: scenarioVersion.input_fingerprint });
      setIntegratedSnapshot(snapshot);
      onIntegratedSnapshot?.(snapshot);
      setGirderResult(snapshot.girder_result ?? null);
    });
  }

  return (
    <section className="panel full girder-planning-panel">
      <div className="panel-title"><div><h2>架梁专项策划</h2><span>统一项目数据、梁场设备、固定路线和专项确认；正式结果由联合排程生成。</span></div></div>
      {error && <div className="notice error">{error}</div>}
      <section className="girder-card girder-workflow">
        <div className="girder-card-heading"><div><h3>主数据版本与派生工点</h3><p>路线工点由统一主数据的 workpoint_id + side 自动派生，不再单独上传。</p></div></div>
        <div className="girder-actions">
          <button type="button" onClick={saveScenarioVersion} disabled={Boolean(busy) || !scenario.project_data_version_id}>保存专项方案版本</button>
          <button type="button" onClick={validateCurrent} disabled={Boolean(busy) || !scenarioVersion}>校验专项</button>
          <button type="button" onClick={confirmSpecialty} disabled={Boolean(busy) || !scenarioVersion || !readiness || readiness.status === "blocking"}>专业确认</button>
          <button type="button" onClick={previewCurrent} disabled={Boolean(busy) || !scenarioVersion}>专项预览</button>
          <button type="button" onClick={solveCurrent} disabled={Boolean(busy) || scenarioVersion?.status !== "specialty_confirmed"}>联合计算</button>
        </div>
        <div className="girder-version-strip"><span>主数据版本：{scenario.project_data_version_id || "未确认"}</span><span>方案版本：{scenarioVersion ? `v${scenarioVersion.version_no} · ${scenarioVersion.status}` : "未保存"}</span><span>派生路线工点：{preview.workpoints.length}</span></div>
      </section>
      <section className="girder-card"><div className="girder-card-heading"><div><h3>专项开关与通行口径</h3></div></div><div className="girder-grid compact"><label className="girder-check"><input type="checkbox" checked={config.enabled} onChange={(event) => updateConfig({ ...config, enabled: event.target.checked })} />启用架梁专项</label><label>架后通行缓冲（天）<input type="number" min={0} value={config.parameters.post_erection_passage_buffer_days} onChange={(event) => updateConfig({ ...config, parameters: { ...config.parameters, post_erection_passage_buffer_days: Number(event.target.value), post_erection_buffer_confirmed: false } })} /></label><label className="girder-check"><input type="checkbox" checked={config.parameters.post_erection_buffer_confirmed} onChange={(event) => updateConfig({ ...config, parameters: { ...config.parameters, post_erection_buffer_confirmed: event.target.checked } })} />确认架后缓冲</label><label className="girder-check"><input type="checkbox" checked={config.coarse_mode} onChange={(event) => updateConfig({ ...config, coarse_mode: event.target.checked })} />粗粒度预览模式</label></div></section>
      <YardMachineEditor config={config} startDate={scenario.project.start_date} onChange={updateConfig} />
      <RouteEditor config={config} workpoints={preview.workpoints} onChange={updateConfig} />
      <GirderDiagnostics conflicts={preview.field_conflicts} evidence={preview.source_evidence} readiness={readiness} diagnostics={preview.diagnostics} />
      <GirderResultPanel result={girderResult} integrated={integratedSnapshot} />
    </section>
  );
}

// Type-only imports are retained explicitly so schema drift is caught by TypeScript.
void (null as GirderWorkPoint | FieldConflict | SourceEvidence | ValidationMessage | null);
