import type { ResourceAssistantPlanResult } from "../../types/scheduler";
import { isRecord } from "../../domain/resourceAssistant";

export function ControlPierFocusView({ result }: { result: ResourceAssistantPlanResult | null }) {
  const releases = result?.metrics.control_pier_release_dates || [];
  if (!result || releases.length === 0) {
    return (
      <div className="resource-assistant-empty">
        <strong>暂无控制墩专项数据</strong>
        <span>未识别控制墩，或当前方案未完成可行求解。</span>
      </div>
    );
  }
  return (
    <div className="control-pier-focus">
      {releases.filter(isRecord).map((item) => {
        const chain = Array.isArray(item.task_chain) ? item.task_chain.filter(isRecord).slice(0, 8) : [];
        return (
          <article className="control-pier-focus-item" key={String(item.structure_id)}>
            <div>
              <strong>{String(item.structure_name || "控制墩")}</strong>
              <span>{String(item.release_task_name || "下部结构完成")}</span>
              {chain.length > 0 && (
                <div className="control-pier-chain">
                  {chain.map((task) => (
                    <span key={String(task.task_id)}>{String(task.task_name || task.task_id)}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="control-pier-focus-date">
              <b>{String(item.release_date || "-")}</b>
              <span>{item.wait_days === null || item.wait_days === undefined ? "连续梁未匹配" : `等待 ${item.wait_days} 天`}</span>
            </div>
          </article>
        );
      })}
    </div>
  );
}
