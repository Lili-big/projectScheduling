import { useMemo, useState } from "react";
import type { LineGraphSnapshot, WorkpointDeliveryControl } from "../../contracts";
import { diagnosticClass, diagnosticLabel, focusDiagnostic } from "./adapter";

export function LineGraphView({
  graph,
  controls = [],
  onConfirmConnection,
}: {
  graph: LineGraphSnapshot | null;
  controls?: WorkpointDeliveryControl[];
  onConfirmConnection?: (fromNodeId: string, toNodeId: string) => void;
}) {
  const [connectionNodes, setConnectionNodes] = useState<string[]>([]);
  const controlByNode = useMemo(() => new Map(controls.map((item) => [item.node_id, item])), [controls]);
  const groups = useMemo(() => {
    const grouped = new Map<string, LineGraphSnapshot["nodes"]>();
    for (const node of graph?.nodes ?? []) {
      const key = node.alignment_code || "未分线路";
      grouped.set(key, [...(grouped.get(key) ?? []), node]);
    }
    for (const nodes of grouped.values()) {
      nodes.sort((left, right) => (left.start_mileage_m ?? Number.MAX_SAFE_INTEGER) - (right.start_mileage_m ?? Number.MAX_SAFE_INTEGER));
    }
    return [...grouped.entries()];
  }, [graph]);

  if (!graph) return <div className="girder-sim-empty">请选择已确认项目主数据版本以生成线路图。</div>;

  function toggleConnectionNode(nodeId: string) {
    setConnectionNodes((current) => current.includes(nodeId) ? current.filter((item) => item !== nodeId) : [...current.slice(-1), nodeId]);
  }

  return (
    <section className="girder-sim-card" aria-label="项目线路图">
      <div className="girder-sim-card-heading">
        <div>
          <h3>项目线路图</h3>
          <p>系统按线路与里程连接工点；桥梁按幅别显示，梁场部署到具体节点。</p>
        </div>
        <span className={`girder-sim-status ${graph.status}`}>{graph.status === "ready" ? "线路可用" : graph.status === "warning" ? "存在提示" : "线路阻断"}</span>
      </div>
      {graph.diagnostics.length > 0 && (
        <div className="girder-sim-diagnostics">
          {graph.diagnostics.map((item) => <button type="button" className={diagnosticClass(item)} key={`${item.code}-${item.subject_id ?? item.entity_refs.join("-")}`} onClick={() => focusDiagnostic(item)}>{diagnosticLabel(item)}</button>)}
        </div>
      )}
      <div className="girder-sim-lines">
        {groups.map(([alignment, nodes]) => (
          <div className="girder-sim-line" key={alignment}>
            <strong>{alignment}</strong>
            <div className="girder-sim-line-track">
              {nodes.map((node) => {
                const control = controlByNode.get(node.node_id);
                return (
                  <button
                    type="button"
                    key={node.node_id}
                    data-entity-id={node.node_id}
                    className={`girder-sim-node ${node.node_type} ${control?.risk_status ?? ""} ${connectionNodes.includes(node.node_id) ? "selected" : ""}`}
                    title={`${node.node_id}｜${node.start_mileage_m ?? "缺里程"}`}
                    onClick={() => toggleConnectionNode(node.node_id)}
                  >
                    <span>{node.name}</span>
                    <small>{node.start_mileage_m == null ? "缺里程" : `K${(node.start_mileage_m / 1000).toFixed(3)}`}</small>
                    {control && <em>最晚 {control.latest_delivery_date}</em>}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {onConfirmConnection && (
        <div className="girder-sim-connection">
          <span>人工连接确认：依次选择两个节点（已选 {connectionNodes.length}/2）</span>
          <button
            type="button"
            disabled={connectionNodes.length !== 2}
            onClick={() => {
              if (connectionNodes.length !== 2) return;
              onConfirmConnection(connectionNodes[0], connectionNodes[1]);
              setConnectionNodes([]);
            }}
          >确认连接</button>
        </div>
      )}
    </section>
  );
}
