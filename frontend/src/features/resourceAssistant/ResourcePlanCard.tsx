import { AlertCircle, CheckCircle2, Eye, Loader2, Play, SlidersHorizontal } from "lucide-react";
import type { ResourceAssistantPlan, ResourceAssistantPlanResult } from "../../types/scheduler";
import {
  editableResourcePools,
  metricsSummary,
  resourceAssistantOutcomeDetail,
  resourceAssistantOutcomeLabels,
  resourceAssistantOutcomeTone,
  resourceAssistantResourceLabel,
  resourceAssistantProfileLabels,
  resourceAssistantStatusLabels,
  resourceAssistantStatusTone,
} from "../../domain/resourceAssistant";

export function ResourcePlanCard({
  plan,
  result,
  disabled,
  solving,
  isSelected,
  onSelect,
  onSolve,
  onViewDetails,
  onConfirmBaseline,
  confirmingBaseline,
  baselineVersionNo,
  onQuantityChange,
}: {
  plan: ResourceAssistantPlan;
  result?: ResourceAssistantPlanResult | null;
  disabled?: boolean;
  solving?: boolean;
  isSelected: boolean;
  onSelect: () => void;
  onSolve: () => void;
  onViewDetails?: () => void;
  onConfirmBaseline?: () => void;
  confirmingBaseline?: boolean;
  baselineVersionNo?: number | null;
  onQuantityChange: (resourceType: string, quantity: number) => void;
}) {
  const statusTone = resourceAssistantStatusTone(plan.solve_status);
  return (
    <article className={`resource-plan-card ${isSelected ? "is-selected" : ""}`}>
      <button className="resource-plan-card-hit" type="button" onClick={onSelect} aria-label={`查看${plan.scenario_name}`} />
      <header className="resource-plan-header">
        <div>
          <span className="resource-plan-profile">{resourceAssistantProfileLabels[plan.profile]}</span>
          <h3>{plan.scenario_name}</h3>
        </div>
        <span className={`resource-status-pill ${statusTone}`}>{resourceAssistantStatusLabels[plan.solve_status]}</span>
      </header>
      <p className="resource-plan-positioning">{plan.positioning}</p>
      <div className="resource-plan-metrics">{metricsSummary(result?.metrics)}</div>
      {result?.plan_status && (
        <div className="resource-plan-outcome">
          <span className={`resource-status-pill ${resourceAssistantOutcomeTone(result.plan_status)}`}>
            {resourceAssistantOutcomeLabels[result.plan_status]}
          </span>
          <small>{resourceAssistantOutcomeDetail(result)}</small>
        </div>
      )}
      <div className="resource-plan-resources">
        {editableResourcePools(plan).map((pool) => (
          <label className="resource-plan-resource" key={pool.id}>
            <span>{resourceAssistantResourceLabel(pool.type, plan.resource_pools)}</span>
            <input
              type="number"
              min={0}
              value={pool.quantity ?? 0}
              disabled={disabled}
              onChange={(event) => onQuantityChange(pool.type, Number(event.target.value))}
            />
          </label>
        ))}
      </div>
      <div className="resource-plan-footer">
        <span title={plan.generation_rationale}>
          <SlidersHorizontal size={14} />
          {plan.generation_source === "llm" ? "LLM生成" : plan.generation_source === "user_adjusted" ? "用户调整" : "本地回退"}
        </span>
        {plan.validation_messages.some((item) => item.level === "error") ? (
          <span className="danger">
            <AlertCircle size={14} />
            校验异常
          </span>
        ) : (
          <span>
            <CheckCircle2 size={14} />
            可送入求解
          </span>
        )}
      </div>
      <div className="resource-plan-actions">
        <button className="secondary resource-plan-solve" type="button" disabled={disabled} onClick={onSolve}>
          {solving ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
          {solving ? "求解中" : `求解${resourceAssistantProfileLabels[plan.profile]}`}
        </button>
        {result && onViewDetails && (
          <button className="secondary resource-plan-details" type="button" onClick={onViewDetails}>
            <Eye size={14} />
            查看方案详情
          </button>
        )}
        {result?.result && ["OPTIMAL", "FEASIBLE"].includes(result.result.status) && onConfirmBaseline && (
          <button className="secondary" type="button" disabled={disabled || confirmingBaseline} onClick={onConfirmBaseline}>
            {confirmingBaseline ? <Loader2 size={14} className="spin" /> : <CheckCircle2 size={14} />}
            {baselineVersionNo ? `已设为基准（第 ${baselineVersionNo} 版）` : "设为基准计划"}
          </button>
        )}
      </div>
      {plan.stale_reason && <div className="resource-plan-stale">{plan.stale_reason}</div>}
    </article>
  );
}
