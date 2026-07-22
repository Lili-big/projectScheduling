import type { BeamTypeCapacity, BeamYardPlan, ErectionLinePlan, LineGraphSnapshot } from "../../contracts";
import { yardNodeId } from "./adapter";

export function YardPlanEditor({
  graph,
  yards,
  lines,
  onYardsChange,
  onLinesChange,
}: {
  graph: LineGraphSnapshot | null;
  yards: BeamYardPlan[];
  lines: ErectionLinePlan[];
  onYardsChange: (yards: BeamYardPlan[]) => void;
  onLinesChange: (lines: ErectionLinePlan[]) => void;
}) {
  function addYard() {
    const suffix = `${Date.now()}-${yards.length + 1}`;
    const yardId = `yard-${suffix}`;
    const lineId = `line-${suffix}`;
    const today = new Date().toISOString().slice(0, 10);
    const firstNode = graph?.nodes.find((node) => node.alignment_code != null && node.start_mileage_m != null);
    const firstMileage = firstNode?.start_mileage_m != null && firstNode.end_mileage_m != null
      ? (firstNode.start_mileage_m + firstNode.end_mileage_m) / 2
      : firstNode?.start_mileage_m ?? 0;
    onYardsChange([...yards, {
      beam_yard_id: yardId,
      name: `${yards.length + 1}号梁场`,
      deployment_node_id: firstNode?.node_id ?? null,
      alignment_code: firstNode?.alignment_code ?? "",
      mileage_m: firstMileage,
      production_start_date: today,
      capacities: [],
      enabled: true,
    }]);
    onLinesChange([...lines, {
      erection_line_id: lineId,
      beam_yard_id: yardId,
      available_date: today,
      daily_erection_capacity_pieces: 1,
      first_erection_preparation_days: 0,
      bridge_transfer_days: 1,
      side_switch_days: 1,
      enabled: true,
    }]);
  }

  function updateYard(index: number, patch: Partial<BeamYardPlan>) {
    onYardsChange(yards.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item));
  }

  function updateLine(yardId: string, patch: Partial<ErectionLinePlan>) {
    onLinesChange(lines.map((item) => item.beam_yard_id === yardId ? { ...item, ...patch } : item));
  }

  function removeYard(yardId: string) {
    onYardsChange(yards.filter((item) => item.beam_yard_id !== yardId));
    onLinesChange(lines.filter((item) => item.beam_yard_id !== yardId));
  }

  return (
    <section className="girder-sim-card" aria-label="梁场与架梁能力">
      <div className="girder-sim-card-heading">
        <div><h3>梁场与架梁能力</h3><p>制梁能力按梁型维护，单位为片/天；每个梁场首期只配置一条架梁线。</p></div>
        <button type="button" onClick={addYard} disabled={!graph}>新增梁场</button>
      </div>
      {yards.length === 0 && <div className="girder-sim-empty">尚未录入梁场。</div>}
      {yards.map((yard, index) => {
        const line = lines.find((item) => item.beam_yard_id === yard.beam_yard_id);
        const selectedNodeId = yardNodeId(yard, graph?.nodes ?? []);
        const selectedNode = graph?.nodes.find((node) => node.node_id === selectedNodeId);
        const deploymentMissing = Boolean(yard.deployment_node_id)
          && !(graph?.nodes ?? []).some((node) => node.node_id === yard.deployment_node_id);
        return (
          <article className="girder-sim-yard" key={yard.beam_yard_id} data-entity-id={yard.beam_yard_id} tabIndex={-1}>
            <div className="girder-sim-grid four">
              <label>梁场名称<input value={yard.name} onChange={(event) => updateYard(index, { name: event.target.value })} /></label>
              <label>部署位置<select value={selectedNodeId} onChange={(event) => {
                const node = graph?.nodes.find((item) => item.node_id === event.target.value);
                if (node?.alignment_code != null && node.start_mileage_m != null) {
                  const centerMileage = node.end_mileage_m == null ? node.start_mileage_m : (node.start_mileage_m + node.end_mileage_m) / 2;
                  updateYard(index, { deployment_node_id: node.node_id, alignment_code: node.alignment_code, mileage_m: centerMileage });
                }
              }}>
                {selectedNodeId === "" && <option value="">请选择可定位节点</option>}
                {deploymentMissing && <option value={yard.deployment_node_id ?? ""}>原部署节点已失效，请重新选择</option>}
                {(graph?.nodes ?? []).filter((node) => node.alignment_code != null && node.start_mileage_m != null).map((node) => <option value={node.node_id} key={node.node_id}>{node.side === "left" ? "左幅" : "右幅"}｜{node.name}｜{node.alignment_code} {formatMileage(node.start_mileage_m!)}</option>)}
              </select></label>
              <label>梁场中心里程（m）<input
                type="number"
                step="0.001"
                min={selectedNode?.start_mileage_m ?? undefined}
                max={selectedNode?.end_mileage_m ?? undefined}
                value={yard.mileage_m}
                onChange={(event) => updateYard(index, { mileage_m: Number(event.target.value) })}
              /></label>
              <label>投产日期<input type="date" value={yard.production_start_date} onChange={(event) => updateYard(index, { production_start_date: event.target.value })} /></label>
              <label>架梁可用日期<input type="date" value={line?.available_date ?? ""} onChange={(event) => updateLine(yard.beam_yard_id, { available_date: event.target.value })} /></label>
              <label>架梁能力（片/天）<input type="number" min="1" value={line?.daily_erection_capacity_pieces ?? 0} onChange={(event) => updateLine(yard.beam_yard_id, { daily_erection_capacity_pieces: Number(event.target.value) })} /></label>
              <label>首架准备（天）<input type="number" min="0" value={line?.first_erection_preparation_days ?? 0} onChange={(event) => updateLine(yard.beam_yard_id, { first_erection_preparation_days: Number(event.target.value) })} /></label>
              <label>桥间转场（天）<input type="number" min="0" value={line?.bridge_transfer_days ?? 0} onChange={(event) => updateLine(yard.beam_yard_id, { bridge_transfer_days: Number(event.target.value) })} /></label>
              <label>换幅（天）<input type="number" min="0" value={line?.side_switch_days ?? 0} onChange={(event) => updateLine(yard.beam_yard_id, { side_switch_days: Number(event.target.value) })} /></label>
            </div>
            <div className="girder-sim-capacity-heading"><strong>分梁型产能与期初库存</strong><button type="button" onClick={() => updateYard(index, { capacities: [...yard.capacities, emptyCapacity()] })}>增加梁型</button></div>
            {yard.capacities.map((capacity, capacityIndex) => (
              <div className="girder-sim-capacity-row" key={`${yard.beam_yard_id}-${capacityIndex}`}>
                <label>梁型<input aria-label="梁型" placeholder="如 T32" value={capacity.beam_type_id} onChange={(event) => updateCapacity(yard, index, capacityIndex, { beam_type_id: event.target.value }, updateYard)} /></label>
                <label>制梁能力（片/天）<input aria-label="制梁能力" type="number" min="0" value={capacity.daily_capacity_pieces} onChange={(event) => updateCapacity(yard, index, capacityIndex, { daily_capacity_pieces: Number(event.target.value) }, updateYard)} /></label>
                <label>期初库存（片）<input aria-label="期初库存" type="number" min="0" value={capacity.initial_inventory_pieces} onChange={(event) => updateCapacity(yard, index, capacityIndex, { initial_inventory_pieces: Number(event.target.value) }, updateYard)} /></label>
                <label>最大库存（片，可空）<input aria-label="最大库存" type="number" min="0" placeholder="不限制" value={capacity.max_inventory_pieces ?? ""} onChange={(event) => updateCapacity(yard, index, capacityIndex, { max_inventory_pieces: event.target.value === "" ? null : Number(event.target.value) }, updateYard)} /></label>
                <button type="button" onClick={() => updateYard(index, { capacities: yard.capacities.filter((_, itemIndex) => itemIndex !== capacityIndex) })}>删除梁型</button>
              </div>
            ))}
            <button className="danger" type="button" onClick={() => removeYard(yard.beam_yard_id)}>删除梁场</button>
          </article>
        );
      })}
    </section>
  );
}

function formatMileage(mileage: number): string {
  const kilometers = Math.floor(mileage / 1000);
  return `${kilometers}+${(mileage - kilometers * 1000).toFixed(0).padStart(3, "0")}`;
}

function emptyCapacity(): BeamTypeCapacity {
  return { beam_type_id: "", daily_capacity_pieces: 0, initial_inventory_pieces: 0, max_inventory_pieces: null };
}

function updateCapacity(
  yard: BeamYardPlan,
  yardIndex: number,
  capacityIndex: number,
  patch: Partial<BeamTypeCapacity>,
  updateYard: (index: number, patch: Partial<BeamYardPlan>) => void,
) {
  updateYard(yardIndex, {
    capacities: yard.capacities.map((item, index) => index === capacityIndex ? { ...item, ...patch } : item),
  });
}
