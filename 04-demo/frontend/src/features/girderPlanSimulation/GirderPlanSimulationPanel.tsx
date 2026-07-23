import { useEffect, useMemo, useState } from "react";
import { getCurrentProjectMasterVersion, listProjectMasterVersions } from "../../api/projectMasterApi";
import {
  confirmGirderPlanRun,
  createGirderPlanScenario,
  getGirderPlanLineGraph,
  getGirderPlanScenario,
  listGirderPlanScenarios,
  runGirderPlanScenario,
  validateGirderPlanScenario,
} from "../../api/girderPlanSimulationApi";
import type {
  GirderPlanReadiness,
  GirderPlanScenarioVersion,
  GirderPlanSimulationRun,
  LineGraphSnapshot,
  ProjectMasterVersionSummary,
} from "../../contracts";
import { diagnosticClass, diagnosticLabel, draftFromScenario, emptyGirderPlanDraft, focusDiagnostic } from "./adapter";
import { LineGraphView } from "./LineGraphView";
import { RouteSequenceEditor } from "./RouteSequenceEditor";
import { SimulationResultPanel } from "./SimulationResultPanel";
import { YardPlanEditor } from "./YardPlanEditor";

type Busy = "loading" | "saving" | "validating" | "running" | "confirming" | null;

export function GirderPlanSimulationPanel({ projectId }: { projectId: string }) {
  const [projectVersions, setProjectVersions] = useState<ProjectMasterVersionSummary[]>([]);
  const [projectVersionId, setProjectVersionId] = useState("");
  const [graph, setGraph] = useState<LineGraphSnapshot | null>(null);
  const [scenarios, setScenarios] = useState<GirderPlanScenarioVersion[]>([]);
  const [scenario, setScenario] = useState<GirderPlanScenarioVersion | null>(null);
  const [draft, setDraft] = useState(emptyGirderPlanDraft);
  const [readiness, setReadiness] = useState<GirderPlanReadiness | null>(null);
  const [run, setRun] = useState<GirderPlanSimulationRun | null>(null);
  const [busy, setBusy] = useState<Busy>("loading");
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    let active = true;
    setBusy("loading");
    setError(null);
    const scenariosPromise = listGirderPlanScenarios(projectId);
    Promise.all([listProjectMasterVersions(projectId, 1, 200), getCurrentProjectMasterVersion(projectId)])
      .then(async ([versionPage, current]) => {
        if (!active) return;
        const confirmed = versionPage.items.filter((item) => item.status === "confirmed");
        setProjectVersions(confirmed.length ? confirmed : [current]);
        setProjectVersionId(current.version_id);
        const [graphResult, scenariosResult] = await Promise.allSettled([
          getGirderPlanLineGraph(current.version_id),
          scenariosPromise,
        ]);
        if (!active) return;
        if (graphResult.status === "fulfilled") setGraph(graphResult.value);
        else setGraph(null);
        if (scenariosResult.status === "fulfilled") setScenarios(scenariosResult.value);
        else setScenarios([]);
        const failures = [
          graphResult.status === "rejected" ? `线路图加载失败：${messageOf(graphResult.reason)}` : null,
          scenariosResult.status === "rejected" ? `策划方案加载失败：${messageOf(scenariosResult.reason)}` : null,
        ].filter((item): item is string => Boolean(item));
        setError(failures.length ? failures.join("；") : null);
      })
      .catch((reason) => active && setError(messageOf(reason)))
      .finally(() => active && setBusy(null));
    return () => { active = false; };
  }, [projectId, reloadToken]);

  const selectedVersion = useMemo(() => projectVersions.find((item) => item.version_id === projectVersionId), [projectVersions, projectVersionId]);

  async function changeProjectVersion(versionId: string) {
    setProjectVersionId(versionId);
    setBusy("loading");
    setError(null);
    setScenario(null);
    setReadiness(null);
    setRun(null);
    setDraft(emptyGirderPlanDraft());
    try {
      setGraph(await getGirderPlanLineGraph(versionId));
    } catch (reason) {
      setGraph(null);
      setError(messageOf(reason));
    } finally {
      setBusy(null);
    }
  }

  async function selectScenario(versionId: string) {
    if (!versionId) {
      setScenario(null);
      setDraft(emptyGirderPlanDraft());
      setReadiness(null);
      setRun(null);
      return;
    }
    setBusy("loading");
    setError(null);
    try {
      const loaded = await getGirderPlanScenario(versionId);
      if (loaded.project_master_version_id !== projectVersionId) {
        setProjectVersionId(loaded.project_master_version_id);
        setGraph(await getGirderPlanLineGraph(loaded.project_master_version_id));
      }
      setScenario(loaded);
      setDraft(draftFromScenario(loaded));
      setReadiness(null);
      setRun(null);
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(null);
    }
  }

  async function saveScenario() {
    if (!graph || !projectVersionId) return;
    setBusy("saving");
    setError(null);
    try {
      const saved = await createGirderPlanScenario({
        scenario_id: draft.scenarioId,
        project_id: projectId,
        project_master_version_id: projectVersionId,
        line_graph_id: graph.line_graph_id,
        expected_latest_version_no: draft.latestVersionNo,
        beam_yards: draft.beamYards,
        erection_lines: draft.erectionLines,
        route_plans: draft.routePlans,
        connection_overrides: [],
        parameters: draft.parameters,
        created_by: "本地计划工程师",
      });
      setScenario(saved);
      setDraft(draftFromScenario(saved));
      setScenarios(await listGirderPlanScenarios(projectId));
      setReadiness(null);
      setRun(null);
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(null);
    }
  }

  async function validateScenario() {
    if (!scenario) return null;
    setBusy("validating");
    setError(null);
    try {
      const result = await validateGirderPlanScenario(scenario.scenario_version_id, scenario.input_fingerprint);
      setReadiness(result);
      return result;
    } catch (reason) {
      setError(messageOf(reason));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function calculate(forceRecompute = false) {
    if (!scenario) return;
    setBusy("running");
    setError(null);
    try {
      const check = await validateGirderPlanScenario(scenario.scenario_version_id, scenario.input_fingerprint);
      setReadiness(check);
      if (check.status === "blocking") return;
      setRun(await runGirderPlanScenario(scenario.scenario_version_id, scenario.input_fingerprint, forceRecompute));
    } catch (reason) {
      setError(messageOf(reason));
    } finally {
      setBusy(null);
    }
  }

  async function confirmRun(confirmedBy: string, reason: string) {
    if (!run || !scenario) return;
    setBusy("confirming");
    setError(null);
    try {
      const confirmed = await confirmGirderPlanRun(run.run_id, scenario.input_fingerprint, confirmedBy, reason);
      setRun(confirmed);
      setScenario({ ...scenario, status: "confirmed", confirmed_by: confirmedBy, confirmation_reason: reason, confirmed_at: confirmed.confirmed_at });
    } catch (cause) {
      setError(messageOf(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="girder-sim-page">
      <header className="girder-sim-page-header">
        <div><h2>架梁计划推演</h2><p>基于线路图、分梁型制梁能力、片日架梁能力和人工顺序，生成独立的最早可行计划与工点最晚交付日期。</p></div>
        <div className="girder-sim-independent">独立策划成果｜不写入现有架梁专项与综合排程</div>
      </header>
      <section className="girder-sim-toolbar">
        <label>已确认项目主数据版本<select value={projectVersionId} onChange={(event) => changeProjectVersion(event.target.value)}>
          {projectVersions.map((item) => <option value={item.version_id} key={item.version_id}>v{item.version_no}｜{item.version_id}</option>)}
        </select></label>
        <label>策划方案版本<select value={scenario?.scenario_version_id ?? ""} onChange={(event) => selectScenario(event.target.value)}><option value="">新建方案</option>{scenarios.map((item) => <option key={item.scenario_version_id} value={item.scenario_version_id}>v{item.version_no}｜{item.status}｜{item.scenario_version_id}</option>)}</select></label>
        <button type="button" onClick={() => setReloadToken((value) => value + 1)} disabled={busy != null}>重新加载</button>
      </section>
      {busy === "loading" && <div className="girder-sim-notice">正在加载已确认项目数据和线路图……</div>}
      {error && <div className="girder-sim-notice error">{error}<button type="button" onClick={() => setReloadToken((value) => value + 1)}>重试</button></div>}
      {selectedVersion && <div className="girder-sim-version-note">当前项目版本：{selectedVersion.version_id}｜内容指纹 {selectedVersion.content_fingerprint}</div>}
      {scenario?.status === "stale" && <div className="girder-sim-notice warning">方案已失效：{scenario.stale_reason ?? "项目版本或方案输入已经变化"}。请基于当前输入保存新版本并重新计算。</div>}
      <LineGraphView graph={graph} controls={run?.workpoint_controls} yards={draft.beamYards} />
      <YardPlanEditor graph={graph} yards={draft.beamYards} lines={draft.erectionLines} onYardsChange={(beamYards) => setDraft((current) => ({ ...current, beamYards }))} onLinesChange={(erectionLines) => setDraft((current) => ({ ...current, erectionLines }))} />
      <RouteSequenceEditor graph={graph} yards={draft.beamYards} lines={draft.erectionLines} routes={draft.routePlans} readiness={readiness} onChange={(routePlans) => setDraft((current) => ({ ...current, routePlans }))} />
      <section className="girder-sim-card">
        <div className="girder-sim-card-heading"><div><h3>计算参数与操作</h3><p>自然日连续计算，当日产梁从下一自然日起可用于架设。</p></div></div>
        <div className="girder-sim-grid six">
          <NumberParameter label="架前准备缓冲" value={draft.parameters.bridge_readiness_buffer_days} onChange={(value) => setDraft((current) => ({ ...current, parameters: { ...current.parameters, bridge_readiness_buffer_days: value } }))} />
          <NumberParameter label="路基通行缓冲" value={draft.parameters.roadbed_passage_buffer_days} onChange={(value) => setDraft((current) => ({ ...current, parameters: { ...current.parameters, roadbed_passage_buffer_days: value } }))} />
          <NumberParameter label="隧道通行缓冲" value={draft.parameters.tunnel_passage_buffer_days} onChange={(value) => setDraft((current) => ({ ...current, parameters: { ...current.parameters, tunnel_passage_buffer_days: value } }))} />
          <NumberParameter label="便道通行缓冲" value={draft.parameters.access_passage_buffer_days} onChange={(value) => setDraft((current) => ({ ...current, parameters: { ...current.parameters, access_passage_buffer_days: value } }))} />
          <NumberParameter label="架后通行缓冲" value={draft.parameters.post_erection_passage_buffer_days} onChange={(value) => setDraft((current) => ({ ...current, parameters: { ...current.parameters, post_erection_passage_buffer_days: value } }))} />
          <label>规划时域截止<input type="date" value={draft.parameters.planning_horizon_end_date} onChange={(event) => setDraft((current) => ({ ...current, parameters: { ...current.parameters, planning_horizon_end_date: event.target.value } }))} /></label>
        </div>
        <div className="girder-sim-actions"><button type="button" onClick={saveScenario} disabled={!graph || busy != null}>保存新版本</button><button type="button" onClick={validateScenario} disabled={!scenario || busy != null}>校验方案</button><button className="primary" type="button" onClick={() => calculate(false)} disabled={!scenario || busy != null}>生成架梁计划</button><button type="button" onClick={() => calculate(true)} disabled={!scenario || busy != null}>强制重算</button></div>
      </section>
      {readiness && <section className="girder-sim-card"><div className="girder-sim-card-heading"><h3>方案校验：{readiness.status}</h3></div><div className="girder-sim-diagnostics">{readiness.diagnostics.length === 0 ? <div className="success">全部硬条件通过。</div> : readiness.diagnostics.map((item) => <button type="button" key={`${item.code}-${item.subject_id ?? item.entity_refs.join("-")}`} className={diagnosticClass(item)} onClick={() => focusDiagnostic(item)}>{diagnosticLabel(item)}</button>)}</div></section>}
      <SimulationResultPanel graph={graph} run={run} onConfirm={confirmRun} confirming={busy === "confirming"} />
    </div>
  );
}

function NumberParameter({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label>{label}（天）<input type="number" min="0" value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}

function messageOf(reason: unknown): string {
  const message = reason instanceof Error ? reason.message : String(reason);
  if (/Unexpected token\s*['"]?<['"]?|<!doctype|not valid JSON/i.test(message)) {
    return "后端服务尚未加载架梁计划推演接口，请重启后端后重试";
  }
  return message;
}
