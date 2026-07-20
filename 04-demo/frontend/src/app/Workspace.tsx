import {
  AlertCircle,
  Bot,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  Database,
  Flag,
  Loader2,
  Play,
  RotateCcw,
  Save,
  Server,
  Sparkles,
  Timer,
  Workflow,
  X,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  getDemoScenario,
  saveLocalScenarioConfig,
} from "../api/scenarioApi";
import {
  getCurrentProjectMasterVersion,
  getProjectMasterWorkpoint,
  listProjectMasterWorkpoints,
} from "../api/projectMasterApi";
import {
  compareScenarios,
  generateScheduleInput,
  solveMinResources as solveMinResourcesRequest,
  solveResourceCost as solveResourceCostRequest,
  solveScenario,
} from "../api/schedulingApi";
import {
  applyAiParameterSuggestions as applyAiParameterSuggestionsRequest,
  parseAiParameterAssistant as parseAiParameterAssistantRequest,
} from "../api/assistantApi";
import type {
  ComponentType,
  RelationshipType,
  WorkPointType,
  WorkSectionSide,
  ResourceCostType,
  ControlLevel,
  ObjectiveTermConfig,
  ObjectiveContribution,
  ObjectiveModelingGate,
  ObjectiveTermId,
  TargetAchievement,
  ScheduleStrategyConfig,
  TabKey,
  GanttMode,
  TaskViewMode,
  BusyState,
  AiParameterApplyRequest,
  AiParameterApplyResponse,
  AiParameterParseResponse,
  ComponentModel,
  UpperStructureModel,
  StructureModel,
  WorkSection,
  ProjectBridge,
  ProjectModel,
  ProductivityOption,
  TaskOverride,
  ProcessTemplate,
  LogicRule,
  UpperStructureLogicRule,
  ResourceCalendar,
  ResourcePool,
  MilestoneConstraint,
  ScenarioInput,
  Task,
  ScheduledTask,
  PrecedenceLink,
  Resource,
  ResourceAllocation,
  MilestoneResult,
  ValidationMessage,
  ScheduleInput,
  GeneratedScheduleInput,
  ScheduleResult,
  ScenarioSolveResult,
  ScenarioAlternativeResult,
  CompareResponse,
  LocalScenarioConfig,
  ContinuitySplitDetail,
  ContinuityJumpDetail,
  ResourcePathStep,
  ResourcePath,
  DrillGroupRefinementDiagnostics,
  ContinuityMetrics,
  ControlPriorityAnalysis,
  ResourceOrganizationAnalysis,
  ContinuousBeamTeamSpanSummary,
  TaskViewFilters,
  TaskViewRow,
  TaskViewGroup,
  TaskViewParentGroup,
  ResourceAssistantPlan,
  ResourceAssistantPlanResult,
  IntegratedCalculationSnapshot,
  ProjectMasterWorkpoint,
} from "../contracts";

import {
  PREDECESSOR_HOVER_CLOSE_DELAY_MS,
  PREDECESSOR_HOVER_DELAY_MS,
  defaultResourceTypeByComponent,
  keyResourceComponentTypes,
  pileResourceTypeByMethod,
  pileResourceTypeByProcess,
  resourceCostTypeLabels,
  upperStructureCodes,
} from "../domain/constants";
import {
  componentColors,
  componentLabels,
  componentOrder,
  componentSortIndex,
  diagnosticLevelLabels,
  durationMethodLabels,
  milestoneStatusLabels,
  quantitySourceLabels,
  sideLabels,
} from "../domain/labels";
import {
  defaultStandardSectionHeightForUnit,
  isSectionBasedPierProductivity,
  normalizeProductivityOptionForProcess,
  pileProductivityUnitOptions,
  sectionHeightForOption,
  segmentedPierProductivityUnitOptions,
  supportsSegmentedPierUnits,
} from "../domain/productivity";
import { derivePlanStatus } from "../domain/scheduleDerived";
import { findComponent, findStructure, findWorkSection, isComponentType } from "../domain/projectTree";
import { scenarioWithTaskProcessPatch } from "../domain/scenarioMutations";
import { milestoneStatusClass, scopeLabel } from "../domain/milestones";
import {
  groupUpperStructures,
  isCastInPlaceBoxBeamUpper,
  isContinuousBeamUpper,
  isSimpleBeamUpper,
  upperGroupIndex,
} from "../domain/logic";
import {
  applyRequiredResourceTypesToTasks,
  defaultResourceTypeForProcess,
  defaultResourceTypeForTask,
  isLimitedResourcePoolAvailable,
  normalizeLimitedResourcePool,
  normalizeResourcePoolForWorkspace,
  normalizeScenarioResourcePools,
  processResourceLabel,
  resourcePoolBillingPeriodDays,
  resourcePoolCostType,
  resourcePoolMode,
  resourcePoolQuantity,
  resourcePoolsScopeIssues,
  removeResourcePoolById,
  resourcePoolsSemanticFingerprint,
  upsertResourcePoolById,
  resourcePoolUnitCost,
  resourcePoolUsableLimit,
  resourceTypeLabel,
  taskResourceTypesLabel,
} from "../domain/resources";
import type { MetricTone, PlanStatusDisplay } from "../domain/scheduleDerived";
import { mergeUpperStructureLogicRules } from "../domain/upperStructureLogic";
import { SideNavigation, WorkspaceTabStrip } from "../features/layout/WorkspaceNavigation";
import { ProcessTab } from "../features/process/ProcessTab";
import { LogicTab } from "../features/logic/LogicTab";
import { ResourcesTab, type ResourceWorkpointState } from "../features/resources/ResourcesTab";
import { MilestonesTab } from "../features/milestones/MilestonesTab";
import { ParameterAssistantPanel } from "../features/assistant/parameter";
import { ResourceAssistantPanel } from "../features/resourceAssistant/ResourceAssistantPanel";
import { PlanControlPanel } from "../features/planControl";
import { ProgressVisualizationPanel } from "../features/progressVisualization/ProgressVisualizationPanel";
import { GirderPlanningPanel } from "../features/girderPlanning";
import { GirderPlanSimulationPanel } from "../features/girderPlanSimulation";
import { ProjectMasterDataWorkspace } from "../features/projectMasterData";
import { Metric } from "../components/common/Metric";
import { PanelTitle } from "../components/common/PanelTitle";
import {
  PredecessorPopover,
  clearPredecessorHoverTimer,
  clearPredecessorHoverTimers,
} from "../components/common/PredecessorPopover";
import type { PredecessorDetail } from "../components/common/PredecessorPopover";
import { DateRangePicker } from "../components/common/DateRangePicker";
import {
  buildProjectMasterTaskViewMaps,
  createProjectMasterDisplayCoordinator,
  createProjectMasterDisplayIdentity,
  filterTaskViewRows,
  TaskViewWorkspace,
  type ProjectMasterDisplayState,
  type TaskViewProjectMasterMaps,
} from "../features/taskView";
import {
  buildResourceScopeResult,
  formatScheduleStatus,
  ScheduleResultsWorkspace,
} from "../features/scheduleResults";
import {
  generateScheduleWorkflow,
  loadScenarioWorkflow,
  scenarioFingerprintForSolve as serializeScenarioFingerprint,
} from "./workflows/scenarioWorkflow";
import { solveScenarioWorkflow } from "./workflows/solveWorkflow";
import { useWorkspaceController } from "./useWorkspaceController";

type ObjectiveTermDefinition = {
  id: ObjectiveTermId;
  label: string;
  group: string;
  description: string;
  defaultWeight: number;
  defaultEnabled?: boolean;
  appliesTo: string;
  source?: "objective" | "derived_objective";
  parentTermId?: ObjectiveTermId;
};

type ObjectiveContributionSummary = {
  items: ObjectiveContribution[];
  total: number;
  isLegacy: boolean;
};

const objectiveTermDefinitions: ObjectiveTermDefinition[] = [
  {
    id: "control_node_late",
    label: "控制性里程碑节点尽量不延误",
    group: "控制优先",
    description: "看控制性里程碑晚于目标日期的天数；每晚 1 天按最高优先级计罚，优先保障关键节点。",
    defaultWeight: 10_000_000_000,
    appliesTo: "目标函数排程",
  },
  {
    id: "makespan_and_soft_milestone",
    label: "计划工期尽可能短",
    group: "工期",
    description: "看项目从开工到完工的整体跨度；计划工期越长，罚分越高。",
    defaultWeight: 5_000_000,
    appliesTo: "目标函数排程",
  },
  {
    id: "resource_idle",
    label: "资源尽量少空等",
    group: "资源组织",
    description: "看单个资源两次任务之间是否长时间停等；中途空闲天数越多，罚分越高。",
    defaultWeight: 50_000,
    appliesTo: "目标函数排程",
  },
];

function defaultObjectiveTermsConfig(): Record<ObjectiveTermId, ObjectiveTermConfig> {
  return Object.fromEntries(
    objectiveTermDefinitions.map((term) => [
      term.id,
      { enabled: term.defaultEnabled ?? true, weight: term.defaultWeight },
    ]),
  ) as Record<ObjectiveTermId, ObjectiveTermConfig>;
}

const defaultScheduleStrategyConfig: ScheduleStrategyConfig = {
  normal_balance_bucket: "month",
  normal_earliest_start_offset: 0,
  normal_latest_finish_offset: null,
  normal_max_early_finish_days: 60,
  max_parallel_normal_per_work_section: 5,
  enable_balance_objective: false,
  objective_terms: defaultObjectiveTermsConfig(),
};

const controlLevelLabels: Record<ControlLevel, string> = {
  control: "控制性工程",
  key: "控制性工程",
  normal: "非控制工程",
  rough: "非控制工程",
};

const scheduleSourceLabels: Record<string, string> = {
  current_resources_control_priority_balanced: "当前资源目标函数排程",
  current_resources_target_failed: "当前资源目标未满足",
  current_resources_best_effort_refinement: "当前资源目标函数排程",
  current_resources_refinement_failed: "当前资源目标未满足",
  target_unconfirmed: "限时内无法确认",
  physical_infeasible: "物理无可行排程",
  max_resources_target_failed: "最大资源目标未满足",
  current_resources_capacity_shortest: "固定资源参考排程",
  current_resources_capacity_shortest_fallback: "固定资源参考排程",
  control_priority_balanced_reoptimization: "目标函数重排",
  minimum_resources_control_priority_balanced: "最少资源候选排程",
  minimum_resources_best_effort_refinement: "最少资源候选目标未满足",
  minimum_resources_refinement_fallback: "最少资源候选回退",
  capacity_model_verified_schedule: "候选资源内部搜索排程",
};

const drillGroupRefinementStatusLabels: Record<string, string> = {
  not_applicable: "未触发两阶段",
  coarse_only: "墩组分配结果",
  stage1_final: "墩组分配结果",
  stage2_refined: "路径复核结果",
  stage2_fallback: "墩组分配结果",
};

const resourcePathStatusLabels: Record<string, string> = {
  smooth: "顺畅",
  reasonable_jump: "有合理跨越",
  abnormal_jump: "有异常跳转",
  not_enabled: "未启用",
  not_evaluated: "未评价",
};

const resourceBalanceStatusLabels: Record<string, string> = {
  balanced: "分配均衡",
  slightly_unbalanced: "轻微不均",
  under_used: "部分资源低利用",
  unbalanced: "分配不均",
  not_enabled: "未启用",
  not_evaluated: "未评价",
};

const resourceIdleStatusLabels: Record<string, string> = {
  continuous: "施工连续",
  minor_idle: "存在短空档",
  idle_risk: "存在窝工风险",
  not_enabled: "未启用",
  not_evaluated: "未评价",
};

const controlTargetSourceLabels: Record<string, string> = {
  cast_in_place_continuous_beam_rule: "现浇连续梁规则",
  continuous_main_pier_inherited: "连续梁主墩继承",
  task_control_level: "任务控制属性",
  milestone_scope: "节点范围",
  control_chain_predecessor: "控制链前置追溯",
};

const editableControlLevelOptions: Array<{ value: ControlLevel; label: string }> = [
  { value: "control", label: "控制性工程" },
  { value: "normal", label: "非控制工程" },
];

type PlanListSortMode = "by_time" | "by_structure" | "by_process";
type PlanWindowMode = "detail" | "gantt";

const planListSortOptions: Array<{ value: PlanListSortMode; label: string }> = [
  { value: "by_time", label: "按时间" },
  { value: "by_structure", label: "按墩台" },
  { value: "by_process", label: "按工艺" },
];

function editableControlLevelValue(value: ControlLevel): ControlLevel {
  return value === "control" || value === "key" ? "control" : "normal";
}

