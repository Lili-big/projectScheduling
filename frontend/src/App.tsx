import {
  AlertCircle,
  Bot,
  CalendarDays,
  CheckCircle2,
  Database,
  Flag,
  GitCompare,
  Layers3,
  Loader2,
  Play,
  Save,
  Server,
  Sparkles,
  Upload,
  Workflow,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

type ComponentType =
  | "pile"
  | "cap"
  | "spread_foundation"
  | "ground_tie_beam"
  | "middle_tie_beam"
  | "pier_body"
  | "cap_beam"
  | "abutment_body";
type RelationshipType = "FS" | "SS";
type WorkPointType = "road" | "bridge" | "tunnel";
type WorkSectionSide = "left" | "right" | "none";
type TabKey = "project" | "process" | "logic" | "resources" | "milestones" | "results";
type GanttMode = "by_structure" | "by_process";

type ComponentModel = {
  id: string;
  name: string;
  component_type: ComponentType;
  quantity: number;
  quantity_label: string;
  method_id?: string | null;
  productivity_option_id?: string | null;
  enabled: boolean;
  properties: Record<string, unknown>;
};

type UpperStructureModel = {
  id: string;
  name: string;
  structure_type: string;
  side: WorkSectionSide;
  span_index: number;
  support_range: string;
  span_length_m: number;
  beam_count_per_span?: number | null;
  span_group_expression: string;
  properties: Record<string, unknown>;
};

type StructureModel = {
  id: string;
  name: string;
  structure_type: "pier" | "abutment";
  order: number;
  support_no?: string | null;
  support_index?: number | null;
  components: ComponentModel[];
};

type WorkSection = {
  id: string;
  name: string;
  order: number;
  side: WorkSectionSide;
  structures: StructureModel[];
  upper_structures: UpperStructureModel[];
};

type ProjectBridge = {
  id: string;
  name: string;
  order: number;
  workpoint_type: WorkPointType;
  import_source: Record<string, unknown>;
  work_sections: WorkSection[];
};

type ProjectModel = {
  project_id: string;
  project_name: string;
  start_date: string;
  bridges: ProjectBridge[];
};

type ProductivityOption = {
  id: string;
  name: string;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  is_default: boolean;
};

type ProcessTemplate = {
  id: string;
  component_type: ComponentType;
  process_name: string;
  method_id?: string | null;
  duration_method: string;
  quantity_source: string;
  productivity_value: number;
  productivity_unit: string;
  resource_type: string;
  productivity_options?: ProductivityOption[];
  applicability: Record<string, unknown>;
  is_default: boolean;
};

type LogicRule = {
  id: string;
  scope: "same_structure" | "structure_sequence";
  structure_type?: "pier" | "abutment" | null;
  to_component: ComponentType;
  predecessor_candidates: ComponentType[];
  predecessor_strategy: "all" | "first_available";
  relationship: RelationshipType;
  lag_days: number;
  severity?: "error" | "warning";
  note: string;
};

type ResourceCalendar = {
  id: string;
  name: string;
  working_weekdays: number[];
  blackout_dates: string[];
};

type ResourcePool = {
  id: string;
  type: string;
  label: string;
  quantity: number;
  max_quantity?: number | null;
  calendar_id: string;
  enabled: boolean;
  compatible_process_ids: string[];
};

type MilestoneConstraint = {
  id: string;
  name: string;
  level: "contract" | "control" | "internal";
  mode: "hard" | "soft";
  scope_type: "project" | "bridge" | "work_section" | "structure" | "component";
  scope_id?: string | null;
  target_event: "start" | "finish";
  target_date: string;
  penalty_per_day: number;
};

type ScenarioInput = {
  scenario_id: string;
  scenario_name: string;
  project: ProjectModel;
  process_library: ProcessTemplate[];
  logic_rules: LogicRule[];
  resource_calendars: ResourceCalendar[];
  resource_pools: ResourcePool[];
  milestones: MilestoneConstraint[];
  time_limit_seconds: number;
};

type Task = {
  id: string;
  name: string;
  bridge_id?: string | null;
  work_section_id?: string | null;
  component_id?: string | null;
  sequence_order: number;
  structure_id: string;
  structure_name: string;
  structure_type: string;
  component_type: ComponentType;
  process_name: string;
  productivity_rule_id: string;
  quantity: number;
  quantity_label: string;
  duration_days: number;
  compatible_resource_types: string[];
};

type ScheduledTask = Task & {
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
  assigned_resource_id?: string | null;
  assigned_resource_name?: string | null;
  assigned_resource_type?: string | null;
  predecessor_ids: string[];
};

type PrecedenceLink = {
  id: string;
  predecessor_id: string;
  successor_id: string;
  relationship: RelationshipType;
  lag_days: number;
  source_rule_id: string;
  severity?: "error" | "warning";
};

type Resource = {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
  calendar_id: string;
};

type ResourceAllocation = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  task_id: string;
  task_name: string;
  start_offset: number;
  end_offset: number;
  start_date: string;
  finish_date: string;
};

type MilestoneResult = MilestoneConstraint & {
  actual_date?: string | null;
  actual_offset?: number | null;
  lateness_days: number;
  penalty: number;
  status: "met" | "late" | "not_evaluated";
};

type ValidationMessage = {
  level: "info" | "warning" | "error";
  message: string;
  subject_id?: string | null;
};

type ScheduleInput = {
  project_name: string;
  start_date: string;
  tasks: Task[];
  precedence_links: PrecedenceLink[];
  resources: Resource[];
  milestones: MilestoneConstraint[];
  time_limit_seconds: number;
};

type GeneratedScheduleInput = {
  schedule_input: ScheduleInput;
  validation: ValidationMessage[];
  source_summary: Record<string, unknown>;
};

type ScheduleResult = {
  status: "OPTIMAL" | "FEASIBLE" | "INFEASIBLE" | "UNKNOWN" | "MODEL_INVALID";
  objective_days: number | null;
  plan_start_date: string;
  plan_finish_date?: string | null;
  tasks: ScheduledTask[];
  resource_allocations: ResourceAllocation[];
  milestone_results: MilestoneResult[];
  validation: ValidationMessage[];
  stats: Record<string, unknown>;
  objective_breakdown: Record<string, unknown>;
};

type ScenarioSolveResult = {
  scenario_id: string;
  scenario_name: string;
  generated: GeneratedScheduleInput;
  result: ScheduleResult;
  milestone_results: MilestoneResult[];
  diagnostics: ValidationMessage[];
  metrics: Record<string, unknown>;
};

type CompareResponse = {
  summaries: Array<Record<string, unknown>>;
  best_scenario_id?: string | null;
  notes: string[];
};

type ImportBridgeParamsResponse = {
  scenario: ScenarioInput;
  canonical_bridge: Record<string, unknown>;
  summary: Record<string, unknown>;
  quality_checks: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
};

type ProcessNlChange = {
  action: string;
  process_id?: string | null;
  process_name?: string | null;
  matched_count: number;
  targets: string[];
  message: string;
};

type ProcessNlResponse = {
  scenario: ScenarioInput;
  changes: ProcessNlChange[];
  warnings: string[];
};

type ContinuitySplitDetail = {
  structure_id: string;
  structure_name: string;
  component_label: string;
  process_name: string;
  resource_count: number;
  resource_names: string[];
};

type ContinuityJumpDetail = {
  resource_id: string;
  resource_name: string;
  from_location: string;
  to_location: string;
  jump_distance: number | null;
  is_jump_pier: boolean;
  is_side_switch: boolean;
  is_cross_side_jump: boolean;
  is_direction_reversal: boolean;
};

type ResourcePathStep = {
  task_id: string;
  task_name: string;
  location: string;
  component_type: ComponentType;
  component_label: string;
  start_date: string;
  finish_date: string;
};

type ResourcePath = {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  task_count: number;
  start_date?: string | null;
  finish_date?: string | null;
  jump_pier_count: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  path: ResourcePathStep[];
};

