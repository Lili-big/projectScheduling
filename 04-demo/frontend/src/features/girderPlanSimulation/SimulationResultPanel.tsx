import { useMemo, useState } from "react";
import type { GirderPlanSimulationRun, LineGraphSnapshot } from "../../contracts";

export function SimulationResultPanel({
  graph,
  run,
  onConfirm,
  confirming,
}: {
  graph: LineGraphSnapshot | null;
  run: GirderPlanSimulationRun | null;
  onConfirm: (confirmedBy: string, reason: string) => void;
  confirming: boolean;
}) {
  const [confirmedBy, setConfirmedBy] = useState("本地计划工程师");
  const [reason, setReason] = useState("");
  const nameByNode = useMemo(() => new Map((graph?.nodes ?? []).map((node) => [node.node_id, node.name])), [graph]);

  if (!run) return <section className="girder-sim-card"><div className="girder-sim-empty">保存并运行方案后，这里展示梁场甘特、桥梁日期、工点交付控制和库存台账。</div></section>;
  return (
    <section className="girder-sim-card girder-sim-results" aria-label="独立架梁策划成果">
      <div className="girder-sim-result-banner">
        <strong>独立策划成果</strong>
        <span>非工程技术可行结论、非综合排程收敛结果、非正式执行基线</span>
        <span className={`girder-sim-status ${run.status}`}>{run.status}</span>
      </div>
      {run.reused_from_run_id && <div className="girder-sim-note">本次复用了相同输入指纹的运行：{run.reused_from_run_id}</div>}
      <h3>梁场甘特与桥梁日期</h3>
      <div className="girder-sim-gantt">
        {run.bridge_schedules.map((item) => <div className="girder-sim-gantt-row" key={`${item.route_plan_id}-${item.target_node_id}`}>
          <span>{item.beam_yard_id}｜{nameByNode.get(item.target_node_id) ?? item.target_node_id}</span>
          <div><b>{item.start_date}</b><i>→</i><b>{item.finish_date}</b></div>
          <small>{Object.entries(item.beam_type_counts).map(([type, pieces]) => `${type} ${pieces}片`).join("、")}｜{item.controlling_factors.join("、")}</small>
        </div>)}
      </div>
      <h3>工点最晚交付控制</h3>
      <div className="girder-sim-table-wrap"><table><thead><tr><th>工点</th><th>首次需要</th><th>最晚交付</th><th>控制来源</th><th>当前计划</th><th>风险</th><th>关联线路</th></tr></thead><tbody>
        {run.workpoint_controls.map((item) => <tr key={item.node_id} className={item.risk_status} data-entity-id={item.node_id} tabIndex={-1}>
          <td>{nameByNode.get(item.node_id) ?? item.node_id}</td><td>{item.first_required_date}</td><td>{item.latest_delivery_date}</td><td>{item.controlling_source}（缓冲{item.buffer_days}天）</td>
          <td>{item.current_plan_finish_date ?? "材料不足"}</td><td>{item.risk_status === "late" ? `晚交 ${item.late_days} 天` : item.risk_status === "on_time" ? "按期" : "材料不足"}</td>
          <td>{item.route_requirements.map((entry) => `${entry.route_plan_id}:${entry.required_date}`).join("；")}</td>
        </tr>)}
      </tbody></table></div>
      <h3>分梁型库存序列</h3>
      <div className="girder-sim-table-wrap compact"><table><thead><tr><th>日期</th><th>梁场</th><th>梁型</th><th>期初</th><th>生产</th><th>架设</th><th>期末</th></tr></thead><tbody>
        {run.inventory_ledger.map((item) => <tr key={`${item.date}-${item.beam_yard_id}-${item.beam_type_id}`}><td>{item.date}</td><td>{item.beam_yard_id}</td><td>{item.beam_type_id}</td><td>{item.opening_inventory_pieces}</td><td>{item.produced_pieces}</td><td>{item.erected_pieces}</td><td>{item.closing_inventory_pieces}</td></tr>)}
      </tbody></table></div>
      {run.status === "calculated" && <div className="girder-sim-confirm">
        <input aria-label="确认人" value={confirmedBy} onChange={(event) => setConfirmedBy(event.target.value)} placeholder="确认人" />
        <input aria-label="确认原因" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="确认原因（必填）" />
        <button type="button" disabled={confirming || !confirmedBy.trim() || !reason.trim()} onClick={() => onConfirm(confirmedBy, reason)}>确认独立策划成果</button>
      </div>}
      {run.status === "confirmed" && <div className="girder-sim-note success">已由 {run.confirmed_by} 确认：{run.confirmation_reason}</div>}
      {run.status === "stale" && <div className="girder-sim-note warning">输入已经变化，本结果仅保留用于追溯，必须重新计算。</div>}
    </section>
  );
}
