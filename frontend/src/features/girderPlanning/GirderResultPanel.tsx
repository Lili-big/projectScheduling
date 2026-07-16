import type { GirderPlanningResult, IntegratedCalculationSnapshot } from "../../types/scheduler";

export function GirderResultPanel({
  result,
  integrated,
}: {
  result: GirderPlanningResult | null;
  integrated?: IntegratedCalculationSnapshot | null;
}) {
  if (!result) return <div className="empty-state">尚未执行架梁专项预览或联合计算。</div>;
  return (
    <section className="girder-result-grid">
      <article className="girder-card"><h3>1. 架梁日期如何计算</h3><p>共生成 {result.span_plans.length} 个分跨架梁计划，唯一归属 {result.ownerships.length} 个桥梁幅别。</p></article>
      <article className="girder-card"><h3>2. 前置工程何时必须完成</h3><p>形成 {result.latest_finish_controls.length} 个建议最迟完成控制，默认作为高优先级软控制。</p></article>
      <article className="girder-card"><h3>3. 供梁和存梁是否满足</h3><p>库存日序列 {result.yard_inventory_series.length} 条；任何负库存都会阻断计算。</p></article>
      <article className="girder-card"><h3>4. 路线与运梁路径是否成立</h3><p>路线运行 {result.route_runs.length} 条，通行释放 {result.passage_releases.length} 个。</p></article>
      <article className="girder-card"><h3>5. 本次方案发生了什么变化</h3><p>联合状态：{integrated?.status ?? result.status}；计算轮次：{integrated?.iterations.length ?? 0}。</p></article>
    </section>
  );
}