type ContinuityMetrics = {
  continuity_score: number;
  same_structure_craft_split_count: number;
  jump_pier_count: number;
  max_jump_distance: number;
  side_switch_count: number;
  cross_side_jump_count: number;
  direction_reversal_count: number;
  same_structure_craft_split_details: ContinuitySplitDetail[];
  jump_transition_details: ContinuityJumpDetail[];
  resource_paths: ResourcePath[];
};

type StructureRow = ReturnType<typeof buildStructureRows>[number];

type StructureFilters = {
  workpointLabel: string;
  bridgeAndSection: string;
  structureLevel: string;
  sideLabel: string;
  location: string;
  name: string;
  typeLabel: string;
  dimension: string;
  processLabel: string;
  productivityLabel: string;
};

const apiBase = "";

const componentLabels: Record<ComponentType, string> = {
  pile: "桩基",
  cap: "承台",
  spread_foundation: "扩大基础",
  ground_tie_beam: "地系梁",
  middle_tie_beam: "中系梁",
  pier_body: "墩柱",
  cap_beam: "盖梁",
  abutment_body: "桥台",
};

const durationMethodLabels: Record<string, string> = {
  units_per_day: "按日完成量计算",
  days_per_unit: "按单位耗时计算",
  fixed_days: "固定工期",
};

const quantitySourceLabels: Record<string, string> = {
  pile_length_m: "桩长",
  pier_height_m: "墩高",
  count: "构件数量",
};

const pileProductivityUnitOptions = [
  { unit: "m/天", duration_method: "units_per_day", quantity_source: "pile_length_m" },
  { unit: "根/天", duration_method: "units_per_day", quantity_source: "count" },
  { unit: "天/根", duration_method: "days_per_unit", quantity_source: "count" },
  { unit: "天/m", duration_method: "days_per_unit", quantity_source: "pile_length_m" },
];

const componentColors: Record<ComponentType, string> = {
  pile: "#2563eb",
  cap: "#0f766e",
  spread_foundation: "#0d9488",
  ground_tie_beam: "#64748b",
  middle_tie_beam: "#0891b2",
  pier_body: "#b45309",
  cap_beam: "#7c3aed",
  abutment_body: "#be123c",
};

const componentOrder: ComponentType[] = [
  "pile",
  "cap",
  "spread_foundation",
  "ground_tie_beam",
  "pier_body",
  "middle_tie_beam",
  "cap_beam",
  "abutment_body",
];

const workpointLabels: Record<WorkPointType, string> = {
  road: "路",
  bridge: "桥",
  tunnel: "隧",
};

const sideLabels: Record<WorkSectionSide, string> = {
  left: "左幅",
  right: "右幅",
  none: "无幅别",
};

const scheduleStatusLabels: Record<ScheduleResult["status"], string> = {
  OPTIMAL: "最优",
  FEASIBLE: "可行",
  INFEASIBLE: "不可行",
  UNKNOWN: "未知",
  MODEL_INVALID: "模型无效",
};

const milestoneStatusLabels: Record<MilestoneResult["status"], string> = {
  met: "已满足",
  late: "已迟延",
  not_evaluated: "未评估",
};

const diagnosticLevelLabels: Record<ValidationMessage["level"], string> = {
  info: "正常",
  warning: "提醒",
  error: "严重偏差",
};

const tabs: Array<{ key: TabKey; label: string; icon: ReactNode }> = [
  { key: "project", label: "项目参数", icon: <Layers3 size={15} /> },
  { key: "process", label: "工艺工效库", icon: <Database size={15} /> },
  { key: "logic", label: "工艺逻辑", icon: <Workflow size={15} /> },
  { key: "resources", label: "资源配置", icon: <Server size={15} /> },
  { key: "milestones", label: "里程碑", icon: <Flag size={15} /> },
  { key: "results", label: "模拟结果", icon: <CheckCircle2 size={15} /> },
];

