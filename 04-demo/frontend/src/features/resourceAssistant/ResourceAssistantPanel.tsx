import { ArrowLeft, Bot, CheckCircle2, Download, Loader2, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  compareAiResourceAssistantResults,
  generateAiResourceAssistantRecommendation,
  initializeAiResourceAssistant,
  solveAiResourceAssistantPlan,
  updateAiResourceAssistantPlan,
} from "../../api/resourceAssistantApi";
import { createBaselinePlan } from "../../api/planControlApi";
import {
  invalidatedAfterPlanChange,
  llmConfigStatusLabel,
  resourceAssistantProfileLabels,
  resourceAssistantStatusLabels,
  resourceAssistantStatusTone,
  resultByPlanId,
} from "../../domain/resourceAssistant";
import type {
  ResourceAssistantComparison,
  ResourceAssistantInitialResponse,
  ResourceAssistantLlmGenerationContext,
  ResourceAssistantPlan,
  ResourceAssistantPlanResult,
  ResourceAssistantRecommendation,
  ProjectMasterWorkpoint,
  ScenarioInput,
} from "../../contracts";
import { PanelTitle } from "../../components/common/PanelTitle";
import { MetricComparisonTable } from "./MetricComparisonTable";
import { RecommendationPanel } from "./RecommendationPanel";
import { ResourcePlanCard } from "./ResourcePlanCard";

type LlmContextDownloadSnapshot = {
  context: ResourceAssistantLlmGenerationContext;
  projectName: string;
  generatedAt: Date;
};

const DEFAULT_BASELINE_REASON = "确认为执行基准计划";

