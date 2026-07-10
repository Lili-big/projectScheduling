import type { ResourceAssistantPlanResult } from "../../types/scheduler";
import { numberValue, resourceAssistantResourceLabel } from "../../domain/resourceAssistant";

export function ResourceUtilizationView({ result }: { result: ResourceAssistantPlanResult | null }) {
  const metrics = result?.metrics;
  if (!metrics || metrics.resource_utilization_by_type.length === 0) {
    return (
      <div className="resource-assistant-empty">
        <strong>暂无资源利用率</strong>
        <span>方案求解后显示资源占用。</span>
      </div>
    );
  }
  return (
    <div className="resource-utilization-list">
      {metrics.resource_utilization_by_type.map((item) => {
        const resourceType = String(item.resource_type || "");
        const utilization = Math.max(0, Math.min(1, numberValue(item.utilization_rate)));
        return (
          <div className="resource-utilization-row" key={resourceType}>
            <div>
              <strong>{resourceAssistantResourceLabel(resourceType)}</strong>
              <span>
                {numberValue(item.resource_count).toFixed(0)} 个资源 / {numberValue(item.work_days).toFixed(0)} 工日
              </span>
            </div>
            <div className="resource-utilization-bar" aria-label={`${resourceAssistantResourceLabel(resourceType)}利用率`}>
              <span style={{ width: `${Math.round(utilization * 100)}%` }} />
            </div>
            <b>{Math.round(utilization * 100)}%</b>
          </div>
        );
      })}
    </div>
  );
}