export default function App() {
  const [scenario, setScenario] = useState<ScenarioInput | null>(null);
  const [generated, setGenerated] = useState<GeneratedScheduleInput | null>(null);
  const [solveResult, setSolveResult] = useState<ScenarioSolveResult | null>(null);
  const [openTabs, setOpenTabs] = useState<TabKey[]>(["project"]);
  const [activeTab, setActiveTab] = useState<TabKey | null>("project");
  const [ganttMode, setGanttMode] = useState<GanttMode>("by_structure");
  const [savedResults, setSavedResults] = useState<ScenarioSolveResult[]>([]);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [busy, setBusy] = useState<"loading" | "generating" | "solving" | "minResources" | "comparing" | "importing" | "nl" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastImport, setLastImport] = useState<ImportBridgeParamsResponse | null>(null);

  useEffect(() => {
    void loadScenario();
  }, []);

  const result = solveResult?.result ?? null;
  const statusTone = result?.status === "OPTIMAL" || result?.status === "FEASIBLE" ? "ok" : "warn";
  const flatStructures = useMemo(() => (scenario ? flattenStructures(scenario.project) : []), [scenario]);
  const summary = useMemo(() => buildSummary(scenario, generated, solveResult), [scenario, generated, solveResult]);

  async function loadScenario() {
    setBusy("loading");
    setError(null);
    try {
      const demo = await apiGet<ScenarioInput>("/api/demo-scenario");
      const imported = await apiPost<ImportBridgeParamsResponse>("/api/import-local-bridge-params", demo);
      setScenario(imported.scenario);
      setGenerated(null);
      setSolveResult(null);
      setComparison(null);
      setLastImport(imported);
      openModule("project");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function generateOnly() {
    if (!scenario) return;
    setBusy("generating");
    setError(null);
    try {
      const nextGenerated = await apiPost<GeneratedScheduleInput>("/api/generate-schedule-input", scenario);
      setGenerated(nextGenerated);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveCurrent() {
    if (!scenario) return;
    setBusy("solving");
    setError(null);
    try {
      await solveWith(scenario);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveMinResources() {
    if (!scenario) return;
    const hasHardMilestone = scenario.milestones.some((milestone) => milestone.mode === "hard");
    const fallbackTargetDays = solveResult?.result.objective_days ?? null;
    if (!hasHardMilestone && !fallbackTargetDays) {
      setError("请先运行“固定资源条件下，推算最短工期”，或设置至少一个可匹配的强制里程碑目标。");
      return;
    }
    setBusy("minResources");
    setError(null);
    try {
      const solved = await apiPost<ScenarioSolveResult>("/api/solve-min-resources", {
        scenario,
        fallback_target_days: fallbackTargetDays,
      });
      setGenerated(solved.generated);
      setSolveResult(solved);
      openModule("results");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function solveWith(nextScenario: ScenarioInput) {
    const solved = await apiPost<ScenarioSolveResult>("/api/solve-scenario", nextScenario);
    setGenerated(solved.generated);
    setSolveResult(solved);
  }

  async function compareSavedResults(nextResults = savedResults) {
    if (!nextResults.length) return;
    setBusy("comparing");
    setError(null);
    try {
      const nextComparison = await apiPost<CompareResponse>("/api/compare-scenarios", { results: nextResults });
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
      const imported = await apiPostFormData<ImportBridgeParamsResponse>("/api/import-bridge-params", payload);
      setScenario(imported.scenario);
      setGenerated(null);
      setSolveResult(null);
      setComparison(null);
      setLastImport(imported);
      openModule("project");
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
      const result = await apiPost<ProcessNlResponse>("/api/apply-process-natural-language", { scenario, prompt });
      setScenario(result.scenario);
      setGenerated(null);
      setSolveResult(null);
      setComparison(null);
      return result;
    } catch (err) {
      setError(errorText(err));
      return null;
    } finally {
      setBusy(null);
    }
  }

  function saveCurrentResult() {
    if (!solveResult) return;
    const nextResult = {
      ...solveResult,
      scenario_id: `${solveResult.scenario_id}-${savedResults.length + 1}`,
      scenario_name: `${solveResult.scenario_name} #${savedResults.length + 1}`,
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

  function updateComponent(componentId: string, patch: Partial<ComponentModel>) {
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
              structures: section.structures.map((structure) => ({
                ...structure,
                components: structure.components.map((component) =>
                  component.id === componentId ? { ...component, ...patch } : component,
                ),
              })),
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
      case "project":
        return scenario ? (
          <ProjectTab
            scenario={scenario}
            flatStructures={flatStructures}
            onPatchScenario={patchScenario}
            onPatchProject={patchProject}
            onUpdateComponent={updateComponent}
            onImportBridgeParams={importBridgeParams}
            onApplyProcessNaturalLanguage={applyProcessNaturalLanguage}
            importing={busy === "importing"}
            applyingProcessText={busy === "nl"}
            importResult={lastImport}
          />
        ) : null;
      case "process":
        return scenario ? <ProcessTab scenario={scenario} onUpdateProcess={updateProcess} /> : null;
      case "logic":
        return scenario ? <LogicTab scenario={scenario} onUpdateLogic={updateLogic} /> : null;
      case "resources":
        return scenario ? <ResourcesTab scenario={scenario} onUpdateResourcePool={updateResourcePool} /> : null;
      case "milestones":
        return scenario ? <MilestonesTab scenario={scenario} onUpdateMilestone={updateMilestone} /> : null;
      case "results":
        return (
          <ResultsTab
            scenario={scenario}
            generated={generated}
            solveResult={solveResult}
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
      <header className="topbar">
        <div>
          <div className="eyebrow">Bridge Scenario Scheduler</div>
          <h1>{scenario?.scenario_name ?? "桥梁场景化 CP-SAT 自动排程 Demo"}</h1>
        </div>
        <div className="actions">
          <button className="primary" onClick={solveCurrent} disabled={Boolean(busy) || !scenario}>
            {busy === "solving" || busy === "loading" ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
            固定资源条件下，推算最短工期
          </button>
          <button className="secondary" onClick={solveMinResources} disabled={Boolean(busy) || !scenario}>
            {busy === "minResources" ? <Loader2 className="spin" size={16} /> : <Server size={16} />}
            固定工期条件下，推算最少资源
          </button>
        </div>
      </header>

      <div className="app-body">
        <SideNavigation activeTab={activeTab} openTabs={openTabs} onOpen={openModule} />

        <main className="workspace">
          <WorkspaceTabStrip
            openTabs={openTabs}
            activeTab={activeTab}
            onSelect={setActiveTab}
            onClose={closeModule}
          />
        <section className="summary-band">
          <Metric label="计划状态" value={result ? scheduleStatusLabels[result.status] : "未求解"} tone={statusTone} icon={<Server size={18} />} />
          <Metric label="总工期" value={summary.days} tone="neutral" icon={<CalendarDays size={18} />} />
          <Metric label="工作项" value={summary.tasks} tone="neutral" icon={<CheckCircle2 size={18} />} />
          <Metric label="资源 / 里程碑" value={summary.resourcesAndMilestones} tone="neutral" icon={<Flag size={18} />} />
        </section>

        {error && (
          <section className="notice error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </section>
        )}

          <div className="workspace-content">
            {openTabs.length === 0 ? (
              <WorkspaceEmptyState onOpenProject={() => openModule("project")} />
            ) : (
              openTabs.map((tabKey) => (
                <div
                  key={tabKey}
                  className={`workspace-module ${tabKey === "project" ? "project-workspace" : ""}`}
                  hidden={activeTab !== tabKey}
                >
                  {renderModule(tabKey)}
                </div>
              ))
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

function SideNavigation({
  activeTab,
  openTabs,
  onOpen,
}: {
  activeTab: TabKey | null;
  openTabs: TabKey[];
  onOpen: (tabKey: TabKey) => void;
}) {
  return (
    <aside className="side-nav" aria-label="功能导航">
      <div className="side-nav-section">
        <div className="side-nav-heading">功能导航</div>
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.key}
            className={`side-nav-item ${activeTab === tab.key ? "active" : ""}`}
            aria-current={activeTab === tab.key ? "page" : undefined}
            onClick={() => onOpen(tab.key)}
          >
            <span className="side-nav-icon">{tab.icon}</span>
            <span>{tab.label}</span>
            {openTabs.includes(tab.key) && <span className="side-nav-dot" aria-hidden="true" />}
          </button>
        ))}
      </div>
    </aside>
  );
}

function WorkspaceTabStrip({
  openTabs,
  activeTab,
  onSelect,
  onClose,
}: {
  openTabs: TabKey[];
  activeTab: TabKey | null;
  onSelect: (tabKey: TabKey) => void;
  onClose: (tabKey: TabKey) => void;
}) {
  return (
    <nav className="workspace-tabs" aria-label="已打开页签">
      {openTabs.map((tabKey) => {
        const tab = tabConfig(tabKey);
        const isActive = activeTab === tabKey;
        return (
          <div className={`workspace-tab ${isActive ? "active" : ""}`} key={tabKey}>
            <button
              type="button"
              className="workspace-tab-main"
              role="tab"
              aria-selected={isActive}
              onClick={() => onSelect(tabKey)}
            >
              {tab.icon}
              <span>{tab.label}</span>
            </button>
            <button
              type="button"
              className="workspace-tab-close"
              aria-label={`关闭${tab.label}`}
              onClick={() => onClose(tabKey)}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </nav>
  );
}

function WorkspaceEmptyState({ onOpenProject }: { onOpenProject: () => void }) {
  return (
    <section className="workspace-empty">
      <div className="workspace-empty-icon">
        <Layers3 size={28} />
      </div>
      <h2>暂无打开页签</h2>
      <p>从左侧选择一个功能模块。</p>
      <button type="button" className="primary" onClick={onOpenProject}>
        打开项目参数
      </button>
    </section>
  );
}

function tabConfig(tabKey: TabKey): { key: TabKey; label: string; icon: ReactNode } {
  return tabs.find((tab) => tab.key === tabKey) ?? tabs[0];
}

function ProjectTab({
  scenario,
  flatStructures,
  onPatchScenario,
  onPatchProject,
  onUpdateComponent,
  onImportBridgeParams,
  onApplyProcessNaturalLanguage,
  importing,
  applyingProcessText,
  importResult,
}: {
  scenario: ScenarioInput;
  flatStructures: ReturnType<typeof flattenStructures>;
  onPatchScenario: (patch: Partial<ScenarioInput>) => void;
  onPatchProject: (patch: Partial<ProjectModel>) => void;
  onUpdateComponent: (componentId: string, patch: Partial<ComponentModel>) => void;
  onImportBridgeParams: (file: File, targetBridge: string) => void;
  onApplyProcessNaturalLanguage: (prompt: string) => Promise<ProcessNlResponse | null>;
  importing: boolean;
  applyingProcessText: boolean;
  importResult: ImportBridgeParamsResponse | null;
}) {
  const [targetBridge, setTargetBridge] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processPrompt, setProcessPrompt] = useState("");
  const [processNlResult, setProcessNlResult] = useState<ProcessNlResponse | null>(null);
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [structureFilters, setStructureFilters] = useState<StructureFilters>({
    workpointLabel: "",
    bridgeAndSection: "",
    structureLevel: "",
    sideLabel: "",
    location: "",
    name: "",
    typeLabel: "",
    dimension: "",
    processLabel: "",
    productivityLabel: "",
  });
  const importSummary = importResult?.summary ?? null;
  const importWarnings = importResult?.warnings ?? [];
  const structureRows = buildStructureRows(scenario.project, scenario.process_library);
  const filteredStructureRows = filterStructureRows(structureRows, structureFilters);

  async function submitProcessPrompt() {
    if (!processPrompt.trim() || applyingProcessText) return;
    const result = await onApplyProcessNaturalLanguage(processPrompt);
    if (result) setProcessNlResult(result);
  }

  function useAssistantExample(prompt: string) {
    setProcessPrompt(prompt);
    setAssistantOpen(true);
  }

  return (
    <div className="tab-grid project-tab-grid">
      <section className="panel project-params-panel">
        <PanelTitle title="项目桥梁参数" subtitle={`${scenario.project.bridges.length} 座桥 / 多工区结构树`} />
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
        </div>
        <div className="import-strip">
          <label>
            目标桥名
            <input value={targetBridge} onChange={(event) => setTargetBridge(event.target.value)} placeholder="可留空自动识别" />
          </label>
          <label>
            Excel
            <input
              type="file"
              accept=".xlsx,.xlsm"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <button
            className="secondary"
            disabled={!selectedFile || importing}
            onClick={() => selectedFile && onImportBridgeParams(selectedFile, targetBridge)}
          >
            {importing ? <Loader2 className="spin" size={16} /> : <Upload size={16} />}
            导入参数
          </button>
        </div>
        {importSummary && (
          <div className="import-result">
            <div>
              <strong>{displayValue(importSummary.bridgeName)}</strong>
              <span>
                {displayValue(importSummary.carriagewayCount)} 幅 / {displayValue(importSummary.supportCount)} 墩台 / {importComponentCountSummary(importSummary)}
              </span>
            </div>
            <code>{displayValue(importSummary.spanExpression)}</code>
            {importWarnings.length > 0 && (
              <div className="import-warnings">
                {importWarnings.slice(0, 4).map((warning, index) => (
                  <span key={`${displayValue(warning.id)}-${index}`}>{displayValue(warning.message)}</span>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="panel full project-structure-panel">
        <PanelTitle title="结构构件清单" subtitle={`${filteredStructureRows.length} / ${structureRows.length} 项，结构尺寸和桩基工艺会进入任务生成层`} />
        <div className="table-wrap tall project-structure-table">
          <table>
            <thead>
              <tr>
                <th>工点</th>
                <th>桥梁 / 工区</th>
                <th>结构层级</th>
                <th>幅别</th>
                <th>位置</th>
                <th>构件</th>
                <th>类型</th>
                <th>结构尺寸</th>
                <th>工艺</th>
                <th>工效</th>
              </tr>
              <tr className="filter-row">
                <th>
                  <input value={structureFilters.workpointLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, workpointLabel: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.bridgeAndSection} onChange={(event) => setStructureFilters((current) => ({ ...current, bridgeAndSection: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <select value={structureFilters.structureLevel} onChange={(event) => setStructureFilters((current) => ({ ...current, structureLevel: event.target.value }))}>
                    <option value="">全部</option>
                    <option value="下部结构">下部结构</option>
                    <option value="上部结构">上部结构</option>
                  </select>
                </th>
                <th>
                  <select value={structureFilters.sideLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, sideLabel: event.target.value }))}>
                    <option value="">全部</option>
                    <option value="左幅">左幅</option>
                    <option value="右幅">右幅</option>
                    <option value="无幅别">无幅别</option>
                  </select>
                </th>
                <th>
                  <input value={structureFilters.location} onChange={(event) => setStructureFilters((current) => ({ ...current, location: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.name} onChange={(event) => setStructureFilters((current) => ({ ...current, name: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.typeLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, typeLabel: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.dimension} onChange={(event) => setStructureFilters((current) => ({ ...current, dimension: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.processLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, processLabel: event.target.value }))} placeholder="筛选" />
                </th>
                <th>
                  <input value={structureFilters.productivityLabel} onChange={(event) => setStructureFilters((current) => ({ ...current, productivityLabel: event.target.value }))} placeholder="筛选" />
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredStructureRows.map((row) => {
                const processOptions = row.component ? processOptionsForComponent(row.component, scenario.process_library) : [];
                const selectedProcess = row.component ? selectedProcessForComponent(row.component, scenario.process_library) : null;
                const productivityOptions = selectedProcess ? processProductivityOptions(selectedProcess) : [];
                const selectedProductivity = row.component && selectedProcess ? selectedProductivityOption(row.component, selectedProcess) : null;
                const showProcessSelect = processOptions.length > 1 || (processOptions.length > 0 && !selectedProcess);
                const showProductivitySelect = Boolean(selectedProcess && selectedProductivity && productivityOptions.length > 1);

                return (
                  <tr key={row.id}>
                    <td><span className="tag">{row.workpointLabel}</span></td>
                    <td>{row.bridgeAndSection}</td>
                    <td><span className="tag">{row.structureLevel}</span></td>
                    <td>{row.sideLabel}</td>
                    <td>{row.location}</td>
                    <td>{row.name}</td>
                    <td><span className="tag">{row.typeLabel}</span></td>
                    <td className="note-cell">{row.dimension}</td>
                    <td>
                      {row.component && processOptions.length > 0 ? (
                        showProcessSelect ? (
                          <select
                            value={selectedProcess?.id ?? ""}
                            onChange={(event) => {
                              const nextProcess = processOptions.find((process) => process.id === event.target.value);
                              if (!nextProcess) return;
                              const nextDefault = defaultProductivityOption(nextProcess);
                              onUpdateComponent(row.component!.id, {
                                method_id: nextProcess.method_id ?? nextProcess.id,
                                productivity_option_id: nextDefault?.id ?? null,
                              });
                            }}
                          >
                            {!selectedProcess && <option value="">请选择工艺</option>}
                            {processOptions.map((process) => (
                              <option key={process.id} value={process.id}>{process.process_name}</option>
                            ))}
                          </select>
                        ) : (
                          <code>-</code>
                        )
                      ) : (
                        <code>-</code>
                      )}
                    </td>
                    <td>
                      {selectedProcess && selectedProductivity ? (
                        showProductivitySelect ? (
                          <select
                            value={selectedProductivity.id}
                            onChange={(event) => onUpdateComponent(row.component!.id, { productivity_option_id: event.target.value })}
                          >
                            {productivityOptions.map((option) => (
                              <option key={option.id} value={option.id}>{productivityOptionLabel(option)}</option>
                            ))}
                          </select>
                        ) : (
                          <span className="text-pill">{productivityOptionLabel(selectedProductivity)}</span>
                        )
                      ) : (
                        <code>{row.productivityLabel}</code>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      {assistantOpen ? (
        <aside className="nl-process-panel" aria-label="AI 操作助手">
          <div className="nl-process-title">
            <div className="nl-process-heading">
              <span className="assistant-mark"><Bot size={16} /></span>
              <div>
                <strong>AI 操作助手</strong>
                <span>自然语言快捷设置</span>
              </div>
            </div>
            <button className="icon-button" type="button" aria-label="收起 AI 操作助手" onClick={() => setAssistantOpen(false)}>
              <X size={16} />
            </button>
          </div>
          <textarea
            value={processPrompt}
            onChange={(event) => setProcessPrompt(event.target.value)}
            placeholder="例如：左幅的3#墩和4#墩的桩基工艺设置成人工挖孔。"
          />
          <div className="assistant-examples" aria-label="快捷示例">
            <button type="button" onClick={() => useAssistantExample("桩基默认采用旋挖钻施工，其中1#墩-1桩基、1#墩-2桩基采用人工挖孔桩。")}>
              默认旋挖
            </button>
            <button type="button" onClick={() => useAssistantExample("渠溪河大桥连续梁主墩使用爬模施工。")}>
              主墩爬模
            </button>
            <button type="button" onClick={() => useAssistantExample("左幅的3#墩和4#墩的桩基工艺设置成人工挖孔。")}>
              指定墩位
            </button>
          </div>
          <button className="primary assistant-submit" disabled={!processPrompt.trim() || applyingProcessText} onClick={submitProcessPrompt}>
            {applyingProcessText ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            让助手执行
          </button>
          {processNlResult && (
            <div className="nl-process-result">
              {processNlResult.changes.map((change, index) => (
                <span key={`${change.action}-${index}`}>{change.message}</span>
              ))}
              {processNlResult.warnings.map((warning, index) => (
                <span className="warn" key={`${warning}-${index}`}>{warning}</span>
              ))}
            </div>
          )}
        </aside>
      ) : (
        <button className="assistant-launcher" type="button" aria-label="打开 AI 操作助手" onClick={() => setAssistantOpen(true)}>
          <Bot size={18} />
          <span>AI 助手</span>
        </button>
      )}
    </div>
  );
}

function ProcessTab({
  scenario,
  onUpdateProcess,
}: {
  scenario: ScenarioInput;
  onUpdateProcess: (index: number, patch: Partial<ProcessTemplate>) => void;
}) {
  const resourcePoolByType = new Map(scenario.resource_pools.map((pool) => [pool.type, pool]));

  function productivityOptions(process: ProcessTemplate): ProductivityOption[] {
    return process.productivity_options?.length
      ? process.productivity_options
      : [
          {
            id: `${process.id}-default`,
            name: "默认工效",
            duration_method: process.duration_method,
            quantity_source: process.quantity_source,
            productivity_value: process.productivity_value,
            productivity_unit: process.productivity_unit,
            is_default: true,
          },
        ];
  }

  function patchProductivityOption(processIndex: number, optionId: string, patch: Partial<ProductivityOption>) {
    const process = scenario.process_library[processIndex];
    const nextOptions = productivityOptions(process).map((option) => {
      if (option.id !== optionId) return option;
      const nextOption = { ...option, ...patch };
      if (patch.productivity_unit && process.component_type === "pile") {
        const unitRule = pileProductivityUnitOptions.find((item) => item.unit === patch.productivity_unit);
        if (unitRule) {
          nextOption.duration_method = unitRule.duration_method;
          nextOption.quantity_source = unitRule.quantity_source;
        }
      }
      return nextOption;
    });
    updateProcessWithOptions(processIndex, nextOptions);
  }

  function addProductivityOption(processIndex: number) {
    const process = scenario.process_library[processIndex];
    const options = productivityOptions(process);
    const defaultOption = options.find((option) => option.is_default) ?? options[0];
    updateProcessWithOptions(processIndex, [
      ...options,
      {
        ...defaultOption,
        id: `${process.id}-option-${Date.now()}`,
        name: `工效分组${options.length + 1}`,
        is_default: false,
      },
    ]);
  }

  function removeProductivityOption(processIndex: number, optionId: string) {
    const options = productivityOptions(scenario.process_library[processIndex]);
    if (options.length <= 1) return;
    const removed = options.find((option) => option.id === optionId);
    let nextOptions = options.filter((option) => option.id !== optionId);
    if (removed?.is_default) {
      nextOptions = nextOptions.map((option, index) => ({ ...option, is_default: index === 0 }));
    }
    updateProcessWithOptions(processIndex, nextOptions);
  }

  function setDefaultProductivityOption(processIndex: number, optionId: string) {
    updateProcessWithOptions(
      processIndex,
      productivityOptions(scenario.process_library[processIndex]).map((option) => ({ ...option, is_default: option.id === optionId })),
    );
  }

  function updateProcessWithOptions(processIndex: number, options: ProductivityOption[]) {
    const defaultOption = options.find((option) => option.is_default) ?? options[0];
    const normalizedOptions = options.map((option) => ({ ...option, is_default: option.id === defaultOption.id }));
    onUpdateProcess(processIndex, {
      productivity_options: normalizedOptions,
      duration_method: defaultOption.duration_method,
      quantity_source: defaultOption.quantity_source,
      productivity_value: defaultOption.productivity_value,
      productivity_unit: defaultOption.productivity_unit,
    });
  }

  return (
    <section className="panel full">
      <PanelTitle title="施工工艺及工效库" subtitle="工艺模板按构件类型、适用工艺和默认资源类型维护" />
      <div className="table-wrap tall">
        <table>
          <thead>
            <tr>
              <th>构件</th>
              <th>工艺名称</th>
              <th>工期算法</th>
              <th>工程量来源</th>
              <th>工效分组</th>
              <th>默认资源</th>
            </tr>
          </thead>
          <tbody>
            {scenario.process_library.map((process, index) => {
              const currentPool = resourcePoolByType.get(process.resource_type);
              return (
                <tr key={process.id}>
                  <td><span className="tag">{componentLabels[process.component_type]}</span></td>
                  <td>
                    <input
                      className="wide-input"
                      value={process.process_name}
                      onChange={(event) => onUpdateProcess(index, { process_name: event.target.value })}
                    />
                  </td>
                  <td><span className="text-pill">{durationMethodLabels[process.duration_method] ?? process.duration_method}</span></td>
                  <td><span className="text-pill">{quantitySourceLabels[process.quantity_source] ?? process.quantity_source}</span></td>
                  <td>
                    <div className="productivity-groups">
                      {productivityOptions(process).map((option) => (
                        <div className={`productivity-group ${option.is_default ? "default" : ""}`} key={option.id}>
                          <input
                            className="productivity-name-input"
                            value={option.name}
                            onChange={(event) => patchProductivityOption(index, option.id, { name: event.target.value })}
                          />
                          <input
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={option.productivity_value}
                            onChange={(event) => patchProductivityOption(index, option.id, { productivity_value: Number(event.target.value) })}
                          />
                          {process.component_type === "pile" ? (
                            <select
                              className="productivity-unit-control"
                              value={option.productivity_unit}
                              onChange={(event) => patchProductivityOption(index, option.id, { productivity_unit: event.target.value })}
                            >
                              {pileProductivityUnitOptions.map((item) => (
                                <option value={item.unit} key={item.unit}>{item.unit}</option>
                              ))}
                            </select>
                          ) : (
                            <span className="text-pill productivity-unit-control">{option.productivity_unit}</span>
                          )}
                          <span className="text-pill productivity-source-pill">{quantitySourceLabels[option.quantity_source] ?? option.quantity_source}</span>
                          {option.is_default ? (
                            <span className="default-badge">默认分组</span>
                          ) : (
                            <button
                              className="mini-button set-default"
                              type="button"
                              onClick={() => setDefaultProductivityOption(index, option.id)}
                            >
                              设为默认
                            </button>
                          )}
                          <button
                            className="mini-button"
                            type="button"
                            disabled={productivityOptions(process).length <= 1}
                            onClick={() => removeProductivityOption(index, option.id)}
                          >
                            删除
                          </button>
                        </div>
                      ))}
                      <button className="mini-button add" type="button" onClick={() => addProductivityOption(index)}>
                        新增分组
                      </button>
                    </div>
                  </td>
                  <td>
                    <select
                      value={process.resource_type}
                      onChange={(event) => onUpdateProcess(index, { resource_type: event.target.value })}
                    >
                      {!currentPool && <option value={process.resource_type}>{process.resource_type}</option>}
                      {scenario.resource_pools.map((pool) => (
                        <option value={pool.type} key={pool.id}>{pool.label}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LogicTab({
  scenario,
  onUpdateLogic,
}: {
  scenario: ScenarioInput;
  onUpdateLogic: (index: number, patch: Partial<LogicRule>) => void;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="工艺逻辑约束" subtitle="工艺逻辑作为排程必须满足的前后关系进入求解器" />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>规则</th>
              <th>范围</th>
              <th>当前构件</th>
              <th>候选前置</th>
              <th>策略</th>
              <th>关系</th>
              <th>间隔</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {scenario.logic_rules.map((rule, index) => (
              <tr key={rule.id}>
                <td>
                  <div className="rule-name">{logicRuleDisplayName(rule)}</div>
                  <code className="muted-code">{rule.id}</code>
                </td>
                <td>
                  <select value={rule.scope} onChange={(event) => onUpdateLogic(index, { scope: event.target.value as LogicRule["scope"] })}>
                    <option value="same_structure">同墩台</option>
                    <option value="structure_sequence">跨墩台顺序</option>
                  </select>
                </td>
                <td>{componentLabels[rule.to_component]}</td>
                <td>{rule.predecessor_candidates.map((item) => componentLabels[item]).join(" / ")}</td>
                <td>
                  <select
                    value={rule.predecessor_strategy}
                    onChange={(event) => onUpdateLogic(index, { predecessor_strategy: event.target.value as LogicRule["predecessor_strategy"] })}
                  >
                    <option value="first_available">优先回退</option>
                    <option value="all">全部满足</option>
                  </select>
                </td>
                <td>
                  <select
                    value={rule.relationship}
                    onChange={(event) => onUpdateLogic(index, { relationship: event.target.value as RelationshipType })}
                  >
                    <option value="FS">FS</option>
                    <option value="SS">SS</option>
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    value={rule.lag_days}
                    onChange={(event) => onUpdateLogic(index, { lag_days: Number(event.target.value) })}
                  />
                  <span className="unit">天</span>
                </td>
                <td className="note-cell">{rule.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function logicRuleDisplayName(rule: LogicRule): string {
  if (rule.note) {
    return rule.note.replace(/。$/, "");
  }
  const predecessors = rule.predecessor_candidates.map((item) => componentLabels[item]).join("、");
  return `${componentLabels[rule.to_component]}在${predecessors}之后施工`;
}

function ResourcesTab({
  scenario,
  onUpdateResourcePool,
}: {
  scenario: ScenarioInput;
  onUpdateResourcePool: (index: number, patch: Partial<ResourcePool>) => void;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="资源配置约束" subtitle="资源池按数量自动展开为命名资源，求解器自动从候选资源中选择" />
      <div className="resource-grid">
        {scenario.resource_pools.map((pool, index) => (
          <div className="resource-card" key={pool.id}>
            <div>
              <strong>{pool.label}</strong>
              <code>{pool.type}</code>
            </div>
            <label>
              默认数量
              <input
                type="number"
                min={0}
                value={pool.quantity}
                onChange={(event) => {
                  const quantity = Number(event.target.value);
                  onUpdateResourcePool(index, { quantity, max_quantity: Math.max(pool.max_quantity ?? pool.quantity, quantity) });
                }}
              />
            </label>
            <label>
              最大数量
              <input
                type="number"
                min={pool.quantity}
                value={pool.max_quantity ?? pool.quantity}
                onChange={(event) => onUpdateResourcePool(index, { max_quantity: Math.max(Number(event.target.value), pool.quantity) })}
              />
            </label>
            <label>
              日历
              <select value={pool.calendar_id} onChange={(event) => onUpdateResourcePool(index, { calendar_id: event.target.value })}>
                {scenario.resource_calendars.map((calendar) => (
                  <option value={calendar.id} key={calendar.id}>{calendar.name}</option>
                ))}
              </select>
            </label>
            <label className="check-row">
              <input
                type="checkbox"
                checked={pool.enabled}
                onChange={(event) => onUpdateResourcePool(index, { enabled: event.target.checked })}
              />
              启用
            </label>
          </div>
        ))}
      </div>
    </section>
  );
}

function MilestonesTab({
  scenario,
  onUpdateMilestone,
}: {
  scenario: ScenarioInput;
  onUpdateMilestone: (index: number, patch: Partial<MilestoneConstraint>) => void;
}) {
  return (
    <section className="panel full">
      <PanelTitle title="关键里程碑节点约束" subtitle="固定资源最短工期允许突破目标并给出偏差；固定工期最少资源会把强制目标作为不可突破工期" />
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>节点</th>
              <th>等级</th>
              <th>约束</th>
              <th>范围</th>
              <th>事件</th>
              <th>目标日期</th>
              <th>罚分/天</th>
            </tr>
          </thead>
          <tbody>
            {scenario.milestones.map((milestone, index) => (
              <tr key={milestone.id}>
                <td>
                  <input
                    className="wide-input"
                    value={milestone.name}
                    onChange={(event) => onUpdateMilestone(index, { name: event.target.value })}
                  />
                </td>
                <td>
                  <select value={milestone.level} onChange={(event) => onUpdateMilestone(index, { level: event.target.value as MilestoneConstraint["level"] })}>
                    <option value="contract">合同</option>
                    <option value="control">强控</option>
                    <option value="internal">内部</option>
                  </select>
                </td>
                <td>
                  <select value={milestone.mode} onChange={(event) => onUpdateMilestone(index, { mode: event.target.value as MilestoneConstraint["mode"] })}>
                    <option value="hard">强制目标</option>
                    <option value="soft">提醒目标</option>
                  </select>
                </td>
                <td>{scopeLabel(milestone, scenario)}</td>
                <td>
                  <select
                    value={milestone.target_event}
                    onChange={(event) => onUpdateMilestone(index, { target_event: event.target.value as MilestoneConstraint["target_event"] })}
                  >
                    <option value="finish">完成</option>
                    <option value="start">开始</option>
                  </select>
                </td>
                <td>
                  <input
                    type="date"
                    value={milestone.target_date}
                    onChange={(event) => onUpdateMilestone(index, { target_date: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    min={0}
                    value={milestone.penalty_per_day}
                    disabled={milestone.mode === "hard"}
                    onChange={(event) => onUpdateMilestone(index, { penalty_per_day: Number(event.target.value) })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ResultsTab({
  scenario,
  generated,
  solveResult,
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
  ganttMode: GanttMode;
  onGanttModeChange: (mode: GanttMode) => void;
  onSaveCurrent: () => void;
  savedResults: ScenarioSolveResult[];
  comparison: CompareResponse | null;
  onCompare: () => void;
  comparing: boolean;
}) {
  const [openPredecessorTaskId, setOpenPredecessorTaskId] = useState<string | null>(null);
  const predecessorLayerRef = useRef<HTMLDivElement | null>(null);
  const result = solveResult?.result ?? null;
  const generatedForDetails = solveResult?.generated ?? generated;
  const recommendedResourceCounts = recommendedResourceCountsFromResult(result);
  const continuityMetrics = continuityMetricsFromResult(result);
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
  const logicRuleById = useMemo(
    () => new Map((scenario?.logic_rules ?? []).map((rule) => [rule.id, rule])),
    [scenario],
  );

  useEffect(() => {
    if (!openPredecessorTaskId) return;

    function closeWhenClickOutside(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (predecessorLayerRef.current?.contains(target)) return;
      setOpenPredecessorTaskId(null);
    }

    document.addEventListener("pointerdown", closeWhenClickOutside);
    return () => document.removeEventListener("pointerdown", closeWhenClickOutside);
  }, [openPredecessorTaskId]);

  function predecessorDetails(task: ScheduledTask): PredecessorDetail[] {
    const links = linksBySuccessor.get(task.id) ?? [];
    return task.predecessor_ids.map((predecessorId) => {
      const predecessor = scheduledTaskById.get(predecessorId);
      const link = links.find((item) => item.predecessor_id === predecessorId);
      const rule = link ? logicRuleById.get(link.source_rule_id) : undefined;
      return {
        predecessorId,
        predecessor,
        link,
        rule,
      };
    });
  }

  return (
    <div className="results-grid" ref={predecessorLayerRef}>
      <section className="panel full">
        <div className="panel-title">
          <div>
            <h2>约束诊断</h2>
            <span>生成层、求解层和里程碑检查的摘要</span>
          </div>
          <div className="actions inline">
            <button className="secondary" onClick={onSaveCurrent} disabled={!solveResult}>
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
          {(solveResult?.diagnostics ?? generated?.validation ?? []).slice(0, 12).map((message, index) => (
            <div className={`diagnostic ${message.level}`} key={`${message.subject_id ?? "message"}-${index}`}>
              <strong>{diagnosticLevelLabels[message.level]}</strong>
              <span>{message.message}</span>
            </div>
          ))}
          {!solveResult && !generated && <div className="empty">等待生成或求解</div>}
        </div>
      </section>

      {recommendedResourceCounts.length > 0 && (
        <section className="panel full">
          <PanelTitle title="推荐资源数量" subtitle="固定工期条件下推算的最少并行资源" />
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>资源</th>
                  <th>推荐数量</th>
                  <th>最大数量</th>
                </tr>
              </thead>
              <tbody>
                {recommendedResourceCounts.map((item) => (
                  <tr key={item.resource_pool_id}>
                    <td>{item.label}</td>
                    <td>{item.recommended_quantity}</td>
                    <td>{item.max_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
                <th>构件</th>
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
                    <td><span className="tag">{componentLabels[task.component_type]}</span></td>
                    <td>{task.duration_days} 天</td>
                    <td>{task.start_date}</td>
                    <td>{task.finish_date}</td>
                    <td>{task.assigned_resource_name ?? "-"}</td>
                    <td className="predecessor-cell">
                      {task.predecessor_ids.length > 0 ? (
                        <button
                          className="predecessor-count has-items"
                          type="button"
                          onClick={() => setOpenPredecessorTaskId(isOpen ? null : task.id)}
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
                          onClose={() => setOpenPredecessorTaskId(null)}
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
        <Gantt tasks={result?.tasks ?? []} makespan={Math.max(result?.objective_days ?? 1, 1)} mode={ganttMode} />
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

type PredecessorDetail = {
  predecessorId: string;
  predecessor?: ScheduledTask;
  link?: PrecedenceLink;
  rule?: LogicRule;
};

function PredecessorPopover({
  task,
  details,
  onClose,
}: {
  task: ScheduledTask;
  details: PredecessorDetail[];
  onClose: () => void;
}) {
  return (
    <div className="predecessor-popover">
      <div className="predecessor-popover-head">
        <div>
          <strong>{task.name}</strong>
          <span>{details.length ? `${details.length} 个前置工作` : "无前置工作"}</span>
        </div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭前置工作详情">
          <X size={14} />
        </button>
      </div>
      {details.length ? (
        <div className="predecessor-list">
          {details.map((detail) => (
            <div className="predecessor-item" key={`${task.id}-${detail.predecessorId}-${detail.link?.id ?? "missing"}`}>
              <div className="predecessor-item-title">
                <strong>{detail.predecessor?.name ?? detail.predecessorId}</strong>
                <span>{detail.predecessor ? componentLabels[detail.predecessor.component_type] : "未找到工作项"}</span>
              </div>
              <div className="predecessor-meta">
                <span>关系：{formatPrecedenceRelation(detail.link)}</span>
                <span>计划：{detail.predecessor ? `${detail.predecessor.start_date} 至 ${detail.predecessor.finish_date}` : "-"}</span>
              </div>
              <div className="predecessor-rule">
                {detail.rule ? logicRuleDisplayName(detail.rule) : `规则：${detail.link?.source_rule_id ?? "-"}`}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="predecessor-empty">这个工作项可以直接作为起始工作安排。</div>
      )}
    </div>
  );
}

function formatPrecedenceRelation(link?: PrecedenceLink): string {
  if (!link) return "-";
  const relationship = link.relationship === "FS" ? "完成后开始 FS" : "开始后开始 SS";
  return `${relationship}，间隔 ${link.lag_days} 天`;
}

function Metric({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone: "ok" | "warn" | "neutral";
  icon: ReactNode;
}) {
  return (
    <div className={`metric ${tone}`}>
      <div className="metric-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function PanelTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="panel-title">
      <h2>{title}</h2>
      <span>{subtitle}</span>
    </div>
  );
}

function Gantt({ tasks, makespan, mode }: { tasks: ScheduledTask[]; makespan: number; mode: GanttMode }) {
  if (!tasks.length) return <div className="empty">暂无排程结果</div>;
  const groups = buildGanttGroups(tasks, mode);
  return (
    <div className="gantt">
      {groups.map((group) => (
        <div className="gantt-group" key={group.id}>
          <div className="gantt-group-title">
            <strong>{group.title}</strong>
            <span>{group.startDate} 至 {group.finishDate}</span>
          </div>
          {group.tasks.map((task) => (
            <div className="gantt-row" key={task.id}>
              <div className="gantt-label">{task.name}</div>
              <div className="gantt-track">
                <div
                  className="gantt-bar"
                  style={{
                    left: `${(task.start_offset / makespan) * 100}%`,
                    width: `${Math.max(((task.end_offset - task.start_offset) / makespan) * 100, 1.2)}%`,
                    backgroundColor: componentColors[task.component_type],
                  }}
                  title={ganttTaskHoverTitle(task)}
                >
                  <span>{task.duration_days}d</span>
                </div>
              </div>
            </div>
          ))}
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

function ganttTaskHoverTitle(task: ScheduledTask): string {
  return [
    `工作项：${task.name}`,
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

function buildGanttGroups(tasks: ScheduledTask[], mode: GanttMode) {
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
      title: children[0].structure_name,
      tasks: children.sort(
        (a, b) =>
          componentOrder.indexOf(a.component_type) - componentOrder.indexOf(b.component_type)
          || a.start_offset - b.start_offset
          || a.name.localeCompare(b.name),
      ),
      ...taskDateRange(children),
    }));
}

function flattenStructures(project: ProjectModel) {
  return project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) =>
      section.structures.map((structure) => ({ bridge, section, structure })),
    ),
  );
}

function buildStructureRows(project: ProjectModel, processLibrary: ProcessTemplate[]) {
  return project.bridges.flatMap((bridge) =>
    bridge.work_sections.flatMap((section) => {
      const lowerRows = section.structures.flatMap((structure) =>
        structure.components.map((component) => {
          const processes = processOptionsForComponent(component, processLibrary);
          const process = selectedProcessForComponent(component, processLibrary);
          const productivityOption = process ? selectedProductivityOption(component, process) : null;
          return {
            id: component.id,
            workpointLabel: workpointLabels[bridge.workpoint_type ?? "bridge"],
            bridgeAndSection: `${bridge.name} / ${section.name}`,
            structureLevel: "下部结构",
            sideLabel: sideLabels[section.side ?? "none"],
            location: structure.support_no ?? structure.name,
            name: component.name,
            typeLabel: componentLabels[component.component_type],
            dimension: dimensionSummary(component),
            processLabel: processes.length > 1 ? process?.process_name ?? "未匹配工艺" : "-",
            productivityLabel: productivityOption ? productivityOptionLabel(productivityOption) : "-",
            order: structure.order * 100 + componentOrder.indexOf(component.component_type),
            component,
          };
        }),
      );
      const upperRows = (section.upper_structures ?? []).map((upper) => ({
        id: upper.id,
        workpointLabel: workpointLabels[bridge.workpoint_type ?? "bridge"],
        bridgeAndSection: `${bridge.name} / ${section.name}`,
        structureLevel: "上部结构",
        sideLabel: sideLabels[section.side ?? "none"],
        location: `第${upper.span_index}跨 ${upper.support_range}`,
        name: upper.name,
        typeLabel: upper.structure_type,
        dimension: upperStructureDimensionSummary(upper),
        processLabel: "-",
        productivityLabel: "-",
        order: 100000 + upper.span_index,
        component: undefined,
      }));
      return [...lowerRows, ...upperRows].sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
    }),
  );
}

function processOptionsForComponent(component: ComponentModel, processLibrary: ProcessTemplate[]): ProcessTemplate[] {
  return processLibrary.filter((process) => process.component_type === component.component_type);
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

function productivityOptionLabel(option: ProductivityOption): string {
  const groupName = option.name.trim() === "默认工效" ? "默认" : option.name.trim() || "工效";
  return `${groupName}-${displayValue(option.productivity_value)}${option.productivity_unit}`;
}

function filterStructureRows(rows: StructureRow[], filters: StructureFilters): StructureRow[] {
  return rows.filter((row) =>
    Object.entries(filters).every(([key, value]) => {
      const needle = value.trim().toLowerCase();
      if (!needle) return true;
      return String(row[key as keyof StructureFilters]).toLowerCase().includes(needle);
    }),
  );
}

function upperStructureDimensionSummary(upper: UpperStructureModel): string {
  const parts = [`跨径${displayValue(upper.span_length_m)}m`];
  if (upper.beam_count_per_span) {
    parts.push(`${displayValue(upper.beam_count_per_span)}片`);
  }
  if (upper.structure_type.includes("连续") && upper.span_group_expression) {
    parts.push(`联跨${upper.span_group_expression}`);
  }
  return parts.join("，");
}

function buildSummary(
  scenario: ScenarioInput | null,
  generated: GeneratedScheduleInput | null,
  solveResult: ScenarioSolveResult | null,
) {
  const recommendedCounts = recommendedResourceCountsFromResult(solveResult?.result ?? null);
  const resourceCount = recommendedCounts.length
    ? recommendedCounts.reduce((sum, item) => sum + item.recommended_quantity, 0)
    : generated?.schedule_input.resources.length
    ?? scenario?.resource_pools.reduce((sum, pool) => sum + (pool.enabled ? pool.quantity : 0), 0)
    ?? 0;
  const milestoneCount = scenario?.milestones.length ?? 0;
  return {
    days: solveResult?.result.objective_days ? `${solveResult.result.objective_days} 天` : "-",
    tasks: generated?.schedule_input.tasks.length ? `${generated.schedule_input.tasks.length} 项` : "-",
    resourcesAndMilestones: `${resourceCount} / ${milestoneCount}`,
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

function recommendedResourceCountsFromResult(result: ScheduleResult | null): Array<{
  resource_pool_id: string;
  label: string;
  recommended_quantity: number;
  max_quantity: number;
}> {
  const raw = result?.stats?.recommended_resource_counts ?? result?.objective_breakdown?.recommended_resource_counts;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      resource_pool_id: String(item.resource_pool_id ?? item.resource_type ?? item.label ?? ""),
      label: String(item.label ?? item.resource_type ?? "-"),
      recommended_quantity: Number(item.recommended_quantity ?? 0),
      max_quantity: Number(item.max_quantity ?? 0),
    }))
    .filter((item) => item.resource_pool_id);
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

function milestoneStatusClass(milestone: MilestoneResult): string {
  if (milestone.status !== "late") return milestone.status;
  return milestone.mode === "hard" ? "late-hard" : "late-soft";
}

function scopeLabel(milestone: MilestoneConstraint, scenario: ScenarioInput): string {
  const project = scenario.project;
  if (milestone.scope_type === "project") {
    return "全项目下部结构";
  }

  if (milestone.scope_type === "bridge") {
    const bridge = project.bridges.find((item) => item.id === milestone.scope_id) ?? project.bridges[0];
    return bridge ? `${bridge.name}全桥下部结构` : "全桥下部结构";
  }

  if (milestone.scope_type === "work_section") {
    const section = findWorkSection(project, milestone.scope_id ?? "");
    if (!section) return "指定工区下部结构";
    if (section.side && section.side !== "none") {
      return `${sideLabels[section.side]}下部结构`;
    }
    return `${section.name}全部工作`;
  }

  if (milestone.scope_type === "structure") {
    const found = findStructure(project, milestone.scope_id ?? "");
    return found ? `${found.structure.support_no ?? found.structure.name}全部下部结构` : "指定墩台全部下部结构";
  }

  if (milestone.scope_type === "component") {
    if (isComponentType(milestone.scope_id)) {
      return `全部${componentLabels[milestone.scope_id]}`;
    }
    const found = findComponent(project, milestone.scope_id ?? "");
    if (found) {
      const location = found.structure.support_no ?? found.structure.name;
      return `${location}${componentLabels[found.component.component_type]}`;
    }
    return "指定构件";
  }

  return "-";
}

function findWorkSection(project: ProjectModel, sectionId: string): WorkSection | null {
  for (const bridge of project.bridges) {
    const section = bridge.work_sections.find((item) => item.id === sectionId);
    if (section) return section;
  }
  return null;
}

function findStructure(project: ProjectModel, structureId: string): { section: WorkSection; structure: StructureModel } | null {
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      const structure = section.structures.find((item) => item.id === structureId);
      if (structure) return { section, structure };
    }
  }
  return null;
}

function findComponent(project: ProjectModel, componentId: string): { section: WorkSection; structure: StructureModel; component: ComponentModel } | null {
  for (const bridge of project.bridges) {
    for (const section of bridge.work_sections) {
      for (const structure of section.structures) {
        const component = structure.components.find((item) => item.id === componentId);
        if (component) return { section, structure, component };
      }
    }
  }
  return null;
}

function isComponentType(value: string | null | undefined): value is ComponentType {
  return Boolean(value && Object.prototype.hasOwnProperty.call(componentLabels, value));
}

function dimensionSummary(component: ComponentModel): string {
  const properties = component.properties;
  const dimensions = properties?.dimensions_m;
  if (component.component_type === "pier_body") {
    const pierSummary = pierBodyDimensionSummary(component, dimensions);
    if (pierSummary) return pierSummary;
  }
  if (Array.isArray(dimensions) && dimensions.length) {
    return dimensions.map((item) => `${displayValue(item)}m`).join(" × ");
  }
  if (isRecord(dimensions)) {
    const parts = Object.entries(dimensions)
      .filter(([, value]) => value !== null && value !== undefined)
      .map(([key, value]) => dimensionPartSummary(component, key, value));
    if (parts.length) return parts.join("，");
  }
  if (isRecord(properties)) {
    const propertyParts = Object.entries(properties)
      .filter(([key, value]) => isDimensionKey(key) && value !== null && value !== undefined)
      .map(([key, value]) => dimensionPartSummary(component, key, value));
    if (propertyParts.length) return propertyParts.join("，");
  }
  const raw = properties?.raw;
  if (isRecord(raw)) {
    const rawValues = Object.values(raw).filter((value) => value !== null && value !== undefined);
    if (rawValues.length) return rawValues.map(displayValue).join(" / ");
  }
  return "-";
}

function pierBodyDimensionSummary(component: ComponentModel, dimensions: unknown): string | null {
  const sectionDimensions = Array.isArray(dimensions) ? dimensions.filter(isNumber) : [];
  const raw = isRecord(component.properties?.raw) ? component.properties.raw : {};
  const pierForm = displayValue(raw.pier_form ?? component.properties?.form ?? "");
  const heightM = numberFromUnknown(component.properties?.height_m)
    ?? numberFromUnknown(component.properties?.heightM)
    ?? cmToM(raw.pier_height);
  const count = numberFromUnknown(component.properties?.count) ?? numberFromUnknown(raw.pier_count);
  const parts: string[] = [];

  if (sectionDimensions.length === 1 || pierForm.includes("柱式")) {
    const diameter = sectionDimensions[0];
    if (diameter !== undefined) parts.push(`直径${displayValue(diameter)}m`);
  } else if (sectionDimensions.length >= 2) {
    parts.push(`截面${sectionDimensions.map((item) => `${displayValue(item)}m`).join(" × ")}`);
  }
  if (heightM !== null) parts.push(`墩高${displayValue(heightM)}m`);
  if (count !== null && count > 1) parts.push(`${displayValue(count)}根`);
  return parts.length ? parts.join("，") : null;
}

function isDimensionKey(key: string): boolean {
  return [
    "diameterM",
    "diameter_m",
    "lengthM",
    "length_m",
    "heightM",
    "height_m",
    "widthM",
    "width_m",
    "thicknessM",
    "thickness_m",
    "totalLengthM",
    "total_length_m",
  ].includes(key);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function numberFromUnknown(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const match = value.match(/-?\d+(?:\.\d+)?/);
    if (match) return Number(match[0]);
  }
  return null;
}

function cmToM(value: unknown): number | null {
  const number = numberFromUnknown(value);
  return number === null ? null : number / 100;
}

function dimensionPartSummary(component: ComponentModel, key: string, value: unknown): string {
  const unit = key.endsWith("M") || key.endsWith("_m") ? "m" : "";
  return `${dimensionLabel(component, key)}${displayValue(value)}${unit}`;
}

function dimensionLabel(component: ComponentModel, key: string): string {
  const labels: Record<string, string> = {
    diameterM: "直径",
    diameter_m: "直径",
    heightM: "高度",
    height_m: "高度",
    widthM: "宽度",
    width_m: "宽度",
    thicknessM: "厚度",
    thickness_m: "厚度",
    totalLengthM: "总长",
    total_length_m: "总长",
  };
  if (key === "lengthM" || key === "length_m") {
    return component.component_type === "pile" ? "桩长" : "长度";
  }
  return labels[key] ?? key;
}

function sourceSummary(component: ComponentModel): string {
  const source = component.properties?.source_trace;
  if (!isRecord(source)) return "-";
  const sheet = displayValue(source.sheet);
  const row = source.row ? `#${displayValue(source.row)}` : "";
  return `${sheet}${row}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4).replace(/\.?0+$/, "");
  return String(value);
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

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

function formatScheduleStatus(value: unknown): string {
  if (typeof value === "string" && Object.prototype.hasOwnProperty.call(scheduleStatusLabels, value)) {
    return scheduleStatusLabels[value as ScheduleResult["status"]];
  }
  return value == null ? "-" : String(value);
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

async function apiPostFormData<T>(path: string, payload: FormData): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    method: "POST",
    body: payload,
  });
  if (!response.ok) throw new Error(await responseErrorText(response));
  return response.json() as Promise<T>;
}

async function responseErrorText(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const payload = JSON.parse(text) as { detail?: unknown };
    return typeof payload.detail === "string" ? payload.detail : text;
  } catch {
    return text;
  }
}
