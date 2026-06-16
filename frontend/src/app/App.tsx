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
  GitCompare,
  Loader2,
  Play,
  Save,
  Server,
  Sparkles,
  Upload,
  Workflow,
  X,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import {
  applyProcessNaturalLanguage as applyProcessNaturalLanguageRequest,
  compareScenarios,
  generateScheduleInput,
  getDemoScenario,
  importLocalBridgeParams,
  saveProcessLibrary,
  solveMinResources as solveMinResourcesRequest,
  solveResourceCost as solveResourceCostRequest,
  solveScenario,
  uploadBridgeParams,
} from "../api/schedulerApi";
import type {
  ComponentType,
  RelationshipType,
  WorkPointType,
  WorkSectionSide,
  ResourceMode,
  ResourceCostType,
  ControlLevel,
  ScheduleStrategy,
  ScheduleStrategyConfig,
  ResourceGuaranteeMode,
  BalanceBucket,
  TabKey,
  GanttMode,
  TaskViewMode,
  BusyState,
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
  ImportBridgeParamsResponse,
  ProcessNlChange,
  ProcessNlResponse,
  ContinuitySplitDetail,
  ContinuityJumpDetail,
  ResourcePathStep,
  ResourcePath,
  ContinuityMetrics,
  TaskViewFilters,
  TaskViewRow,
  TaskViewGroup,
  TaskViewParentGroup,
} from "../types/scheduler";

import {
  PREDECESSOR_HOVER_CLOSE_DELAY_MS,
  PREDECESSOR_HOVER_DELAY_MS,
  defaultResourceTypeByComponent,
  keyResourceComponentTypes,
  pileResourceTypeByMethod,
  pileResourceTypeByProcess,
  resourceCostTypeLabels,
  resourceModeLabels,
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
  scheduleStatusLabels,
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
  processResourceLabel,
  resourcePoolBillingPeriodDays,
  resourcePoolCostType,
  resourcePoolMode,
  resourcePoolQuantity,
  resourcePoolUnitCost,
  resourcePoolUsableLimit,
  taskResourceTypesLabel,
} from "../domain/resources";
import type { MetricTone, PlanStatusDisplay } from "../domain/scheduleDerived";
import { mergeUpperStructureLogicRules } from "../domain/upperStructureLogic";
import { SideNavigation, WorkspaceTabStrip } from "../features/layout/WorkspaceNavigation";
import { ProcessTab } from "../features/process/ProcessTab";
import { LogicTab } from "../features/logic/LogicTab";
import { ResourcesTab } from "../features/resources/ResourcesTab";
import { MilestonesTab } from "../features/milestones/MilestonesTab";
import { GlobalProcessAssistant } from "../features/assistant/GlobalProcessAssistant";
import { Metric } from "../components/common/Metric";
import { PanelTitle } from "../components/common/PanelTitle";
import {
  PredecessorPopover,
  clearPredecessorHoverTimer,
  clearPredecessorHoverTimers,
} from "../components/common/PredecessorPopover";
import type { PredecessorDetail } from "../components/common/PredecessorPopover";

const defaultScheduleStrategyConfig: ScheduleStrategyConfig = {
  strategy: "comprehensive",
  resource_guarantee: "priority",
  normal_balance_bucket: "month",
  normal_earliest_start_offset: 0,
  normal_latest_finish_offset: null,
  normal_max_early_finish_days: 60,
  max_parallel_normal_per_work_section: 5,
  enable_balance_objective: true,
};

const scheduleStrategyLabels: Record<ScheduleStrategy, string> = {
  shortest_duration: "总工期最短",
  min_resource: "资源投入最少",
  resource_cost: "资源成本最低",
  control_priority: "控制性工程优先",
  balanced_normal: "普通工程均衡推进",
  comprehensive: "控制优先 + 均衡推进",
};

const resourceGuaranteeLabels: Record<ResourceGuaranteeMode, string> = {
  strict: "严格保障",
  priority: "优先保障",
  off: "不启用",
};

const balanceBucketLabels: Record<BalanceBucket, string> = {
  week: "按周",
  month: "按月",
};

const controlLevelLabels: Record<ControlLevel, string> = {
  control: "控制性工程",
  key: "控制性工程",
  normal: "普通工程",
  rough: "普通工程",
};