export function ResourceAssistantPanel({
  scenario,
  workpoints,
  renderPlanDetail,
  onOpenPlanControl,
  integratedSnapshotId,
}: {
  scenario: ScenarioInput | null;
  workpoints: ProjectMasterWorkpoint[];
  renderPlanDetail?: (plan: ResourceAssistantPlan, result: ResourceAssistantPlanResult) => ReactNode;
  onOpenPlanControl?: () => void;
  integratedSnapshotId?: string | null;
}) {
  const [initial, setInitial] = useState<ResourceAssistantInitialResponse | null>(null);
  const [targetWorkpointId, setTargetWorkpointId] = useState("");
  const [plans, setPlans] = useState<ResourceAssistantPlan[]>([]);
  const [planResults, setPlanResults] = useState<ResourceAssistantPlanResult[]>([]);
  const [comparison, setComparison] = useState<ResourceAssistantComparison | null>(null);
  const [recommendation, setRecommendation] = useState<ResourceAssistantRecommendation | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [detailPlanId, setDetailPlanId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [solvingPlanIds, setSolvingPlanIds] = useState<Record<string, boolean>>({});
  const [recommending, setRecommending] = useState(false);
  const [confirmingBaseline, setConfirmingBaseline] = useState(false);
  const [baselineVersionNo, setBaselineVersionNo] = useState<number | null>(null);
  const [baselinePlanId, setBaselinePlanId] = useState<string | null>(null);
  const [baselineConfirmedBy, setBaselineConfirmedBy] = useState("本地计划工程师");
  const [baselineReason, setBaselineReason] = useState(DEFAULT_BASELINE_REASON);
  const [error, setError] = useState<string | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [llmContextDownload, setLlmContextDownload] = useState<LlmContextDownloadSnapshot | null>(null);
  const [llmContextDownloadUrl, setLlmContextDownloadUrl] = useState<string | null>(null);
  const plansRef = useRef<ResourceAssistantPlan[]>([]);
  const resultsRef = useRef<ResourceAssistantPlanResult[]>([]);
  const comparisonRequestRef = useRef(0);
  const scopeRequestRef = useRef(0);
  const baselineConfirmedByInputRef = useRef<HTMLInputElement | null>(null);
  const baselineReasonInputRef = useRef<HTMLInputElement | null>(null);
  const scenarioFingerprint = useMemo(
    () => resourceAssistantScenarioFingerprint(scenario),
    [scenario],
  );
  const workpointLabels = useMemo(
    () => Object.fromEntries(workpoints.map((workpoint) => [workpoint.workpoint_id, workpoint.workpoint_name])),
    [workpoints],
  );
  const selectableWorkpoints = useMemo(
    () => workpoints.filter(
      (workpoint) => workpoint.workpoint_type === "bridge" && workpoint.schedule_support === "bridge_supported",
    ),
    [workpoints],
  );
  const targetWorkpoint = selectableWorkpoints.find((workpoint) => workpoint.workpoint_id === targetWorkpointId) ?? null;

  function replacePlans(nextPlans: ResourceAssistantPlan[]) {
    plansRef.current = nextPlans;
    setPlans(nextPlans);
  }

  function replaceResults(nextResults: ResourceAssistantPlanResult[]) {
    resultsRef.current = nextResults;
    setPlanResults(nextResults);
  }

  function invalidateComparisonAndRecommendation() {
    comparisonRequestRef.current += 1;
    setComparison(null);
    setRecommendation(null);
    setRecommendationError(null);
  }

  useEffect(() => {
    scopeRequestRef.current += 1;
    plansRef.current = [];
    resultsRef.current = [];
    comparisonRequestRef.current += 1;
    setInitial(null);
    setTargetWorkpointId("");
    setPlans([]);
    setPlanResults([]);
    setComparison(null);
    setRecommendation(null);
    setSelectedPlanId(null);
    setDetailPlanId(null);
    setGenerating(false);
    setSolvingPlanIds({});
    setRecommending(false);
    setConfirmingBaseline(false);
    setBaselineVersionNo(null);
    setBaselinePlanId(null);
    setBaselineReason(DEFAULT_BASELINE_REASON);
    setError(null);
    setRecommendationError(null);
    setLlmContextDownload(null);
  }, [scenarioFingerprint]);

  useEffect(() => {
    if (!llmContextDownload) {
      setLlmContextDownloadUrl(null);
      return;
    }
    const blob = new Blob([JSON.stringify(llmContextDownload.context, null, 2)], {
      type: "application/json;charset=utf-8",
    });
    const objectUrl = URL.createObjectURL(blob);
    setLlmContextDownloadUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [llmContextDownload]);

  const resultsById = useMemo(() => resultByPlanId(planResults), [planResults]);
  const selectedPlan = plans.find((plan) => plan.scenario_id === selectedPlanId) || plans[0] || null;
  const detailPlan = detailPlanId ? plans.find((plan) => plan.scenario_id === detailPlanId) || null : null;
  const detailResult = detailPlan ? resultsById[detailPlan.scenario_id] || null : null;
  const completedPlanCount = plans.filter((plan) => Boolean(resultsById[plan.scenario_id]?.plan_status)).length;
  const allPlansComplete = plans.length === 3 && completedPlanCount === plans.length;
  const isAnySolving = Object.values(solvingPlanIds).some(Boolean);
  const llmContextFileName = useMemo(
    () => llmContextDownload ? buildLlmContextFileName(llmContextDownload.projectName, llmContextDownload.generatedAt) : "",
    [llmContextDownload],
  );

  async function refreshComparison(nextPlans: ResourceAssistantPlan[], nextResults: ResourceAssistantPlanResult[]) {
    const requestId = ++comparisonRequestRef.current;
    const scopeId = scopeRequestRef.current;
    try {
      const nextComparison = await compareAiResourceAssistantResults({ resource_plans: nextPlans, plan_results: nextResults });
      if (requestId === comparisonRequestRef.current && scopeId === scopeRequestRef.current) setComparison(nextComparison);
    } catch (exc) {
      if (requestId === comparisonRequestRef.current && scopeId === scopeRequestRef.current) {
        setError(exc instanceof Error ? `方案已求解，但指标对比刷新失败：${exc.message}` : "方案已求解，但指标对比刷新失败。");
      }
    }
  }

  async function handleGenerate() {
    if (!scenario || !targetWorkpoint) return;
    const scopeId = scopeRequestRef.current;
    const requestedWorkpointId = targetWorkpoint.workpoint_id;
    setGenerating(true);
    setError(null);
    setLlmContextDownload(null);
    try {
      const response = await initializeAiResourceAssistant({
        scenario,
        target_workpoint_id: requestedWorkpointId,
        generation_mode: "llm_first",
      });
      if (scopeId !== scopeRequestRef.current || targetWorkpointId !== requestedWorkpointId) return;
      if (response.resource_plans.some((plan) => plan.target_workpoint_id !== requestedWorkpointId)) {
        throw new Error("资源方案返回的推进工点与当前选择不一致。请重新生成。")
      }
      setInitial(response);
      setLlmContextDownload({
        context: response.llm_generation_context,
        projectName: response.project_profile.project_name,
        generatedAt: new Date(),
      });
      replacePlans(response.resource_plans);
      replaceResults([]);
      invalidateComparisonAndRecommendation();
      setDetailPlanId(null);
      setSelectedPlanId(response.resource_plans[0]?.scenario_id || null);
    } catch (exc) {
      if (scopeId === scopeRequestRef.current) setError(exc instanceof Error ? exc.message : "资源方案生成失败");
    } finally {
      if (scopeId === scopeRequestRef.current) setGenerating(false);
    }
  }

  async function handleSolvePlan(planId: string) {
    if (!scenario || solvingPlanIds[planId]) return;
    const targetPlan = plansRef.current.find((plan) => plan.scenario_id === planId);
    if (!targetPlan) return;
    const scopeId = scopeRequestRef.current;
    if (!targetPlan.target_workpoint_id || targetPlan.target_workpoint_id !== targetWorkpointId) {
      setError("当前方案与所选资源推进工点不一致，请重新生成三方案。");
      return;
    }
    setError(null);
    replaceResults(resultsRef.current.filter((result) => result.scenario_id !== planId));
    if (detailPlanId === planId) setDetailPlanId(null);
    invalidateComparisonAndRecommendation();
    setSolvingPlanIds((current) => ({ ...current, [planId]: true }));
    replacePlans(
      plansRef.current.map((plan) =>
        plan.scenario_id === planId ? { ...plan, solve_status: "solving", stale_reason: null } : plan,
      ),
    );
    try {
      const response = await solveAiResourceAssistantPlan({ scenario, resource_plan: targetPlan });
      if (scopeId !== scopeRequestRef.current) return;
      const nextPlans = plansRef.current.map((plan) => (plan.scenario_id === planId ? response.resource_plan : plan));
      const nextResults = [...resultsRef.current.filter((result) => result.scenario_id !== planId), response.plan_result];
      replacePlans(nextPlans);
      replaceResults(nextResults);
      setRecommendation(null);
      setRecommendationError(null);
      await refreshComparison(nextPlans, nextResults);
    } catch (exc) {
      if (scopeId !== scopeRequestRef.current) return;
      replacePlans(
        plansRef.current.map((plan) =>
          plan.scenario_id === planId ? { ...plan, solve_status: "failed", stale_reason: "本次求解请求失败，可重试。" } : plan,
        ),
      );
      setError(exc instanceof Error ? exc.message : `${targetPlan.scenario_name} 求解失败`);
    } finally {
      if (scopeId === scopeRequestRef.current) {
        setSolvingPlanIds((current) => ({ ...current, [planId]: false }));
      }
    }
  }

  async function handleRecommendation() {
    if (!allPlansComplete || recommending) return;
    setRecommending(true);
    const scopeId = scopeRequestRef.current;
    setRecommendationError(null);
    try {
      const response = await generateAiResourceAssistantRecommendation({
        resource_plans: plansRef.current,
        plan_results: resultsRef.current,
      });
      if (scopeId !== scopeRequestRef.current) return;
      setComparison(response.comparison);
      setRecommendation(response.recommendation);
    } catch (exc) {
      if (scopeId === scopeRequestRef.current) setRecommendationError(exc instanceof Error ? exc.message : "推荐生成失败，可重试。");
    } finally {
      if (scopeId === scopeRequestRef.current) setRecommending(false);
    }
  }

  async function handleConfirmBaseline(planId: string) {
    if (!scenario || confirmingBaseline) return;
    const plan = plansRef.current.find((item) => item.scenario_id === planId);
    const planResult = resultsRef.current.find((item) => item.scenario_id === planId);
    if (!plan || !planResult || !planResult.result || !["OPTIMAL", "FEASIBLE"].includes(planResult.result.status)) return;
    if (!plan.target_workpoint_id || plan.target_workpoint_id !== targetWorkpointId) {
      setError("当前方案与所选资源推进工点不一致，请重新生成三方案。");
      return;
    }
    if (!baselineConfirmedBy.trim()) {
      setError("请先填写基准确认人。");
      focusBaselineConfirmationInput(baselineConfirmedByInputRef.current);
      return;
    }
    if (!baselineReason.trim()) {
      setError("请先填写选择原因。");
      focusBaselineConfirmationInput(baselineReasonInputRef.current);
      return;
    }
    if (scenario.girder_planning?.enabled && !integratedSnapshotId) {
      setError("当前场景启用了架梁专项，请先在“架梁专项策划”完成专业确认和联合计算，再发布统一基线。");
      return;
    }
    setConfirmingBaseline(true);
    setError(null);
    try {
      const version = await createBaselinePlan({
        scenario,
        resource_plan: plan,
        plan_result: planResult,
        confirmed_by: baselineConfirmedBy.trim(),
        confirmation_reason: baselineReason.trim(),
        integrated_snapshot_id: scenario.girder_planning?.enabled ? integratedSnapshotId ?? null : null,
      });
      setBaselineVersionNo(version.version_no);
      setBaselinePlanId(planId);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "基准计划确认失败");
    } finally {
      setConfirmingBaseline(false);
    }
  }

  async function handleQuantityChange(
    planId: string,
    resourcePoolId: string,
    workpointId: string | null,
    quantity: number,
  ) {
    const plan = plansRef.current.find((item) => item.scenario_id === planId);
    if (!plan) return;
    if (!plan.target_workpoint_id || workpointId !== plan.target_workpoint_id || workpointId !== targetWorkpointId) {
      setError("只能调整当前资源推进工点的本地资源。");
      return;
    }
    setError(null);
    try {
      const response = await updateAiResourceAssistantPlan({
        plan_id: planId,
        resource_updates: {},
        scoped_resource_updates: [{ resource_pool_id: resourcePoolId, workpoint_id: workpointId, quantity }],
        resource_plan: plan,
      });
      replacePlans(plansRef.current.map((item) => (item.scenario_id === planId ? response.resource_plan : item)));
      replaceResults(invalidatedAfterPlanChange(resultsRef.current, planId));
      if (detailPlanId === planId) setDetailPlanId(null);
      invalidateComparisonAndRecommendation();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "资源数量更新失败");
    }
  }

  if (!scenario) {
    return (
      <section className="panel full resource-assistant-panel">
        <PanelTitle title="AI多方案比选" subtitle="待导入项目数据" />
      </section>
    );
  }

  function handleTargetWorkpointChange(nextWorkpointId: string) {
    if (nextWorkpointId === targetWorkpointId) return;
    scopeRequestRef.current += 1;
    comparisonRequestRef.current += 1;
    plansRef.current = [];
    resultsRef.current = [];
    setTargetWorkpointId(nextWorkpointId);
    setInitial(null);
    setPlans([]);
    setPlanResults([]);
    setComparison(null);
    setRecommendation(null);
    setSelectedPlanId(null);
    setDetailPlanId(null);
    setGenerating(false);
    setSolvingPlanIds({});
    setRecommending(false);
    setConfirmingBaseline(false);
    setBaselineVersionNo(null);
    setBaselinePlanId(null);
    setBaselineReason(DEFAULT_BASELINE_REASON);
    setError(null);
    setRecommendationError(null);
    setLlmContextDownload(null);
  }

  if (detailPlan && detailResult && renderPlanDetail) {
    return (
      <div className="resource-assistant resource-assistant-detail">
        <section className="panel full resource-detail-header">
          <button className="secondary" type="button" onClick={() => setDetailPlanId(null)}>
            <ArrowLeft size={15} />
            返回多方案比选
          </button>
          <div className="resource-detail-heading">
            <span>{resourceAssistantProfileLabels[detailPlan.profile]}</span>
            <h2>{detailPlan.scenario_name}</h2>
          </div>
          <span className={`resource-status-pill ${resourceAssistantStatusTone(detailPlan.solve_status)}`}>
            {resourceAssistantStatusLabels[detailPlan.solve_status]}
          </span>
        </section>
        {renderPlanDetail(detailPlan, detailResult)}
      </div>
    );
  }

  return (
    <div className="resource-assistant">
      <section className="panel full resource-assistant-panel">
        <PanelTitle
          title="AI多方案比选"
          subtitle={initial ? `${initial.project_profile.project_name} / ${llmConfigStatusLabel(initial.llm_config_status)}` : scenario.scenario_name}
          action={
            <div className="actions">
              <button className="secondary" type="button" disabled={!targetWorkpoint || generating || isAnySolving || recommending} onClick={handleGenerate}>
                {generating ? <Loader2 size={15} className="spin" /> : <Sparkles size={15} />}
                生成三方案
              </button>
              {llmContextDownloadUrl && (
                <a
                  className="secondary resource-assistant-context-download"
                  href={llmContextDownloadUrl}
                  download={llmContextFileName}
                >
                  <Download size={15} />
                  下载本次 LLM 项目信息 JSON
                </a>
              )}
              {baselineVersionNo && onOpenPlanControl && (
                <button className="secondary" type="button" onClick={onOpenPlanControl}>进入计划执行（第 {baselineVersionNo} 版）</button>
              )}
              <button
                className="primary"
                type="button"
                disabled={!allPlansComplete || recommending}
                title={allPlansComplete ? "基于完整三方案结果生成推荐解释" : `还需完成 ${Math.max(0, 3 - completedPlanCount)} 个方案`}
                onClick={handleRecommendation}
              >
                {recommending ? <Loader2 size={15} className="spin" /> : <Bot size={15} />}
                生成LLM推荐
              </button>
            </div>
          }
        />
        <div className="resource-assistant-workpoint-scope">
          <label>
            资源推进工点
            <select
              value={targetWorkpointId}
              disabled={generating || isAnySolving || recommending || selectableWorkpoints.length === 0}
              onChange={(event) => handleTargetWorkpointChange(event.target.value)}
            >
              <option value="">请选择工点</option>
              {selectableWorkpoints.map((workpoint) => (
                <option key={workpoint.workpoint_id} value={workpoint.workpoint_id}>
                  {workpointOptionLabel(workpoint.workpoint_id, workpoint.workpoint_name, selectableWorkpoints)}
                </option>
              ))}
            </select>
          </label>
          <span>
            {selectableWorkpoints.length === 0
              ? "当前项目没有可参与 AI 资源推进的桥梁工点。"
              : targetWorkpoint
                ? `AI 仅调整“${targetWorkpoint.workpoint_name}”的本地资源；求解和指标仍为全项目口径。`
                : "请先选择资源推进工点。"}
          </span>
        </div>
        {error && <div className="notice danger">{error}</div>}
        {plans.length > 0 && (
          <div className="notice">
            单方案固定资源求解最长 15 秒：目标为最大延期优先、总工期其次；资源空闲与连续性仅按最终排程诊断。
          </div>
        )}
        {plans.length > 0 && (
          <div className="baseline-confirmation-bar">
            <label>基准确认人<input ref={baselineConfirmedByInputRef} required value={baselineConfirmedBy} onChange={(event) => setBaselineConfirmedBy(event.target.value)} /></label>
            <label>选择原因<input ref={baselineReasonInputRef} required value={baselineReason} onChange={(event) => setBaselineReason(event.target.value)} placeholder="例如：工期与资源投入最符合执行目标" /></label>
            <span>在下方已求解可行方案卡中确认基准。</span>
          </div>
        )}
        {initial ? <ProjectProfileStrip initial={initial} /> : <div className="resource-assistant-empty compact">等待生成工程画像和资源方案。</div>}
      </section>

      {plans.length > 0 && (
        <section className="resource-plan-grid">
          {plans.map((plan) => (
            <ResourcePlanCard
              key={plan.scenario_id}
              plan={plan}
              result={resultsById[plan.scenario_id]}
              disabled={generating || Boolean(solvingPlanIds[plan.scenario_id])}
              solving={Boolean(solvingPlanIds[plan.scenario_id])}
              isSelected={selectedPlan?.scenario_id === plan.scenario_id}
              onSelect={() => setSelectedPlanId(plan.scenario_id)}
              onSolve={() => handleSolvePlan(plan.scenario_id)}
              onViewDetails={resultsById[plan.scenario_id] && renderPlanDetail ? () => {
                setSelectedPlanId(plan.scenario_id);
                setDetailPlanId(plan.scenario_id);
              } : undefined}
              onConfirmBaseline={() => {
                setSelectedPlanId(plan.scenario_id);
                void handleConfirmBaseline(plan.scenario_id);
              }}
              confirmingBaseline={confirmingBaseline && selectedPlanId === plan.scenario_id}
              baselineVersionNo={baselinePlanId === plan.scenario_id ? baselineVersionNo : null}
              workpointLabels={workpointLabels}
              onQuantityChange={(resourcePoolId, workpointId, quantity) =>
                handleQuantityChange(plan.scenario_id, resourcePoolId, workpointId, quantity)}
            />
          ))}
        </section>
      )}

      {plans.length > 0 && (
        <section className="panel full">
          <PanelTitle title="三方案核心指标" subtitle={`已完成 ${completedPlanCount}/${plans.length} 套方案`} />
          <MetricComparisonTable comparison={comparison} plans={plans} planResults={planResults} />
        </section>
      )}

      <RecommendationPanel
        recommendation={recommendation}
        plans={plans}
        loading={recommending}
        error={recommendationError}
        onRetry={allPlansComplete ? handleRecommendation : undefined}
      />
    </div>
  );
}