export default function App() {
  const [scenario, setScenario] = useState<ScenarioInput | null>(null);
  const [generated, setGenerated] = useState<GeneratedScheduleInput | null>(null);
  const [generatedScenarioFingerprint, setGeneratedScenarioFingerprint] = useState<string | null>(null);
  const [solveResult, setSolveResult] = useState<ScenarioSolveResult | null>(null);
  const [solveResultScenarioFingerprint, setSolveResultScenarioFingerprint] = useState<string | null>(null);
  const [openTabs, setOpenTabs] = useState<TabKey[]>(["tasks"]);
  const [activeTab, setActiveTab] = useState<TabKey | null>("tasks");
  const [sideNavCollapsed, setSideNavCollapsed] = useState(false);
  const [ganttMode, setGanttMode] = useState<GanttMode>("by_time");
  const [savedResults, setSavedResults] = useState<ScenarioSolveResult[]>([]);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [processLibraryDirty, setProcessLibraryDirty] = useState(false);
  const [logicDirty, setLogicDirty] = useState(false);
  const [resourcesDirty, setResourcesDirty] = useState(false);
  const [milestonesDirty, setMilestonesDirty] = useState(false);
  const [integratedSnapshot, setIntegratedSnapshot] = useState<IntegratedCalculationSnapshot | null>(null);
  const [resourceWorkpointState, setResourceWorkpointState] = useState<ResourceWorkpointState>({
    status: "ready",
    versionId: "",
    workpoints: [],
  });
  const [resourceWorkpointReloadToken, setResourceWorkpointReloadToken] = useState(0);
  const [resourceSaveError, setResourceSaveError] = useState<string | null>(null);
  const resourceWorkpointRequestRef = useRef(0);
  const scenarioRef = useRef<ScenarioInput | null>(scenario);
  scenarioRef.current = scenario;
  const currentResourceWorkpoints = useMemo(
    () => resourceWorkpointState.status === "ready"
      && resourceWorkpointState.versionId === (scenario?.project_data_version_id ?? "")
      ? resourceWorkpointState.workpoints
      : [],
    [resourceWorkpointState, scenario?.project_data_version_id],
  );

  useEffect(() => {
    void loadScenario();
  }, []);

  const scenarioFingerprint = useMemo(() => (scenario ? scenarioFingerprintForSolve(scenario) : null), [scenario]);
  const currentGenerated = scenarioFingerprint !== null && generatedScenarioFingerprint === scenarioFingerprint ? generated : null;
  const currentSolveResult = scenarioFingerprint !== null && solveResultScenarioFingerprint === scenarioFingerprint ? solveResult : null;
  const {
    autoTaskViewFingerprintRef,
    busy,
    error,
    rememberScenarioFingerprint,
    setBusy,
    setError,
  } = useWorkspaceController({
    scenarioFingerprint,
    onScenarioInvalidated: () => {
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      setIntegratedSnapshot(null);
      setSavedResults([]);
    },
  });

  useEffect(() => {
    const versionId = scenario?.project_data_version_id ?? "";
    const requestId = ++resourceWorkpointRequestRef.current;
    setResourceSaveError(null);
    if (!versionId) {
      setResourceWorkpointState({ status: "ready", versionId: "", workpoints: [] });
      return;
    }
    setResourceWorkpointState({ status: "loading", versionId });
    void loadAllBridgeWorkpoints(versionId)
      .then((workpoints) => {
        if (requestId !== resourceWorkpointRequestRef.current) return;
        setResourceWorkpointState({ status: "ready", versionId, workpoints });
      })
      .catch((loadError) => {
        if (requestId !== resourceWorkpointRequestRef.current) return;
        setResourceWorkpointState({ status: "error", versionId, message: errorText(loadError) });
      });
    return () => {
      if (requestId === resourceWorkpointRequestRef.current) resourceWorkpointRequestRef.current += 1;
    };
  }, [resourceWorkpointReloadToken, scenario?.project_data_version_id]);

  useEffect(() => {
    if (activeTab !== "tasks" || !scenario || !scenarioFingerprint || currentGenerated || busy) return;
    if (autoTaskViewFingerprintRef.current === scenarioFingerprint) return;

    autoTaskViewFingerprintRef.current = scenarioFingerprint;
    setBusy("generating");
    setError(null);
    void generateTaskViewForScenario(scenario, { openTasks: false })
      .catch((err) => {
        setError(errorText(err));
      })
      .finally(() => {
        setBusy((current) => (current === "generating" ? null : current));
      });
  }, [activeTab, busy, currentGenerated, scenario, scenarioFingerprint]);

  async function loadScenario() {
    setBusy("loading");
    setError(null);
    try {
      let normalizedScenario = await loadScenarioWorkflow(
        getDemoScenario,
        normalizeScenarioForWorkspace,
      );
      try {
        const currentMaster = await getCurrentProjectMasterVersion(normalizedScenario.project.project_id);
        normalizedScenario = { ...normalizedScenario, project_data_version_id: currentMaster.version_id };
      } catch {
        // First use is an expected empty state; the main-data workspace creates the first version.
      }
      setScenario(normalizedScenario);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      setIntegratedSnapshot(null);
      setOpenTabs((current) => (current.includes("tasks") ? current : [...current, "tasks"]));
      setActiveTab("tasks");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function generateTaskViewForScenario(
    requestScenario: ScenarioInput,
    options: { openTasks?: boolean } = {},
  ) {
    const { generated: nextGenerated, fingerprint } = await generateScheduleWorkflow(
      requestScenario,
      normalizeScenarioForWorkspace,
      generateScheduleInput,
    );
    setGenerated(nextGenerated);
    setGeneratedScenarioFingerprint(fingerprint);
    if (options.openTasks !== false) {
      openModule("tasks");
    }
    return nextGenerated;
  }

  async function generateOnly() {
    if (!scenario) return;
    setBusy("generating");
    setError(null);
    try {
      await generateTaskViewForScenario(scenario, { openTasks: true });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveCurrent() {
    if (!scenario) return;
    const requestScenario = normalizeScenarioForWorkspace(scenario);
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    setBusy("solving");
    setError(null);
    openModule("results");
    try {
      await solveWith(requestScenario, requestFingerprint);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveMinResources() {
    if (!scenario) return;
    const requestScenario = normalizeScenarioForWorkspace(scenario);
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    const hasHardMilestone = requestScenario.milestones.some((milestone) => milestone.mode === "hard");
    const matchingSolveResult = solveResultScenarioFingerprint === requestFingerprint ? solveResult : null;
    const fallbackTargetDays = matchingSolveResult?.result.objective_days ?? null;
    if (!hasHardMilestone && !fallbackTargetDays) {
      setError("请先运行“固定资源条件下，推算最短工期”，或设置至少一个可匹配的强制里程碑目标。");
      return;
    }
    setBusy("minResources");
    setError(null);
    try {
      const solved = await solveMinResourcesRequest({
        scenario: requestScenario,
        fallback_target_days: fallbackTargetDays,
      });
      setGenerated(solved.generated);
      setGeneratedScenarioFingerprint(requestFingerprint);
      setSolveResult(solved);
      setSolveResultScenarioFingerprint(requestFingerprint);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveResourceCost() {
    if (!scenario) return;
    const requestScenario = normalizeScenarioForWorkspace(scenario);
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    const hasHardMilestone = requestScenario.milestones.some((milestone) => milestone.mode === "hard");
    const matchingSolveResult = solveResultScenarioFingerprint === requestFingerprint ? solveResult : null;
    const fallbackTargetDays = matchingSolveResult?.result.objective_days ?? null;
    if (!hasHardMilestone && !fallbackTargetDays) {
      setError("请先运行“固定资源条件下，推算最短工期”，或设置至少一个可匹配的强制里程碑目标。");
      return;
    }
    setBusy("resourceCost");
    setError(null);
    try {
      const solved = await solveResourceCostRequest({
        scenario: requestScenario,
        fallback_target_days: fallbackTargetDays,
      });
      setGenerated(solved.generated);
      setGeneratedScenarioFingerprint(requestFingerprint);
      setSolveResult(solved);
      setSolveResultScenarioFingerprint(requestFingerprint);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveWith(nextScenario: ScenarioInput, fingerprint = scenarioFingerprintForSolve(nextScenario)) {
    const { solved } = await solveScenarioWorkflow(nextScenario, normalizeScenarioForWorkspace, solveScenario);
    setGenerated(solved.generated);
    setGeneratedScenarioFingerprint(fingerprint);
    setSolveResult(solved);
    setSolveResultScenarioFingerprint(fingerprint);
  }

  async function compareSavedResults(nextResults = savedResults) {
    if (!nextResults.length) return;
    setBusy("comparing");
    setError(null);
    try {
      const nextComparison = await compareScenarios({ results: nextResults });
      setComparison(nextComparison);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function parseAiParameterAssistant(payload: FormData): Promise<AiParameterParseResponse | null> {
    if (!scenario) return null;
    setBusy("aiParameter");
    setError(null);
    try {
      payload.set("scenario", JSON.stringify(normalizeScenarioForWorkspace(scenario)));
      return await parseAiParameterAssistantRequest(payload);
    } catch (err) {
      setError(errorText(err));
      return null;
    } finally {
      setBusy(null);
    }
  }

  async function applyAiParameterSuggestions(request: AiParameterApplyRequest): Promise<AiParameterApplyResponse | null> {
    if (!scenario) return null;
    setBusy("aiParameter");
    setError(null);
    try {
      const requestScenario = normalizeScenarioForWorkspace(scenario);
      const result = await applyAiParameterSuggestionsRequest({ ...request, scenario: requestScenario });
      const resultScenario = normalizeScenarioForWorkspace(result.scenario);
      const resultFingerprint = scenarioFingerprintForSolve(resultScenario);
      rememberScenarioFingerprint(resultFingerprint);
      setScenario(resultScenario);
      if (hasProcessLibraryChanged(scenario.process_library, resultScenario.process_library)) {
        setProcessLibraryDirty(true);
      }
      if (hasResourcePoolsChanged(scenario.resource_pools, resultScenario.resource_pools)) {
        setResourcesDirty(true);
      }
      if (hasMilestonesChanged(scenario.milestones, resultScenario.milestones)) {
        setMilestonesDirty(true);
      }
      clearGeneratedOutputs();
      return { ...result, scenario: resultScenario };
    } catch (err) {
      setError(errorText(err));
      return null;
    } finally {
      setBusy(null);
    }
  }

  function saveCurrentResult(resultToSave: ScenarioSolveResult | null = currentSolveResult) {
    if (!resultToSave) return;
    const nextResult = {
      ...resultToSave,
      scenario_id: `${resultToSave.scenario_id}-${savedResults.length + 1}`,
      scenario_name: `${resultToSave.scenario_name} #${savedResults.length + 1}`,
    };
    const nextResults = [...savedResults, nextResult];
    setSavedResults(nextResults);
    void compareSavedResults(nextResults);
  }

  function patchScenario(patch: Partial<ScenarioInput>) {
    setScenario((current) => (current ? normalizeScenarioForWorkspace({ ...current, ...patch }) : current));
  }

  function openModule(tabKey: TabKey) {
    setOpenTabs((current) => (current.includes(tabKey) ? current : [...current, tabKey]));
    setActiveTab(tabKey);
  }

  function closeModule(tabKey: TabKey) {
    setOpenTabs((current) => {
      const nextTabs = current.filter((key) => key !== tabKey);
      if (activeTab === tabKey) {
        const closedIndex = current.indexOf(tabKey);
        const nextIndex = Math.min(closedIndex, nextTabs.length - 1);
        setActiveTab(nextTabs[nextIndex] ?? null);
      } else if (activeTab && !nextTabs.includes(activeTab)) {
        setActiveTab(nextTabs[0] ?? null);
      }
      return nextTabs;
    });
  }

  function patchProject(patch: Partial<ProjectModel>) {
    setScenario((current) =>
      current ? { ...current, project: { ...current.project, ...patch } } : current,
    );
  }

  function updateProcess(index: number, patch: Partial<ProcessTemplate>) {
    setProcessLibraryDirty(true);
    setScenario((current) =>
      current
        ? {
            ...current,
            process_library: current.process_library.map((process, processIndex) =>
              processIndex === index ? { ...process, ...patch } : process,
            ),
          }
        : current,
    );
  }

  async function saveCurrentProcessLibrary() {
    await saveCurrentLocalScenarioConfig("savingProcessLibrary");
  }

  async function saveCurrentLogicConfig() {
    await saveCurrentLocalScenarioConfig("savingLogic");
  }

  async function saveCurrentResourceConfig() {
    if (!scenario) return;
    setResourceSaveError(null);
    const validationError = currentResourceScopeSaveError(scenario);
    if (validationError) {
      setResourceSaveError(validationError);
      return;
    }
    await saveCurrentLocalScenarioConfig("savingResources", setResourceSaveError);
  }

  async function saveCurrentMilestoneConfig() {
    await saveCurrentLocalScenarioConfig("savingMilestones");
  }

  async function saveCurrentLocalScenarioConfig(
    busyState: Exclude<BusyState, null>,
    onSaveError?: (message: string) => void,
  ) {
    if (!scenario) return;
    const validationError = currentResourceScopeSaveError(scenario);
    if (validationError) {
      (onSaveError ?? setError)(validationError);
      return;
    }
    const requestVersionId = scenario.project_data_version_id ?? "";
    const requestResourceFingerprint = resourcePoolsSemanticFingerprint(scenario.resource_pools);
    setBusy(busyState);
    setError(null);
    try {
      const config = await saveLocalScenarioConfig(localScenarioConfigFromScenario(scenario));
      const latestScenario = scenarioRef.current;
      const responseIsCurrent = Boolean(
        latestScenario
        && (latestScenario.project_data_version_id ?? "") === requestVersionId
        && resourcePoolsSemanticFingerprint(latestScenario.resource_pools) === requestResourceFingerprint,
      );
      if (!responseIsCurrent) return;
      setScenario((current) => (current ? normalizeScenarioForWorkspace({ ...current, ...config }) : current));
      setProcessLibraryDirty(false);
      setLogicDirty(false);
      setResourcesDirty(false);
      setMilestonesDirty(false);
      setResourceSaveError(null);
      clearGeneratedOutputs();
    } catch (err) {
      (onSaveError ?? setError)(errorText(err));
    } finally {
      setBusy((current) => (current === busyState ? null : current));
    }
  }

  function currentResourceScopeSaveError(requestScenario: ScenarioInput): string | null {
    const versionId = requestScenario.project_data_version_id ?? "";
    if (resourceWorkpointState.status !== "ready" || resourceWorkpointState.versionId !== versionId) {
      return "当前项目主数据版本的权威桥梁工点尚未就绪";
    }
    const authoritativeIds = resourceWorkpointState.workpoints.map((workpoint) => workpoint.workpoint_id);
    const issues = resourcePoolsScopeIssues(requestScenario.resource_pools, authoritativeIds);
    return issues[0] ?? null;
  }

  function clearGeneratedOutputs() {
    setGenerated(null);
    setGeneratedScenarioFingerprint(null);
    setSolveResult(null);
    setSolveResultScenarioFingerprint(null);
    setComparison(null);
    setSavedResults([]);
    setIntegratedSnapshot(null);
  }

  function updateLogic(index: number, patch: Partial<LogicRule>) {
    setLogicDirty(true);
    setScenario((current) =>
      current
        ? {
            ...current,
            logic_rules: current.logic_rules.map((rule, ruleIndex) =>
              ruleIndex === index ? { ...rule, ...patch } : rule,
            ),
          }
        : current,
    );
  }

  function updateUpperStructureLogic(ruleId: string, patch: Partial<UpperStructureLogicRule>) {
    setLogicDirty(true);
    setScenario((current) =>
      current
        ? {
            ...current,
            upper_structure_logic_rules: mergeUpperStructureLogicRules(current.upper_structure_logic_rules).map((rule) =>
              rule.id === ruleId ? { ...rule, ...patch } : rule,
            ),
          }
        : current,
    );
  }

  function upsertResourcePool(poolId: string, patch: Partial<ResourcePool>) {
    setResourcesDirty(true);
    setResourceSaveError(null);
    setScenario((current) =>
      current
        ? {
            ...current,
            resource_pools: upsertResourcePoolById(current.resource_pools, poolId, patch),
          }
        : current,
    );
  }

  function addResourcePool(pool: ResourcePool) {
    setResourcesDirty(true);
    setResourceSaveError(null);
    setScenario((current) => current ? {
      ...current,
      resource_pools: [...current.resource_pools, normalizeResourcePoolForWorkspace(pool)],
    } : current);
  }

  function removeResourcePool(poolId: string) {
    setResourcesDirty(true);
    setResourceSaveError(null);
    setScenario((current) => current ? {
      ...current,
      resource_pools: removeResourcePoolById(current.resource_pools, poolId),
    } : current);
  }

  function updateMilestone(index: number, patch: Partial<MilestoneConstraint>) {
    setMilestonesDirty(true);
    setScenario((current) =>
      current
        ? {
            ...current,
            milestones: current.milestones.map((milestone, milestoneIndex) =>
              milestoneIndex === index ? { ...milestone, ...patch } : milestone,
            ),
          }
        : current,
    );
  }

  function updateTaskProcessAndGenerate(task: Task, patch: TaskOverride) {
    if (!scenario) return;
    const nextScenario = scenarioWithTaskProcessPatch(scenario, task, patch);
    const nextFingerprint = scenarioFingerprintForSolve(nextScenario);
    const nextGenerated = patchGeneratedScheduleInputForTask(currentGenerated, task.id, nextScenario);
    rememberScenarioFingerprint(nextFingerprint);
    setScenario(nextScenario);
    setGenerated(nextGenerated);
    setGeneratedScenarioFingerprint(nextGenerated ? nextFingerprint : null);
    setSolveResult(null);
    setSolveResultScenarioFingerprint(null);
    setComparison(null);
  }

  function updateStructureControlLevel(task: Task, controlLevel: ControlLevel) {
    if (!scenario) return;
    setScenario((current) => {
      if (!current) return current;
      return {
        ...current,
        project: {
          ...current.project,
          bridges: current.project.bridges.map((bridge) => ({
            ...bridge,
            work_sections: bridge.work_sections.map((section) => ({
              ...section,
              structures: section.structures.map((structure) =>
                structure.id === task.structure_id ? { ...structure, control_level: controlLevel } : structure,
              ),
            })),
          })),
        },
      };
    });
  }

  return (
    <div className="app-shell">
      <div className={`app-body ${sideNavCollapsed ? "side-nav-collapsed" : ""}`}>
        <SideNavigation
          activeTab={activeTab}
          openTabs={openTabs}
          onOpen={openModule}
          collapsed={sideNavCollapsed}
          onToggleCollapsed={() => setSideNavCollapsed((current) => !current)}
        />

        <main className="workspace">
          <WorkspaceTabStrip
            openTabs={openTabs}
            activeTab={activeTab}
            onSelect={setActiveTab}
            onClose={closeModule}
          />
        {error && (
          <section className="notice error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </section>
        )}

        <div className={`workspace-content ${activeTab === "progressVisualization" ? "progress-visualization-workspace" : ""}`}>
        {scenario && activeTab === "projectFiles" && (
          <ProjectMasterDataWorkspace
            projectId={scenario.project.project_id}
            activeVersionId={scenario.project_data_version_id}
            onVersionConfirmed={(versionId) => setScenario((current) => current ? { ...current, project_data_version_id: versionId } : current)}
          />
        )}
        {scenario && activeTab === "parameterAssistant" && (
          <ParameterAssistantPanel
            scenario={scenario}
            busy={busy === "aiParameter"}
            onParse={parseAiParameterAssistant}
            onApply={applyAiParameterSuggestions}
          />
        )}
        {scenario && activeTab === "process" && (
          <ProcessTab
            scenario={scenario}
            onUpdateProcess={updateProcess}
            onSaveProcessLibrary={saveCurrentProcessLibrary}
            savingProcessLibrary={busy === "savingProcessLibrary"}
            processLibraryDirty={processLibraryDirty}
          />
        )}
        {scenario && activeTab === "logic" && (
          <LogicTab
            scenario={scenario}
            onUpdateLogic={updateLogic}
            onUpdateUpperStructureLogic={updateUpperStructureLogic}
            onSaveLocalConfig={saveCurrentLogicConfig}
            savingLocalConfig={busy === "savingLogic"}
            localConfigDirty={logicDirty}
          />
        )}
        {scenario && activeTab === "resources" && (
          <ResourcesTab
            scenario={scenario}
            workpointState={resourceWorkpointState}
            onRetryWorkpoints={() => setResourceWorkpointReloadToken((current) => current + 1)}
            onUpsertResourcePool={upsertResourcePool}
            onAddResourcePool={addResourcePool}
            onRemoveResourcePool={removeResourcePool}
            onSaveLocalConfig={saveCurrentResourceConfig}
            savingLocalConfig={busy === "savingResources"}
            localConfigDirty={resourcesDirty}
            saveError={resourceSaveError}
          />
        )}
        {activeTab === "resourceAssistant" && (
          <ResourceAssistantPanel
            scenario={scenario}
            integratedSnapshotId={integratedSnapshot?.status === "converged" ? integratedSnapshot.integrated_snapshot_id : null}
            onOpenPlanControl={() => openModule("planControl")}
            renderPlanDetail={(plan, planResult) => (
              <ResultsTab
                mode="readOnly"
                scenario={resourceAssistantDetailScenario(scenario, plan)}
                generated={planResult.generated ?? null}
                solveResult={resourceAssistantDetailSolveResult(plan, planResult)}
                resourceWorkpoints={currentResourceWorkpoints}
                externalDiagnostics={planResult.diagnostics}
                onPatchScenario={() => undefined}
                onPatchProject={() => undefined}
                onSolveCurrent={() => undefined}
                onSolveMinResources={() => undefined}
                onSolveResourceCost={() => undefined}
                busy={null}
                ganttMode={ganttMode}
                onGanttModeChange={setGanttMode}
                onSaveCurrent={() => undefined}
                savedResults={[]}
              />
            )}
          />
        )}
        {scenario && activeTab === "planControl" && <PlanControlPanel scenario={scenario} />}
        {scenario && activeTab === "girderPlanning" && (
          <GirderPlanningPanel scenario={scenario} onScenarioChange={setScenario} onIntegratedSnapshot={setIntegratedSnapshot} />
        )}
        {scenario && activeTab === "girderPlanSimulation" && (
          <GirderPlanSimulationPanel projectId={scenario.project.project_id} />
        )}
        {activeTab === "progressVisualization" && <ProgressVisualizationPanel />}
        {scenario && activeTab === "milestones" && (
          <MilestonesTab
            scenario={scenario}
            onUpdateMilestone={updateMilestone}
            onSaveLocalConfig={saveCurrentMilestoneConfig}
            savingLocalConfig={busy === "savingMilestones"}
            localConfigDirty={milestonesDirty}
            scopeLabelForMilestone={scopeLabel}
          />
        )}
        {scenario && activeTab === "tasks" && (
          <TaskViewTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onGenerateTaskView={generateOnly}
            onUpdateTaskProcess={updateTaskProcessAndGenerate}
            onUpdateStructureControlLevel={updateStructureControlLevel}
            busy={busy}
          />
        )}
        {activeTab === "results" && (
          <ResultsTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            resourceWorkpoints={currentResourceWorkpoints}
            onPatchScenario={patchScenario}
            onPatchProject={patchProject}
            onSolveCurrent={solveCurrent}
            onSolveMinResources={solveMinResources}
            onSolveResourceCost={solveResourceCost}
            busy={busy}
            ganttMode={ganttMode}
            onGanttModeChange={setGanttMode}
            onSaveCurrent={saveCurrentResult}
            savedResults={savedResults}
          />
        )}
        </div>
      </main>
    </div>
    </div>
  );
}

function TaskViewTab({
  scenario,
  generated,
  solveResult,
  onGenerateTaskView,
  onUpdateTaskProcess,
  onUpdateStructureControlLevel,
  busy,
}: {
  scenario: ScenarioInput;
  generated: GeneratedScheduleInput | null;
  solveResult: ScenarioSolveResult | null;
  onGenerateTaskView: () => void;
  onUpdateTaskProcess: (task: Task, patch: TaskOverride) => void;
  onUpdateStructureControlLevel: (task: Task, controlLevel: ControlLevel) => void;
  busy: BusyState;
}) {
  const [groupMode, setGroupMode] = useState<TaskViewMode>("by_structure");
  const [filters, setFilters] = useState<TaskViewFilters>({
    structureText: "",
    processText: "",
  });
  const [collapsedTaskParents, setCollapsedTaskParents] = useState<Set<string>>(() => new Set());
  const [collapsedTaskGroups, setCollapsedTaskGroups] = useState<Set<string>>(() => new Set());
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const [predecessorAnchorRect, setPredecessorAnchorRect] = useState<DOMRect | null>(null);
  const [projectMasterDisplayState, setProjectMasterDisplayState] = useState<ProjectMasterDisplayState | null>(null);
  const predecessorHoverOpenTimerRef = useRef<number | null>(null);
  const predecessorHoverCloseTimerRef = useRef<number | null>(null);
  const generatedForDetails = solveResult?.generated ?? generated;
  const projectMasterDisplayCoordinator = useMemo(
    () => createProjectMasterDisplayCoordinator(getProjectMasterWorkpoint),
    [],
  );
  const projectMasterWorkpointIds = useMemo(() => {
    return Array.from(new Set(
      (generatedForDetails?.schedule_input.tasks ?? [])
        .map((task) => task.bridge_id)
        .filter((bridgeId): bridgeId is string => typeof bridgeId === "string" && bridgeId.length > 0),
    )).sort();
  }, [generatedForDetails]);
  const projectMasterDisplayIdentity = useMemo(
    () => scenario.project_data_version_id && generatedForDetails
      ? createProjectMasterDisplayIdentity(scenario.project_data_version_id, projectMasterWorkpointIds)
      : null,
    [generatedForDetails, projectMasterWorkpointIds, scenario.project_data_version_id],
  );
  const currentProjectMasterDisplayState = projectMasterDisplayIdentity
    && projectMasterDisplayState?.identity.requestKey === projectMasterDisplayIdentity.requestKey
    ? projectMasterDisplayState
    : null;
  const projectMasterDisplayStatus = projectMasterDisplayIdentity
    ? currentProjectMasterDisplayState?.status ?? "loading"
    : "ready";
  const projectMasterWorkpoints = currentProjectMasterDisplayState?.status === "ready"
    ? currentProjectMasterDisplayState.workpoints
    : [];
  const projectMasterMaps = useMemo(
    () => buildProjectMasterTaskViewMaps(projectMasterWorkpoints),
    [projectMasterWorkpoints],
  );
  const workSectionDisplayById = useMemo(
    () => buildWorkSectionDisplayById(
      projectMasterDisplayIdentity ? null : scenario.project,
      projectMasterMaps,
    ),
    [projectMasterDisplayIdentity, projectMasterMaps, scenario.project],
  );
  const linksBySuccessor = useMemo(
    () => buildPredecessorLinksBySuccessor(generatedForDetails),
    [generatedForDetails],
  );
  const taskById = useMemo(
    () => new Map((generatedForDetails?.schedule_input.tasks ?? []).map((task) => [task.id, task])),
    [generatedForDetails],
  );
  const rows = useMemo(
    () => projectMasterDisplayStatus === "ready"
      ? buildTaskViewRows(
        generatedForDetails,
        scenario,
        linksBySuccessor,
        workSectionDisplayById,
        projectMasterMaps,
        Boolean(projectMasterDisplayIdentity),
      )
      : [],
    [
      generatedForDetails,
      linksBySuccessor,
      projectMasterDisplayIdentity,
      projectMasterDisplayStatus,
      projectMasterMaps,
      scenario,
      workSectionDisplayById,
    ],
  );
  const filteredRows = useMemo(() => filterTaskViewRows(rows, filters), [filters, rows]);
  const structureParents = useMemo(() => buildTaskViewStructureParents(filteredRows, scenario), [filteredRows, scenario]);
  const processGroups = useMemo(() => buildTaskViewGroups(filteredRows, "by_process"), [filteredRows]);
  const generating = busy === "generating";
  const refreshingTaskGraph = generating;

  useEffect(() => () => {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
  }, []);

  useEffect(() => {
    const unsubscribe = projectMasterDisplayCoordinator.subscribe(setProjectMasterDisplayState);
    return unsubscribe;
  }, [projectMasterDisplayCoordinator]);

  useEffect(() => {
    if (!projectMasterDisplayIdentity) {
      setProjectMasterDisplayState(null);
      return;
    }
    void projectMasterDisplayCoordinator.setIdentity(
      projectMasterDisplayIdentity.projectDataVersionId,
      projectMasterDisplayIdentity.workpointIds,
    ).then(() => {
      const state = projectMasterDisplayCoordinator.getState();
      if (state) setProjectMasterDisplayState(state);
    });
  }, [projectMasterDisplayCoordinator, projectMasterDisplayIdentity]);

  function retryProjectMasterDisplay() {
    void projectMasterDisplayCoordinator.retry();
  }

  function closePredecessorPopover() {
    setOpenPredecessorTaskId(null);
    setPredecessorAnchorRect(null);
  }

  function showPredecessorPopover(taskId: string, anchor: HTMLElement) {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
    predecessorHoverOpenTimerRef.current = window.setTimeout(() => {
      setPredecessorAnchorRect(anchor.getBoundingClientRect());
      setOpenPredecessorTaskId(taskId);
    }, PREDECESSOR_HOVER_DELAY_MS);
  }

  function schedulePredecessorPopoverClose() {
    clearPredecessorHoverTimer(predecessorHoverOpenTimerRef);
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
    predecessorHoverCloseTimerRef.current = window.setTimeout(closePredecessorPopover, PREDECESSOR_HOVER_CLOSE_DELAY_MS);
  }

  function keepPredecessorPopoverOpen() {
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
  }

  function predecessorDetails(row: TaskViewRow): PredecessorDetail[] {
    return row.predecessorLinks.map((link) => {
      const predecessor = taskById.get(link.predecessor_id);
      return {
        predecessorId: link.predecessor_id,
        predecessor,
        predecessorSideLabel: predecessor ? workSectionLabelForTask(predecessor, workSectionDisplayById) : "-",
        link,
      };
    });
  }

  function toggleParentGroup(groupId: string) {
    setCollapsedTaskParents((current) => toggleStringSet(current, groupId));
  }

  function toggleTaskGroup(groupId: string) {
    setCollapsedTaskGroups((current) => toggleStringSet(current, groupId));
  }

  function updateTaskProcess(task: Task, processId: string) {
    const component = editableComponentForTask(task, scenario);
    const nextProcess = processOptionsForComponent(component, scenario.process_library).find((process) => process.id === processId);
    if (!nextProcess) return;
    const nextDefault = defaultProductivityOption(nextProcess);
    onUpdateTaskProcess(task, {
      method_id: nextProcess.method_id ?? nextProcess.id,
      productivity_option_id: nextDefault?.id ?? null,
    });
  }

  function renderTaskRows(group: TaskViewGroup) {
    return group.rows.map((row) => {
      const isOpen = openPredecessorTaskId === row.task.id;
      const editableComponent = editableComponentForTask(row.task, scenario);
      const processOptions = processOptionsForComponent(editableComponent, scenario.process_library);
      const selectedProcess = selectedProcessForComponent(editableComponent, scenario.process_library);
      const productivityOptions = selectedProcess ? processProductivityOptions(selectedProcess) : [];
      const selectedProductivity = selectedProcess ? selectedProductivityOption(editableComponent, selectedProcess) : null;
      const showProcessSelect = processOptions.length > 1 || (processOptions.length > 0 && !selectedProcess);
      const showProductivitySelect = Boolean(selectedProcess && selectedProductivity && productivityOptions.length > 1);
      const editableStructure = findStructure(scenario.project, row.task.structure_id)?.structure ?? null;
      const controlLevel = editableStructure?.control_level ?? row.task.control_level ?? "normal";

      return (
        <tr key={`${group.id}-${row.task.id}`}>
          <td>
            {editableStructure ? (
              <select
                value={editableControlLevelValue(controlLevel)}
                disabled={refreshingTaskGraph}
                onChange={(event) => onUpdateStructureControlLevel(row.task, event.target.value as ControlLevel)}
              >
                {editableControlLevelOptions.map(({ value, label }) => (
                  <option value={value} key={value}>{label}</option>
                ))}
              </select>
            ) : (
              <span className="text-pill">{controlLevelLabels[controlLevel]}</span>
            )}
          </td>
          <td>{row.bridgeName} / {row.sectionName}</td>
          <td><span className="side-tag">{row.sideLabel}</span></td>
          <td>{row.structureLabel}</td>
          <td><span className="tag">{componentLabels[row.task.component_type]}</span></td>
          <td>{row.task.name}</td>
          <td>
            {processOptions.length > 0 ? (
              showProcessSelect ? (
                <select
                  value={selectedProcess?.id ?? ""}
                  disabled={refreshingTaskGraph}
                  onChange={(event) => updateTaskProcess(row.task, event.target.value)}
                >
                  {!selectedProcess && <option value="">请选择工艺</option>}
                  {processOptions.map((process) => (
                    <option key={process.id} value={process.id}>{process.process_name}</option>
                  ))}
                </select>
              ) : (
                <span className="text-pill">{selectedProcess?.process_name ?? row.task.process_name}</span>
              )
            ) : (
              <span className="text-pill">{row.task.process_name}</span>
            )}
          </td>
          <td>
            {selectedProcess && selectedProductivity ? (
              showProductivitySelect ? (
                <select
                  value={selectedProductivity.id}
                  disabled={refreshingTaskGraph}
                  onChange={(event) => onUpdateTaskProcess(row.task, { productivity_option_id: event.target.value })}
                >
                  {productivityOptions.map((option) => (
                    <option key={option.id} value={option.id}>{productivityOptionLabel(option)}</option>
                  ))}
                </select>
              ) : (
                <span className="text-pill">{productivityOptionLabel(selectedProductivity)}</span>
              )
            ) : (
              <code>-</code>
            )}
          </td>
          <td className="structure-parameter-cell">
            {structureParameterLabelForTask(row.task, editableComponent) || "-"}
          </td>
          <td>{row.task.quantity_label || displayValue(row.task.quantity)}</td>
          <td>{row.task.duration_days} 天</td>
          <td className="duration-expression" title={durationExpression(row.task, scenario)}>
            {durationExpression(row.task, scenario)}
          </td>
          <td>{taskResourceTypesLabel(row.task, scenario.resource_pools)}</td>
          <td className="predecessor-cell">
            {row.predecessorLinks.length > 0 ? (
              <button
                className="predecessor-count has-items"
                type="button"
                onMouseEnter={(event) => showPredecessorPopover(row.task.id, event.currentTarget)}
                onMouseLeave={schedulePredecessorPopoverClose}
                onFocus={(event) => showPredecessorPopover(row.task.id, event.currentTarget)}
                onBlur={schedulePredecessorPopoverClose}
                aria-expanded={isOpen}
              >
                {row.predecessorLinks.length}
              </button>
            ) : (
              <span className="predecessor-zero">0</span>
            )}
            {isOpen && (
              <PredecessorPopover
                task={row.task}
                details={predecessorDetails(row)}
                anchorRect={predecessorAnchorRect}
                onMouseEnter={keepPredecessorPopoverOpen}
                onMouseLeave={schedulePredecessorPopoverClose}
              />
            )}
          </td>
        </tr>
      );
    });
  }

  function renderTaskGroup(group: TaskViewGroup, mode: TaskViewMode, nested = false) {
    const collapsed = collapsedTaskGroups.has(group.id);
    return (
      <div className={`task-view-group${nested ? " nested" : ""}`} key={group.id}>
        <button className="task-view-group-title" type="button" onClick={() => toggleTaskGroup(group.id)}>
          <span className="task-view-group-heading">
            {collapsed ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
            <strong>{group.title}</strong>
          </span>
          <span>{taskViewGroupSubtitle(group.rows, mode, scenario)}</span>
        </button>
        {!collapsed && (
          <div className="table-wrap task-view-table-wrap">
            <table className="task-view-table">
              <thead>
                <tr>
                  <th>管控级别</th>
                  <th>桥梁 / 工区</th>
                  <th>幅别</th>
                  <th>墩号 / 结构物</th>
                  <th>构件</th>
                  <th>任务名称</th>
                  <th>工艺</th>
                  <th>工效</th>
                  <th>结构物参数</th>
                  <th>工程量</th>
                  <th>工期</th>
                  <th>工期计算</th>
                  <th>资源配置</th>
                  <th>前置</th>
                </tr>
              </thead>
              <tbody>{renderTaskRows(group)}</tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  return (
    <TaskViewWorkspace
      displayStatus={projectMasterDisplayStatus}
      onRetry={retryProjectMasterDisplay}
    >
      <section className="panel full task-view-header-panel">
        <PanelTitle
          title="任务视图"
          subtitle="调用 OR-Tools CP-SAT 前核验结构物识别、工期计算和工艺逻辑关系"
          action={
            <div className="task-view-title-actions">
              {generatedForDetails && (
                <div className="segmented">
                  <button className={groupMode === "by_structure" ? "active" : ""} type="button" onClick={() => setGroupMode("by_structure")}>
                    按墩号
                  </button>
                  <button className={groupMode === "by_process" ? "active" : ""} type="button" onClick={() => setGroupMode("by_process")}>
                    按工艺
                  </button>
                </div>
              )}
              <button className="secondary" type="button" onClick={onGenerateTaskView} disabled={refreshingTaskGraph || !scenario}>
              {generating ? <Loader2 className="spin" size={16} /> : <ClipboardList size={16} />}
              {generatedForDetails ? "刷新任务视图" : "生成任务视图"}
              </button>
            </div>
          }
        />
        {!generatedForDetails && (
          <div className="task-view-empty">
            <ClipboardList size={34} />
            <strong>尚未生成求解前任务图</strong>
            <span>生成后可按墩号或工艺核验任务、工期和前置关系；此操作不会调用 CP-SAT。</span>
          </div>
        )}
        {generatedForDetails && (
          <div className="task-view-filters">
            <label>
              结构物
              <input
                value={filters.structureText}
                onChange={(event) => setFilters((current) => ({ ...current, structureText: event.target.value }))}
                placeholder="桥梁、工区、幅别、墩号、任务"
              />
            </label>
            <label>
              工艺 / 构件
              <input
                value={filters.processText}
                onChange={(event) => setFilters((current) => ({ ...current, processText: event.target.value }))}
                placeholder="工艺名称或构件类型"
              />
            </label>
          </div>
        )}
      </section>

      {generatedForDetails && (
        <>
          <section className="panel full task-view-panel">
            <PanelTitle
              title="任务清单"
              subtitle={groupMode === "by_structure" ? "按桥梁 / 工区展开，墩号从小到大展示，组内按工序顺序排列" : "按工艺聚合，组内仍按桥梁 / 工区、墩号、工序排序"}
            />
            <div className="task-view-groups">
              {filteredRows.length > 0 ? (
                groupMode === "by_structure" ? (
                  structureParents.map((parent) => {
                    const collapsed = collapsedTaskParents.has(parent.id);
                    return (
                      <div className="task-view-parent-group" key={parent.id}>
                        <button className="task-view-parent-title" type="button" onClick={() => toggleParentGroup(parent.id)}>
                          <span className="task-view-group-heading">
                            {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                            <strong>{parent.title}</strong>
                          </span>
                          <span>{parent.subtitle}</span>
                        </button>
                        {!collapsed && (
                          <div className="task-view-child-groups">
                            {parent.groups.map((group) => renderTaskGroup(group, "by_structure", true))}
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  processGroups.map((group) => renderTaskGroup(group, "by_process"))
                )
              ) : (
                <div className="empty">当前筛选条件下没有任务</div>
              )}
            </div>
          </section>
        </>
      )}
    </TaskViewWorkspace>
  );
}

function ResultsTab({
  mode = "interactive",
  scenario,
  generated,
  solveResult,
  resourceWorkpoints,
  externalDiagnostics = [],
  onPatchScenario,
  onPatchProject,
  onSolveCurrent,
  onSolveMinResources,
  onSolveResourceCost,
  busy,
  ganttMode,
  onGanttModeChange,
  onSaveCurrent,
  savedResults,
}: {
  mode?: "interactive" | "readOnly";
  scenario: ScenarioInput | null;
  generated: GeneratedScheduleInput | null;
  solveResult: ScenarioSolveResult | null;
  resourceWorkpoints: ProjectMasterWorkpoint[];
  externalDiagnostics?: ValidationMessage[];
  onPatchScenario: (patch: Partial<ScenarioInput>) => void;
  onPatchProject: (patch: Partial<ProjectModel>) => void;
  onSolveCurrent: () => void;
  onSolveMinResources: () => void;
  onSolveResourceCost: () => void;
  busy: BusyState;
  ganttMode: GanttMode;
  onGanttModeChange: (mode: GanttMode) => void;
  onSaveCurrent: (result?: ScenarioSolveResult | null) => void;
  savedResults: ScenarioSolveResult[];
}) {
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const [predecessorAnchorRect, setPredecessorAnchorRect] = useState<DOMRect | null>(null);
  const [selectedResultIndex, setSelectedResultIndex] = useState(0);
  const [planWindowStart, setPlanWindowStart] = useState("");
  const [planWindowFinish, setPlanWindowFinish] = useState("");
  const [planWindowMode, setPlanWindowMode] = useState<PlanWindowMode>("detail");
  const [selectedPlanTaskId, setSelectedPlanTaskId] = useState<string | null>(null);
  const [selectedResourceId, setSelectedResourceId] = useState<string | null>(null);
  const predecessorHoverOpenTimerRef = useRef<number | null>(null);
  const predecessorHoverCloseTimerRef = useRef<number | null>(null);
  const resultOptions = useMemo(() => scenarioResultOptions(solveResult), [solveResult]);
  const resultOptionSummaries = useMemo(() => summarizeResultOptions(resultOptions), [resultOptions]);
  const activeSolveResult = resultOptions[Math.min(selectedResultIndex, Math.max(0, resultOptions.length - 1))] ?? null;
  const result = activeSolveResult?.result ?? null;
  const planStatus = useMemo(() => derivePlanStatus(result), [result]);
  const summary = useMemo(() => buildSummary(scenario, generated, activeSolveResult), [scenario, generated, activeSolveResult]);
  const generatedForDetails = activeSolveResult?.generated ?? generated;
  const resourceRecommendationStatus = resourceRecommendationStatusFromResult(result);
  const alternativeOutput = alternativeOutputFromResult(solveResult?.result ?? result);
  const resourceCostSummary = resourceCostSummaryFromResult(result);
  const continuityMetrics = continuityMetricsFromResult(result);
  const drillGroupRefinement = drillGroupRefinementFromResult(result);
  const objectiveContributionSummary = objectiveContributionSummaryFromResult(result);
  const refinementSummary = refinementSummaryFromResult(result);
  const controlPriorityAnalysis = controlPriorityAnalysisFromResult(result);
  const resourceOrganization = resourceOrganizationFromResult(result);
  const continuousBeamTeamSpanSummary = continuousBeamTeamSpanSummaryFromResult(result);
  const strategyConfig = withDefaultScheduleStrategy(scenario?.schedule_strategy);
  const objectiveTerms = strategyConfig.objective_terms ?? defaultObjectiveTermsConfig();
  const enabledObjectiveCount = objectiveTermDefinitions.filter((term) => objectiveTerms[term.id]?.enabled).length;
  const isReadOnly = mode === "readOnly";
  const activePlanWindowMode: PlanWindowMode = planWindowMode;
  const planSortLabel = planListSortOptions.find((option) => option.value === ganttMode)?.label ?? "按时间";
  const resourcePoolsForDisplay = scenario?.resource_pools ?? [];
  const resourceAllocations = useMemo(() => result?.resource_allocations ?? [], [result]);
  const resourceScopeResult = useMemo(
    () => buildResourceScopeResult({
      generated: generatedForDetails,
      result,
      resourcePools: resourcePoolsForDisplay,
      workpoints: resourceWorkpoints,
    }),
    [generatedForDetails, resourcePoolsForDisplay, resourceWorkpoints, result],
  );
  const workSectionDisplayById = useMemo(
    () => buildWorkSectionDisplayById(scenario?.project ?? null),
    [scenario?.project],
  );
  const diagnostics = useMemo(() => {
    const messages = activeSolveResult?.diagnostics ?? (externalDiagnostics.length ? externalDiagnostics : generated?.validation ?? []);
    if (!planStatus.diagnostic) return messages;
    const alreadyIncluded = messages.some((message) => message.subject_id === planStatus.diagnostic?.subject_id);
    return alreadyIncluded ? messages : [planStatus.diagnostic, ...messages];
  }, [activeSolveResult, externalDiagnostics, generated, planStatus.diagnostic]);
  const scheduledTaskById = useMemo(
    () => new Map((result?.tasks ?? []).map((task) => [task.id, task])),
    [result],
  );
  const selectedResourceAllocations = useMemo(
    () => sortResourceAllocationsByPlan(resourceAllocations.filter((item) => item.resource_id === selectedResourceId)),
    [resourceAllocations, selectedResourceId],
  );
  const selectedResource = selectedResourceAllocations[0] ?? null;
  const filteredPlanTasks = useMemo(() => {
    const filtered = filterScheduledTasksByWindow(result?.tasks ?? [], planWindowStart, planWindowFinish);
    return sortScheduledTasksForPlan(filtered, ganttMode);
  }, [ganttMode, result, planWindowStart, planWindowFinish]);
  const selectedPlanTask = useMemo(
    () => filteredPlanTasks.find((task) => task.id === selectedPlanTaskId) ?? filteredPlanTasks[0] ?? null,
    [filteredPlanTasks, selectedPlanTaskId],
  );
  const linksBySuccessor = useMemo(() => {
    const links = new Map<string, PrecedenceLink[]>();
    for (const link of generatedForDetails?.schedule_input.precedence_links ?? []) {
      const current = links.get(link.successor_id) ?? [];
      current.push(link);
      links.set(link.successor_id, current);
    }
    return links;
  }, [generatedForDetails]);
  useEffect(() => {
    setSelectedResultIndex(0);
    setSelectedPlanTaskId(null);
    setSelectedResourceId(null);
  }, [solveResult]);

  useEffect(() => {
    if (!filteredPlanTasks.length) {
      if (selectedPlanTaskId !== null) setSelectedPlanTaskId(null);
      return;
    }
    if (!selectedPlanTaskId || !filteredPlanTasks.some((task) => task.id === selectedPlanTaskId)) {
      setSelectedPlanTaskId(filteredPlanTasks[0].id);
    }
  }, [filteredPlanTasks, selectedPlanTaskId]);

  useEffect(() => {
    if (selectedResourceId && !resourceAllocations.some((item) => item.resource_id === selectedResourceId)) {
      setSelectedResourceId(null);
    }
  }, [resourceAllocations, selectedResourceId]);

  useEffect(() => () => {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
  }, []);

  function closePredecessorPopover() {
    setOpenPredecessorTaskId(null);
    setPredecessorAnchorRect(null);
  }

  function showPredecessorPopover(taskId: string, anchor: HTMLElement) {
    clearPredecessorHoverTimers(predecessorHoverOpenTimerRef, predecessorHoverCloseTimerRef);
    predecessorHoverOpenTimerRef.current = window.setTimeout(() => {
      setPredecessorAnchorRect(anchor.getBoundingClientRect());
      setOpenPredecessorTaskId(taskId);
    }, PREDECESSOR_HOVER_DELAY_MS);
  }

  function schedulePredecessorPopoverClose() {
    clearPredecessorHoverTimer(predecessorHoverOpenTimerRef);
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
    predecessorHoverCloseTimerRef.current = window.setTimeout(closePredecessorPopover, PREDECESSOR_HOVER_CLOSE_DELAY_MS);
  }

  function keepPredecessorPopoverOpen() {
    clearPredecessorHoverTimer(predecessorHoverCloseTimerRef);
  }

  function updateStrategyConfig(patch: Partial<ScheduleStrategyConfig>) {
    if (!scenario) return;
    onPatchScenario({ schedule_strategy: withDefaultScheduleStrategy({ ...strategyConfig, ...patch }) });
  }

  function updateObjectiveTerm(termId: ObjectiveTermId, patch: Partial<ObjectiveTermConfig>) {
    if (!scenario) return;
    const current = objectiveTerms[termId] ?? defaultObjectiveTermsConfig()[termId];
    if (patch.enabled === false && current?.enabled && enabledObjectiveCount <= 1) return;
    const nextTerms = {
      ...objectiveTerms,
      [termId]: {
        ...current,
        ...patch,
      },
    } as Record<ObjectiveTermId, ObjectiveTermConfig>;
    updateStrategyConfig({
      objective_terms: nextTerms,
      enable_balance_objective: false,
    });
  }

  function restoreDefaultObjectiveTerms() {
    updateStrategyConfig({
      objective_terms: defaultObjectiveTermsConfig(),
      enable_balance_objective: false,
    });
  }

  function predecessorDetails(task: ScheduledTask): PredecessorDetail[] {
    const links = linksBySuccessor.get(task.id) ?? [];
    return task.predecessor_ids.map((predecessorId) => {
      const predecessor = scheduledTaskById.get(predecessorId);
      const link = links.find((item) => item.predecessor_id === predecessorId);
      return {
        predecessorId,
        predecessor,
        predecessorSideLabel: predecessor ? workSectionLabelForTask(predecessor, workSectionDisplayById) : "-",
        link,
      };
    });
  }

  return (
    <ScheduleResultsWorkspace>
      {!isReadOnly && scenario && (
        <section className="panel full simulation-params-panel">
          <PanelTitle
            title="模拟参数"
            subtitle="方案、计划起点和求解配置"
            action={
              <div className="actions inline">
                <button className="primary" onClick={onSolveCurrent} disabled={Boolean(busy) || !scenario}>
                  {busy === "solving" || busy === "loading" ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
                  固定资源条件下，推算最短工期
                </button>
                <button className="secondary" onClick={onSolveMinResources} disabled={Boolean(busy) || !scenario}>
                  {busy === "minResources" ? <Loader2 className="spin" size={16} /> : <Server size={16} />}
                  固定工期条件下，推算最少资源
                </button>
                <button className="primary" onClick={onSolveResourceCost} disabled={Boolean(busy) || !scenario}>
                  {busy === "resourceCost" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
                  资源成本优化排程
                </button>
              </div>
            }
          />
          <div className="form-grid">
            <label>
              方案名称
              <input value={scenario.scenario_name} onChange={(event) => onPatchScenario({ scenario_name: event.target.value })} />
            </label>
            <label>
              项目名称
              <input value={scenario.project.project_name} onChange={(event) => onPatchProject({ project_name: event.target.value })} />
            </label>
            <label>
              计划开始
              <input type="date" value={scenario.project.start_date} onChange={(event) => onPatchProject({ start_date: event.target.value })} />
            </label>
            <label>
              求解上限(秒)
              <input
                type="number"
                min={1}
                max={15}
                value={scenario.time_limit_seconds}
                onChange={(event) => onPatchScenario({ time_limit_seconds: Math.min(15, Number(event.target.value)) })}
              />
            </label>
          </div>
          <div className="objective-config">
              <div className="objective-config-header">
                <div>
                  <h3>算法倾向选择</h3>
                  <span>已选择 {enabledObjectiveCount}/{objectiveTermDefinitions.length} 个排程倾向</span>
                </div>
              </div>
              <div className="objective-choice-grid">
                {objectiveTermDefinitions.map((term) => {
                  const termConfig = objectiveTerms[term.id];
                  const keepOneEnabled = termConfig.enabled && enabledObjectiveCount <= 1;
                  return (
                    <label
                      className={`objective-choice${termConfig.enabled ? " selected" : ""}${keepOneEnabled ? " locked" : ""}`}
                      key={term.id}
                    >
                      <input
                        type="checkbox"
                        checked={termConfig.enabled}
                        disabled={keepOneEnabled}
                        aria-label={`选择${term.label}`}
                        onChange={(event) => updateObjectiveTerm(term.id, { enabled: event.target.checked })}
                      />
                      <span className="objective-choice-copy">
                        <strong>{term.label}</strong>
                        <span>{term.group}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
              <details className="objective-advanced">
                <summary>高级设置</summary>
                <div className="objective-advanced-toolbar">
                  <span>查看说明、调整权重或恢复默认倾向。</span>
                  <button className="secondary objective-reset-button" type="button" onClick={restoreDefaultObjectiveTerms}>
                    <RotateCcw size={15} />
                    恢复默认
                  </button>
                </div>
                <div className="objective-table-wrap">
                  <table className="objective-table">
                    <thead>
                      <tr>
                        <th>倾向</th>
                        <th>说明</th>
                        <th>当前权重</th>
                      </tr>
                    </thead>
                    <tbody>
                      {objectiveTermDefinitions.map((term) => {
                        const termConfig = objectiveTerms[term.id];
                        return (
                          <tr className={termConfig.enabled ? undefined : "objective-row-disabled"} key={term.id}>
                            <td>
                              <strong>{term.label}</strong>
                              <span>{term.group}</span>
                              <span>{term.appliesTo}</span>
                            </td>
                            <td className="objective-description">{term.description}</td>
                            <td>
                              <input
                                type="number"
                                min={1}
                                max={10_000_000_000}
                                step={1}
                                value={termConfig.weight}
                                disabled={!termConfig.enabled}
                                onChange={(event) => updateObjectiveTerm(term.id, {
                                  weight: normalizeObjectiveWeight(event.target.value),
                                })}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
        </section>
      )}

      <section className="summary-band">
        <Metric label="计划状态" value={planStatus.label} tone={planStatus.tone} hint={planStatus.hint} icon={<Server size={18} />} />
        <Metric label="总工期" value={summary.days} tone="neutral" icon={<CalendarDays size={18} />} />
        <Metric label="工作项" value={summary.tasks} tone="neutral" icon={<CheckCircle2 size={18} />} />
        <Metric label="求解耗时" value={summary.elapsed} tone="neutral" icon={<Timer size={18} />} />
        <Metric label="资源 / 里程碑" value={summary.resourcesAndMilestones} tone="neutral" icon={<Flag size={18} />} />
      </section>

      <section className="panel full resource-scope-result-panel">
        <PanelTitle title="资源作用域结果" subtitle="展示求解输入中的显式作用域、权威分配工点和数量口径" />
        {resourceScopeResult.showProjectSharedNotice && (
          <div className="resource-shared-result-notice" role="note">
            {resourceScopeResult.notice}
          </div>
        )}
        <div className="table-wrap short">
          <table className="resource-scope-result-table">
            <thead>
              <tr>
                <th>资源</th>
                <th>作用域</th>
                <th>分配工点</th>
                <th>当前数量</th>
                <th>推荐数量</th>
              </tr>
            </thead>
            <tbody>
              {resourceScopeResult.rows.map((row) => (
                <tr key={row.key}>
                  <td>{row.resourceLabel}</td>
                  <td>{row.scopeLabel}</td>
                  <td>{row.workpointLabel}</td>
                  <td>{row.currentQuantity ?? "不可用"}</td>
                  <td>{row.recommendedQuantity ?? "未提供"}</td>
                </tr>
              ))}
              {!resourceScopeResult.rows.length && (
                <tr>
                  <td colSpan={5}>尚无可展示的资源作用域结果</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {refinementSummary && (
        <section className={`business-conclusion ${refinementSummary.tone}`}>
          <div className="business-conclusion-heading">
            <div className="business-conclusion-icon">
              <Workflow size={22} />
            </div>
            <div>
              <span>目标函数主结果</span>
              <h2>{refinementSummary.title}</h2>
            </div>
          </div>
          <div className="business-conclusion-grid">
            <div>
              <span>推荐排程总工期</span>
              <strong>{refinementSummary.recommendedDays}</strong>
            </div>
            <div>
              <span>最短工期基准</span>
              <strong>{refinementSummary.baselineDays}</strong>
            </div>
            <div>
              <span>业务目标状态</span>
              <strong>{refinementSummary.businessStatus}</strong>
            </div>
            <div>
              <span>求解器状态</span>
              <strong>{refinementSummary.solverStatus}</strong>
            </div>
            <div>
              <span>硬里程碑晚点</span>
              <strong>{refinementSummary.hardMilestoneLateDays}</strong>
            </div>
            <div>
              <span>固定工期超期</span>
              <strong>{refinementSummary.fixedDurationOverrunDays}</strong>
            </div>
          </div>
          {refinementSummary.stageDescription && (
            <p>{refinementSummary.stageDescription}</p>
          )}
          {refinementSummary.optimalityMessage && (
            <p>{refinementSummary.optimalityMessage}</p>
          )}
          {refinementSummary.fallbackMessage && (
            <p>{refinementSummary.fallbackMessage}</p>
          )}
          {refinementSummary.bestEffortMessage && (
            <p>{refinementSummary.bestEffortMessage}</p>
          )}
        </section>
      )}

      {objectiveContributionSummary && (
        <section className="panel full">
          <PanelTitle
            title="目标函数贡献"
            subtitle={objectiveContributionSummary.isLegacy ? "旧字段汇总，部分派生项可能只展示已有结果字段" : "后端返回的目标项原始罚分、有效权重和加权贡献"}
          />
          <div className="table-wrap short">
            <table>
              <thead>
                <tr>
                  <th>指标</th>
                  <th>状态</th>
                  <th>原始罚分</th>
                  <th>有效权重</th>
                  <th>加权贡献</th>
                </tr>
              </thead>
              <tbody>
                {objectiveContributionSummary.items.map((item) => (
                  <tr key={item.term_id}>
                    <td>
                      <strong>{item.label || item.term_id}</strong>
                      <span className="muted-cell">
                        {item.group || objectiveTermDefinitionById(item.term_id)?.group || item.source}
                        {item.parent_term_id ? ` / 继承 ${objectiveTermDefinitionById(item.parent_term_id)?.label ?? item.parent_term_id}` : ""}
                      </span>
                      {item.notes && <span className="muted-cell">{item.notes}</span>}
                    </td>
                    <td>{objectiveContributionStatus(item)}</td>
                    <td>{formatObjectiveNumber(item.raw_penalty)}</td>
                    <td>{formatObjectiveNumber(item.effective_weight)}</td>
                    <td>{formatObjectiveNumber(item.weighted_contribution)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="summary-footnote">
            目标函数合计：{formatObjectiveNumber(objectiveContributionSummary.total)}
          </div>
        </section>
      )}

      {resultOptions.length > 1 && (
        <section className="panel full">
          <PanelTitle title="方案输出" subtitle="固定资源方案与可验证最少资源候选方案" />
          <div className="segmented result-switcher">
            {resultOptions.map((option, index) => (
              <button
                className={selectedResultIndex === index ? "active" : ""}
                key={`${option.scenario_id}-${index}`}
                onClick={() => setSelectedResultIndex(index)}
                type="button"
              >
                {resultOptionLabel(option, index)}
              </button>
            ))}
          </div>
          <div className="table-wrap short">
            <table>
              <thead>
                <tr>
                  <th>方案</th>
                  <th>状态</th>
                  <th>总工期</th>
                  <th>完工日期</th>
                  <th>资源数量</th>
                  <th>新增资源</th>
                </tr>
              </thead>
              <tbody>
                {resultOptions.map((option, index) => {
                  const item = resultOptionSummaries[index] ?? resultOptionSummary(option);
                  return (
                    <tr key={`${option.scenario_id}-${index}`}>
                      <td>{resultOptionLabel(option, index)}</td>
                      <td>{formatScheduleStatus(option.result.status)}</td>
                      <td>{option.result.objective_days ?? "-"}</td>
                      <td>{option.result.plan_finish_date ?? "-"}</td>
                      <td>{item.resourceCount}</td>
                      <td>{item.addedResourceCount}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panel full">
        <div className="panel-title">
          <div>
            <h2>约束诊断</h2>
            <span>生成层、求解层和里程碑检查的摘要</span>
          </div>
          {!isReadOnly && (
            <div className="actions inline">
              <button className="secondary" onClick={() => onSaveCurrent(activeSolveResult)} disabled={!activeSolveResult}>
                <Save size={15} />
                保存方案
              </button>
            </div>
          )}
        </div>
        <div className="diagnostics">
          {alternativeOutput.status === "not_output" && (
            <div className="diagnostic warning">
              <strong>方案2未输出</strong>
              <span>{alternativeOutput.message || "方案2未输出：新增资源分支未形成可展示候选方案。"}</span>
            </div>
          )}
          {diagnostics.slice(0, 12).map((message, index) => (
            <div className={`diagnostic ${message.level}`} key={`${message.subject_id ?? "message"}-${index}`}>
              <strong>{diagnosticLevelLabels[message.level]}</strong>
              <span>{message.message}</span>
            </div>
          ))}
          {busy === "solving" && !solveResult && (
            <div className="diagnostic info">
              <strong>求解中</strong>
              <span>正在按固定资源推算最短工期，请稍候...</span>
            </div>
          )}
          {!solveResult && !generated && diagnostics.length === 0 && busy !== "solving" && (
            <div className="empty">等待生成或求解</div>
          )}
        </div>
      </section>

      {controlPriorityAnalysis && (
        <section className="panel full">
          <PanelTitle title="目标函数诊断" subtitle="资源组织与求解过程诊断" />
          {resourceOrganization && (
            <div className="control-diagnostic-grid refinement-diagnostics">
              <div className="table-wrap short">
                <div className="table-caption">资源组织汇总</div>
                <table>
                  <thead>
                    <tr>
                      <th>资源类型</th>
                      <th>启用/输入</th>
                      <th>工作量差</th>
                      <th>最大空档</th>
                      <th>均衡</th>
                      <th>连续</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resourceOrganization.resource_types.slice(0, 8).map((item) => (
                      <tr key={item.resource_type}>
                        <td>{resourceTypeLabel(item.resource_type, resourcePoolsForDisplay)}</td>
                        <td>{item.used_resource_count} / {item.resource_count}</td>
                        <td>{item.workload_range_days} 天</td>
                        <td>{item.max_idle_gap_days} 天</td>
                        <td>{resourceBalanceStatusLabels[item.balance_status] ?? item.balance_status}</td>
                        <td>{resourceIdleStatusLabels[item.idle_status] ?? item.idle_status}</td>
                      </tr>
                    ))}
                    {!resourceOrganization.resource_types.length && (
                      <tr>
                        <td colSpan={6}>暂无资源组织诊断</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="table-wrap short">
                <div className="table-caption">资源队伍明细</div>
                <table>
                  <thead>
                    <tr>
                      <th>资源</th>
                      <th>任务</th>
                      <th>工作天</th>
                      <th>空闲天</th>
                      <th>最大空档</th>
                      <th>利用率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...resourceOrganization.resources]
                      .sort((a, b) => (
                        b.max_idle_gap_days - a.max_idle_gap_days
                        || b.idle_days - a.idle_days
                        || b.active_days - a.active_days
                        || a.resource_name.localeCompare(b.resource_name)
                      ))
                      .slice(0, 10)
                      .map((item) => (
                        <tr key={item.resource_id}>
                          <td>
                            <strong>{item.resource_name}</strong>
                            <span className="muted-cell">{resourceTypeLabel(item.resource_type, resourcePoolsForDisplay)}</span>
                          </td>
                          <td>{item.task_count}</td>
                          <td>{item.active_days} 天</td>
                          <td>{item.idle_days} 天</td>
                          <td>{item.max_idle_gap_days} 天</td>
                          <td>{formatPercent(item.utilization_within_span)}</td>
                        </tr>
                      ))}
                    {!resourceOrganization.resources.length && (
                      <tr>
                        <td colSpan={6}>暂无资源队伍明细</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {continuousBeamTeamSpanSummary && continuousBeamTeamSpanSummary.spans.length > 0 && (
            <div className="table-wrap short refinement-path-groups">
              <div className="table-caption">现浇连续梁班组联级占用</div>
              <table>
                <thead>
                  <tr>
                    <th>联</th>
                    <th>工作区</th>
                    <th>班组</th>
                    <th>任务数</th>
                    <th>开始</th>
                    <th>完成</th>
                  </tr>
                </thead>
                <tbody>
                  {continuousBeamTeamSpanSummary.spans.map((span) => (
                    <tr key={span.span_id}>
                      <td>
                        <strong>{span.span_name}</strong>
                        <span className="muted-cell">{span.span_id}</span>
                      </td>
                      <td>{span.work_section_id ?? "-"}</td>
                      <td>{span.resource_name ?? "-"}</td>
                      <td>{span.task_ids.length}</td>
                      <td>{span.start_date}</td>
                      <td>{span.finish_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {controlPriorityAnalysis.path_group_diagnostics.length > 0 && (
            <div className="table-wrap short refinement-path-groups">
              <table>
                <thead>
                  <tr>
                    <th>路径组</th>
                    <th>资源</th>
                    <th>实际可施工序列</th>
                  </tr>
                </thead>
                <tbody>
                  {controlPriorityAnalysis.path_group_diagnostics.map((group) => (
                    <tr key={group.key}>
                      <td>{group.side_label} / {group.component_label} / {group.process_name}</td>
                      <td>{resourceTypeLabel(group.resource_type, resourcePoolsForDisplay)}</td>
                      <td className="path-group-sequence">
                        {group.actual_sequence.join(" -> ")}
                        <span className="muted-cell">共 {group.actual_sequence.length} 个位置</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {drillGroupRefinement && drillGroupRefinement.coarse_group_count > 0 && (
            <div className="table-wrap short refinement-path-groups">
              <div className="table-caption">桩基墩组诊断</div>
              <table>
                <thead>
                  <tr>
                    <th>状态</th>
                    <th>墩组数量</th>
                    <th>复核节点</th>
                    <th>复核弧</th>
                    <th>弧减少</th>
                    <th>回退原因</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>{drillGroupRefinementStatusLabels[drillGroupRefinement.status] ?? drillGroupRefinement.status}</td>
                    <td>{drillGroupRefinement.coarse_group_count}</td>
                    <td>{drillGroupRefinement.stage2_node_count}</td>
                    <td>{drillGroupRefinement.stage2_arc_count}</td>
                    <td>{formatPercent(drillGroupRefinement.arc_reduction_ratio)}</td>
                    <td>{drillGroupRefinement.fallback_reason || "-"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {resourceCostSummary && (
        <section className="panel full">
          <PanelTitle title="线性成本推荐方案" subtitle="固定工期条件下，在资源上限内选择成本最低的资源配置" />
          <div className="cost-result-layout">
            <div className="table-wrap short">
              <table>
                <thead>
                  <tr>
                    <th>资源</th>
                    <th>当前数量</th>
                    <th>推荐数量</th>
                    <th>新增数量</th>
                    <th>成本类型</th>
                    <th>单价</th>
                    <th>活跃天数</th>
                    <th>资源成本</th>
                  </tr>
                </thead>
                <tbody>
                  {resourceCostSummary.selectedResources.map((resource) => (
                    <tr key={resource.resource_pool_id}>
                      <td>{resource.label}</td>
                      <td>{resource.current_quantity}</td>
                      <td>{resource.selected_quantity}</td>
                      <td>{resource.added_quantity}</td>
                      <td>{resourceCostTypeLabels[resource.cost_type]}</td>
                      <td>{formatResourceUnitCost(resource)}</td>
                      <td>{resource.cost_type === "monthly_rental" ? resource.active_days : "-"}</td>
                      <td>{formatMoney(resource.incremental_cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-wrap short">
              <table>
                <thead>
                  <tr>
                    <th>成本项</th>
                    <th>金额</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>线性资源成本</td>
                    <td>{formatMoney(resourceCostSummary.resourceIncrementalCost)}</td>
                  </tr>
                  <tr>
                    <td>参考延误成本</td>
                    <td>{formatMoney(resourceCostSummary.softMilestonePenalty)}</td>
                  </tr>
                  <tr>
                    <td><strong>展示综合成本</strong></td>
                    <td><strong>{formatMoney(resourceCostSummary.totalCost)}</strong></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          {resourceCostSummary.businessExplanation && (
            <p className="business-explanation">{resourceCostSummary.businessExplanation}</p>
          )}
        </section>
      )}

      <section className="panel full">
        <PanelTitle
          title="里程碑结果"
          subtitle="软节点允许超期，迟延天数仅作为诊断展示"
        />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>节点</th>
                <th>约束</th>
                <th>目标</th>
                <th>实际</th>
                <th>迟延</th>
                <th>罚分</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              {result?.milestone_results.map((milestone) => (
                <tr key={milestone.id}>
                  <td>{milestone.name}</td>
                  <td>{milestone.mode === "hard" ? "强制目标" : "提醒目标"}</td>
                  <td>{milestone.target_date}</td>
                  <td>{milestone.actual_date ?? "-"}</td>
                  <td>{milestone.lateness_days} 天</td>
                  <td>{milestone.penalty}</td>
                  <td><span className={`status-pill ${milestoneStatusClass(milestone)}`}>{milestoneStatusLabels[milestone.status]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel full">
        <PanelTitle
          title="计划视图"
          subtitle={result?.plan_finish_date ? `${result.plan_start_date} 至 ${result.plan_finish_date} · ${planSortLabel}` : "等待求解"}
          action={(
            <div className="schedule-view-actions">
              <div className="segmented plan-sort-switcher" aria-label="计划排序">
                {planListSortOptions.map((option) => (
                  <button
                    className={ganttMode === option.value ? "active" : ""}
                    key={option.value}
                    onClick={() => onGanttModeChange(option.value)}
                    type="button"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="segmented" aria-label="计划视图窗口">
                <button
                  className={activePlanWindowMode === "detail" ? "active" : ""}
                  onClick={() => setPlanWindowMode("detail")}
                  type="button"
                >
                  工作项详情
                </button>
                <button
                  className={activePlanWindowMode === "gantt" ? "active" : ""}
                  onClick={() => setPlanWindowMode("gantt")}
                  type="button"
                >
                  甘特图
                </button>
              </div>
            </div>
          )}
        />
        {activePlanWindowMode === "gantt" ? (
          <PlanTimelineView
            tasks={filteredPlanTasks}
            makespan={Math.max(result?.objective_days ?? 1, 1)}
            selectedTaskId={selectedPlanTask?.id ?? null}
            onSelectTask={setSelectedPlanTaskId}
            workSectionDisplayById={workSectionDisplayById}
            resourcePools={resourcePoolsForDisplay}
          />
        ) : (
          <div className="schedule-split-view">
            <PlanWorkList
              tasks={filteredPlanTasks}
              selectedTaskId={selectedPlanTask?.id ?? null}
              onSelectTask={setSelectedPlanTaskId}
            />
            <PlanTaskDetailTable
              tasks={filteredPlanTasks}
              selectedTaskId={selectedPlanTask?.id ?? null}
              onSelectTask={setSelectedPlanTaskId}
              scenario={scenario}
              predecessorDetails={predecessorDetails}
              openPredecessorTaskId={openPredecessorTaskId}
              predecessorAnchorRect={predecessorAnchorRect}
              showPredecessorPopover={showPredecessorPopover}
              schedulePredecessorPopoverClose={schedulePredecessorPopoverClose}
              keepPredecessorPopoverOpen={keepPredecessorPopoverOpen}
            />
          </div>
        )}
      </section>

      <section className="panel full">
        <PanelTitle title="资源泳道" subtitle="横轴按计划时间展示每条资源的占用连续性" />
        <ResourceLanes
          allocations={resourceAllocations}
          makespan={Math.max(result?.objective_days ?? 1, 1)}
          resourcePools={resourcePoolsForDisplay}
          selectedResourceId={selectedResourceId}
          onSelectResource={setSelectedResourceId}
        />
        <ResourceAllocationDetails
          allocations={selectedResourceAllocations}
          selectedResource={selectedResource}
          taskById={scheduledTaskById}
          workSectionDisplayById={workSectionDisplayById}
          resourcePools={resourcePoolsForDisplay}
        />
      </section>

      <section className="panel full">
        <PanelTitle title="资源路径图" subtitle="按施工先后展示资源经过的左/右幅-墩号序列" />
        <ResourcePathChart resourcePaths={continuityMetrics?.resource_paths ?? []} resourcePools={resourcePoolsForDisplay} />
      </section>

    </ScheduleResultsWorkspace>
  );
}

function PlanWorkList({
  tasks,
  selectedTaskId,
  onSelectTask,
}: {
  tasks: ScheduledTask[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
}) {
  return (
    <div className="plan-work-list">
      <div className="plan-work-list-header">工作项</div>
      <div className="plan-work-list-body">
        {tasks.length ? (
          tasks.map((task) => (
            <button
              className={`plan-work-list-row ${selectedTaskId === task.id ? "selected" : ""}`}
              key={task.id}
              onClick={() => onSelectTask(task.id)}
              title={task.name}
              type="button"
            >
              {task.name}
            </button>
          ))
        ) : (
          <div className="schedule-split-empty">暂无工作项</div>
        )}
      </div>
    </div>
  );
}

function PlanTimelineView({
  tasks,
  makespan,
  selectedTaskId,
  onSelectTask,
  workSectionDisplayById,
  resourcePools,
}: {
  tasks: ScheduledTask[];
  makespan: number;
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  workSectionDisplayById: Map<string, WorkSectionDisplay>;
  resourcePools: ResourcePool[];
}) {
  if (!tasks.length) return <div className="schedule-split-empty">暂无工作项</div>;
  const safeMakespan = Math.max(makespan, ...tasks.map((task) => task.end_offset), 1);
  return (
    <div className="plan-timeline-view">
      <div className="plan-timeline-header">
        <span>工作项</span>
        <span>计划时间</span>
      </div>
      <div className="plan-timeline-body">
        {tasks.map((task) => {
          const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
          const selected = selectedTaskId === task.id;
          return (
            <div className={`plan-timeline-row ${selected ? "selected" : ""}`} key={task.id}>
              <button
                className="plan-timeline-work"
                onClick={() => onSelectTask(task.id)}
                title={task.name}
                type="button"
              >
                {task.name}
              </button>
              <div className="plan-timeline-track">
                <div
                  className="plan-timeline-bar"
                  style={{
                    left: `${(task.start_offset / safeMakespan) * 100}%`,
                    width: `${Math.max(((task.end_offset - task.start_offset) / safeMakespan) * 100, 1.2)}%`,
                    backgroundColor: componentColors[task.component_type],
                  }}
                  title={ganttTaskHoverTitle(task, sideLabel, resourcePools)}
                >
                  <span>{task.duration_days}d</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PlanTaskDetailTable({
  tasks,
  selectedTaskId,
  onSelectTask,
  scenario,
  predecessorDetails,
  openPredecessorTaskId,
  predecessorAnchorRect,
  showPredecessorPopover,
  schedulePredecessorPopoverClose,
  keepPredecessorPopoverOpen,
}: {
  tasks: ScheduledTask[];
  selectedTaskId: string | null;
  onSelectTask: (taskId: string) => void;
  scenario: ScenarioInput | null;
  predecessorDetails: (task: ScheduledTask) => PredecessorDetail[];
  openPredecessorTaskId: string | null;
  predecessorAnchorRect: DOMRect | null;
  showPredecessorPopover: (taskId: string, anchor: HTMLElement) => void;
  schedulePredecessorPopoverClose: () => void;
  keepPredecessorPopoverOpen: () => void;
}) {
  if (!tasks.length) {
    return (
      <div className="schedule-detail-pane">
        <div className="schedule-split-empty">暂无工作项详情</div>
      </div>
    );
  }

  return (
    <div className="schedule-detail-pane">
      <div className="plan-detail-table-wrap">
        <table className="plan-detail-table">
          <colgroup>
            <col className="plan-detail-component-col" />
            <col className="plan-detail-expression-col" />
            <col className="plan-detail-duration-col" />
            <col className="plan-detail-date-col" />
            <col className="plan-detail-date-col" />
            <col className="plan-detail-resource-col" />
            <col className="plan-detail-predecessor-col" />
          </colgroup>
          <thead>
            <tr>
              <th>构件</th>
              <th>计划表达式</th>
              <th>工期</th>
              <th>计划开始</th>
              <th>计划完成</th>
              <th>资源</th>
              <th>前置工作</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((task) => {
              const details = predecessorDetails(task);
              const isOpen = openPredecessorTaskId === task.id;
              const selected = selectedTaskId === task.id;
              const resourceDisplay = taskResourceDisplay(task);
              return (
                <tr
                  className={selected ? "selected" : ""}
                  key={task.id}
                  onClick={() => onSelectTask(task.id)}
                >
                  <td title={componentLabels[task.component_type]}>{componentLabels[task.component_type]}</td>
                  <td className="duration-expression" title={durationExpression(task, scenario)}>
                    {durationExpression(task, scenario)}
                  </td>
                  <td>{effectiveTaskDurationDays(task, scenario)} 天</td>
                  <td>{task.start_date}</td>
                  <td>{task.finish_date}</td>
                  <td title={resourceDisplay}>{resourceDisplay}</td>
                  <td className="predecessor-cell">
                    {details.length > 0 ? (
                      <button
                        className="predecessor-count has-items"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectTask(task.id);
                          showPredecessorPopover(task.id, event.currentTarget);
                        }}
                        onMouseEnter={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                        onMouseLeave={schedulePredecessorPopoverClose}
                        onPointerEnter={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                        onPointerLeave={schedulePredecessorPopoverClose}
                        onFocus={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                        onBlur={schedulePredecessorPopoverClose}
                      >
                        {details.length}
                      </button>
                    ) : (
                      <span className="predecessor-zero">0</span>
                    )}
                    {isOpen && (
                      <PredecessorPopover
                        task={task}
                        details={details}
                        anchorRect={predecessorAnchorRect}
                        onMouseEnter={keepPredecessorPopoverOpen}
                        onMouseLeave={schedulePredecessorPopoverClose}
                      />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResourceLanes({
  allocations,
  makespan,
  resourcePools,
  selectedResourceId,
  onSelectResource,
}: {
  allocations: ResourceAllocation[];
  makespan: number;
  resourcePools: ResourcePool[];
  selectedResourceId: string | null;
  onSelectResource: (resourceId: string) => void;
}) {
  if (!allocations.length) return <div className="empty">暂无资源分配</div>;
  const groups = groupBy(allocations, (item) => item.resource_id);
  return (
    <div className="lanes">
      {Object.entries(groups).map(([, rawItems]) => {
        const items = sortResourceAllocationsByPlan(rawItems);
        const resourceId = items[0].resource_id;
        const selected = selectedResourceId === resourceId;
        return (
          <div
            aria-pressed={selected}
            className={`lane-row ${selected ? "selected" : ""}`}
            key={resourceId}
            onClick={() => onSelectResource(resourceId)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelectResource(resourceId);
              }
            }}
            role="button"
            tabIndex={0}
          >
            <div className="lane-label">
              <strong>{items[0].resource_name}</strong>
              <code>{resourceTypeLabel(items[0].resource_type, resourcePools)}</code>
            </div>
            <div className="lane-track">
              {items.map((allocation) => (
                <div
                  className="lane-bar"
                  key={allocation.task_id}
                  style={{
                    left: `${(allocation.start_offset / makespan) * 100}%`,
                    width: `${Math.max(((allocation.end_offset - allocation.start_offset) / makespan) * 100, 1.2)}%`,
                  }}
                  title={allocationHoverTitle(allocation, resourcePools)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ResourceAllocationDetails({
  allocations,
  selectedResource,
  taskById,
  workSectionDisplayById,
  resourcePools,
}: {
  allocations: ResourceAllocation[];
  selectedResource: ResourceAllocation | null;
  taskById: Map<string, ScheduledTask>;
  workSectionDisplayById: Map<string, WorkSectionDisplay>;
  resourcePools: ResourcePool[];
}) {
  if (!selectedResource) {
    return (
      <div className="resource-task-detail">
        <div className="empty">未选择资源</div>
      </div>
    );
  }
  const totalActiveDays = allocations.reduce((total, allocation) => total + resourceAllocationDurationDays(allocation), 0);
  return (
    <div className="resource-task-detail">
      <div className="resource-task-detail-header">
        <div>
          <strong>{selectedResource.resource_name}</strong>
          <span>{resourceTypeLabel(selectedResource.resource_type, resourcePools)}</span>
        </div>
        <div className="resource-task-stats">
          <span>{allocations.length} 项</span>
          <span>{totalActiveDays} 天</span>
        </div>
      </div>
      <div className="table-wrap short resource-task-table">
        <table>
          <thead>
            <tr>
              <th>序号</th>
              <th>工作项</th>
              <th>幅别</th>
              <th>构件</th>
              <th>工艺</th>
              <th>计划开始</th>
              <th>计划完成</th>
              <th>工期</th>
            </tr>
          </thead>
          <tbody>
            {allocations.map((allocation, index) => {
              const task = taskById.get(allocation.task_id);
              return (
                <tr key={allocation.task_id}>
                  <td>{index + 1}</td>
                  <td>
                    <strong>{allocation.task_name}</strong>
                    <span className="muted-cell">{allocation.task_id}</span>
                  </td>
                  <td><span className="side-tag">{task ? workSectionLabelForTask(task, workSectionDisplayById) : "-"}</span></td>
                  <td>{task ? componentLabels[task.component_type] : "-"}</td>
                  <td>{task?.process_name ?? "-"}</td>
                  <td>{allocation.start_date}</td>
                  <td>{allocation.finish_date}</td>
                  <td>{resourceAllocationDurationDays(allocation)} 天</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResourcePathChart({
  resourcePaths,
  resourcePools,
}: {
  resourcePaths: ResourcePath[];
  resourcePools: ResourcePool[];
}) {
  const visiblePaths = resourcePaths.filter((path) => path.path.length > 0);
  if (!visiblePaths.length) return <div className="empty">暂无资源路径</div>;
  return (
    <div className="resource-path-chart">
      {visiblePaths.map((path) => {
        const labels = compactPathLabels(path.path.map((step) => shortLocationLabel(step.location)));
        return (
          <div className="resource-path-row" key={path.resource_id}>
            <div className="resource-path-label">
              <strong>{path.resource_name}</strong>
            </div>
            <div className="resource-path-sequence" title={resourcePathHoverTitle(path, labels, resourcePools)}>
              {labels.map((label, index) => (
                <span className="resource-path-step" key={`${path.resource_id}-${label}-${index}`}>
                  {label}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ganttTaskHoverTitle(task: ScheduledTask, sideLabel = "-", resourcePools: ResourcePool[] = []): string {
  const resourceType = task.assigned_resource_type
    ?? (task.continuous_span_resource_id ? "cast_in_place_continuous_beam_team" : null);
  return [
    `工作项：${task.name}`,
    `幅别：${sideLabel}`,
    `构件：${componentLabels[task.component_type]}`,
    `计划：${task.start_date} 至 ${task.finish_date}`,
    `工期：${task.duration_days} 天`,
    `分配资源：${taskResourceDisplay(task)}`,
    `资源序列：${task.assigned_resource_id ?? task.continuous_span_resource_id ?? "-"}`,
    `资源类型：${resourceType ? resourceTypeLabel(resourceType, resourcePools) : "-"}`,
  ].join("\n");
}

function taskResourceDisplay(task: ScheduledTask): string {
  if (task.assigned_resource_name) return task.assigned_resource_name;
  if (task.continuous_span_resource_name) return `${task.continuous_span_resource_name}（联级）`;
  return "-";
}

function allocationHoverTitle(allocation: ResourceAllocation, resourcePools: ResourcePool[] = []): string {
  return [
    `工作项：${allocation.task_name}`,
    `计划：${allocation.start_date} 至 ${allocation.finish_date}`,
    `分配资源：${allocation.resource_name}`,
    `资源序列：${allocation.resource_id}`,
    `资源类型：${resourceTypeLabel(allocation.resource_type, resourcePools)}`,
  ].join("\n");
}

function sortResourceAllocationsByPlan(allocations: ResourceAllocation[]): ResourceAllocation[] {
  return [...allocations].sort((a, b) => (
    a.start_offset - b.start_offset
    || a.end_offset - b.end_offset
    || a.task_name.localeCompare(b.task_name)
    || a.task_id.localeCompare(b.task_id)
  ));
}

function resourceAllocationDurationDays(allocation: ResourceAllocation): number {
  return Math.max(allocation.end_offset - allocation.start_offset, 0);
}

function resourcePathHoverTitle(path: ResourcePath, labels: string[], resourcePools: ResourcePool[] = []): string {
  return [
    `资源：${path.resource_name}`,
    `资源类型：${resourceTypeLabel(path.resource_type, resourcePools)}`,
    `施工路径：${labels.join("-")}`,
    `任务数：${path.task_count}`,
  ].join("\n");
}

function compactPathLabels(labels: string[]): string[] {
  const compacted: string[] = [];
  for (const label of labels) {
    if (!label || compacted[compacted.length - 1] === label) continue;
    compacted.push(label);
  }
  return compacted;
}

function shortLocationLabel(location: string): string {
  const sidePrefix = location.includes("左幅") ? "左" : location.includes("右幅") ? "右" : "";
  const numberMatch = location.match(/(\d+)\s*号[墩台]?/);
  if (sidePrefix && numberMatch) return `${sidePrefix}${numberMatch[1]}`;
  if (numberMatch) return numberMatch[1];
  return location.replace(/幅/g, "").replace(/号墩/g, "").replace(/号台/g, "").replace(/\s+/g, "");
}

type WorkSectionDisplay = {
  label: string;
  shortLabel: string;
};

function buildWorkSectionDisplayById(
  project: ProjectModel | null,
  projectMasterMaps?: TaskViewProjectMasterMaps,
): Map<string, WorkSectionDisplay> {
  const result = new Map<string, WorkSectionDisplay>();
  if (project) {
    for (const bridge of project.bridges) {
      for (const section of bridge.work_sections) {
        const label = sideLabels[section.side];
        const shortLabel = section.side === "left" ? "左" : section.side === "right" ? "右" : label;
        result.set(section.id, { label, shortLabel });
      }
    }
  }
  if (projectMasterMaps) {
    for (const [sectionId, section] of projectMasterMaps.sections) {
      const shortLabel = section.sideLabel === "左幅" ? "左" : section.sideLabel === "右幅" ? "右" : section.sideLabel;
      result.set(sectionId, { label: section.sideLabel, shortLabel });
    }
  }
  return result;
}

function workSectionLabelForTask(task: Task, workSectionDisplayById: Map<string, WorkSectionDisplay>): string {
  if (!task.work_section_id) return "名称不可用";
  return workSectionDisplayById.get(task.work_section_id)?.label ?? "名称不可用";
}

function buildPredecessorLinksBySuccessor(generated: GeneratedScheduleInput | null): Map<string, PrecedenceLink[]> {
  const links = new Map<string, PrecedenceLink[]>();
  for (const link of generated?.schedule_input.precedence_links ?? []) {
    const current = links.get(link.successor_id) ?? [];
    current.push(link);
    links.set(link.successor_id, current);
  }
  return links;
}

function buildTaskViewRows(
  generated: GeneratedScheduleInput | null,
  scenario: ScenarioInput | null,
  linksBySuccessor: Map<string, PrecedenceLink[]>,
  workSectionDisplayById: Map<string, WorkSectionDisplay>,
  projectMasterMaps: TaskViewProjectMasterMaps,
  useProjectMasterAuthority: boolean,
): TaskViewRow[] {
  if (!generated) return [];
  const projectMaps = buildTaskViewProjectMaps(
    useProjectMasterAuthority ? null : scenario?.project ?? null,
    projectMasterMaps,
  );
  const rows = generated.schedule_input.tasks.map((task) => {
    const bridge = task.bridge_id ? projectMaps.bridges.get(task.bridge_id) : undefined;
    const section = task.work_section_id ? projectMaps.sections.get(task.work_section_id) : undefined;
    const structure = projectMaps.structures.get(task.structure_id);
    const bridgeName = bridge?.name ?? "名称不可用";
    const sectionName = section?.name ?? "名称不可用";
    const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
    const structureLabel = structure?.label ?? task.structure_name;
    const continuousParent = continuousTaskParentDisplay(task, projectMaps.continuousBeamGroups);
    const componentLabel = componentLabels[task.component_type];
    const searchText = [
      bridgeName,
      sectionName,
      sideLabel,
      structureLabel,
      continuousParent?.label,
      task.structure_name,
      task.name,
      componentLabel,
      task.process_name,
    ].join(" ").toLowerCase();

    return {
      task,
      bridgeName,
      bridgeOrder: bridge?.order ?? Number.MAX_SAFE_INTEGER,
      sectionName,
      sectionOrder: section?.order ?? Number.MAX_SAFE_INTEGER,
      sideLabel,
      structureLabel,
      parentStructureId: continuousParent?.id ?? task.structure_id,
      parentStructureLabel: continuousParent?.label ?? structureLabel,
      predecessorLinks: linksBySuccessor.get(task.id) ?? [],
      searchText,
    };
  });
  return sortTaskViewRows(rows);
}

function buildTaskViewProjectMaps(
  project: ProjectModel | null,
  projectMasterMaps: TaskViewProjectMasterMaps,
) {
  const bridges = new Map<string, { name: string; order: number }>();
  const sections = new Map<string, { name: string; order: number }>();
  const structures = new Map<string, { label: string; order: number }>();
  const continuousBeamGroups = new Map<string, { id: string; label: string }>();

  if (project) {
    for (const bridge of project.bridges) {
      bridges.set(bridge.id, { name: bridge.name, order: bridge.order });
      for (const section of bridge.work_sections) {
        sections.set(section.id, { name: section.name, order: section.order });
        for (const uppers of groupUpperStructures(section.upper_structures ?? [], isContinuousBeamUpper)) {
          const groupIndex = upperGroupIndex(uppers[0]);
          continuousBeamGroups.set(
            continuousTaskParentKey(bridge.id, section.id, groupIndex),
            {
              id: continuousTaskParentId(bridge.id, section.id, groupIndex),
              label: continuousBeamGroupLabel(section, uppers),
            },
          );
        }
        for (const structure of section.structures) {
          structures.set(structure.id, {
            label: structure.support_no ?? structure.name,
            order: structure.order,
          });
        }
      }
    }
  }
  for (const [bridgeId, bridge] of projectMasterMaps.bridges) bridges.set(bridgeId, bridge);
  for (const [sectionId, section] of projectMasterMaps.sections) sections.set(sectionId, section);
  return { bridges, sections, structures, continuousBeamGroups };
}

function continuousTaskParentDisplay(
  task: Task,
  continuousBeamGroups: Map<string, { id: string; label: string }>,
): { id: string; label: string } | null {
  if (task.component_type !== "cast_in_place_continuous_beam") return null;
  if (!task.bridge_id || !task.work_section_id) return null;
  const groupIndex = continuousTaskGroupIndex(task.structure_id);
  if (groupIndex === null) return null;
  return continuousBeamGroups.get(continuousTaskParentKey(task.bridge_id, task.work_section_id, groupIndex))
    ?? {
      id: continuousTaskParentId(task.bridge_id, task.work_section_id, groupIndex),
      label: fallbackContinuousTaskParentLabel(task),
    };
}

function continuousTaskParentKey(bridgeId: string, sectionId: string, groupIndex: number): string {
  return `${bridgeId}:${sectionId}:${groupIndex}`;
}

function continuousTaskParentId(bridgeId: string, sectionId: string, groupIndex: number): string {
  return `${bridgeId}:${sectionId}:continuous-beam:${groupIndex}`;
}

function continuousTaskGroupIndex(structureId: string): number | null {
  const match = structureId.match(/-CB-G(\d+)/);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function continuousBeamGroupLabel(section: WorkSection, uppers: UpperStructureModel[]): string {
  const sideLabel = section.side && section.side !== "none" ? sideLabels[section.side] : "";
  const supports = uppers.flatMap((upper) => supportIndicesFromText(upper.support_range));
  const minSupport = supports.length ? Math.min(...supports) : Math.max(0, Math.min(...uppers.map((upper) => upper.span_index)) - 1);
  const maxSupport = supports.length ? Math.max(...supports) : Math.max(...uppers.map((upper) => upper.span_index));
  if (Number.isFinite(minSupport) && Number.isFinite(maxSupport)) {
    return `${sideLabel}${minSupport}#-${maxSupport}#墩现浇连续梁`;
  }
  return `${sideLabel}现浇连续梁`;
}

function supportIndicesFromText(value: string): number[] {
  return Array.from(value.matchAll(/(\d+)\s*(?:#|号)?\s*(?:墩|台)?/g))
    .map((match) => Number(match[1]))
    .filter((item) => Number.isFinite(item));
}

function fallbackContinuousTaskParentLabel(task: Task): string {
  const match = task.structure_id.match(/-CB-G(\d+)/);
  const groupSuffix = match ? `第${Number(match[1])}联` : "";
  const sidePrefix = task.structure_name.includes("左幅") ? "左幅" : task.structure_name.includes("右幅") ? "右幅" : "";
  return `${sidePrefix}${groupSuffix}现浇连续梁`;
}

function sortTaskViewRows(rows: TaskViewRow[]): TaskViewRow[] {
  return [...rows].sort((left, right) => (
    left.bridgeOrder - right.bridgeOrder
    || left.sectionOrder - right.sectionOrder
    || left.task.sequence_order - right.task.sequence_order
    || compareStructureIds(left.task.structure_id, right.task.structure_id)
    || componentSortIndex(left.task.component_type) - componentSortIndex(right.task.component_type)
    || left.task.name.localeCompare(right.task.name)
  ));
}

function buildTaskViewStructureParents(rows: TaskViewRow[], scenario: ScenarioInput | null): TaskViewParentGroup[] {
  const parents = new Map<string, TaskViewParentGroup>();
  for (const row of rows) {
    const id = `${row.task.bridge_id ?? "-"}:${row.task.work_section_id ?? "-"}`;
    if (!parents.has(id)) {
      parents.set(id, {
        id,
        title: `${row.bridgeName} / ${row.sectionName}`,
        subtitle: "",
        rows: [],
        groups: [],
      });
    }
    parents.get(id)!.rows.push(row);
  }
  return Array.from(parents.values()).map((parent) => {
    const groups = buildTaskViewGroups(parent.rows, "by_structure");
    return {
      ...parent,
      groups,
      subtitle: `${groups.length} 个结构物 · ${parent.rows.length} 项 · 工期合计 ${taskViewDurationTotal(parent.rows, scenario)} 天`,
    };
  });
}

function buildTaskViewGroups(rows: TaskViewRow[], mode: TaskViewMode): TaskViewGroup[] {
  const groups = new Map<string, TaskViewGroup>();
  for (const row of rows) {
    const id = mode === "by_process"
      ? `${row.task.component_type}:${row.task.process_name}`
      : `${row.task.bridge_id ?? "-"}:${row.task.work_section_id ?? "-"}:${row.parentStructureId}`;
    const title = mode === "by_process"
      ? `${componentLabels[row.task.component_type]} / ${row.task.process_name}`
      : taskViewStructureTitle(row);
    if (!groups.has(id)) {
      groups.set(id, { id, title, subtitle: "", rows: [] });
    }
    groups.get(id)!.rows.push(row);
  }
  return Array.from(groups.values()).map((group) => ({
    ...group,
    subtitle: taskViewGroupSubtitle(group.rows, mode),
  }));
}

function taskViewStructureTitle(row: TaskViewRow): string {
  if (row.sideLabel === "-" || row.parentStructureLabel.includes(row.sideLabel)) return row.parentStructureLabel;
  return `${row.sideLabel} ${row.parentStructureLabel}`;
}

function taskViewGroupSubtitle(rows: TaskViewRow[], mode: TaskViewMode, scenario: ScenarioInput | null = null): string {
  if (!rows.length) return "-";
  const first = rows[0];
  const structureCount = new Set(rows.map((row) => `${row.task.work_section_id ?? "-"}:${row.task.structure_id}`)).size;
  const base = mode === "by_process"
    ? `${structureCount} 个结构物`
    : `${first.bridgeName} / ${first.sectionName}`;
  return `${base} · ${rows.length} 项 · 工期合计 ${taskViewDurationTotal(rows, scenario)} 天`;
}

function taskViewDurationTotal(rows: TaskViewRow[], scenario: ScenarioInput | null = null): number {
  return rows.reduce((total, row) => total + effectiveTaskDurationDays(row.task, scenario), 0);
}

function taskViewDurationRange(rows: TaskViewRow[], scenario: ScenarioInput | null = null): string {
  if (!rows.length) return "-";
  const durations = rows.map((row) => effectiveTaskDurationDays(row.task, scenario));
  const min = Math.min(...durations);
  const max = Math.max(...durations);
  return min === max ? `${min} 天` : `${min}-${max} 天`;
}

function processOptionsForComponent(component: ComponentModel, processLibrary: ProcessTemplate[]): ProcessTemplate[] {
  return processLibrary.filter((process) => process.component_type === component.component_type);
}

function editableComponentForTask(task: Task, scenario: ScenarioInput): ComponentModel {
  const source = task.component_id ? findComponent(scenario.project, task.component_id) : null;
  if (source) return source.component;

  const override = scenario.task_overrides?.[task.id] ?? {};
  const [processId, optionId] = task.productivity_rule_id.split(":");
  const process = scenario.process_library.find((item) => item.id === override.method_id || item.method_id === override.method_id)
    ?? scenario.process_library.find((item) => item.id === processId)
    ?? scenario.process_library.find((item) => item.component_type === task.component_type && item.process_name === task.process_name);

  return {
    id: task.id,
    name: task.name,
    component_type: task.component_type,
    quantity: task.quantity,
    quantity_label: task.quantity_label,
    structure_parameter_label: task.structure_parameter_label ?? null,
    method_id: override.method_id ?? process?.method_id ?? process?.id ?? processId ?? null,
    productivity_option_id: override.productivity_option_id ?? optionId ?? null,
    enabled: true,
    properties: task.properties ?? {},
  };
}

function selectedProcessForComponent(component: ComponentModel, processLibrary: ProcessTemplate[]): ProcessTemplate | null {
  const options = processOptionsForComponent(component, processLibrary);
  if (component.method_id) {
    return options.find((process) => process.id === component.method_id || process.method_id === component.method_id) ?? null;
  }
  return options.find((process) => process.is_default) ?? options[0] ?? null;
}

function processProductivityOptions(process: ProcessTemplate): ProductivityOption[] {
  if (process.productivity_options?.length) {
    return process.productivity_options;
  }
  return [
    {
      id: `${process.id}-default`,
      name: "默认工效",
      duration_method: process.duration_method,
      quantity_source: process.quantity_source,
      productivity_value: process.productivity_value,
      productivity_unit: process.productivity_unit,
      standard_section_height_m: defaultStandardSectionHeightForUnit(process.productivity_unit),
      is_default: true,
    },
  ];
}

function defaultProductivityOption(process: ProcessTemplate): ProductivityOption | null {
  const options = processProductivityOptions(process);
  return options.find((option) => option.is_default) ?? options[0] ?? null;
}

function selectedProductivityOption(component: ComponentModel, process: ProcessTemplate): ProductivityOption | null {
  const options = processProductivityOptions(process);
  if (component.productivity_option_id) {
    const selected = options.find((option) => option.id === component.productivity_option_id);
    if (selected) return selected;
  }
  return options.find((option) => option.is_default) ?? options[0] ?? null;
}

type LocalProductivityRule = ProductivityOption & {
  component_type: ComponentType;
  process_name: string;
  resource_type: string;
};

function patchGeneratedScheduleInputForTask(
  generated: GeneratedScheduleInput | null,
  taskId: string,
  scenario: ScenarioInput,
): GeneratedScheduleInput | null {
  if (!generated) return null;
  let patched = false;
  const tasks = generated.schedule_input.tasks.map((task) => {
    if (task.id !== taskId) return task;
    const nextTask = taskWithScenarioProcessPatch(task, scenario);
    patched = nextTask !== task;
    return nextTask;
  });
  if (!patched) return generated;
  return {
    ...generated,
    schedule_input: {
      ...generated.schedule_input,
      tasks,
    },
  };
}

function taskWithScenarioProcessPatch(task: Task, scenario: ScenarioInput): Task {
  const component = editableComponentForTask(task, scenario);
  const process = selectedProcessForComponent(component, scenario.process_library);
  if (!process) return task;
  const option = selectedProductivityOption(component, process);
  const rule = localProductivityRuleFor(process, component, option);
  const quantity = localQuantityForTask(component, task, rule.quantity_source);
  const patchedTask = {
    ...task,
    process_name: rule.process_name,
    productivity_rule_id: rule.id,
    quantity: quantity.value,
    quantity_label: quantity.label,
    structure_parameter_label: structureParameterLabelForTask(task, component),
    duration_days: calculateLocalDurationDays(quantity.value, rule),
    compatible_resource_types: [rule.resource_type],
  };
  return applyRequiredResourceTypesToTasks([patchedTask], scenario.resource_pools)[0] ?? patchedTask;
}

function localProductivityRuleFor(
  process: ProcessTemplate,
  component: ComponentModel,
  option: ProductivityOption | null,
): LocalProductivityRule {
  const rule: LocalProductivityRule = option
    ? {
        ...option,
        id: `${process.id}:${option.id}`,
        component_type: process.component_type,
        process_name: process.process_name,
        resource_type: process.resource_type,
      }
    : {
        id: process.id,
        name: process.process_name,
        duration_method: process.duration_method,
        quantity_source: process.quantity_source,
        productivity_value: process.productivity_value,
        productivity_unit: process.productivity_unit,
        standard_section_height_m: defaultStandardSectionHeightForUnit(process.productivity_unit),
        is_default: process.is_default,
        component_type: process.component_type,
        process_name: process.process_name,
        resource_type: process.resource_type,
      };

  if (isContinuousStandardSegmentComponent(component, process)) {
    return {
      ...rule,
      duration_method: "days_per_unit",
      quantity_source: "count",
    };
  }
  return rule;
}

function isContinuousStandardSegmentComponent(component: ComponentModel, process: ProcessTemplate): boolean {
  return component.component_type === "cast_in_place_continuous_beam"
    && (component.method_id === "standard_segment" || process.id.startsWith("cast_in_place_continuous_standard_segment"));
}

function localQuantityForTask(
  component: ComponentModel,
  task: Task,
  quantitySource: string,
): { value: number; label: string } {
  const value = localQuantityValueForTask(component, task, quantitySource);
  if (quantitySource === "count") return { value, label: `${displayValue(value)}${countUnitForTask(component, task)}` };
  return {
    value,
    label: `${displayValue(value)}${quantityUnitForSource(quantitySource)}`,
  };
}

function localQuantityValueForTask(component: ComponentModel, task: Task, quantitySource: string): number {
  if (quantitySource === "count") {
    if (isContinuousStandardSegmentQuantity(component, task)) {
      return positiveNumber(component.quantity, task.quantity, 1);
    }
    if (component.component_type === "pile") return 1;
    return positiveNumber(component.quantity, task.quantity, 1);
  }
  if (quantitySource === "pile_length_m") {
    return positiveNumber(
      componentPropertyNumber(component, ["lengthM", "length_m", "pileLengthM", "pile_length_m", "totalLengthM", "total_length_m"]),
      component.quantity,
      task.quantity,
      1,
    );
  }
  if (quantitySource === "pier_height_m") {
    return pierAverageHeightForComponent(component, task);
  }
  if (quantitySource === "deck_length_m") {
    return positiveNumber(
      componentPropertyNumber(component, ["lengthM", "length_m", "totalLengthM", "total_length_m", "deckLengthM", "deck_length_m"]),
      component.quantity,
      task.quantity,
      1,
    );
  }
  return positiveNumber(component.quantity, task.quantity, 1);
}

function isContinuousStandardSegmentQuantity(component: ComponentModel, task: Task): boolean {
  return component.component_type === "cast_in_place_continuous_beam"
    && (component.method_id === "standard_segment" || isContinuousBeamStandardSegmentTask(task));
}

function componentPropertyNumber(component: ComponentModel, keys: string[]): number | null {
  for (const key of keys) {
    const direct = numberFromUnknown(component.properties[key]);
    if (direct !== null) return direct;
  }
  const dimensions = component.properties.dimensions_m;
  if (isRecord(dimensions)) {
    for (const key of keys) {
      const dimension = numberFromUnknown(dimensions[key]);
      if (dimension !== null) return dimension;
    }
  }
  return null;
}

function numberFromUnknown(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function positiveNumber(...values: Array<number | null | undefined>): number {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
  }
  return 1;
}

function calculateLocalDurationDays(quantity: number, rule: LocalProductivityRule): number {
  const productivity = positiveNumber(rule.productivity_value, 1);
  if (rule.component_type === "pier_body" && rule.quantity_source === "pier_height_m" && isSectionBasedPierProductivity(rule)) {
    const sectionHeight = sectionHeightForOption(rule);
    if (sectionHeight) {
      const sectionCount = Math.max(1, Math.ceil(quantity / sectionHeight));
      return Math.max(1, Math.ceil(sectionCount * productivity));
    }
  }
  if (rule.duration_method === "units_per_day") {
    return Math.max(1, Math.ceil(quantity / productivity));
  }
  if (rule.duration_method === "days_per_unit") {
    return Math.max(1, Math.ceil(quantity * productivity));
  }
  return Math.max(1, Math.ceil(productivity));
}

function productivityOptionLabel(option: ProductivityOption): string {
  const groupName = option.name.trim() === "默认工效" ? "默认" : option.name.trim() || "工效";
  const base = `${groupName}-${displayValue(option.productivity_value)}${option.productivity_unit}`;
  if (isSectionBasedPierProductivity(option)) {
    return `${base}（${displayValue(sectionHeightForOption(option))}m/节）`;
  }
  return base;
}

function productivityOptionForTask(task: Task, scenario: ScenarioInput | null): ProductivityOption | null {
  if (!scenario) return null;
  const [processId, optionId] = task.productivity_rule_id.split(":");
  const process = scenario.process_library.find((item) => item.id === processId)
    ?? scenario.process_library.find((item) => item.component_type === task.component_type && item.process_name === task.process_name);
  if (!process) return null;
  const options = processProductivityOptions(process);
  return options.find((option) => option.id === optionId)
    ?? options.find((option) => option.is_default)
    ?? options[0]
    ?? null;
}

function durationExpression(task: Task, scenario: ScenarioInput | null): string {
  const option = productivityOptionForTask(task, scenario);
  if (!option) {
    return `${displayValue(task.quantity)} -> ${task.duration_days}天`;
  }

  const isContinuousStandardSegment = isContinuousBeamStandardSegmentTask(task);
  const effectiveOption = isContinuousStandardSegment
    ? { ...option, duration_method: "days_per_unit", quantity_source: "count" }
    : option;
  const quantityName = quantitySourceLabels[effectiveOption.quantity_source] ?? "工程量";
  const quantityText = `${quantityName}${task.quantity_label || `${displayValue(task.quantity)}${quantityUnitForSource(effectiveOption.quantity_source)}`}`;
  const resultText = `${effectiveTaskDurationDays(task, scenario)}天`;

  if (isSectionBasedPierProductivity(effectiveOption)) {
    const sectionHeight = sectionHeightForOption(effectiveOption);
    if (sectionHeight) {
      const sectionCount = Math.max(1, Math.ceil(task.quantity / sectionHeight));
      return `${quantityText} / ${displayValue(sectionHeight)}m/节 = ${sectionCount}节；${sectionCount} × ${displayValue(effectiveOption.productivity_value)}天/节 = ${resultText}`;
    }
  }

  if (effectiveOption.duration_method === "units_per_day") {
    return `${quantityText} / ${displayValue(effectiveOption.productivity_value)}${effectiveOption.productivity_unit} = ${resultText}`;
  }

  if (effectiveOption.duration_method === "days_per_unit") {
    return `${quantityText} × ${displayValue(effectiveOption.productivity_value)}${effectiveOption.productivity_unit} = ${resultText}`;
  }

  return `${displayValue(effectiveOption.productivity_value)}${effectiveOption.productivity_unit} = ${resultText}`;
}

function quantityUnitForSource(quantitySource: string): string {
  if (quantitySource.endsWith("_m")) return "m";
  return "";
}

function effectiveTaskDurationDays(task: Task, scenario: ScenarioInput | null): number {
  const option = productivityOptionForTask(task, scenario);
  if (option && isContinuousBeamStandardSegmentTask(task)) {
    return Math.max(1, Math.ceil(task.quantity * option.productivity_value));
  }
  return task.duration_days;
}

function isContinuousBeamStandardSegmentTask(task: Task): boolean {
  return task.component_type === "cast_in_place_continuous_beam"
    && task.productivity_rule_id.startsWith("cast_in_place_continuous_standard_segment:");
}

const bridgeCompletionMilestoneName = "下部及现浇结构施工完成";
const legacyBridgeMilestoneNames = new Set([
  "合同下部结构及上部现浇梁完工",
  "下部结构及上部现浇梁强控节点",
]);

function resourceAssistantDetailScenario(
  scenario: ScenarioInput | null,
  plan: ResourceAssistantPlan,
): ScenarioInput | null {
  if (!scenario) return null;
  return {
    ...scenario,
    scenario_id: plan.scenario_id,
    scenario_name: plan.scenario_name,
    resource_pools: plan.resource_pools,
  };
}

function countUnitForTask(component: ComponentModel, task: Task): string {
  if (component.component_type === "pile") return "根";
  if (component.component_type === "cast_in_place_box_beam") return "联";
  if (component.component_type === "cast_in_place_continuous_beam") {
    const taskType = component.properties.continuous_task_type ?? task.properties?.continuous_task_type;
    return taskType === "zero_block" || taskType === "standard_segment_batch" ? "块" : "段";
  }
  return "个";
}

function pierAverageHeightForComponent(component: ComponentModel, task: Task): number {
  const columnHeights = component.properties.column_heights_m;
  if (Array.isArray(columnHeights)) {
    const validHeights = columnHeights
      .map(numberFromUnknown)
      .filter((value): value is number => value !== null && value > 0);
    if (validHeights.length) {
      return validHeights.reduce((total, value) => total + value, 0) / validHeights.length;
    }
  }
  const structuredHeight = componentPropertyNumber(component, ["heightM", "height_m", "pierHeightM", "pier_height_m"]);
  if (structuredHeight !== null && structuredHeight > 0) return structuredHeight;
  const count = componentPropertyNumber(component, ["count"]);
  if (count === null || count <= 1) return positiveNumber(component.quantity, task.quantity, 1);
  return positiveNumber(task.quantity, 1);
}

function structureParameterLabelForTask(task: Task, component: ComponentModel): string | null {
  if (task.structure_parameter_label) return task.structure_parameter_label;
  if (component.structure_parameter_label) return component.structure_parameter_label;

  const properties = Object.keys(component.properties).length ? component.properties : (task.properties ?? {});
  const form = typeof properties.form === "string" ? properties.form.trim() : "";
  const dimensions = properties.dimensions_m;
  const count = numberFromUnknown(properties.count);

  if (component.component_type === "pile") {
    const diameter = componentPropertyNumber(component, ["diameterM", "diameter_m"])
      ?? (isRecord(dimensions) ? numberFromUnknown(dimensions.diameterM) : null);
    return [form || "桩基础", diameter && diameter > 0 ? `桩径${displayValue(diameter)}m` : ""].filter(Boolean).join("，");
  }
  if (component.component_type === "pier_body") {
    const parts = [form || "墩柱"];
    if (Array.isArray(dimensions)) {
      const values = dimensions.map(numberFromUnknown).filter((value): value is number => value !== null && value > 0);
      if (values.length === 1) parts.push(`柱径${displayValue(values[0])}m`);
      else if (values.length > 1) parts.push(`截面${values.map((value) => `${displayValue(value)}m`).join(" × ")}`);
    }
    if (count !== null && count > 0) parts.push(`${displayValue(count)}根`);
    return parts.join("，");
  }
  if (Array.isArray(dimensions)) {
    const values = dimensions.map(numberFromUnknown).filter((value): value is number => value !== null && value > 0);
    if (values.length) return values.map((value) => `${displayValue(value)}m`).join(" × ");
  }
  return form || null;
}

function resourceAssistantDetailSolveResult(
  plan: ResourceAssistantPlan,
  planResult: ResourceAssistantPlanResult,
): ScenarioSolveResult | null {
  if (plan.scenario_id !== planResult.scenario_id || !planResult.generated || !planResult.result) return null;
  return {
    scenario_id: plan.scenario_id,
    scenario_name: plan.scenario_name,
    generated: planResult.generated,
    result: planResult.result,
    milestone_results: planResult.result.milestone_results,
    diagnostics: planResult.diagnostics,
    metrics: { ...planResult.metrics },
    alternative_results: [],
  };
}

function normalizeScenarioForWorkspace(scenario: ScenarioInput): ScenarioInput {
  return normalizeScenarioResourcePools({
    ...scenario,
    milestones: bridgeCompletionMilestonesForProject(scenario),
  });
}

function localScenarioConfigFromScenario(scenario: ScenarioInput): LocalScenarioConfig {
  return {
    process_library: scenario.process_library,
    logic_rules: scenario.logic_rules,
    upper_structure_logic_rules: scenario.upper_structure_logic_rules ?? [],
    resource_pools: scenario.resource_pools,
    milestones: scenario.milestones,
  };
}

function bridgeCompletionMilestonesForProject(scenario: ScenarioInput): MilestoneConstraint[] {
  const bridgeMilestones = scenario.milestones.filter(
    (milestone) => milestone.scope_type === "bridge" && Boolean(milestone.scope_id),
  );
  const template = bridgeMilestones[0];
  const fallbackTargetDate = template?.target_date ?? defaultBridgeCompletionTargetDate(scenario.project.start_date);
  const byBridgeId = new Map<string, MilestoneConstraint>();
  for (const milestone of bridgeMilestones) {
    if (milestone.scope_id && !byBridgeId.has(milestone.scope_id)) {
      byBridgeId.set(milestone.scope_id, milestone);
    }
  }

  return [...scenario.project.bridges]
    .sort((left, right) => left.order - right.order || left.name.localeCompare(right.name))
    .map((bridge): MilestoneConstraint => {
      const existing = byBridgeId.get(bridge.id);
      const existingName = existing?.name.trim();
      return {
        id: `M-${bridge.id}-lower-cast-in-place-finish`,
        name: existingName && !legacyBridgeMilestoneNames.has(existingName) ? existingName : bridgeCompletionMilestoneName,
        level: "control",
        mode: "hard",
        scope_type: "bridge",
        scope_id: bridge.id,
        target_event: "finish",
        target_date: existing?.target_date ?? fallbackTargetDate,
        penalty_per_day: 0,
        related_structure_ids: [],
      };
    });
}

function defaultBridgeCompletionTargetDate(startDate: string): string {
  const year = Number(startDate.slice(0, 4));
  return Number.isFinite(year) ? `${year + 2}-12-31` : startDate;
}

function buildSummary(
  scenario: ScenarioInput | null,
  generated: GeneratedScheduleInput | null,
  solveResult: ScenarioSolveResult | null,
) {
  const recommendedCounts = recommendedResourceCountsFromResult(solveResult?.result ?? null);
  const solveMode = solveResult?.result.objective_breakdown?.solve_mode ?? solveResult?.result.stats?.solve_mode;
  const useRecommendedResourceCount = solveMode === "min_resources_fixed_duration" || solveMode === "resource_cost_optimization";
  const resourceCount = useRecommendedResourceCount && recommendedCounts.length
    ? recommendedCounts.reduce((sum, item) => sum + item.recommended_quantity, 0)
    : generated?.schedule_input.resources.length
    ?? scenario?.resource_pools.reduce((sum, pool) => sum + (pool.enabled && resourcePoolMode(pool) === "LIMITED" ? resourcePoolQuantity(pool) : 0), 0)
    ?? 0;
  const milestoneCount = scenario?.milestones.length ?? 0;
  const elapsedSeconds = elapsedSecondsFromResult(solveResult?.result ?? null);
  return {
    days: solveResult?.result.objective_days ? `${solveResult.result.objective_days} 天` : "-",
    tasks: generated?.schedule_input.tasks.length ? `${generated.schedule_input.tasks.length} 项` : "-",
    elapsed: formatElapsedSeconds(elapsedSeconds),
    resourcesAndMilestones: `${resourceCount} / ${milestoneCount}`,
  };
}

function elapsedSecondsFromResult(result: ScheduleResult | null): number | null {
  if (!result) return null;
  const stats = result.stats ?? {};
  for (const key of ["total_elapsed_seconds", "request_elapsed_seconds", "wall_time_seconds", "cp_sat_wall_time_seconds"]) {
    const value = Number(stats[key]);
    if (Number.isFinite(value) && value >= 0) return value;
  }
  return null;
}

function formatElapsedSeconds(value: number | null): string {
  if (value === null) return "-";
  if (value < 10) return `${value.toFixed(2)} 秒`;
  if (value < 60) return `${value.toFixed(1)} 秒`;
  return `${(value / 60).toFixed(1)} 分钟`;
}

function scenarioResultOptions(solveResult: ScenarioSolveResult | null): ScenarioSolveResult[] {
  if (!solveResult) return [];
  const alternatives = (solveResult.alternative_results ?? []).map((item) => scenarioSolveResultFromAlternative(item));
  return [solveResult, ...alternatives];
}

function scenarioSolveResultFromAlternative(item: ScenarioAlternativeResult): ScenarioSolveResult {
  return {
    scenario_id: item.scenario_id,
    scenario_name: item.scenario_name,
    generated: item.generated,
    result: item.result,
    milestone_results: item.milestone_results,
    diagnostics: item.diagnostics,
    metrics: item.metrics,
    alternative_results: [],
  };
}

type ResultOptionSummary = { resourceCount: number; addedResourceCount: number };

function summarizeResultOptions(options: ScenarioSolveResult[]): ResultOptionSummary[] {
  const baselineResourceCount = options[0] ? actualUsedResourceCount(options[0].result) : 0;
  return options.map((option) => resultOptionSummary(option, baselineResourceCount));
}

function resultOptionSummary(option: ScenarioSolveResult, baselineResourceCount = actualUsedResourceCount(option.result)): ResultOptionSummary {
  const resourceCount = actualUsedResourceCount(option.result);
  return {
    resourceCount,
    addedResourceCount: Math.max(0, resourceCount - baselineResourceCount),
  };
}

function resultOptionLabel(option: ScenarioSolveResult, index: number): string {
  if (index === 0) return "方案1 当前资源";
  const source = stringFromUnknown(option.result.objective_breakdown?.schedule_source ?? option.result.stats?.schedule_source);
  if (source === "minimum_resources_control_priority_balanced") {
    return `方案${index + 1} 最少资源候选`;
  }
  if (source === "minimum_resources_best_effort_refinement") {
    return `方案${index + 1} 最少资源候选复核`;
  }
  if (source === "minimum_resources_refinement_fallback") return `方案${index + 1} 最少资源候选`;
  return `方案${index + 1} 资源候选`;
}

function actualUsedResourceCount(result: ScheduleResult): number {
  const allocatedResourceIds = new Set(
    result.resource_allocations
      .map((item) => String(item.resource_id ?? ""))
      .filter((resourceId) => resourceId.trim().length > 0),
  );
  return allocatedResourceIds.size;
}


function filterScheduledTasksByWindow(tasks: ScheduledTask[], startDate: string, finishDate: string): ScheduledTask[] {
  return tasks.filter((task) => {
    if (startDate && task.finish_date < startDate) return false;
    if (finishDate && task.start_date > finishDate) return false;
    return true;
  });
}

function sortScheduledTasksForPlan(tasks: ScheduledTask[], mode: PlanListSortMode): ScheduledTask[] {
  return [...tasks].sort((left, right) => {
    if (mode === "by_structure") {
      const continuousGroupCompare = compareContinuousBeamPlanOrder(left, right);
      if (continuousGroupCompare !== null) return continuousGroupCompare;
      return (
        compareStructureIds(left.structure_id, right.structure_id)
        || componentSortIndex(left.component_type) - componentSortIndex(right.component_type)
        || left.start_offset - right.start_offset
        || left.name.localeCompare(right.name)
      );
    }

    if (mode === "by_process") {
      return (
        componentSortIndex(left.component_type) - componentSortIndex(right.component_type)
        || left.process_name.localeCompare(right.process_name)
        || left.start_offset - right.start_offset
        || compareStructureIds(left.structure_id, right.structure_id)
        || left.name.localeCompare(right.name)
      );
    }

    return (
      left.start_offset - right.start_offset
      || left.end_offset - right.end_offset
      || compareStructureIds(left.structure_id, right.structure_id)
      || componentSortIndex(left.component_type) - componentSortIndex(right.component_type)
      || left.name.localeCompare(right.name)
    );
  });
}

function compareContinuousBeamPlanOrder(left: ScheduledTask, right: ScheduledTask): number | null {
  const leftGroupKey = continuousPlanGroupKey(left);
  const rightGroupKey = continuousPlanGroupKey(right);
  if (!leftGroupKey || !rightGroupKey || leftGroupKey !== rightGroupKey) return null;
  return (
    left.sequence_order - right.sequence_order
    || compareStructureIds(left.structure_id, right.structure_id)
    || componentSortIndex(left.component_type) - componentSortIndex(right.component_type)
    || left.start_offset - right.start_offset
    || left.name.localeCompare(right.name)
  );
}

function continuousPlanGroupKey(task: ScheduledTask): string | null {
  if (task.component_type !== "cast_in_place_continuous_beam") return null;
  const groupIndex = continuousTaskGroupIndex(task.structure_id);
  if (groupIndex === null) return null;
  return `${task.bridge_id ?? "-"}:${task.work_section_id ?? "-"}:${groupIndex}`;
}

function importComponentCountSummary(summary: Record<string, unknown>): string {
  const lower = summary.lowerComponentCount;
  const upper = summary.upperComponentCount;
  if (lower !== undefined || upper !== undefined) {
    return `${displayValue(lower)} 下部 / ${displayValue(upper)} 上部`;
  }
  return `${displayValue(summary.componentCount)} 构件`;
}

type RecommendedResourceCount = {
  resource_pool_id: string;
  resource_type: string;
  label: string;
  current_quantity: number;
  recommended_quantity: number;
  added_quantity: number;
  max_quantity: number;
};

type AlternativeOutputStatus = "not_applicable" | "output" | "not_output" | "";

type AlternativeOutputState = {
  status: AlternativeOutputStatus;
  reason: string;
  message: string;
};

type RefinementSummary = {
  source: string;
  tone: MetricTone;
  title: string;
  recommendedDays: string;
  baselineDays: string;
  businessStatus: string;
  solverStatus: string;
  hardMilestoneLateDays: string;
  fixedDurationOverrunDays: string;
  hardMilestoneStatus: string;
  scheduleSource: string;
  stageLabel: string;
  stageDescription: string;
  optimalityMessage: string;
  resourcePathStatus: string;
  fallbackReason: string;
  fallbackMessage: string;
  bestEffortMessage: string;
};

type BestEffortRefinement = {
  enabled: boolean;
  strictStatus: string;
  strictReason: string;
  targetLatenessDays: number;
  fixedDurationOverrunDays: number;
};

function objectiveModelingGateFromResult(
  result: ScheduleResult | null,
  termId: ObjectiveTermId,
): ObjectiveModelingGate | null {
  const raw = result?.stats?.objective_modeling_gates ?? result?.objective_breakdown?.objective_modeling_gates;
  if (!isRecord(raw)) return null;
  const gate = raw[termId];
  if (!isRecord(gate)) return null;
  return {
    term_id: String(gate.term_id ?? termId),
    requested_enabled: Boolean(gate.requested_enabled),
    requested_weight: Number(gate.requested_weight ?? 0),
    effective_weight: Number(gate.effective_weight ?? 0),
    modeling_enabled: Boolean(gate.modeling_enabled),
    status: String(gate.status ?? "not_evaluated"),
    reason: String(gate.reason ?? ""),
  };
}

function statusWithObjectiveGate(
  result: ScheduleResult | null,
  termId: ObjectiveTermId,
  fallback: string,
): string {
  const gate = objectiveModelingGateFromResult(result, termId);
  if (gate?.status === "not_enabled") return "not_enabled";
  if (gate?.status === "not_evaluated" && fallback === "not_evaluated") return "not_evaluated";
  return fallback;
}

function recommendedResourceCountsFromResult(result: ScheduleResult | null): RecommendedResourceCount[] {
  const raw = result?.stats?.recommended_resource_counts ?? result?.objective_breakdown?.recommended_resource_counts;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      resource_pool_id: String(item.resource_pool_id ?? item.resource_type ?? item.label ?? ""),
      resource_type: String(item.resource_type ?? ""),
      label: String(item.label ?? item.resource_type ?? "-"),
      current_quantity: Number(item.current_quantity ?? 0),
      recommended_quantity: Number(item.recommended_quantity ?? 0),
      added_quantity: Number(item.added_quantity ?? 0),
      max_quantity: Number(item.max_quantity ?? 0),
    }))
    .filter((item) => item.resource_pool_id);
}

function resourceRecommendationStatusFromResult(result: ScheduleResult | null): string {
  const raw = result?.stats?.resource_recommendation_status ?? result?.objective_breakdown?.resource_recommendation_status;
  return typeof raw === "string" ? raw : "";
}

function alternativeOutputFromResult(result: ScheduleResult | null): AlternativeOutputState {
  const rawStatus = stringFromUnknown(result?.stats?.alternative_output_status ?? result?.objective_breakdown?.alternative_output_status);
  let status: AlternativeOutputStatus = "";
  if (rawStatus === "not_applicable" || rawStatus === "output" || rawStatus === "not_output") {
    status = rawStatus;
  }
  return {
    status,
    reason: stringFromUnknown(result?.stats?.alternative_output_reason ?? result?.objective_breakdown?.alternative_output_reason),
    message: stringFromUnknown(result?.stats?.alternative_output_message ?? result?.objective_breakdown?.alternative_output_message),
  };
}

function targetAchievementFromResult(result: ScheduleResult | null): TargetAchievement | null {
  const raw = result?.stats?.target_achievement ?? result?.objective_breakdown?.target_achievement;
  if (!isRecord(raw)) return null;
  return {
    business_success: Boolean(raw.business_success),
    target_status: stringFromUnknown(raw.target_status) || "unconfirmed",
    solver_status: stringFromUnknown(raw.solver_status) || result?.status || "",
    hard_milestone_late_days: Number(raw.hard_milestone_late_days ?? 0),
    fixed_duration_overrun_days: Number(raw.fixed_duration_overrun_days ?? 0),
    failure_reasons: Array.isArray(raw.failure_reasons) ? raw.failure_reasons.map(String) : [],
    time_budget_seconds: numberFromUnknown(raw.time_budget_seconds) ?? undefined,
    time_budget_exhausted: typeof raw.time_budget_exhausted === "boolean" ? raw.time_budget_exhausted : undefined,
    evaluated_at_source: stringFromUnknown(raw.evaluated_at_source) || undefined,
  };
}

function isSolverScheduleAvailable(status: string): boolean {
  const normalized = status.toUpperCase();
  return normalized === "FEASIBLE" || normalized === "OPTIMAL";
}

function targetHasMeasuredFailure(target: TargetAchievement | null): boolean {
  if (!target) return false;
  return target.hard_milestone_late_days > 0 || target.fixed_duration_overrun_days > 0;
}

function targetHasKnownCurrentFailure(target: TargetAchievement | null): boolean {
  if (!target) return false;
  return target.target_status === "unconfirmed"
    && isSolverScheduleAvailable(target.solver_status)
    && targetHasMeasuredFailure(target);
}

function targetFailureIssueText(target: TargetAchievement | null): string {
  if (!target) return "";
  const issues = [
    target.hard_milestone_late_days > 0 ? `硬里程碑晚点 ${target.hard_milestone_late_days} 天` : "",
    target.fixed_duration_overrun_days > 0 ? `固定工期超期 ${target.fixed_duration_overrun_days} 天` : "",
  ].filter(Boolean);
  return issues.join("，") || "业务目标未满足";
}

function solverStatusDisplay(status: string): string {
  const normalized = status.toUpperCase();
  if (normalized === "FEASIBLE") return "可行（未证明最优）";
  if (normalized === "OPTIMAL") return "最优";
  return formatScheduleStatus(normalized || status);
}

function targetOptimalityMessage(target: TargetAchievement | null): string {
  if (!target) return "";
  if (target.solver_status.toUpperCase() !== "FEASIBLE") return "";
  if (!target.business_success || target.target_status === "unconfirmed") return "";
  if (target.time_budget_exhausted) {
    const budgetText = target.time_budget_seconds ? `${target.time_budget_seconds} 秒` : "本次";
    return `已生成满足业务目标的可用排程；${budgetText}求解时限耗尽只表示尚未证明最优。`;
  }
  return "已生成满足业务目标的可用排程；FEASIBLE 表示尚未证明最优。";
}

function targetStatusLabel(target: TargetAchievement | null, resourceRecommendationStatus = ""): string {
  if (!target) return "未评估";
  if (targetHasKnownCurrentFailure(target)) {
    if (resourceRecommendationStatus === "resource_upper_bound_infeasible") return "当前资源目标未满足，最大资源也不满足";
    if (resourceRecommendationStatus === "critical_path_infeasible") return "当前资源目标未满足，关键路径不可行";
    if (resourceRecommendationStatus === "recommended_resources_verified") return "当前资源目标未满足，已找到候选资源";
    return "当前资源目标未满足，推荐未确认";
  }
  const labels: Record<string, string> = {
    met: "业务目标已达成",
    current_resources_target_failed: "当前资源目标未满足",
    candidate_resources_target_met: "候选资源目标已达成",
    candidate_resources_target_failed: "候选资源目标未满足",
    max_resources_target_failed: "最大资源目标未满足",
    physical_infeasible: "物理无可行排程",
    unconfirmed: "限时内无法确认",
  };
  return labels[target.target_status] ?? target.target_status;
}

function resourceRecommendationOutcomeText(status: string): string {
  const labels: Record<string, string> = {
    recommended_resources_verified: "已找到并验证推荐资源组合。",
    resource_recommendation_unresolved: "已进入资源增量建议，当前限时内未确认可行推荐资源组合。",
    unconfirmed: "已进入资源增量建议，当前限时内未确认可行推荐资源组合。",
    critical_path_infeasible: "资源增量建议已停止：目标关键路径在当前规则下不可行。",
    resource_upper_bound_infeasible: "资源增量建议已停止：当前最大资源仍不满足目标。",
    physical_infeasible: "资源增量建议已停止：最大资源下仍无可行排程。",
    max_resource_generation_error: "资源增量建议未完成：最大资源场景生成失败。",
    candidate_resources_target_failed: "候选资源复排后仍未满足业务目标。",
  };
  return labels[status] ?? "";
}

function refinementTargetDescription(
  target: TargetAchievement | null,
  resourceRecommendationStatus: string,
): string {
  if (!target) return "";
  const issue = targetFailureIssueText(target);
  const resourceOutcome = resourceRecommendationOutcomeText(resourceRecommendationStatus);
  if (targetHasKnownCurrentFailure(target)) {
    return `系统已生成可查看排程，但${issue}。${resourceOutcome}`;
  }
  if (target.target_status === "current_resources_target_failed") {
    return `系统已生成可查看排程，但${issue}。`;
  }
  if (target.target_status === "candidate_resources_target_failed") {
    return `候选资源已完成复排，但${issue}。`;
  }
  if (target.target_status === "max_resources_target_failed") {
    return `最大资源已完成预检，但${issue}。`;
  }
  if (target.target_status === "physical_infeasible") {
    return "当前资源在业务规则下没有可用排程。";
  }
  if (target.target_status === "unconfirmed") {
    return resourceOutcome || "求解器在当前时限内未返回足够信息，暂时无法确认业务目标是否满足。";
  }
  return "";
}

function fallbackReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    current_resources_target_failed: "当前资源排程未满足目标",
    current_resources_full_objective_unconfirmed: "当前资源完整目标函数求解限时内未确认",
    current_resources_full_objective_physical_infeasible: "当前资源物理无可行排程",
    minimum_resource_full_objective_unknown: "候选资源完整目标函数复排限时内未确认",
    minimum_resources_target_failed: "候选资源排程未满足目标",
    candidate_resources_target_failed: "候选资源排程未满足目标",
    target_unconfirmed: "目标是否满足在限时内未确认",
    physical_infeasible: "物理无可行排程",
  };
  if (labels[reason]) return labels[reason];
  if (/^[a-z0-9_:-]+$/i.test(reason)) return "未通过成功结果校验";
  return reason;
}

function refinementFallbackMessage(source: string, fallbackReason: string): string {
  if (!fallbackReason) return "";
  const reason = fallbackReasonLabel(fallbackReason);
  if (source.startsWith("minimum_resources_")) {
    return `最少资源候选复排未作为成功结果展示，当前保留候选排程用于复核：${reason}。`;
  }
  if (fallbackReason === "current_resources_target_failed") {
    return "当前资源排程未满足目标，已作为参考排程保留。";
  }
  return `当前资源目标函数排程未作为成功结果展示，已保留参考排程：${reason}。`;
}

function resourceOrganizationFromResult(result: ScheduleResult | null): ResourceOrganizationAnalysis | null {
  const analysisRaw = result?.stats?.control_priority_analysis ?? result?.objective_breakdown?.control_priority_analysis;
  const nestedRaw = isRecord(analysisRaw) ? analysisRaw.resource_organization_analysis : undefined;
  const raw = result?.stats?.resource_organization_analysis
    ?? result?.objective_breakdown?.resource_organization_analysis
    ?? nestedRaw;
  if (!isRecord(raw)) return null;
  const resources = Array.isArray(raw.resources)
    ? raw.resources.filter(isRecord).map((item) => ({
        resource_id: String(item.resource_id ?? ""),
        resource_name: String(item.resource_name ?? "-"),
        resource_type: String(item.resource_type ?? ""),
        task_count: Number(item.task_count ?? 0),
        active_days: Number(item.active_days ?? 0),
        first_start_offset: nullableNumberFromUnknown(item.first_start_offset),
        last_end_offset: nullableNumberFromUnknown(item.last_end_offset),
        active_span_days: Number(item.active_span_days ?? 0),
        idle_days: Number(item.idle_days ?? 0),
        max_idle_gap_days: Number(item.max_idle_gap_days ?? 0),
        idle_gap_count: Number(item.idle_gap_count ?? 0),
        utilization_within_span: Number(item.utilization_within_span ?? 0),
        project_utilization: Number(item.project_utilization ?? 0),
        jump_pier_count: Number(item.jump_pier_count ?? 0),
        side_switch_count: Number(item.side_switch_count ?? 0),
        cross_side_jump_count: Number(item.cross_side_jump_count ?? 0),
        path_group_switch_count: Number(item.path_group_switch_count ?? 0),
      })).filter((item) => item.resource_id)
    : [];
  const resourceTypes = Array.isArray(raw.resource_types)
    ? raw.resource_types.filter(isRecord).map((item) => ({
        resource_type: String(item.resource_type ?? ""),
        resource_count: Number(item.resource_count ?? 0),
        used_resource_count: Number(item.used_resource_count ?? 0),
        task_count: Number(item.task_count ?? 0),
        active_days: Number(item.active_days ?? 0),
        min_workload_days: Number(item.min_workload_days ?? 0),
        max_workload_days: Number(item.max_workload_days ?? 0),
        average_workload_days: Number(item.average_workload_days ?? 0),
        workload_range_days: Number(item.workload_range_days ?? 0),
        idle_days: Number(item.idle_days ?? 0),
        max_idle_gap_days: Number(item.max_idle_gap_days ?? 0),
        jump_pier_count: Number(item.jump_pier_count ?? 0),
        side_switch_count: Number(item.side_switch_count ?? 0),
        path_group_switch_count: Number(item.path_group_switch_count ?? 0),
        balance_status: String(item.balance_status ?? "not_evaluated"),
        idle_status: String(item.idle_status ?? "not_evaluated"),
      })).filter((item) => item.resource_type)
    : [];
  return {
    resource_count: Number(raw.resource_count ?? resources.length),
    used_resource_count: Number(raw.used_resource_count ?? resources.filter((item) => item.active_days > 0).length),
    resource_balance_status: String(raw.resource_balance_status ?? "not_evaluated"),
    resource_idle_status: statusWithObjectiveGate(
      result,
      "resource_idle",
      String(raw.resource_idle_status ?? "not_evaluated"),
    ),
    resource_path_status: String(raw.resource_path_status ?? "not_evaluated"),
    workload_balance_enabled: Boolean(raw.workload_balance_enabled),
    idle_enabled: Boolean(raw.idle_enabled),
    path_continuity_enabled: Boolean(raw.path_continuity_enabled),
    resources,
    resource_types: resourceTypes,
  };
}

function continuousBeamTeamSpanSummaryFromResult(result: ScheduleResult | null): ContinuousBeamTeamSpanSummary | null {
  const raw = result?.stats?.continuous_beam_team_spans ?? result?.objective_breakdown?.continuous_beam_team_spans;
  if (!isRecord(raw)) return null;
  const spans = Array.isArray(raw.spans)
    ? raw.spans.filter(isRecord).map((item) => ({
        span_id: String(item.span_id ?? item.span_group_id ?? ""),
        span_name: String(item.span_name ?? item.display_name ?? "-"),
        bridge_id: typeof item.bridge_id === "string" ? item.bridge_id : null,
        work_section_id: typeof item.work_section_id === "string" ? item.work_section_id : null,
        group_index: typeof item.group_index === "string" || typeof item.group_index === "number" ? item.group_index : null,
        task_ids: Array.isArray(item.task_ids) ? item.task_ids.map(String) : [],
        start_offset: Number(item.start_offset ?? 0),
        end_offset: Number(item.end_offset ?? 0),
        start_date: String(item.start_date ?? "-"),
        finish_date: String(item.finish_date ?? "-"),
        resource_id: typeof item.resource_id === "string" ? item.resource_id : null,
        resource_name: typeof item.resource_name === "string" ? item.resource_name : null,
      })).filter((item) => item.span_id)
    : [];
  const diagnostics = Array.isArray(raw.diagnostics)
    ? raw.diagnostics.filter(isRecord).map((item) => ({
        level: ["info", "warning", "error"].includes(String(item.level)) ? String(item.level) as ValidationMessage["level"] : "info",
        message: String(item.message ?? ""),
        subject_id: typeof item.subject_id === "string" ? item.subject_id : null,
      })).filter((item) => item.message)
    : [];
  return {
    enabled: Boolean(raw.enabled),
    span_count: Number(raw.span_count ?? spans.length),
    resource_count: Number(raw.resource_count ?? raw.resource_quantity ?? 0),
    spans,
    diagnostics,
  };
}

function controlPriorityAnalysisFromResult(result: ScheduleResult | null): ControlPriorityAnalysis | null {
  const raw = result?.stats?.control_priority_analysis ?? result?.objective_breakdown?.control_priority_analysis;
  if (!isRecord(raw)) return null;
  const controlObjects = Array.isArray(raw.control_objects)
    ? raw.control_objects.filter(isRecord).map((item) => ({
        id: String(item.id ?? ""),
        name: String(item.name ?? "-"),
        object_type: String(item.object_type ?? ""),
        source: String(item.source ?? ""),
        source_label: String(item.source_label ?? controlTargetSourceLabels[String(item.source ?? "")] ?? item.source ?? "-"),
        task_count: Number(item.task_count ?? 0),
        task_ids: Array.isArray(item.task_ids) ? item.task_ids.map(String) : [],
        remaining_buffer_days: nullableNumberFromUnknown(item.remaining_buffer_days),
        buffer_risk_days: Number(item.buffer_risk_days ?? 0),
        status: String(item.status ?? "not_evaluated"),
      })).filter((item) => item.id)
    : [];
  const controlObjectTasks = Array.isArray(raw.control_object_tasks)
    ? raw.control_object_tasks.filter(isRecord).map((item) => ({
        task_id: String(item.task_id ?? ""),
        task_name: String(item.task_name ?? "-"),
        object_id: String(item.object_id ?? ""),
        object_name: String(item.object_name ?? "-"),
        task_role: String(item.task_role ?? ""),
        source: String(item.source ?? ""),
        source_label: String(item.source_label ?? controlTargetSourceLabels[String(item.source ?? "")] ?? item.source ?? "-"),
        control_level: controlLevelFromUnknown(item.control_level),
        component_type: componentTypeFromUnknown(item.component_type),
        finish_date: String(item.finish_date ?? ""),
        latest_safe_finish_date: item.latest_safe_finish_date ? String(item.latest_safe_finish_date) : null,
        remaining_buffer_days: nullableNumberFromUnknown(item.remaining_buffer_days),
        buffer_risk_days: Number(item.buffer_risk_days ?? 0),
        status: String(item.status ?? "not_evaluated"),
      })).filter((item) => item.task_id)
    : [];
  const controlChainPredecessors = Array.isArray(raw.control_chain_predecessors)
    ? raw.control_chain_predecessors.filter(isRecord).map((item) => ({
        task_id: String(item.task_id ?? ""),
        task_name: String(item.task_name ?? "-"),
        source: String(item.source ?? ""),
        source_label: String(item.source_label ?? controlTargetSourceLabels[String(item.source ?? "")] ?? item.source ?? "-"),
        control_level: controlLevelFromUnknown(item.control_level),
        component_type: componentTypeFromUnknown(item.component_type),
        finish_date: String(item.finish_date ?? ""),
        latest_safe_finish_date: item.latest_safe_finish_date ? String(item.latest_safe_finish_date) : null,
        remaining_buffer_days: nullableNumberFromUnknown(item.remaining_buffer_days),
        buffer_risk_days: Number(item.buffer_risk_days ?? 0),
        status: String(item.status ?? "not_evaluated"),
        deadline_source: String(item.deadline_source ?? ""),
        impacted_control_objects: Array.isArray(item.impacted_control_objects)
          ? item.impacted_control_objects.filter(isRecord).map((object) => ({
              id: String(object.id ?? ""),
              name: String(object.name ?? "-"),
            })).filter((object) => object.id)
          : [],
      })).filter((item) => item.task_id)
    : [];
  const controlTargets = Array.isArray(raw.control_targets)
    ? raw.control_targets.filter(isRecord).map((item) => ({
        task_id: String(item.task_id ?? ""),
        task_name: String(item.task_name ?? "-"),
        control_level: controlLevelFromUnknown(item.control_level),
        component_type: componentTypeFromUnknown(item.component_type),
        source: String(item.source ?? ""),
      })).filter((item) => item.task_id)
    : [];
  const bufferRisks = Array.isArray(raw.control_buffer_risks)
    ? raw.control_buffer_risks.filter(isRecord).map((item) => ({
        task_id: String(item.task_id ?? ""),
        task_name: String(item.task_name ?? "-"),
        control_level: controlLevelFromUnknown(item.control_level),
        is_control_target: Boolean(item.is_control_target),
        target_source: String(item.target_source ?? ""),
        deadline_source: String(item.deadline_source ?? ""),
        latest_safe_finish_date: String(item.latest_safe_finish_date ?? ""),
        necessary_buffer_days: Number(item.necessary_buffer_days ?? 0),
        finish_date: String(item.finish_date ?? ""),
        remaining_buffer_days: Number(item.remaining_buffer_days ?? 0),
        buffer_risk_days: Number(item.buffer_risk_days ?? 0),
        status: String(item.status ?? "not_evaluated"),
      })).filter((item) => item.task_id)
    : [];
  const pathGroups = Array.isArray(raw.path_group_diagnostics)
    ? raw.path_group_diagnostics.filter(isRecord).map(pathGroupDiagnosticFromRecord).filter((item) => item.key)
    : [];
  const resourceOrganization = resourceOrganizationFromResult(result);
  return {
    control_task_count: Number(raw.control_task_count ?? 0),
    control_objects: controlObjects,
    control_object_tasks: controlObjectTasks,
    control_chain_predecessors: controlChainPredecessors,
    control_targets: controlTargets,
    control_buffer_risks: bufferRisks,
    control_buffer_status: String(raw.control_buffer_status ?? "not_evaluated"),
    normal_balance_status: String(raw.normal_balance_status ?? "not_evaluated"),
    resource_path_status: String(raw.resource_path_status ?? resourceOrganization?.resource_path_status ?? "not_evaluated"),
    resource_balance_status: String(raw.resource_balance_status ?? resourceOrganization?.resource_balance_status ?? "not_evaluated"),
    resource_idle_status: statusWithObjectiveGate(
      result,
      "resource_idle",
      String(raw.resource_idle_status ?? resourceOrganization?.resource_idle_status ?? "not_evaluated"),
    ),
    resource_organization_analysis: resourceOrganization ?? undefined,
    path_group_diagnostics: pathGroups,
    fallback_reason: typeof raw.fallback_reason === "string" ? raw.fallback_reason : undefined,
  };
}

function refinementSummaryFromResult(result: ScheduleResult | null): RefinementSummary | null {
  if (!result) return null;
  const analysis = controlPriorityAnalysisFromResult(result);
  const source = stringFromUnknown(result.objective_breakdown?.schedule_source ?? result.stats?.schedule_source);
  if (!analysis && !source) return null;
  const bestEffort = bestEffortRefinementFromResult(result);
  const targetAchievement = targetAchievementFromResult(result);
  const stageSummary = refinementStageSummaryFromResult(result, source);
  const resourceRecommendationStatus = resourceRecommendationStatusFromResult(result);
  const isBestEffort = Boolean(bestEffort?.enabled)
    || source === "current_resources_best_effort_refinement"
    || source === "minimum_resources_best_effort_refinement";
  const hardMilestones = result.milestone_results.filter((milestone) => milestone.mode === "hard");
  const hardLateCount = hardMilestones.filter((milestone) => milestone.lateness_days > 0).length;
  const resourcePathStatus = analysis?.resource_path_status ?? "not_evaluated";
  const fallbackReason = isBestEffort ? "" : (
    analysis?.fallback_reason
    ?? stringFromUnknown(result.objective_breakdown?.skipped_named_refinement_reason ?? result.stats?.skipped_named_refinement_reason)
  );
  const baselineDays = Number(result.objective_breakdown?.baseline_makespan_days ?? result.stats?.baseline_makespan_days);
  const isRefinementFailed = source === "current_resources_refinement_failed";
  const isFallback = !isBestEffort && !isRefinementFailed && (source === "current_resources_capacity_shortest_fallback" || Boolean(fallbackReason));
  const tone = refinementTone({
    hardLateCount,
    resourcePathStatus,
    isFallback,
    isBestEffort,
    isRefinementFailed,
    targetAchievement,
  });
  return {
    source,
    tone,
    title: refinementTitle({ source, hardLateCount, isFallback, isBestEffort, isRefinementFailed, targetAchievement }),
    recommendedDays: result.objective_days == null ? "-" : `${result.objective_days} 天`,
    baselineDays: Number.isFinite(baselineDays) ? `${baselineDays} 天` : "-",
    businessStatus: targetStatusLabel(targetAchievement, resourceRecommendationStatus),
    solverStatus: solverStatusDisplay(targetAchievement?.solver_status || result.status),
    hardMilestoneLateDays: targetAchievement ? `${targetAchievement.hard_milestone_late_days} 天` : "-",
    fixedDurationOverrunDays: targetAchievement ? `${targetAchievement.fixed_duration_overrun_days} 天` : "-",
    hardMilestoneStatus: hardMilestones.length
      ? (hardLateCount > 0 ? `不满足 ${hardLateCount} 个` : "全部满足")
      : "未配置",
    scheduleSource: scheduleSourceLabels[source] ?? (source || "-"),
    stageLabel: stageSummary.label,
    stageDescription: refinementTargetDescription(targetAchievement, resourceRecommendationStatus) || stageSummary.description,
    optimalityMessage: targetOptimalityMessage(targetAchievement),
    resourcePathStatus: resourcePathStatusLabels[resourcePathStatus] ?? resourcePathStatus,
    fallbackReason,
    fallbackMessage: refinementFallbackMessage(source, fallbackReason),
    bestEffortMessage: bestEffortMessage(bestEffort),
  };
}

function refinementStageSummaryFromResult(result: ScheduleResult, source: string): { label: string; description: string } {
  if (source === "current_resources_refinement_failed") {
    return {
      label: "当前资源目标未满足",
      description: "当前资源未得到达成业务目标的排程结果，主流程已进入资源建议。",
    };
  }
  if (source === "current_resources_capacity_shortest_fallback") {
    return {
      label: "固定资源参考排程",
      description: "当前展示的是固定资源参考排程。",
    };
  }

  const drillGroup = drillGroupRefinementFromResult(result);
  if (drillGroup && drillGroup.coarse_group_count > 0) {
    if (drillGroup.status === "stage1_final") {
      return {
        label: "墩组分配结果",
        description: "系统已完成钻机墩组资源分配和时间排程。",
      };
    }
    if (drillGroup.status === "stage2_refined") {
      return {
        label: "路径复核结果",
        description: "系统在墩组分配后完成钻机路径复核，并采用复核后的排程结果。",
      };
    }
    if (drillGroup.status === "stage2_fallback") {
      return {
        label: "墩组分配结果",
        description: drillGroup.fallback_reason
          ? `路径复核未作为主结果展示，当前保留墩组分配展开结果：${drillGroup.fallback_reason}。`
          : "路径复核未作为主结果展示，当前保留墩组分配展开结果。",
      };
    }
    if (drillGroup.status === "coarse_only") {
      return {
        label: "墩组分配结果",
        description: "本次采用墩组资源分配结果，未进入路径复核。",
      };
    }
    return {
      label: drillGroupRefinementStatusLabels[drillGroup.status] ?? drillGroup.status,
      description: "本次存在桩基钻机墩组诊断，请结合下方“桩基墩组诊断”表复核阶段状态。",
    };
  }

  if (source === "current_resources_control_priority_balanced") {
    return {
      label: "常规目标函数排程",
      description: "本次没有触发桩基钻机墩组诊断，当前主结果来自常规目标函数排程。",
    };
  }

  return {
    label: scheduleSourceLabels[source] ?? (source || "-"),
    description: "",
  };
}

function bestEffortRefinementFromResult(result: ScheduleResult): BestEffortRefinement | null {
  const raw = result.stats?.best_effort_refinement ?? result.objective_breakdown?.best_effort_refinement;
  if (!isRecord(raw)) return null;
  return {
    enabled: Boolean(raw.enabled),
    strictStatus: stringFromUnknown(raw.strict_refinement_status),
    strictReason: stringFromUnknown(raw.strict_refinement_failure_reason),
    targetLatenessDays: Number(raw.target_lateness_days ?? 0),
    fixedDurationOverrunDays: Number(raw.fixed_duration_overrun_days ?? 0),
  };
}

function bestEffortMessage(bestEffort: BestEffortRefinement | null): string {
  if (!bestEffort?.enabled) return "";
  const parts = [
    bestEffort.strictStatus ? `目标函数求解状态：${bestEffort.strictStatus}` : "",
    bestEffort.strictReason ? `原因：${bestEffort.strictReason}` : "",
    `强制节点迟延合计 ${bestEffort.targetLatenessDays} 天`,
    `固定工期超期 ${bestEffort.fixedDurationOverrunDays} 天`,
  ].filter(Boolean);
  return `当前为目标函数求解后的目标未满足结果，不代表目标已满足。${parts.join("；")}。`;
}

function pathGroupDiagnosticFromRecord(item: Record<string, unknown>) {
  return {
    key: String(item.key ?? ""),
    bridge_id: item.bridge_id == null ? null : String(item.bridge_id),
    work_section_id: item.work_section_id == null ? null : String(item.work_section_id),
    side: String(item.side ?? "N"),
    side_label: String(item.side_label ?? "-"),
    resource_type: String(item.resource_type ?? ""),
    component_type: componentTypeFromUnknown(item.component_type),
    component_label: String(item.component_label ?? item.component_type ?? "-"),
    process_name: String(item.process_name ?? "-"),
    task_count: Number(item.task_count ?? 0),
    resource_count: Number(item.resource_count ?? 0),
    resource_names: Array.isArray(item.resource_names) ? item.resource_names.map(String) : [],
    structure_count: Number(item.structure_count ?? 0),
    actual_sequence: Array.isArray(item.actual_sequence) ? item.actual_sequence.map(String) : [],
  };
}

function refinementTone({
  hardLateCount,
  resourcePathStatus,
  isFallback,
  isBestEffort,
  isRefinementFailed,
  targetAchievement,
}: {
  hardLateCount: number;
  resourcePathStatus: string;
  isFallback: boolean;
  isBestEffort: boolean;
  isRefinementFailed: boolean;
  targetAchievement: TargetAchievement | null;
}): MetricTone {
  if (targetHasKnownCurrentFailure(targetAchievement)) return "danger";
  if (targetAchievement?.target_status === "unconfirmed") return "warn";
  if (targetAchievement?.target_status === "physical_infeasible") return "danger";
  if (targetAchievement && !targetAchievement.business_success) return "danger";
  if (isRefinementFailed) return "danger";
  if (hardLateCount > 0) return "danger";
  if (
    isFallback
    || isBestEffort
    || resourcePathStatus === "abnormal_jump"
  ) {
    return "warn";
  }
  return "ok";
}

function refinementTitle({
  source,
  hardLateCount,
  isFallback,
  isBestEffort,
  isRefinementFailed,
  targetAchievement,
}: {
  source: string;
  hardLateCount: number;
  isFallback: boolean;
  isBestEffort: boolean;
  isRefinementFailed: boolean;
  targetAchievement: TargetAchievement | null;
}): string {
  if (targetHasKnownCurrentFailure(targetAchievement)) {
    const hasHardMilestoneDelay = targetAchievement ? targetAchievement.hard_milestone_late_days > 0 : false;
    const hasFixedDurationOverrun = targetAchievement ? targetAchievement.fixed_duration_overrun_days > 0 : false;
    if (hasHardMilestoneDelay && hasFixedDurationOverrun) return "当前资源排程未满足业务目标";
    if (hasHardMilestoneDelay) return "当前资源排程未满足硬里程碑";
    if (hasFixedDurationOverrun) return "当前资源排程超过固定工期";
  }
  if (targetAchievement?.target_status === "unconfirmed") return "限时内无法确认目标是否满足";
  if (targetAchievement?.target_status === "physical_infeasible") return "当前资源无可行排程";
  if (targetAchievement?.target_status === "current_resources_target_failed") return "当前资源可排程，但目标未满足";
  if (targetAchievement?.target_status === "candidate_resources_target_failed") return "候选资源复排后目标仍未满足";
  if (targetAchievement?.target_status === "max_resources_target_failed") return "当前最大资源仍不满足目标";
  if (targetAchievement?.target_status === "candidate_resources_target_met") return "候选资源目标已达成";
  if (targetAchievement?.target_status === "met") return "当前资源目标已达成";
  if (isRefinementFailed) return "当前资源目标未满足，已转资源建议";
  if (isBestEffort) return hardLateCount > 0 ? "目标函数排程，目标未满足" : "目标函数排程可用于复核";
  if (isFallback) return "已回退固定资源参考排程";
  if (hardLateCount > 0) return "强制节点未满足";
  if (source === "current_resources_control_priority_balanced") return "当前资源排程可用于复核";
  return scheduleSourceLabels[source] ?? "排程结果可用于复核";
}

function controlLevelFromUnknown(value: unknown): ControlLevel {
  return typeof value === "string" && value in controlLevelLabels ? value as ControlLevel : "normal";
}

function componentTypeFromUnknown(value: unknown): ComponentType {
  return typeof value === "string" && isComponentType(value) ? value : "pile";
}

function stringFromUnknown(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function nullableNumberFromUnknown(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPercent(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return `${Math.round(value * 100)}%`;
}

function normalizeObjectiveWeight(value: string | number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 1;
  return Math.min(10_000_000_000, Math.max(1, Math.round(parsed)));
}

function inheritedObjectiveTermConfig(
  term: ObjectiveTermDefinition,
  incomingTerms: Partial<Record<ObjectiveTermId, ObjectiveTermConfig>>,
): ObjectiveTermConfig | undefined {
  const direct = incomingTerms[term.id];
  if (direct) return direct;
  return undefined;
}

function withDefaultScheduleStrategy(config?: ScheduleStrategyConfig | null): ScheduleStrategyConfig {
  const defaultTerms = defaultObjectiveTermsConfig();
  const incomingTerms: Partial<Record<ObjectiveTermId, ObjectiveTermConfig>> = config?.objective_terms ?? {};
  const {
    strategy: _legacyStrategy,
    resource_guarantee: _legacyResourceGuarantee,
    ...configWithoutLegacyControls
  } = (config ?? {}) as ScheduleStrategyConfig & {
    strategy?: unknown;
    resource_guarantee?: unknown;
  };
  const objectiveTerms = objectiveTermDefinitions.reduce<Record<ObjectiveTermId, ObjectiveTermConfig>>((next, term) => {
    const incoming = inheritedObjectiveTermConfig(term, incomingTerms);
    next[term.id] = {
      enabled: incoming?.enabled ?? term.defaultEnabled ?? true,
      weight: normalizeObjectiveWeight(incoming?.weight ?? term.defaultWeight),
    };
    return next;
  }, defaultTerms);

  return {
    ...defaultScheduleStrategyConfig,
    ...configWithoutLegacyControls,
    objective_terms: objectiveTerms,
    enable_balance_objective: false,
  };
}

function objectiveTermDefinitionById(termId: string | undefined | null): ObjectiveTermDefinition | undefined {
  return objectiveTermDefinitions.find((term) => term.id === termId);
}

function objectiveContributionSummaryFromResult(result: ScheduleResult | null): ObjectiveContributionSummary | null {
  if (!result) return null;
  const breakdown = result.objective_breakdown ?? {};
  const rawContributions = breakdown.objective_contributions;
  if (Array.isArray(rawContributions)) {
    const items = rawContributions
      .filter(isRecord)
      .map(objectiveContributionFromRecord)
      .filter((item): item is ObjectiveContribution => Boolean(item));
    if (!items.length) return null;
    return {
      items,
      total: numberFromUnknown(breakdown.weighted_objective) ?? items.reduce((sum, item) => sum + item.weighted_contribution, 0),
      isLegacy: false,
    };
  }

  const legacyItems = legacyObjectiveContributionsFromBreakdown(breakdown);
  if (!legacyItems.length) return null;
  return {
    items: legacyItems,
    total: numberFromUnknown(breakdown.weighted_objective) ?? legacyItems.reduce((sum, item) => sum + item.weighted_contribution, 0),
    isLegacy: true,
  };
}

function objectiveContributionFromRecord(item: Record<string, unknown>): ObjectiveContribution | null {
  const termId = stringFromUnknown(item.term_id);
  if (!termId) return null;
  const definition = objectiveTermDefinitionById(termId);
  const effectiveWeight = numberFromUnknown(item.effective_weight) ?? 0;
  return {
    term_id: termId,
    label: stringFromUnknown(item.label) || definition?.label || termId,
    group: stringFromUnknown(item.group) || definition?.group,
    source: stringFromUnknown(item.source) || definition?.source || "objective",
    enabled: Boolean(item.enabled),
    active: Boolean(item.active),
    configured_weight: numberFromUnknown(item.configured_weight) ?? effectiveWeight,
    effective_weight: effectiveWeight,
    raw_penalty: numberFromUnknown(item.raw_penalty ?? item.raw_value) ?? 0,
    raw_value: numberFromUnknown(item.raw_value ?? item.raw_penalty) ?? undefined,
    unit: stringFromUnknown(item.unit) || undefined,
    weighted_contribution: numberFromUnknown(item.weighted_contribution ?? item.weighted_value) ?? 0,
    weighted_value: numberFromUnknown(item.weighted_value ?? item.weighted_contribution) ?? undefined,
    applies_to: Array.isArray(item.applies_to) ? item.applies_to.map(String) : [],
    parent_term_id: stringFromUnknown(item.parent_term_id) || definition?.parentTermId,
    notes: stringFromUnknown(item.notes),
  };
}

function legacyObjectiveContributionsFromBreakdown(breakdown: Record<string, unknown>): ObjectiveContribution[] {
  const weights = isRecord(breakdown.objective_weights) ? breakdown.objective_weights : {};
  const termsUsed = isRecord(breakdown.objective_terms_used) ? breakdown.objective_terms_used : {};
  const rawPenaltyByTerm: Partial<Record<ObjectiveTermId, number>> = {
    control_node_late: numberFromUnknown(breakdown.control_lateness_days) ?? 0,
    makespan_and_soft_milestone: numberFromUnknown(breakdown.makespan_days) ?? 0,
    resource_idle: numberFromUnknown(breakdown.resource_idle_penalty) ?? 0,
  };

  return objectiveTermDefinitions.map((definition) => {
    const rawTermUsed = termsUsed[definition.id];
    const termUsed: Record<string, unknown> = isRecord(rawTermUsed) ? rawTermUsed : {};
    const effectiveWeight = numberFromUnknown(termUsed.effective_weight ?? weights[definition.id]) ?? 0;
    const configuredWeight = numberFromUnknown(termUsed.weight) ?? definition.defaultWeight;
    const rawPenalty = rawPenaltyByTerm[definition.id] ?? 0;
    const enabled = typeof termUsed.enabled === "boolean" ? termUsed.enabled : effectiveWeight > 0;
    const active = effectiveWeight > 0;
    return {
      term_id: definition.id,
      label: definition.label,
      group: definition.group,
      source: definition.source ?? "objective",
      enabled,
      active,
      configured_weight: configuredWeight,
      effective_weight: effectiveWeight,
      raw_penalty: rawPenalty,
      weighted_contribution: active ? rawPenalty * effectiveWeight : 0,
      applies_to: [definition.appliesTo],
      parent_term_id: definition.parentTermId,
      notes: "旧字段汇总。",
    };
  });
}

function objectiveContributionStatus(item: ObjectiveContribution): string {
  if (!item.enabled || item.effective_weight <= 0) return "未启用";
  if (!item.active) return "本分支不适用";
  if (item.raw_penalty === 0) return "已参与，无罚分";
  return "已参与";
}

function formatObjectiveNumber(value: number): string {
  if (!Number.isFinite(value)) return "-";
  return Math.round(value).toLocaleString("zh-CN");
}

type SelectedResourceCost = {
  resource_pool_id: string;
  label: string;
  resource_type: string;
  cost_type: ResourceCostType;
  selected_quantity: number;
  current_quantity: number;
  added_quantity: number;
  incremental_unit_cost: number;
  billing_period_days: number;
  daily_unit_cost: number;
  active_days: number;
  incremental_cost: number;
};

type ResourceCostSummary = {
  selectedResources: SelectedResourceCost[];
  resourceIncrementalCost: number;
  softMilestonePenalty: number;
  totalCost: number;
  businessExplanation: string;
};

function resourceCostSummaryFromResult(result: ScheduleResult | null): ResourceCostSummary | null {
  if (!result) return null;
  const breakdown = result.objective_breakdown ?? {};
  if (breakdown.solve_mode !== "resource_cost_optimization") return null;
  const rawResources = breakdown.selected_resource_costs;
  const selectedResources = Array.isArray(rawResources)
    ? rawResources.filter(isRecord).map((item) => ({
        resource_pool_id: String(item.resource_pool_id ?? ""),
        label: String(item.label ?? item.resource_type ?? "-"),
        resource_type: String(item.resource_type ?? ""),
        cost_type: resourceCostTypeFromUnknown(item.cost_type),
        selected_quantity: Number(item.selected_quantity ?? 0),
        current_quantity: Number(item.current_quantity ?? 0),
        added_quantity: Number(item.added_quantity ?? 0),
        incremental_unit_cost: Number(item.incremental_unit_cost ?? 0),
        billing_period_days: Number(item.billing_period_days ?? 30),
        daily_unit_cost: Number(item.daily_unit_cost ?? 0),
        active_days: Number(item.active_days ?? 0),
        incremental_cost: Number(item.incremental_cost ?? 0),
      })).filter((item) => item.resource_pool_id)
    : [];
  return {
    selectedResources,
    resourceIncrementalCost: Number(breakdown.resource_incremental_cost ?? 0),
    softMilestonePenalty: Number(breakdown.soft_milestone_penalty ?? 0),
    totalCost: Number(breakdown.total_cost ?? 0),
    businessExplanation: typeof breakdown.business_explanation === "string" ? breakdown.business_explanation : "",
  };
}

function resourceCostTypeFromUnknown(value: unknown): ResourceCostType {
  return typeof value === "string" && value in resourceCostTypeLabels ? value as ResourceCostType : "none";
}

function drillGroupRefinementFromResult(result: ScheduleResult | null): DrillGroupRefinementDiagnostics | null {
  const raw = result?.stats?.drill_group_refinement ?? result?.objective_breakdown?.drill_group_refinement;
  if (!isRecord(raw)) return null;
  return {
    status: typeof raw.status === "string" ? raw.status : "not_applicable",
    coarse_group_count: Number(raw.coarse_group_count ?? 0),
    coarse_child_task_count: Number(raw.coarse_child_task_count ?? 0),
    stage2_node_count: Number(raw.stage2_node_count ?? 0),
    stage2_arc_count: Number(raw.stage2_arc_count ?? 0),
    baseline_candidate_arc_count: Number(raw.baseline_candidate_arc_count ?? 0),
    arc_reduction_ratio: Number(raw.arc_reduction_ratio ?? 0),
    adjacent_resource_switch_penalty: Number(raw.adjacent_resource_switch_penalty ?? 0),
    hole_jump_penalty: Number(raw.hole_jump_penalty ?? 0),
    makespan_tolerance: Number(raw.makespan_tolerance ?? 0),
    fallback_reason: typeof raw.fallback_reason === "string" ? raw.fallback_reason : null,
  };
}

function continuityMetricsFromResult(result: ScheduleResult | null): ContinuityMetrics | null {
  const raw = result?.stats?.continuity_metrics;
  if (!isRecord(raw)) return null;
  const splitDetails = Array.isArray(raw.same_structure_craft_split_details)
    ? raw.same_structure_craft_split_details.filter(isRecord).map((item) => ({
      structure_id: String(item.structure_id ?? ""),
      structure_name: String(item.structure_name ?? "-"),
      component_label: String(item.component_label ?? item.component_type ?? "-"),
      process_name: String(item.process_name ?? "-"),
      resource_count: Number(item.resource_count ?? 0),
      resource_names: Array.isArray(item.resource_names) ? item.resource_names.map(String) : [],
    }))
    : [];
  const jumpDetails = Array.isArray(raw.jump_transition_details)
    ? raw.jump_transition_details.filter(isRecord).map((item) => ({
      resource_id: String(item.resource_id ?? ""),
      resource_name: String(item.resource_name ?? item.resource_id ?? "-"),
      from_location: String(item.from_location ?? "-"),
      to_location: String(item.to_location ?? "-"),
      jump_distance: item.jump_distance === null || item.jump_distance === undefined ? null : Number(item.jump_distance),
      is_jump_pier: Boolean(item.is_jump_pier),
      is_side_switch: Boolean(item.is_side_switch),
      is_cross_side_jump: Boolean(item.is_cross_side_jump),
      is_direction_reversal: Boolean(item.is_direction_reversal),
    }))
    : [];
  return {
    continuity_score: Number(raw.continuity_score ?? 0),
    same_structure_craft_split_count: Number(raw.same_structure_craft_split_count ?? 0),
    jump_pier_count: Number(raw.jump_pier_count ?? 0),
    max_jump_distance: Number(raw.max_jump_distance ?? 0),
    side_switch_count: Number(raw.side_switch_count ?? 0),
    cross_side_jump_count: Number(raw.cross_side_jump_count ?? 0),
    direction_reversal_count: Number(raw.direction_reversal_count ?? 0),
    path_group_switch_count: Number(raw.path_group_switch_count ?? 0),
    same_structure_craft_split_details: splitDetails,
    jump_transition_details: jumpDetails,
    path_group_diagnostics: Array.isArray(raw.path_group_diagnostics)
      ? raw.path_group_diagnostics.filter(isRecord).map(pathGroupDiagnosticFromRecord).filter((item) => item.key)
      : [],
    resource_paths: Array.isArray(raw.resource_paths)
      ? raw.resource_paths.filter(isRecord).map((item) => ({
          resource_id: String(item.resource_id ?? ""),
          resource_name: String(item.resource_name ?? item.resource_id ?? "-"),
          resource_type: String(item.resource_type ?? ""),
          task_count: Number(item.task_count ?? 0),
          start_date: item.start_date ? String(item.start_date) : null,
          finish_date: item.finish_date ? String(item.finish_date) : null,
          jump_pier_count: Number(item.jump_pier_count ?? 0),
          side_switch_count: Number(item.side_switch_count ?? 0),
          cross_side_jump_count: Number(item.cross_side_jump_count ?? 0),
          path_group_switch_count: Number(item.path_group_switch_count ?? 0),
          path: Array.isArray(item.path)
            ? item.path.filter(isRecord).map((step) => ({
                task_id: String(step.task_id ?? ""),
                task_name: String(step.task_name ?? ""),
                location: String(step.location ?? ""),
                component_type: String(step.component_type ?? "pile") as ComponentType,
                component_label: String(step.component_label ?? ""),
                start_date: String(step.start_date ?? ""),
                finish_date: String(step.finish_date ?? ""),
              }))
            : [],
        }))
      : [],
  };
}

function hasProcessLibraryChanged(current: ProcessTemplate[], next: ProcessTemplate[]): boolean {
  if (current.length !== next.length) return true;
  return current.some((process, index) => JSON.stringify(process) !== JSON.stringify(next[index]));
}

function hasResourcePoolsChanged(current: ResourcePool[], next: ResourcePool[]): boolean {
  if (current.length !== next.length) return true;
  return current.some((pool, index) => JSON.stringify(pool) !== JSON.stringify(next[index]));
}

function hasMilestonesChanged(current: MilestoneConstraint[], next: MilestoneConstraint[]): boolean {
  if (current.length !== next.length) return true;
  return current.some((milestone, index) => JSON.stringify(milestone) !== JSON.stringify(next[index]));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, "");
  return String(value);
}

function formatMoney(value: unknown): string {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount)) return "0 元";
  return `${Math.round(amount).toLocaleString("zh-CN")} 元`;
}

function formatResourceUnitCost(resource: SelectedResourceCost): string {
  if (resource.cost_type === "none") return "-";
  if (resource.cost_type === "monthly_rental") {
    return `${formatMoney(resource.incremental_unit_cost)} / ${resource.billing_period_days} 天`;
  }
  return `${formatMoney(resource.incremental_unit_cost)} / 套台`;
}

function compareStructureIds(left: string, right: string): number {
  const a = structureSortKey(left);
  const b = structureSortKey(right);
  return (
    a.bridgeOrder - b.bridgeOrder
    || a.sideOrder - b.sideOrder
    || a.supportOrder - b.supportOrder
    || left.localeCompare(right)
  );
}

function structureSortKey(structureId: string): { bridgeOrder: number; sideOrder: number; supportOrder: number } {
  const parts = structureId.split("-");
  const bridgeOrder = numericPart(parts[0]);
  const sideOrder = parts[1] === "L" ? 0 : parts[1] === "R" ? 1 : 2;
  const supportPart = parts.length >= 3 ? parts.slice(2).join("-") : structureId;
  return {
    bridgeOrder,
    sideOrder,
    supportOrder: numericPart(supportPart),
  };
}

function numericPart(value: string | undefined): number {
  const match = value?.match(/\d+/);
  return match ? Number(match[0]) : Number.MAX_SAFE_INTEGER;
}

function groupBy<T>(items: T[], keyFn: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const key = keyFn(item);
    acc[key] = acc[key] ?? [];
    acc[key].push(item);
    return acc;
  }, {});
}

function toggleStringSet(current: Set<string>, value: string): Set<string> {
  const next = new Set(current);
  if (next.has(value)) {
    next.delete(value);
  } else {
    next.add(value);
  }
  return next;
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

async function loadAllBridgeWorkpoints(versionId: string): Promise<ProjectMasterWorkpoint[]> {
  const pageSize = 200;
  const workpoints: ProjectMasterWorkpoint[] = [];
  for (let page = 1; ; page += 1) {
    const response = await listProjectMasterWorkpoints(versionId, {
      page,
      pageSize,
      workpointType: "bridge",
    });
    workpoints.push(...response.items.filter((workpoint) => workpoint.workpoint_type === "bridge"));
    if (workpoints.length >= response.total || response.items.length < pageSize) break;
  }
  return workpoints.sort((left, right) => (
    left.sort_order - right.sort_order
    || left.workpoint_name.localeCompare(right.workpoint_name)
    || left.workpoint_id.localeCompare(right.workpoint_id)
  ));
}

function scenarioFingerprintForSolve(scenario: ScenarioInput): string {
  return serializeScenarioFingerprint(normalizeScenarioForWorkspace(scenario));
}