const editableControlLevelOptions: Array<{ value: ControlLevel; label: string }> = [
  { value: "control", label: "控制性工程" },
  { value: "normal", label: "普通工程" },
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
  const [ganttMode, setGanttMode] = useState<GanttMode>("by_structure");
  const [savedResults, setSavedResults] = useState<ScenarioSolveResult[]>([]);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [busy, setBusy] = useState<BusyState>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastImport, setLastImport] = useState<ImportBridgeParamsResponse | null>(null);
  const [processLibraryDirty, setProcessLibraryDirty] = useState(false);

  useEffect(() => {
    void loadScenario();
  }, []);

  const scenarioFingerprint = useMemo(() => (scenario ? scenarioFingerprintForSolve(scenario) : null), [scenario]);
  const currentGenerated = scenarioFingerprint !== null && generatedScenarioFingerprint === scenarioFingerprint ? generated : null;
  const currentSolveResult = scenarioFingerprint !== null && solveResultScenarioFingerprint === scenarioFingerprint ? solveResult : null;
  const previousScenarioFingerprintRef = useRef<string | null>(null);

  useEffect(() => {
    if (previousScenarioFingerprintRef.current === null) {
      previousScenarioFingerprintRef.current = scenarioFingerprint;
      return;
    }
    if (previousScenarioFingerprintRef.current === scenarioFingerprint) return;
    previousScenarioFingerprintRef.current = scenarioFingerprint;
    setGenerated(null);
    setGeneratedScenarioFingerprint(null);
    setSolveResult(null);
    setSolveResultScenarioFingerprint(null);
    setComparison(null);
  }, [scenarioFingerprint]);

  async function loadScenario() {
    setBusy("loading");
    setError(null);
    try {
      const demo = await getDemoScenario();
      const imported = await importLocalBridgeParams(demo);
      setScenario(imported.scenario);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      setLastImport(imported);
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
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    const nextGenerated = await generateScheduleInput(requestScenario);
    setGenerated(nextGenerated);
    setGeneratedScenarioFingerprint(requestFingerprint);
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
    const requestScenario = scenario;
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
    const requestScenario = scenario;
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    const hasHardMilestone = scenario.milestones.some((milestone) => milestone.mode === "hard");
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
    const requestScenario = scenario;
    const requestFingerprint = scenarioFingerprintForSolve(requestScenario);
    const hasHardMilestone = scenario.milestones.some((milestone) => milestone.mode === "hard");
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
    const solved = await solveScenario(nextScenario);
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

  async function importBridgeParams(file: File, targetBridge: string) {
    if (!scenario) return;
    setBusy("importing");
    setError(null);
    try {
      const payload = new FormData();
      payload.append("file", file);
      payload.append("scenario", JSON.stringify(scenario));
      if (targetBridge.trim()) {
        payload.append("target_bridge", targetBridge.trim());
      }
      const imported = await uploadBridgeParams(payload);
      const nextScenario: ScenarioInput = { ...imported.scenario, task_overrides: {} };
      const nextFingerprint = scenarioFingerprintForSolve(nextScenario);
      previousScenarioFingerprintRef.current = nextFingerprint;
      setScenario(nextScenario);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      setLastImport({ ...imported, scenario: nextScenario });
      await generateTaskViewForScenario(nextScenario, { openTasks: true });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function applyProcessNaturalLanguage(prompt: string): Promise<ProcessNlResponse | null> {
    if (!scenario) return null;
    setBusy("nl");
    setError(null);
    try {
      const result = await applyProcessNaturalLanguageRequest({ scenario, prompt });
      const resultFingerprint = scenarioFingerprintForSolve(result.scenario);
      previousScenarioFingerprintRef.current = resultFingerprint;
      setScenario(result.scenario);
      if (hasProcessLibraryChanged(scenario.process_library, result.scenario.process_library)) {
        setProcessLibraryDirty(true);
      }
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
      await generateTaskViewForScenario(result.scenario, { openTasks: false });
      return result;
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
    setScenario((current) => (current ? { ...current, ...patch } : current));
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
    if (!scenario) return;
    setBusy("savingProcessLibrary");
    setError(null);
    try {
      const processLibrary = await saveProcessLibrary({
        process_library: scenario.process_library,
      });
      setScenario((current) => (current ? { ...current, process_library: processLibrary } : current));
      setProcessLibraryDirty(false);
      setGenerated(null);
      setGeneratedScenarioFingerprint(null);
      setSolveResult(null);
      setSolveResultScenarioFingerprint(null);
      setComparison(null);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  function updateLogic(index: number, patch: Partial<LogicRule>) {
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

  function updateResourcePool(index: number, patch: Partial<ResourcePool>) {
    setScenario((current) =>
      current
        ? {
            ...current,
            resource_pools: current.resource_pools.map((pool, poolIndex) =>
              poolIndex === index ? { ...pool, ...patch } : pool,
            ),
          }
        : current,
    );
  }

  function updateMilestone(index: number, patch: Partial<MilestoneConstraint>) {
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
    previousScenarioFingerprintRef.current = nextFingerprint;
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

  function renderModule(tabKey: TabKey) {
    if (!scenario && tabKey !== "results") {
      return <div className="empty">正在加载场景...</div>;
    }

    switch (tabKey) {
      case "process":
        return scenario ? (
          <ProcessTab
            scenario={scenario}
            onUpdateProcess={updateProcess}
            onSaveProcessLibrary={saveCurrentProcessLibrary}
            savingProcessLibrary={busy === "savingProcessLibrary"}
            processLibraryDirty={processLibraryDirty}
          />
        ) : null;
      case "logic":
        return scenario ? (
          <LogicTab
            scenario={scenario}
            onUpdateLogic={updateLogic}
            onUpdateUpperStructureLogic={updateUpperStructureLogic}
          />
        ) : null;
      case "resources":
        return scenario ? <ResourcesTab scenario={scenario} onUpdateResourcePool={updateResourcePool} /> : null;
      case "milestones":
        return scenario ? <MilestonesTab scenario={scenario} onUpdateMilestone={updateMilestone} scopeLabelForMilestone={scopeLabel} /> : null;
      case "tasks":
        return scenario ? (
          <TaskViewTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onGenerateTaskView={generateOnly}
            onImportBridgeParams={importBridgeParams}
            onUpdateTaskProcess={updateTaskProcessAndGenerate}
            onUpdateStructureControlLevel={updateStructureControlLevel}
            busy={busy}
          />
        ) : null;
      case "results":
        return (
          <ResultsTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
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
            comparison={comparison}
            onCompare={() => void compareSavedResults()}
            comparing={busy === "comparing"}
          />
        );
    }
  }

  return (
    <div className="app-shell">
      <div className="app-body">
        <SideNavigation activeTab={activeTab} openTabs={openTabs} onOpen={openModule} />

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

        <div className="workspace-content">
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
          />
        )}
        {scenario && activeTab === "resources" && (
          <ResourcesTab scenario={scenario} onUpdateResourcePool={updateResourcePool} />
        )}
        {scenario && activeTab === "milestones" && (
          <MilestonesTab scenario={scenario} onUpdateMilestone={updateMilestone} scopeLabelForMilestone={scopeLabel} />
        )}
        {scenario && activeTab === "tasks" && (
          <TaskViewTab
            scenario={scenario}
            generated={currentGenerated}
            solveResult={currentSolveResult}
            onGenerateTaskView={generateOnly}
            onImportBridgeParams={importBridgeParams}
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
            comparison={comparison}
            onCompare={() => void compareSavedResults()}
            comparing={busy === "comparing"}
          />
        )}
        </div>
      </main>
      {scenario && (
        <GlobalProcessAssistant
          onApplyProcessNaturalLanguage={applyProcessNaturalLanguage}
          applyingProcessText={busy === "nl"}
        />
      )}
    </div>
    </div>
  );
}

function TaskViewTab({
  scenario,
  generated,
  solveResult,
  onGenerateTaskView,
  onImportBridgeParams,
  onUpdateTaskProcess,
  onUpdateStructureControlLevel,
  busy,
}: {
  scenario: ScenarioInput;
  generated: GeneratedScheduleInput | null;
  solveResult: ScenarioSolveResult | null;
  onGenerateTaskView: () => void;
  onImportBridgeParams: (file: File, targetBridge: string) => void;
  onUpdateTaskProcess: (task: Task, patch: TaskOverride) => void;
  onUpdateStructureControlLevel: (task: Task, controlLevel: ControlLevel) => void;
  busy: BusyState;
}) {
  const [groupMode, setGroupMode] = useState<TaskViewMode>("by_structure");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filters, setFilters] = useState<TaskViewFilters>({
    structureText: "",
    processText: "",
  });
  const [collapsedTaskParents, setCollapsedTaskParents] = useState<Set<string>>(() => new Set());
  const [collapsedTaskGroups, setCollapsedTaskGroups] = useState<Set<string>>(() => new Set());
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const [predecessorAnchorRect, setPredecessorAnchorRect] = useState<DOMRect | null>(null);
  const predecessorHoverOpenTimerRef = useRef<number | null>(null);
  const predecessorHoverCloseTimerRef = useRef<number | null>(null);
  const generatedForDetails = solveResult?.generated ?? generated;
  const workSectionDisplayById = useMemo(
    () => buildWorkSectionDisplayById(scenario.project),
    [scenario.project],
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
    () => buildTaskViewRows(generatedForDetails, scenario, linksBySuccessor, workSectionDisplayById),
    [generatedForDetails, linksBySuccessor, scenario, workSectionDisplayById],
  );
  const filteredRows = useMemo(() => filterTaskViewRows(rows, filters), [filters, rows]);
  const structureParents = useMemo(() => buildTaskViewStructureParents(filteredRows, scenario), [filteredRows, scenario]);
  const processGroups = useMemo(() => buildTaskViewGroups(filteredRows, "by_process"), [filteredRows]);
  const importing = busy === "importing";
  const generating = busy === "generating";
  const refreshingTaskGraph = generating || importing;

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
          <td>{row.task.quantity_label || displayValue(row.task.quantity)}</td>
          <td>{effectiveTaskDurationDays(row.task, scenario)} 天</td>
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
    <div className="task-view-grid">
      <section className="panel full task-view-header-panel">
        <PanelTitle
          title="任务视图"
          subtitle="调用 OR-Tools CP-SAT 前核验结构物识别、工期计算和工艺逻辑关系"
          action={
            <div className="task-view-title-actions">
              <div className="task-view-import-action">
                <input
                  type="file"
                  accept=".xlsx,.xlsm"
                  onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
                />
                <button
                  className="secondary"
                  type="button"
                  disabled={!selectedFile || importing}
                  onClick={() => selectedFile && onImportBridgeParams(selectedFile, "")}
                >
                  {importing ? <Loader2 className="spin" size={16} /> : <Upload size={16} />}
                  导入 Excel
                </button>
              </div>
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
    </div>
  );
}

function ResultsTab({
  scenario,
  generated,
  solveResult,
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
  comparison,
  onCompare,
  comparing,
}: {
  scenario: ScenarioInput | null;
  generated: GeneratedScheduleInput | null;
  solveResult: ScenarioSolveResult | null;
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
  comparison: CompareResponse | null;
  onCompare: () => void;
  comparing: boolean;
}) {
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const [predecessorAnchorRect, setPredecessorAnchorRect] = useState<DOMRect | null>(null);
  const [selectedResultIndex, setSelectedResultIndex] = useState(0);
  const predecessorHoverOpenTimerRef = useRef<number | null>(null);
  const predecessorHoverCloseTimerRef = useRef<number | null>(null);
  const resultOptions = useMemo(() => scenarioResultOptions(solveResult), [solveResult]);
  const activeSolveResult = resultOptions[Math.min(selectedResultIndex, Math.max(0, resultOptions.length - 1))] ?? null;
  const result = activeSolveResult?.result ?? null;
  const planStatus = useMemo(() => derivePlanStatus(result), [result]);
  const summary = useMemo(() => buildSummary(scenario, generated, activeSolveResult), [scenario, generated, activeSolveResult]);
  const generatedForDetails = activeSolveResult?.generated ?? generated;
  const recommendedResourceCounts = recommendedResourceCountsFromResult(result);
  const resourceRecommendationStatus = resourceRecommendationStatusFromResult(result);
  const resourceRecommendationMessage = resourceRecommendationMessageFromResult(result);
  const resourceUpperBoundCounts = resourceUpperBoundCountsFromResult(result);
  const resourceCapacityLowerBounds = resourceCapacityLowerBoundsFromResult(result);
  const showResourceRecommendation = shouldShowResourceRecommendation(result, recommendedResourceCounts);
  const showResourceRecommendationDiagnostic = shouldShowResourceRecommendationDiagnostic(resourceRecommendationStatus, resourceRecommendationMessage);
  const resourceCostSummary = resourceCostSummaryFromResult(result);
  const continuityMetrics = continuityMetricsFromResult(result);
  const strategyConfig = withDefaultScheduleStrategy(scenario?.schedule_strategy);
  const workSectionDisplayById = useMemo(
    () => buildWorkSectionDisplayById(scenario?.project ?? null),
    [scenario?.project],
  );
  const diagnostics = useMemo(() => {
    const messages = activeSolveResult?.diagnostics ?? generated?.validation ?? [];
    if (!planStatus.diagnostic) return messages;
    const alreadyIncluded = messages.some((message) => message.subject_id === planStatus.diagnostic?.subject_id);
    return alreadyIncluded ? messages : [planStatus.diagnostic, ...messages];
  }, [activeSolveResult, generated, planStatus.diagnostic]);
  const scheduledTaskById = useMemo(
    () => new Map((result?.tasks ?? []).map((task) => [task.id, task])),
    [result],
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
  }, [solveResult]);

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
    onPatchScenario({ schedule_strategy: { ...strategyConfig, ...patch } });
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
    <div className="results-grid">
      {scenario && (
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
              求解时限(秒)
              <input
                type="number"
                min={1}
                value={scenario.time_limit_seconds}
                onChange={(event) => onPatchScenario({ time_limit_seconds: Number(event.target.value) })}
              />
            </label>
            <label>
              排程策略
              <select
                value={strategyConfig.strategy}
                onChange={(event) => updateStrategyConfig({ strategy: event.target.value as ScheduleStrategy })}
              >
                {Object.entries(scheduleStrategyLabels).map(([value, label]) => (
                  <option value={value} key={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              资源保障
              <select
                value={strategyConfig.resource_guarantee}
                onChange={(event) => updateStrategyConfig({ resource_guarantee: event.target.value as ResourceGuaranteeMode })}
              >
                {Object.entries(resourceGuaranteeLabels).map(([value, label]) => (
                  <option value={value} key={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              均衡周期
              <select
                value={strategyConfig.normal_balance_bucket}
                onChange={(event) => updateStrategyConfig({ normal_balance_bucket: event.target.value as BalanceBucket })}
              >
                {Object.entries(balanceBucketLabels).map(([value, label]) => (
                  <option value={value} key={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              普通工程最早开始(天)
              <input
                type="number"
                min={0}
                value={strategyConfig.normal_earliest_start_offset}
                onChange={(event) => updateStrategyConfig({ normal_earliest_start_offset: Math.max(0, Number(event.target.value)) })}
              />
            </label>
            <label>
              普通工程最晚完成(天)
              <input
                type="number"
                min={1}
                value={strategyConfig.normal_latest_finish_offset ?? ""}
                placeholder="不限制"
                onChange={(event) => updateStrategyConfig({
                  normal_latest_finish_offset: event.target.value ? Math.max(1, Number(event.target.value)) : null,
                })}
              />
            </label>
            <label>
              工区普通工程最大并行
              <input
                type="number"
                min={1}
                value={strategyConfig.max_parallel_normal_per_work_section}
                onChange={(event) => updateStrategyConfig({
                  max_parallel_normal_per_work_section: Math.max(1, Number(event.target.value)),
                })}
              />
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={strategyConfig.enable_balance_objective}
                onChange={(event) => updateStrategyConfig({ enable_balance_objective: event.target.checked })}
              />
              启用普通工程均衡目标
            </label>
          </div>
        </section>
      )}

      <section className="summary-band">
        <Metric label="计划状态" value={planStatus.label} tone={planStatus.tone} hint={planStatus.hint} icon={<Server size={18} />} />
        <Metric label="总工期" value={summary.days} tone="neutral" icon={<CalendarDays size={18} />} />
        <Metric label="工作项" value={summary.tasks} tone="neutral" icon={<CheckCircle2 size={18} />} />
        <Metric label="资源 / 里程碑" value={summary.resourcesAndMilestones} tone="neutral" icon={<Flag size={18} />} />
      </section>

      {resultOptions.length > 1 && (
        <section className="panel full">
          <PanelTitle title="方案输出" subtitle="固定资源方案与可行最少资源方案" />
          <div className="segmented result-switcher">
            {resultOptions.map((option, index) => (
              <button
                className={selectedResultIndex === index ? "active" : ""}
                key={`${option.scenario_id}-${index}`}
                onClick={() => setSelectedResultIndex(index)}
                type="button"
              >
                {index === 0 ? "方案1 当前资源" : `方案${index + 1} 最少资源`}
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
                  const item = resultOptionSummary(option);
                  return (
                    <tr key={`${option.scenario_id}-${index}`}>
                      <td>{index === 0 ? "方案1 当前资源" : `方案${index + 1} 最少资源`}</td>
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
          <div className="actions inline">
            <button className="secondary" onClick={() => onSaveCurrent(activeSolveResult)} disabled={!activeSolveResult}>
              <Save size={15} />
              保存方案
            </button>
            <button className="secondary" onClick={onCompare} disabled={!savedResults.length || comparing}>
              {comparing ? <Loader2 className="spin" size={15} /> : <GitCompare size={15} />}
              对比
            </button>
          </div>
        </div>
        <div className="diagnostics">
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
          {!solveResult && !generated && busy !== "solving" && <div className="empty">等待生成或求解</div>}
        </div>
      </section>

      {showResourceRecommendationDiagnostic && (
        <section className="panel full">
          <PanelTitle title="资源增量诊断" subtitle="当前资源上限探测、最少资源求解和关键路径检查结果" />
          <div className="diagnostics">
            <div className={`diagnostic ${resourceRecommendationStatus === "resource_upper_bound_infeasible" || resourceRecommendationStatus === "critical_path_infeasible" ? "error" : "warning"}`}>
              <strong>{resourceRecommendationStatus === "resource_upper_bound_infeasible" ? "上限不可行" : "未输出推荐"}</strong>
              <span>{resourceRecommendationMessage}</span>
            </div>
            {resourceCapacityLowerBounds.filter((item) => item.exceeds_upper_bound).map((item) => (
              <div className="diagnostic error" key={item.resource_pool_id}>
                <strong>瓶颈资源</strong>
                <span>{item.label} 按目标窗口约需 {item.required_minimum} 个，当前上限 {item.max_quantity} 个。</span>
              </div>
            ))}
          </div>
          {resourceUpperBoundCounts.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>资源</th>
                    <th>当前数量</th>
                    <th>上限数量</th>
                    <th>可增容量</th>
                  </tr>
                </thead>
                <tbody>
                  {resourceUpperBoundCounts.map((item) => (
                    <tr key={item.resource_pool_id}>
                      <td>{item.label}</td>
                      <td>{item.current_quantity}</td>
                      <td>{item.upper_bound_quantity}</td>
                      <td>{item.additional_capacity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {showResourceRecommendation && (
        <section className="panel full">
          <PanelTitle title="资源增量建议" subtitle="为满足强制里程碑目标建议配置的资源数量" />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>资源</th>
                  <th>当前数量</th>
                  <th>推荐数量</th>
                  <th>新增数量</th>
                  <th>最大数量</th>
                </tr>
              </thead>
              <tbody>
                {recommendedResourceCounts.map((item) => (
                  <tr key={item.resource_pool_id}>
                    <td>{item.label}</td>
                    <td>{item.current_quantity}</td>
                    <td>{item.recommended_quantity}</td>
                    <td>{item.added_quantity}</td>
                    <td>{item.max_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
        <PanelTitle title="里程碑结果" subtitle="软节点允许超期，迟延天数会进入加权目标" />
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
          title="计划表"
          subtitle={result?.plan_finish_date ? `${result.plan_start_date} 至 ${result.plan_finish_date}` : "等待求解"}
        />
        <div className="table-wrap plan">
          <table>
            <thead>
              <tr>
                <th>工作项</th>
                <th>幅别</th>
                <th>构件</th>
                <th>计划表达式</th>
                <th>工期</th>
                <th>计划开始</th>
                <th>计划完成</th>
                <th>资源</th>
                <th>前置数</th>
              </tr>
            </thead>
            <tbody>
              {result?.tasks.map((task) => {
                const isOpen = openPredecessorTaskId === task.id;
                return (
                  <tr key={task.id}>
                    <td>{task.name}</td>
                    <td><span className="side-tag">{workSectionLabelForTask(task, workSectionDisplayById)}</span></td>
                    <td><span className="tag">{componentLabels[task.component_type]}</span></td>
                    <td className="duration-expression" title={durationExpression(task, scenario)}>
                      {durationExpression(task, scenario)}
                    </td>
                    <td>{effectiveTaskDurationDays(task, scenario)} 天</td>
                    <td>{task.start_date}</td>
                    <td>{task.finish_date}</td>
                    <td>{task.assigned_resource_name ?? "-"}</td>
                    <td className="predecessor-cell">
                      {task.predecessor_ids.length > 0 ? (
                        <button
                          className="predecessor-count has-items"
                          type="button"
                          onMouseEnter={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                          onMouseLeave={schedulePredecessorPopoverClose}
                          onFocus={(event) => showPredecessorPopover(task.id, event.currentTarget)}
                          onBlur={schedulePredecessorPopoverClose}
                          aria-expanded={isOpen}
                        >
                          {task.predecessor_ids.length}
                        </button>
                      ) : (
                        <span className="predecessor-zero">0</span>
                      )}
                      {isOpen && (
                        <PredecessorPopover
                          task={task}
                          details={predecessorDetails(task)}
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
      </section>

      <section className="panel full">
        <div className="panel-title">
          <div>
            <h2>甘特图</h2>
            <span>{ganttMode === "by_structure" ? "按墩台聚类，墩号从小到大" : "按工艺聚类，子级按计划先后展示"}</span>
          </div>
          <div className="segmented">
            <button className={ganttMode === "by_structure" ? "active" : ""} onClick={() => onGanttModeChange("by_structure")}>
              按墩台
            </button>
            <button className={ganttMode === "by_process" ? "active" : ""} onClick={() => onGanttModeChange("by_process")}>
              按工艺
            </button>
          </div>
        </div>
        <Gantt
          tasks={result?.tasks ?? []}
          makespan={Math.max(result?.objective_days ?? 1, 1)}
          mode={ganttMode}
          workSectionDisplayById={workSectionDisplayById}
        />
      </section>

      <section className="panel full">
        <PanelTitle title="资源泳道" subtitle="横轴按计划时间展示每条资源的占用连续性" />
        <ResourceLanes
          allocations={result?.resource_allocations ?? []}
          makespan={Math.max(result?.objective_days ?? 1, 1)}
        />
      </section>

      <section className="panel full">
        <PanelTitle title="资源路径图" subtitle="按施工先后展示资源经过的左/右幅-墩号序列" />
        <ResourcePathChart resourcePaths={continuityMetrics?.resource_paths ?? []} />
      </section>

      <section className="panel full">
        <PanelTitle title="方案对比" subtitle={`${savedResults.length} 个已保存方案`} />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>方案</th>
                <th>状态</th>
                <th>总工期</th>
                <th>软节点迟延数</th>
                <th>软罚分</th>
                <th>综合分</th>
              </tr>
            </thead>
            <tbody>
              {comparison?.summaries.map((item) => (
                <tr key={String(item.scenario_id)}>
                  <td>{String(item.scenario_name)}</td>
                  <td>{formatScheduleStatus(item.status)}</td>
                  <td>{String(item.total_days ?? "-")}</td>
                  <td>{String(item.soft_late_count ?? 0)}</td>
                  <td>{String(item.soft_penalty ?? 0)}</td>
                  <td>{String(item.score ?? "-")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Gantt({
  tasks,
  makespan,
  mode,
  workSectionDisplayById,
}: {
  tasks: ScheduledTask[];
  makespan: number;
  mode: GanttMode;
  workSectionDisplayById: Map<string, WorkSectionDisplay>;
}) {
  if (!tasks.length) return <div className="empty">暂无排程结果</div>;
  const groups = buildGanttGroups(tasks, mode, workSectionDisplayById);
  return (
    <div className="gantt">
      {groups.map((group) => (
        <div className="gantt-group" key={group.id}>
          <div className="gantt-group-title">
            <strong>{group.title}</strong>
            <span>{group.startDate} 至 {group.finishDate}</span>
          </div>
          {group.tasks.map((task) => {
            const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
            return (
              <div className="gantt-row" key={task.id}>
                <div className="gantt-label">
                  {sideLabel !== "-" && <span className="side-tag mini">{sideLabel}</span>}
                  <span className="gantt-task-name">{task.name}</span>
                </div>
                <div className="gantt-track">
                  <div
                    className="gantt-bar"
                    style={{
                      left: `${(task.start_offset / makespan) * 100}%`,
                      width: `${Math.max(((task.end_offset - task.start_offset) / makespan) * 100, 1.2)}%`,
                      backgroundColor: componentColors[task.component_type],
                    }}
                    title={ganttTaskHoverTitle(task, sideLabel)}
                  >
                    <span>{task.duration_days}d</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function ResourceLanes({
  allocations,
  makespan,
}: {
  allocations: ResourceAllocation[];
  makespan: number;
}) {
  if (!allocations.length) return <div className="empty">暂无资源分配</div>;
  const groups = groupBy(allocations, (item) => item.resource_id);
  return (
    <div className="lanes">
      {Object.entries(groups).map(([, items]) => (
        <div className="lane-row" key={items[0].resource_id}>
          <div className="lane-label">
            <strong>{items[0].resource_name}</strong>
            <code>{items[0].resource_type}</code>
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
                title={allocationHoverTitle(allocation)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function ResourcePathChart({ resourcePaths }: { resourcePaths: ResourcePath[] }) {
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
            <div className="resource-path-sequence" title={resourcePathHoverTitle(path, labels)}>
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

function ganttTaskHoverTitle(task: ScheduledTask, sideLabel = "-"): string {
  return [
    `工作项：${task.name}`,
    `幅别：${sideLabel}`,
    `构件：${componentLabels[task.component_type]}`,
    `计划：${task.start_date} 至 ${task.finish_date}`,
    `工期：${task.duration_days} 天`,
    `分配资源：${task.assigned_resource_name ?? "-"}`,
    `资源序列：${task.assigned_resource_id ?? "-"}`,
    `资源类型：${task.assigned_resource_type ?? "-"}`,
  ].join("\n");
}

function allocationHoverTitle(allocation: ResourceAllocation): string {
  return [
    `工作项：${allocation.task_name}`,
    `计划：${allocation.start_date} 至 ${allocation.finish_date}`,
    `分配资源：${allocation.resource_name}`,
    `资源序列：${allocation.resource_id}`,
    `资源类型：${allocation.resource_type}`,
  ].join("\n");
}

function resourcePathHoverTitle(path: ResourcePath, labels: string[]): string {
  return [
    `资源：${path.resource_name}`,
    `资源类型：${path.resource_type}`,
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

function buildWorkSectionDisplayById(project: ProjectModel | null): Map<string, WorkSectionDisplay> {
  const result = new Map<string, WorkSectionDisplay>();
  if (!project) return result;
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      const hasSide = section.side && section.side !== "none";
      const label = hasSide ? sideLabels[section.side] : section.name || "-";
      const shortLabel = section.side === "left" ? "左" : section.side === "right" ? "右" : label;
      result.set(section.id, { label, shortLabel });
    }
  }
  return result;
}

function workSectionLabelForTask(task: Task, workSectionDisplayById: Map<string, WorkSectionDisplay>): string {
  if (!task.work_section_id) return "-";
  return workSectionDisplayById.get(task.work_section_id)?.label ?? "-";
}

function titleWithWorkSectionLabel(title: string, task: Task, workSectionDisplayById: Map<string, WorkSectionDisplay>): string {
  const sideLabel = workSectionLabelForTask(task, workSectionDisplayById);
  if (sideLabel === "-" || title.includes(sideLabel)) return title;
  return `${sideLabel} ${title}`;
}

function buildGanttGroups(
  tasks: ScheduledTask[],
  mode: GanttMode,
  workSectionDisplayById: Map<string, WorkSectionDisplay>,
) {
  if (mode === "by_process") {
    return componentOrder
      .map((component) => {
        const children = tasks
          .filter((task) => task.component_type === component)
          .sort((a, b) => a.start_offset - b.start_offset || compareStructureIds(a.structure_id, b.structure_id));
        return { id: component, title: componentLabels[component], tasks: children, ...taskDateRange(children) };
      })
      .filter((group) => group.tasks.length > 0);
  }

  return Object.entries(groupBy(tasks, (task) => task.structure_id))
    .sort(([left], [right]) => compareStructureIds(left, right))
    .map(([structureId, children]) => ({
      id: structureId,
      title: titleWithWorkSectionLabel(children[0].structure_name, children[0], workSectionDisplayById),
      tasks: children.sort(
        (a, b) =>
          componentOrder.indexOf(a.component_type) - componentOrder.indexOf(b.component_type)
          || a.start_offset - b.start_offset
          || a.name.localeCompare(b.name),
      ),
      ...taskDateRange(children),
    }));
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
): TaskViewRow[] {
  if (!generated) return [];
  const projectMaps = buildTaskViewProjectMaps(scenario?.project ?? null);
  const rows = generated.schedule_input.tasks.map((task) => {
    const bridge = task.bridge_id ? projectMaps.bridges.get(task.bridge_id) : undefined;
    const section = task.work_section_id ? projectMaps.sections.get(task.work_section_id) : undefined;
    const structure = projectMaps.structures.get(task.structure_id);
    const bridgeName = bridge?.name ?? task.bridge_id ?? "-";
    const sectionName = section?.name ?? task.work_section_id ?? "-";
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

function buildTaskViewProjectMaps(project: ProjectModel | null) {
  const bridges = new Map<string, { name: string; order: number }>();
  const sections = new Map<string, { name: string; order: number }>();
  const structures = new Map<string, { label: string; order: number }>();
  const continuousBeamGroups = new Map<string, { id: string; label: string }>();

  if (!project) return { bridges, sections, structures, continuousBeamGroups };
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

function filterTaskViewRows(rows: TaskViewRow[], filters: TaskViewFilters): TaskViewRow[] {
  const structureNeedle = filters.structureText.trim().toLowerCase();
  const processNeedle = filters.processText.trim().toLowerCase();

  return rows.filter((row) => {
    if (structureNeedle && !row.searchText.includes(structureNeedle)) return false;
    if (processNeedle) {
      const processText = `${row.task.process_name} ${componentLabels[row.task.component_type]}`.toLowerCase();
      if (!processText.includes(processNeedle)) return false;
    }
    return true;
  });
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
    method_id: override.method_id ?? process?.method_id ?? process?.id ?? processId ?? null,
    productivity_option_id: override.productivity_option_id ?? optionId ?? null,
    enabled: true,
    properties: {},
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
  if (quantitySource === "count" && component.component_type === "pile") {
    return { value, label: displayValue(value) };
  }
  if (quantitySource === "count" && isContinuousStandardSegmentQuantity(component, task)) {
    return { value, label: component.quantity_label || task.quantity_label || displayValue(value) };
  }
  return {
    value,
    label: component.quantity_label || task.quantity_label || `${displayValue(value)}${quantityUnitForSource(quantitySource)}`,
  };
}

function localQuantityValueForTask(component: ComponentModel, task: Task, quantitySource: string): number {
  if (quantitySource === "count") {
    if (isContinuousStandardSegmentQuantity(component, task)) {
      return positiveNumber(component.quantity, task.quantity, 1);
    }
    return 1;
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
    return positiveNumber(
      componentPropertyNumber(component, ["heightM", "height_m", "pierHeightM", "pier_height_m"]),
      component.quantity,
      task.quantity,
      1,
    );
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
  const quantityText = isContinuousStandardSegment
    ? (task.quantity_label || `${displayValue(task.quantity)}块`)
    : `${quantityName}${displayValue(task.quantity)}${quantityUnitForSource(effectiveOption.quantity_source)}`;
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
  return {
    days: solveResult?.result.objective_days ? `${solveResult.result.objective_days} 天` : "-",
    tasks: generated?.schedule_input.tasks.length ? `${generated.schedule_input.tasks.length} 项` : "-",
    resourcesAndMilestones: `${resourceCount} / ${milestoneCount}`,
  };
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

function resultOptionSummary(option: ScenarioSolveResult): { resourceCount: number; addedResourceCount: number } {
  const recommendedCounts = recommendedResourceCountsFromResult(option.result);
  if (recommendedCounts.length) {
    return {
      resourceCount: recommendedCounts.reduce((sum, item) => sum + item.recommended_quantity, 0),
      addedResourceCount: recommendedCounts.reduce((sum, item) => sum + item.added_quantity, 0),
    };
  }
  const allocatedResourceIds = new Set(option.result.resource_allocations.map((item) => item.resource_id));
  return {
    resourceCount: allocatedResourceIds.size || option.generated.schedule_input.resources.length,
    addedResourceCount: 0,
  };
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
  label: string;
  current_quantity: number;
  recommended_quantity: number;
  added_quantity: number;
  max_quantity: number;
};

type ResourceUpperBoundCount = {
  resource_pool_id: string;
  label: string;
  current_quantity: number;
  upper_bound_quantity: number;
  additional_capacity: number;
  max_quantity: number;
};

type ResourceCapacityLowerBound = {
  resource_pool_id: string;
  label: string;
  required_minimum: number;
  max_quantity: number;
  exceeds_upper_bound: boolean;
};

function recommendedResourceCountsFromResult(result: ScheduleResult | null): RecommendedResourceCount[] {
  const raw = result?.stats?.recommended_resource_counts ?? result?.objective_breakdown?.recommended_resource_counts;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      resource_pool_id: String(item.resource_pool_id ?? item.resource_type ?? item.label ?? ""),
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

function resourceRecommendationMessageFromResult(result: ScheduleResult | null): string {
  const raw = result?.stats?.resource_recommendation_message ?? result?.objective_breakdown?.resource_recommendation_message;
  return typeof raw === "string" ? raw : "";
}

function shouldShowResourceRecommendation(result: ScheduleResult | null, counts: RecommendedResourceCount[]): boolean {
  if (!counts.length) return false;
  const status = resourceRecommendationStatusFromResult(result);
  if (status) return status === "recommended_resources_verified";
  const solveMode = result?.objective_breakdown?.solve_mode ?? result?.stats?.solve_mode;
  return solveMode === "min_resources_fixed_duration";
}

function shouldShowResourceRecommendationDiagnostic(status: string, message: string): boolean {
  return Boolean(
    message
    && status
    && !["recommended_resources_verified", "not_needed", "not_evaluated"].includes(status),
  );
}

function resourceUpperBoundCountsFromResult(result: ScheduleResult | null): ResourceUpperBoundCount[] {
  const raw = result?.stats?.resource_upper_bound_counts ?? result?.objective_breakdown?.resource_upper_bound_counts;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(isRecord)
    .map((item) => {
      const maxQuantity = Number(item.max_quantity ?? item.upper_bound_quantity ?? 0);
      return {
        resource_pool_id: String(item.resource_pool_id ?? item.resource_type ?? item.label ?? ""),
        label: String(item.label ?? item.resource_type ?? "-"),
        current_quantity: Number(item.current_quantity ?? 0),
        upper_bound_quantity: Number(item.upper_bound_quantity ?? maxQuantity),
        additional_capacity: Number(item.additional_capacity ?? Math.max(0, maxQuantity - Number(item.current_quantity ?? 0))),
        max_quantity: maxQuantity,
      };
    })
    .filter((item) => item.resource_pool_id);
}

function resourceCapacityLowerBoundsFromResult(result: ScheduleResult | null): ResourceCapacityLowerBound[] {
  const raw = result?.stats?.resource_capacity_lower_bounds ?? result?.objective_breakdown?.resource_capacity_lower_bounds;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter(isRecord)
    .map((item) => ({
      resource_pool_id: String(item.resource_pool_id ?? item.resource_type ?? item.label ?? ""),
      label: String(item.label ?? item.resource_type ?? "-"),
      required_minimum: Number(item.required_minimum ?? 0),
      max_quantity: Number(item.max_quantity ?? 0),
      exceeds_upper_bound: Boolean(item.exceeds_upper_bound),
    }))
    .filter((item) => item.resource_pool_id);
}

function withDefaultScheduleStrategy(config?: ScheduleStrategyConfig | null): ScheduleStrategyConfig {
  return { ...defaultScheduleStrategyConfig, ...(config ?? {}) };
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
    same_structure_craft_split_details: splitDetails,
    jump_transition_details: jumpDetails,
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

function taskDateRange(tasks: ScheduledTask[]): { startDate: string; finishDate: string } {
  if (!tasks.length) return { startDate: "-", finishDate: "-" };
  const first = tasks.reduce((current, task) => (task.start_offset < current.start_offset ? task : current), tasks[0]);
  const last = tasks.reduce((current, task) => (task.end_offset > current.end_offset ? task : current), tasks[0]);
  return { startDate: first.start_date, finishDate: last.finish_date };
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

function scenarioFingerprintForSolve(scenario: ScenarioInput): string {
  return JSON.stringify(scenario);
}

function formatScheduleStatus(value: unknown): string {
  if (typeof value === "string" && Object.prototype.hasOwnProperty.call(scheduleStatusLabels, value)) {
    return scheduleStatusLabels[value as ScheduleResult["status"]];
  }
  return value == null ? "-" : String(value);
}