function focusBaselineConfirmationInput(input: HTMLInputElement | null) {
  window.requestAnimationFrame(() => {
    input?.scrollIntoView({ behavior: "smooth", block: "center" });
    input?.focus({ preventScroll: true });
  });
}

function workpointOptionLabel(
  workpointId: string,
  workpointName: string,
  workpoints: ProjectMasterWorkpoint[],
): string {
  return workpoints.filter((item) => item.workpoint_name === workpointName).length > 1
    ? `${workpointName}（${workpointId}）`
    : workpointName;
}

function resourceAssistantScenarioFingerprint(scenario: ScenarioInput | null): string {
  if (!scenario) return "empty";
  const resourcePools = scenario.resource_pools
    .map((pool) => ({
      id: pool.id,
      scope_mode: pool.scope_mode ?? "PROJECT_SHARED",
      workpoint_id: pool.workpoint_id ?? null,
      authorized_workpoint_ids: pool.authorized_workpoint_ids === null
        ? null
        : [...(pool.authorized_workpoint_ids ?? [])].sort(),
      workpoint_overrides: [...(pool.workpoint_overrides ?? [])]
        .sort((left, right) => left.workpoint_id.localeCompare(right.workpoint_id)),
      quantity: pool.quantity,
      max_quantity: pool.max_quantity ?? null,
      enabled: pool.enabled,
      calendar_id: pool.calendar_id,
    }))
    .sort((left, right) => left.id.localeCompare(right.id));
  return JSON.stringify({
    scenario_id: scenario.scenario_id,
    project_data_version_id: scenario.project_data_version_id ?? null,
    start_date: scenario.project.start_date,
    resource_pools: resourcePools,
  });
}

