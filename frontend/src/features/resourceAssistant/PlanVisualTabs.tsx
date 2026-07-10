import { BarChart3, GanttChartSquare, Landmark } from "lucide-react";
import { useMemo, useState } from "react";
import type { ResourceAssistantPlan, ResourceAssistantPlanResult, ScheduledTask } from "../../types/scheduler";
import { resourceAssistantProfileLabels } from "../../domain/resourceAssistant";
import { componentLabels } from "../../domain/labels";
import { ControlPierFocusView } from "./ControlPierFocusView";
import { ResourceUtilizationView } from "./ResourceUtilizationView";

type VisualTab = "gantt" | "resource" | "control";

export function PlanVisualTabs({
  plan,
  result,
}: {
  plan: ResourceAssistantPlan | null;
  result: ResourceAssistantPlanResult | null;
}) {
  const [active, setActive] = useState<VisualTab>("gantt");
  const tasks = useMemo(() => (result?.result?.tasks || []).slice(0, 42), [result]);
  return (
    <section className="panel full resource-visual-panel" data-selected-plan-id={plan?.scenario_id || ""}>
      <div className="resource-visual-header">
        <div>
          <span>方案视图</span>
          <h2>{plan ? `${resourceAssistantProfileLabels[plan.profile]} / ${plan.scenario_name}` : "待选择方案"}</h2>
        </div>
        <div className="resource-visual-tabs" role="tablist" aria-label="方案视图">
          <button className={active === "gantt" ? "is-active" : ""} type="button" onClick={() => setActive("gantt")}>
            <GanttChartSquare size={15} />
            整体计划
          </button>
          <button className={active === "resource" ? "is-active" : ""} type="button" onClick={() => setActive("resource")}>
            <BarChart3 size={15} />
            资源利用
          </button>
          <button className={active === "control" ? "is-active" : ""} type="button" onClick={() => setActive("control")}>
            <Landmark size={15} />
            控制墩
          </button>
        </div>
      </div>
      {active === "gantt" && <CompactGantt tasks={tasks} totalDays={result?.metrics.total_days || 1} />}
      {active === "resource" && <ResourceUtilizationView result={result} />}
      {active === "control" && <ControlPierFocusView result={result} />}
    </section>
  );
}

function CompactGantt({ tasks, totalDays }: { tasks: ScheduledTask[]; totalDays: number }) {
  if (tasks.length === 0) {
    return (
      <div className="resource-assistant-empty">
        <strong>暂无甘特图</strong>
        <span>方案求解后显示任务排程。</span>
      </div>
    );
  }
  const horizon = Math.max(1, totalDays);
  return (
    <div className="resource-gantt">
      {tasks.map((task) => {
        const left = Math.max(0, Math.min(100, (task.start_offset / horizon) * 100));
        const width = Math.max(3, Math.min(100 - left, ((task.end_offset - task.start_offset) / horizon) * 100));
        return (
          <div className="resource-gantt-row" key={task.id}>
            <div className="resource-gantt-label">
              <strong>{task.structure_name}</strong>
              <span>{componentLabels[task.component_type] || task.component_type}</span>
            </div>
            <div className="resource-gantt-track">
              <span style={{ left: `${left}%`, width: `${width}%` }}>
                {task.assigned_resource_name || task.process_name}
              </span>
            </div>
            <div className="resource-gantt-date">{task.finish_date}</div>
          </div>
        );
      })}
    </div>
  );
}
