import type { ResourceAssistantComparison, ResourceAssistantPlan, ResourceAssistantPlanResult } from "../../types/scheduler";
import { metricValueDisplay, resourceAssistantProfileLabels } from "../../domain/resourceAssistant";

export function MetricComparisonTable({
  comparison,
  plans,
  planResults,
}: {
  comparison: ResourceAssistantComparison | null;
  plans: ResourceAssistantPlan[];
  planResults: ResourceAssistantPlanResult[];
}) {
  if (!comparison || comparison.metric_rows.length === 0) {
    const completed = planResults.length;
    return (
      <div className="resource-assistant-empty">
        <strong>暂无指标对比</strong>
        <span>{completed > 0 ? `已完成 ${completed} 个方案，正在刷新指标对比。` : "请先分别求解方案 A、B、C。"}</span>
      </div>
    );
  }
  const columns = plans.map((plan) => ({
    scenarioId: plan.scenario_id,
    label: resourceAssistantProfileLabels[plan.profile],
    name: plan.scenario_name,
  }));
  return (
    <div className="resource-metric-table-wrap">
      <table className="resource-metric-table">
        <thead>
          <tr>
            <th>指标</th>
            {columns.map((column) => (
              <th key={column.scenarioId}>
                <span>{column.label}</span>
                <small>{column.name}</small>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {comparison.metric_rows.map((row) => (
            <tr key={row.metric_id}>
              <td>
                <strong>{row.metric_name}</strong>
                <span>{row.source_type === "solver_result" ? "求解结果" : row.source_type === "demo_estimate" ? "演示估算" : "派生诊断"}</span>
              </td>
              {columns.map((column) => (
                <td key={column.scenarioId}>
                  {planResults.some((result) => result.scenario_id === column.scenarioId)
                    ? metricValueDisplay(row, column.scenarioId)
                    : "待求解"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
