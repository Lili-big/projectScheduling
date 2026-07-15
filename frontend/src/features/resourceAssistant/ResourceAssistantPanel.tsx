import { ArrowLeft, Bot, CheckCircle2, Download, Loader2, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  compareAiResourceAssistantResults,
  createBaselinePlan,
  generateAiResourceAssistantRecommendation,
  initializeAiResourceAssistant,
  solveAiResourceAssistantPlan,
  updateAiResourceAssistantPlan,
} from "../../api/schedulerApi";
import {
  invalidatedAfterPlanChange,
  llmConfigStatusLabel,
  normalizePlanResourceQuantity,
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
  ScenarioInput,
} from "../../types/scheduler";
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
  renderPlanDetail,
  onOpenPlanControl,
}: {
  scenario: ScenarioInput | null;
  renderPlanDetail?: (plan: ResourceAssistantPlan, result: ResourceAssistantPlanResult) => ReactNode;
  onOpenPlanControl?: () => void;
}) {
  const [initial, setInitial] = useState<ResourceAssistantInitialResponse | null>(null);
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
  const baselineConfirmedByInputRef = useRef<HTMLInputElement | null>(null);
  const baselineReasonInputRef = useRef<HTMLInputElement | null>(null);
  const scenarioFingerprint = useMemo(
    () => (scenario ? `${scenario.scenario_id}:${scenario.project.start_date}:${scenario.resource_pools.length}` : "empty"),
    [scenario],
  );

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
    plansRef.current = [];
    resultsRef.current = [];
    comparisonRequestRef.current += 1;
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
    try {
      const nextComparison = await compareAiResourceAssistantResults({ resource_plans: nextPlans, plan_results: nextResults });
      if (requestId === comparisonRequestRef.current) setComparison(nextComparison);
    } catch (exc) {
      if (requestId === comparisonRequestRef.current) {
        setError(exc instanceof Error ? `方案已求解，但指标对比刷新失败：${exc.message}` : "方案已求解，但指标对比刷新失败。");
      }
    }
  }

  async function handleGenerate() {
    if (!scenario) return;
    setGenerating(true);
    setError(null);
    setLlmContextDownload(null);
    try {
      const response = await initializeAiResourceAssistant({ scenario, generation_mode: "llm_first" });
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
      setError(exc instanceof Error ? exc.message : "资源方案生成失败");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSolvePlan(planId: string) {
    if (!scenario || solvingPlanIds[planId]) return;
    const targetPlan = plansRef.current.find((plan) => plan.scenario_id === planId);
    if (!targetPlan) return;
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
      const nextPlans = plansRef.current.map((plan) => (plan.scenario_id === planId ? response.resource_plan : plan));
      const nextResults = [...resultsRef.current.filter((result) => result.scenario_id !== planId), response.plan_result];
      replacePlans(nextPlans);
      replaceResults(nextResults);
      setRecommendation(null);
      setRecommendationError(null);
      await refreshComparison(nextPlans, nextResults);
    } catch (exc) {
      replacePlans(
        plansRef.current.map((plan) =>
          plan.scenario_id === planId ? { ...plan, solve_status: "failed", stale_reason: "本次求解请求失败，可重试。" } : plan,
        ),
      );
      setError(exc instanceof Error ? exc.message : `${targetPlan.scenario_name} 求解失败`);
    } finally {
      setSolvingPlanIds((current) => ({ ...current, [planId]: false }));
    }
  }

  async function handleRecommendation() {
    if (!allPlansComplete || recommending) return;
    setRecommending(true);
    setRecommendationError(null);
    try {
      const response = await generateAiResourceAssistantRecommendation({
        resource_plans: plansRef.current,
        plan_results: resultsRef.current,
      });
      setComparison(response.comparison);
      setRecommendation(response.recommendation);
    } catch (exc) {
      setRecommendationError(exc instanceof Error ? exc.message : "推荐生成失败，可重试。");
    } finally {
      setRecommending(false);
    }
  }

  async function handleConfirmBaseline(planId: string) {
    if (!scenario || confirmingBaseline) return;
    const plan = plansRef.current.find((item) => item.scenario_id === planId);
    const planResult = resultsRef.current.find((item) => item.scenario_id === planId);
    if (!plan || !planResult || !planResult.result || !["OPTIMAL", "FEASIBLE"].includes(planResult.result.status)) return;
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
    setConfirmingBaseline(true);
    setError(null);
    try {
      const version = await createBaselinePlan({
        scenario,
        resource_plan: plan,
        plan_result: planResult,
        confirmed_by: baselineConfirmedBy.trim(),
        confirmation_reason: baselineReason.trim(),
      });
      setBaselineVersionNo(version.version_no);
      setBaselinePlanId(planId);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "基准计划确认失败");
    } finally {
      setConfirmingBaseline(false);
    }
  }

  async function handleQuantityChange(planId: string, resourceType: string, quantity: number) {
    const plan = plansRef.current.find((item) => item.scenario_id === planId);
    if (!plan) return;
    const optimistic = normalizePlanResourceQuantity(plan, resourceType, quantity);
    replacePlans(plansRef.current.map((item) => (item.scenario_id === planId ? optimistic : item)));
    replaceResults(invalidatedAfterPlanChange(resultsRef.current, planId));
    if (detailPlanId === planId) setDetailPlanId(null);
    invalidateComparisonAndRecommendation();
    try {
      const response = await updateAiResourceAssistantPlan({
        plan_id: planId,
        resource_updates: { [resourceType]: quantity },
        resource_plan: plan,
      });
      replacePlans(plansRef.current.map((item) => (item.scenario_id === planId ? response.resource_plan : item)));
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
              <button className="secondary" type="button" disabled={generating || isAnySolving || recommending} onClick={handleGenerate}>
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
              onQuantityChange={(resourceType, quantity) => handleQuantityChange(plan.scenario_id, resourceType, quantity)}
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
