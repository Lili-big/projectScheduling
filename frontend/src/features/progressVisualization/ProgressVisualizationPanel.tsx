import {
  Activity,
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Clock3,
  Database,
  GitCompareArrows,
  Info,
  MapPinned,
  Route,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import type { CSSProperties, ReactNode } from "react";
import { useMemo, useState } from "react";

import bridgeBackground from "../../assets/progress-visualization/bridge-model.png";
import routeBackground from "../../assets/progress-visualization/route-overview.png";
import type { ComponentType, ForecastRiskStatus } from "../../types/scheduler";
import { demoProgressVisualizationData } from "./demoData";
import "./ProgressVisualizationPanel.css";
import type {
  ProgressCurvePoint,
  ProgressRiskEvidence,
  ProgressVisualizationData,
  ProgressVisualizationMode,
  ProgressVisualizationView,
  StructureProgressStatus,
} from "./types";

const riskLabels: Record<ForecastRiskStatus, string> = {
  on_track: "总体可控",
  at_risk: "缓冲偏紧",
  late: "预测延期",
  insufficient_data: "数据不足",
};

const structureStatusLabels: Record<StructureProgressStatus, string> = {
  completed: "已完成",
  in_progress: "进行中",
  ahead: "超前",
  late: "滞后",
  on_track: "按计划",
  not_started: "未开始",
};

const evidenceLabels: Record<ProgressRiskEvidence["type"], string> = {
  project_finish: "项目完工",
  milestone: "关键节点",
  buffer: "剩余缓冲",
  solver: "预测求解",
};

function formatPercent(value: number | null, signed = false): string {
  if (value === null) return "—";
  const prefix = signed && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(1)}%`;
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.slice(0, 10).split("-");
  return `${year}.${month}.${day}`;
}

function formatShortDate(value: string): string {
  const [, month, day] = value.slice(0, 10).split("-");
  return `${month}.${day}`;
}

function varianceText(value: number | null): string {
  if (value === null) return "待预测";
  if (value === 0) return "按期";
  return `${value > 0 ? "+" : ""}${value}天`;
}

function MetricCard({
  label,
  value,
  hint,
  tone = "default",
  icon,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: "default" | "success" | "warning" | "danger";
  icon: ReactNode;
}) {
  return (
    <div className={`progress-visualization-metric ${tone} ${value.length >= 10 ? "compact-value" : ""}`}>
      <span className="progress-visualization-metric-icon">{icon}</span>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{hint}</small>
      </div>
    </div>
  );
}

function ProgressBars({ planned, actual }: { planned: number; actual: number }) {
  return (
    <div className="progress-dual-bars" aria-label={`计划 ${planned}%，实际 ${actual}%`}>
      <span className="progress-dual-bar planned"><i style={{ width: `${planned}%` }} /></span>
      <span className="progress-dual-bar actual"><i style={{ width: `${actual}%` }} /></span>
    </div>
  );
}

function progressPath(points: ProgressCurvePoint[], minTime: number, maxTime: number): string {
  if (!points.length) return "";
  const width = 610;
  const range = Math.max(1, maxTime - minTime);
  return points
    .map((point, index) => {
      const time = Date.parse(`${point.date}T00:00:00Z`);
      const x = 16 + ((time - minTime) / range) * width;
      const y = 130 - (point.value / 100) * 108;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

function ProgressCurve({ data }: { data: ProgressVisualizationData["curve"] }) {
  const allPoints = [...data.baseline, ...data.forecast, ...(data.actual ? [data.actual] : [])];
  const times = allPoints.map((point) => Date.parse(`${point.date}T00:00:00Z`)).filter(Number.isFinite);
  const minTime = times.length ? Math.min(...times) : 0;
  const maxTime = times.length ? Math.max(...times) : 1;
  const actualTime = data.actual ? Date.parse(`${data.actual.date}T00:00:00Z`) : null;
  const actualX = actualTime === null ? 0 : 16 + ((actualTime - minTime) / Math.max(1, maxTime - minTime)) * 610;
  const actualY = data.actual ? 130 - (data.actual.value / 100) * 108 : 0;
  const labels = [...new Set([...data.baseline.map((point) => point.date), ...data.forecast.map((point) => point.date)])];
  const shownLabels = labels.filter((_, index) => index === 0 || index === labels.length - 1 || index % Math.max(1, Math.floor(labels.length / 4)) === 0);

  return (
    <div className="progress-curve">
      <div className="progress-curve-legend">
        <span><i className="baseline" />基准计划累计曲线</span>
        <span><i className="forecast" />滚动预测累计曲线</span>
        <span><i className="actual" />当前实际点</span>
      </div>
      <svg viewBox="0 0 650 152" role="img" aria-label="基准计划、当前实际点与滚动预测累计曲线">
        {[0, 50, 100].map((value) => {
          const y = 130 - (value / 100) * 108;
          return <g key={value}><line x1="16" x2="626" y1={y} y2={y} className="grid" /><text x="2" y={y + 4}>{value}</text></g>;
        })}
        <path d={progressPath(data.baseline, minTime, maxTime)} className="baseline-line" />
        <path d={progressPath(data.forecast, minTime, maxTime)} className="forecast-line" />
        {data.actual && <g><circle cx={actualX} cy={actualY} r="6" className="actual-point" /><circle cx={actualX} cy={actualY} r="12" className="actual-pulse" /></g>}
        {shownLabels.map((date) => {
          const time = Date.parse(`${date}T00:00:00Z`);
          const x = 16 + ((time - minTime) / Math.max(1, maxTime - minTime)) * 610;
          return <text key={date} x={x} y="148" textAnchor="middle">{formatShortDate(date)}</text>;
        })}
      </svg>
    </div>
  );
}

function StateNotice({ data }: { data: ProgressVisualizationData }) {
  if (data.state === "ready") return null;
  const content = {
    no_plan: ["尚未确认执行基准计划", "请先在方案比选中确认可行方案。"],
    no_snapshot: ["实际进度尚未填报", "当前只展示执行基准，实际进度和预测风险暂不可用。"],
    no_forecast: ["待生成滚动预测", "已有实际进度快照，生成预测后可查看完工偏差和风险证据。"],
    stale: ["预测已过期", "进度或计划输入已经变化，旧预测不作为当前风险结论。"],
    insufficient_data: ["预测数据不足", "当前预测可信度较低，请查看求解诊断并补充进度数据。"],
    ready: ["", ""],
  }[data.state];
  return <div className={`progress-visualization-state ${data.state}`}><AlertTriangle size={17} /><div><strong>{content[0]}</strong><span>{content[1]}</span></div></div>;
}

function RouteOverview({
  data,
  mode,
  selectedBridgeId,
  highlightedBridgeId,
  selectedRiskId,
  onSelectBridge,
  onSelectRisk,
  onOpenBridge,
}: {
  data: ProgressVisualizationData;
  mode: ProgressVisualizationMode;
  selectedBridgeId: string | null;
  highlightedBridgeId: string | null;
  selectedRiskId: string | null;
  onSelectBridge: (id: string) => void;
  onSelectRisk: (id: string) => void;
  onOpenBridge: () => void;
}) {
  const selectedBridge = data.bridges.find((bridge) => bridge.id === selectedBridgeId) ?? data.bridges[0];
  return (
    <div className="progress-visualization-stage route" style={{ "--progress-background": `url(${routeBackground})` } as CSSProperties}>
      <div className="progress-visualization-backdrop" />
      <section className="progress-glass-panel route-list-panel">
        <div className="progress-panel-heading"><div><small>BRIDGE WORKPOINTS</small><strong>桥梁工点进度</strong></div><span>{data.bridges.length} 座</span></div>
        <div className="progress-bridge-list">
          {data.bridges.map((bridge) => (
            <button key={bridge.id} type="button" className={`progress-bridge-row ${selectedBridgeId === bridge.id ? "active" : ""}`} onClick={() => onSelectBridge(bridge.id)}>
              <div><strong>{bridge.name}</strong><span>{bridge.completedTasks}/{bridge.totalTasks} 项任务完成</span></div>
              {mode === "progress" ? <ProgressBars planned={bridge.plannedProgress} actual={bridge.actualProgress} /> : <span className={`progress-variance-chip ${bridge.finishVarianceDays && bridge.finishVarianceDays > 0 ? "late" : "ok"}`}>{varianceText(bridge.finishVarianceDays)}</span>}
              <small>计划 {bridge.plannedProgress.toFixed(1)}% · 实际 {bridge.actualProgress.toFixed(1)}%</small>
            </button>
          ))}
        </div>
      </section>

      <div className="progress-route-markers" aria-label="桥梁工点截图映射标记">
        {data.bridges.map((bridge) => (
          <button
            key={bridge.id}
            type="button"
            aria-label={`${bridge.name}，实际进度 ${bridge.actualProgress}%`}
            className={`progress-route-marker ${bridge.riskStatus} ${highlightedBridgeId === bridge.id ? "highlighted" : ""}`}
            style={{ left: `${bridge.position.x}%`, top: `${bridge.position.y}%` }}
            onClick={() => onSelectBridge(bridge.id)}
          >
            <span>{mode === "progress" ? `${Math.round(bridge.actualProgress)}%` : varianceText(bridge.finishVarianceDays)}</span>
          </button>
        ))}
      </div>

      <section className="progress-glass-panel route-focus-card">
        <small>当前选中桥梁</small>
        <strong>{selectedBridge?.name ?? "暂无桥梁"}</strong>
        <div><span>计划 {selectedBridge?.plannedProgress.toFixed(1) ?? "—"}%</span><span>实际 {selectedBridge?.actualProgress.toFixed(1) ?? "—"}%</span><span>完工偏差 {varianceText(selectedBridge?.finishVarianceDays ?? null)}</span></div>
        <button type="button" onClick={onOpenBridge}>查看单桥详情</button>
      </section>

      <section className="progress-glass-panel risk-panel">
        <div className="progress-panel-heading"><div><small>FORECAST EVIDENCE</small><strong>预测风险提示</strong></div><ShieldAlert size={20} /></div>
        <div className="progress-risk-list">
          {data.riskEvidence.length ? data.riskEvidence.map((risk) => (
            <button key={risk.id} type="button" className={`progress-risk-item ${selectedRiskId === risk.id ? "active" : ""}`} onClick={() => onSelectRisk(risk.id)}>
              <span className={`risk-dot ${risk.type}`} />
              <div><small>{evidenceLabels[risk.type]}</small><strong>{risk.message}</strong><span>{risk.varianceDays === null ? "来自当前滚动预测" : `预测偏差 ${varianceText(risk.varianceDays)}`}</span></div>
            </button>
          )) : <div className="progress-empty-copy">当前预测未返回风险证据。</div>}
        </div>
        <div className="progress-evidence-footnote"><Info size={13} />仅展示当前 Demo 返回的预测证据，不代表风险处置闭环。</div>
      </section>
    </div>
  );
}

function BridgeDetail({
  data,
  mode,
  selectedComponent,
  onSelectComponent,
}: {
  data: ProgressVisualizationData;
  mode: ProgressVisualizationMode;
  selectedComponent: ComponentType | "all";
  onSelectComponent: (value: ComponentType | "all") => void;
}) {
  const visibleComponents = selectedComponent === "all"
    ? data.components
    : data.components.filter((component) => component.componentType === selectedComponent);
  const selectedBridge = data.bridges.find((bridge) => bridge.id === data.selectedBridgeId) ?? data.bridges[0];
  return (
    <div className="progress-visualization-stage bridge" style={{ "--progress-background": `url(${bridgeBackground})` } as CSSProperties}>
      <div className="progress-visualization-backdrop" />
      <section className="progress-glass-panel bridge-legend-panel">
        <div className="progress-panel-heading"><div><small>IMAGE PROGRESS</small><strong>{selectedBridge?.name ?? "单桥详情"}</strong></div><MapPinned size={20} /></div>
        <div className="progress-component-filters">
          <button type="button" className={selectedComponent === "all" ? "active" : ""} onClick={() => onSelectComponent("all")}>全部构件</button>
          {data.components.map((component) => <button type="button" key={component.componentType} className={selectedComponent === component.componentType ? "active" : ""} onClick={() => onSelectComponent(component.componentType)}>{component.label}</button>)}
        </div>
        <div className="progress-status-legend">
          {(["completed", "in_progress", "ahead", "late", "on_track", "not_started"] as StructureProgressStatus[]).map((status) => <span key={status}><i className={status} />{structureStatusLabels[status]}</span>)}
        </div>
        <div className="progress-derived-note"><Info size={14} /><span>计划/实际进度为任务等权派生值，仅用于展示，不进入求解。</span></div>
      </section>

      <div className="progress-structure-markers" aria-label="结构物截图映射标记">
        {data.structures.map((marker) => (
          <button
            type="button"
            key={marker.id}
            className={`progress-structure-marker ${marker.status}`}
            style={{ left: `${marker.position.x}%`, top: `${marker.position.y}%` }}
            title={`${marker.name}：计划 ${marker.plannedProgress}% / 实际 ${marker.actualProgress}% / ${varianceText(marker.varianceDays)}`}
          >
            <i />
            <span>{marker.name}<small>{mode === "progress" ? `${Math.round(marker.actualProgress)}%` : varianceText(marker.varianceDays)}</small></span>
          </button>
        ))}
      </div>

      <section className="progress-glass-panel component-progress-panel">
        <div className="progress-panel-heading"><div><small>COMPONENT PROGRESS</small><strong>构件类型对比</strong></div><BarChart3 size={20} /></div>
        <div className="progress-component-list">
          {visibleComponents.map((component) => (
            <div className="progress-component-row" key={component.componentType}>
              <div><strong>{component.label}</strong><span>{component.completedTasks}/{component.totalTasks} 项任务完成</span></div>
              <div className="progress-component-values"><span>计划 {component.plannedProgress.toFixed(1)}%</span><span>实际 {component.actualProgress.toFixed(1)}%</span><em className={component.variance < 0 ? "late" : "ahead"}>{formatPercent(component.variance, true)}</em></div>
              <ProgressBars planned={component.plannedProgress} actual={component.actualProgress} />
            </div>
          ))}
        </div>
      </section>

      <section className="progress-glass-panel bridge-bottom-panel">
        <div className="progress-curve-card"><div className="progress-panel-heading compact"><div><small>BASELINE / ACTUAL / FORECAST</small><strong>累计进度趋势</strong></div></div><ProgressCurve data={data.curve} /></div>
        <div className="progress-milestone-card">
          <div className="progress-panel-heading compact"><div><small>MILESTONE FORECAST</small><strong>关键节点预测</strong></div></div>
          <div className="progress-milestone-list">
            {data.milestones.map((milestone) => <div key={milestone.id} className={milestone.status}><i /><div><strong>{milestone.name}</strong><span>目标 {formatShortDate(milestone.targetDate)} · 预测 {milestone.predictedDate ? formatShortDate(milestone.predictedDate) : "—"}</span></div><em>{varianceText(milestone.latenessDays)}</em></div>)}
          </div>
        </div>
        <div className="progress-diagnostic-card">
          <div className="progress-panel-heading compact"><div><small>FORECAST DIAGNOSTICS</small><strong>预测影响诊断</strong></div></div>
          <dl>
            <div><dt>瓶颈资源</dt><dd>{data.diagnostics.bottleneckResources.join("、") || "暂无"}</dd></div>
            <div><dt>关键任务候选</dt><dd>{data.diagnostics.criticalTasks.slice(0, 2).join("、") || "暂无"}</dd></div>
            <div><dt>转场影响</dt><dd>跳墩 {data.diagnostics.jumpPierCount} 次 / 换幅 {data.diagnostics.sideSwitchCount} 次</dd></div>
            <div><dt>等待影响</dt><dd>{data.diagnostics.waitingStatus}</dd></div>
          </dl>
        </div>
      </section>
    </div>
  );
}

export function ProgressVisualizationPanel({ data = demoProgressVisualizationData }: { data?: ProgressVisualizationData }) {
  const [view, setView] = useState<ProgressVisualizationView>("bridge");
  const [mode, setMode] = useState<ProgressVisualizationMode>("progress");
  const [selectedBridgeId, setSelectedBridgeId] = useState<string | null>(data.selectedBridgeId ?? data.bridges[0]?.id ?? null);
  const [selectedRiskId, setSelectedRiskId] = useState<string | null>(data.riskEvidence[0]?.id ?? null);
  const [selectedComponent, setSelectedComponent] = useState<ComponentType | "all">("all");
  const selectedRisk = useMemo(() => data.riskEvidence.find((item) => item.id === selectedRiskId) ?? null, [data.riskEvidence, selectedRiskId]);
  const riskStatus = data.forecastRiskStatus;
  const finishVariance = data.overview.finishVarianceDays;

  return (
    <section className="progress-visualization-page">
      <header className="progress-visualization-header">
        <div className="progress-visualization-brand">
          <span><Sparkles size={18} /></span>
          <div><small>LINEAR PROJECT CONTROL CENTER</small><h1>线性工程形象进度一张图</h1></div>
        </div>
        <div className="progress-visualization-context">
          <span className="demo-badge"><Database size={13} />演示数据</span>
          <span>{data.projectName}</span>
          <span>{data.planVersionLabel} · {data.planStatusLabel}</span>
          <span>状态日期 {formatDate(data.statusDate)}</span>
          <span>修订 {data.revisionNo ?? "—"}</span>
        </div>
        <div className="progress-visualization-switches">
          <div className="progress-segmented" aria-label="展示层级">
            <button type="button" className={view === "route" ? "active" : ""} onClick={() => setView("route")}><Route size={15} />线路总览</button>
            <button type="button" className={view === "bridge" ? "active" : ""} onClick={() => setView("bridge")}><MapPinned size={15} />单桥详情</button>
          </div>
          <div className="progress-segmented" aria-label="展示模式">
            <button type="button" className={mode === "progress" ? "active" : ""} onClick={() => setMode("progress")}><Activity size={15} />形象进度</button>
            <button type="button" className={mode === "variance" ? "active" : ""} onClick={() => setMode("variance")}><GitCompareArrows size={15} />偏差分析</button>
          </div>
        </div>
      </header>

      <StateNotice data={data} />

      <div className="progress-visualization-metrics">
        <MetricCard label="任务等权计划进度" value={formatPercent(data.overview.plannedProgress)} hint="由基准任务日期派生" icon={<CalendarClock size={18} />} />
        <MetricCard label="任务等权实际进度" value={formatPercent(data.overview.actualProgress)} hint={`填报覆盖率 ${formatPercent(data.overview.coverage)}`} tone="success" icon={<CheckCircle2 size={18} />} />
        <MetricCard label="进度偏差" value={formatPercent(data.overview.progressVariance, true)} hint="实际进度 - 计划进度" tone={(data.overview.progressVariance ?? 0) < 0 ? "danger" : "success"} icon={<GitCompareArrows size={18} />} />
        <MetricCard label="基准完工" value={formatDate(data.overview.baselineFinishDate)} hint="当前执行计划" icon={<Clock3 size={18} />} />
        <MetricCard
          label="预测完工"
          value={formatDate(data.overview.predictedFinishDate)}
          hint={finishVariance === null
            ? "待生成滚动预测"
            : `完工偏差 ${varianceText(finishVariance)} · 可信度 ${data.forecastConfidence ?? "—"}`}
          tone={finishVariance && finishVariance > 0 ? "danger" : "default"}
          icon={<CalendarClock size={18} />}
        />
        <MetricCard label="预测风险" value={riskStatus ? riskLabels[riskStatus] : "待预测"} hint={`迟延节点 ${data.overview.lateMilestoneCount ?? "—"} 个`} tone={riskStatus === "late" ? "danger" : riskStatus === "at_risk" ? "warning" : "success"} icon={<ShieldAlert size={18} />} />
      </div>

      {view === "route" ? (
        <RouteOverview
          data={data}
          mode={mode}
          selectedBridgeId={selectedBridgeId}
          highlightedBridgeId={selectedRisk?.bridgeId ?? selectedBridgeId}
          selectedRiskId={selectedRiskId}
          onSelectBridge={setSelectedBridgeId}
          onSelectRisk={setSelectedRiskId}
          onOpenBridge={() => setView("bridge")}
        />
      ) : (
        <BridgeDetail data={data} mode={mode} selectedComponent={selectedComponent} onSelectComponent={setSelectedComponent} />
      )}
    </section>
  );
}