function buildLlmContextFileName(projectName: string, generatedAt: Date): string {
  const safeProjectName = projectName
    .trim()
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[.-]+|[.-]+$/g, "") || "project";
  const pad = (value: number) => String(value).padStart(2, "0");
  const timestamp = [
    generatedAt.getFullYear(),
    pad(generatedAt.getMonth() + 1),
    pad(generatedAt.getDate()),
    "-",
    pad(generatedAt.getHours()),
    pad(generatedAt.getMinutes()),
    pad(generatedAt.getSeconds()),
  ].join("");
  return `${safeProjectName}-llm-three-plan-context-${timestamp}.json`;
}

function ProjectProfileStrip({ initial }: { initial: ResourceAssistantInitialResponse }) {
  const profile = initial.project_profile;
  return (
    <div className="resource-profile-strip">
      <div><strong>{profile.bridge_count}</strong><span>桥梁</span></div>
      <div><strong>{profile.structure_count}</strong><span>结构物</span></div>
      <div><strong>{profile.task_count}</strong><span>任务</span></div>
      <div><strong>{profile.control_piers.length}</strong><span>控制墩</span></div>
      <div><strong>{profile.continuous_beam_groups.length}</strong><span>连续梁组</span></div>
      <div className="wide"><strong>{initial.plan_generation.source === "llm" ? "LLM" : "本地回退"}</strong><span>{initial.plan_generation.validation_status}</span></div>
    </div>
  );
}
