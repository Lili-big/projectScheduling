import { useMemo, useState } from "react";

import {
  confirmGirderSpecialty,
  confirmProjectDataVersion,
  createPlanningScenarioVersion,
  createProjectDataVersion,
  importGirderWorkpoints,
  previewGirderPlanning,
  solveIntegratedSchedule,
  validateGirderPlanning,
} from "../../api/schedulerApi";
import type {
  FieldConflict,
  GirderImportPreview,
  GirderPlanningConfig,
  GirderPlanningReadiness,
  GirderPlanningResult,
  IntegratedCalculationSnapshot,
  GirderWorkPoint,
  PlanningScenarioVersion,
  ProjectDataVersion,
  ScenarioInput,
  SourceEvidence,
  ValidationMessage,
} from "../../types/scheduler";
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
  const [projectVersion, setProjectVersion] = useState<ProjectDataVersion | null>(null);
  const [scenarioVersion, setScenarioVersion] = useState<PlanningScenarioVersion | null>(null);
  const [preview, setPreview] = useState<ImportPreview>({ workpoints: [], source_evidence: [], field_conflicts: [], diagnostics: [] });
  const [readiness, setReadiness] = useState<GirderPlanningReadiness | null>(null);
  const [girderResult, setGirderResult] = useState<GirderPlanningResult | null>(null);
  const [integratedSnapshot, setIntegratedSnapshot] = useState<IntegratedCalculationSnapshot | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  async function saveProjectVersion() {
    await run("project", async () => {
      const saved = await createProjectDataVersion({
        project: scenario.project,
        workpoints: preview.workpoints,
        source_evidence: preview.source_evidence,
        field_conflicts: preview.field_conflicts,
        expected_latest_version_no: projectVersion?.version_no ?? null,
        created_by: "本地计划工程师",
      });
      setProjectVersion(saved);
      setScenarioVersion(null);
    });
  }

  async function importFile(file: File) {
    if (!projectVersion) { setError("请先创建项目主数据草稿，再导入工点文件。"); return; }
    await run("import", async () => {
      const data = new FormData();
      data.append("project_data_version_id", projectVersion.project_data_version_id);
      data.append("coarse_mode", String(config.coarse_mode));
      data.append("file", file);
      const imported = await importGirderWorkpoints(data) as ImportPreview;
      setPreview(imported);
      setProjectVersion(null);
      setScenarioVersion(null);
    });
  }

  async function confirmProject() {
    if (!projectVersion) return;
    await run("confirm-project", async () => setProjectVersion(await confirmProjectDataVersion(projectVersion.project_data_version_id, { expected_input_fingerprint: projectVersion.input_fingerprint, confirmed_by: "项目总工", confirmation_reason: "结构与架梁工点数据已核对" })));
  }

  async function saveScenarioVersion() {
    if (!projectVersion || projectVersion.status !== "confirmed") { setError("请先确认项目主数据版本。"); return; }
    await run("scenario", async () => {
      const saved = await createPlanningScenarioVersion({ scenario: withGirderPlanningConfig(scenario, config), project_data_version_id: projectVersion.project_data_version_id, girder_planning: config, expected_latest_version_no: scenarioVersion?.version_no ?? null, created_by: "本地计划工程师" });
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
        <div className="girder-card-heading"><div><h3>版本与导入</h3><p>项目主数据确认后才能创建正式方案版本。</p></div></div>
        <div className="girder-actions">
          <button type="button" onClick={saveProjectVersion} disabled={Boolean(busy)}>{projectVersion ? "保存新的统一项目版本" : "创建项目主数据草稿"}</button>
          <label className="girder-file-button">导入架梁工点<input type="file" accept=".xlsx,.xlsm,.csv,.tsv" disabled={Boolean(busy) || !projectVersion} onChange={(event) => { const file = event.target.files?.[0]; if (file) void importFile(file); }} /></label>
          <button type="button" onClick={confirmProject} disabled={Boolean(busy) || !projectVersion || projectVersion.status !== "draft"}>确认项目数据</button>
          <button type="button" onClick={saveScenarioVersion} disabled={Boolean(busy) || projectVersion?.status !== "confirmed"}>保存专项方案版本</button>
          <button type="button" onClick={validateCurrent} disabled={Boolean(busy) || !scenarioVersion}>校验专项</button>
          <button type="button" onClick={confirmSpecialty} disabled={Boolean(busy) || !scenarioVersion || !readiness || readiness.status === "blocking"}>专业确认</button>
          <button type="button" onClick={previewCurrent} disabled={Boolean(busy) || !scenarioVersion}>专项预览</button>
          <button type="button" onClick={solveCurrent} disabled={Boolean(busy) || scenarioVersion?.status !== "specialty_confirmed"}>联合计算</button>
        </div>
        <div className="girder-version-strip"><span>项目版本：{projectVersion ? `v${projectVersion.version_no} · ${projectVersion.status}` : "未保存"}</span><span>方案版本：{scenarioVersion ? `v${scenarioVersion.version_no} · ${scenarioVersion.status}` : "未保存"}</span><span>已导入工点：{preview.workpoints.length}</span></div>
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
