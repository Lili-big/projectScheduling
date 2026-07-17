import { Bot, CheckCircle2, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import type { ResourceAssistantPlan, ResourceAssistantRecommendation } from "../../contracts";
import { llmConfigStatusLabel, resourceAssistantProfileLabels } from "../../domain/resourceAssistant";

export function RecommendationPanel({
  recommendation,
  plans,
  loading = false,
  error,
  onRetry,
}: {
  recommendation: ResourceAssistantRecommendation | null;
  plans: ResourceAssistantPlan[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}) {
  if (!recommendation && !loading && !error) {
    return null;
  }
  if (!recommendation) {
    return (
      <section className="panel full recommendation-panel">
        <div className="recommendation-title"><div><span>AI解释推荐</span><h2>{loading ? "正在生成推荐" : "推荐生成失败"}</h2></div></div>
        <p className="recommendation-explanation">{loading ? "正在基于完整三方案结果生成确定性推荐和解释。" : error}</p>
        {error && onRetry && <button className="secondary" type="button" onClick={onRetry}>重试生成推荐</button>}
      </section>
    );
  }
  const plan = plans.find((item) => item.scenario_id === recommendation.recommended_scenario_id);
  return (
    <section className="panel full recommendation-panel">
      <div className="recommendation-title">
        <div>
          <span>AI解释推荐</span>
          <h2>
            {recommendation.recommendation_status === "recommended" && plan
              ? `${resourceAssistantProfileLabels[plan.profile]}：${plan.scenario_name}`
              : "暂无推荐方案"}
          </h2>
        </div>
        <span className="recommendation-source">
          <Bot size={15} />
          {recommendation.explanation_source === "llm" ? "外部模型解释" : llmConfigStatusLabel(recommendation.llm_status)}
        </span>
      </div>
      <p className="recommendation-explanation">{recommendation.ai_explanation || recommendation.rule_reason}</p>
      <div className="recommendation-grid">
        <EvidenceList icon={<CheckCircle2 size={15} />} title="证据" items={recommendation.evidence} />
        <EvidenceList icon={<TriangleAlert size={15} />} title="风险" items={recommendation.risk_notes} />
        <EvidenceList icon={<Bot size={15} />} title="边际收益" items={recommendation.marginal_benefit_notes} />
      </div>
    </section>
  );
}

function EvidenceList({ icon, title, items }: { icon: ReactNode; title: string; items: string[] }) {
  return (
    <div className="recommendation-list">
      <h3>
        {icon}
        {title}
      </h3>
      <ul>
        {(items.length ? items : ["暂无"]).map((item, index) => (
          <li key={`${title}-${index}`}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
