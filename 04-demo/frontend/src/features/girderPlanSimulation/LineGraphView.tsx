import { useMemo, useState } from "react";
import { LandPlot, Route, Warehouse, Waypoints } from "lucide-react";
import type { BeamYardPlan, LineGraphNode, LineGraphSnapshot, WorkpointDeliveryControl } from "../../contracts";
import { diagnosticClass, diagnosticLabel, focusDiagnostic, yardNodeId } from "./adapter";

type SpatialGroupLayout = {
  spatialGroupId: string;
  displayOrder: number;
  nodes: LineGraphNode[];
  kStartMileageM: number | null;
  kEndMileageM: number | null;
  widthPx: number;
};

export function LineGraphView({
  graph,
  controls = [],
  yards = [],
  onConfirmConnection,
}: {
  graph: LineGraphSnapshot | null;
  controls?: WorkpointDeliveryControl[];
  yards?: BeamYardPlan[];
  onConfirmConnection?: (fromNodeId: string, toNodeId: string) => void;
}) {
  const [connectionNodes, setConnectionNodes] = useState<string[]>([]);
  const controlByNode = useMemo(() => new Map(controls.map((item) => [item.node_id, item])), [controls]);
  const layout = useMemo(() => {
    const grouped = new Map<string, { displayOrder: number; nodes: LineGraphNode[] }>();
    for (const node of graph?.nodes ?? []) {
      const current = grouped.get(node.spatial_group_id);
      grouped.set(node.spatial_group_id, {
        displayOrder: Math.min(current?.displayOrder ?? node.display_order, node.display_order),
        nodes: [...(current?.nodes ?? []), node],
      });
    }
    const groups = [...grouped.entries()]
      .sort((left, right) => left[1].displayOrder - right[1].displayOrder || left[0].localeCompare(right[0]));
    for (const [, group] of groups) {
      group.nodes.sort((left, right) => (
        left.display_order - right.display_order
        || (left.start_mileage_m ?? Number.POSITIVE_INFINITY) - (right.start_mileage_m ?? Number.POSITIVE_INFINITY)
        || segmentOrder(left.bridge_segment_kind) - segmentOrder(right.bridge_segment_kind)
        || left.node_id.localeCompare(right.node_id)
      ));
    }
    return groups.map(([spatialGroupId, group]): SpatialGroupLayout => {
      const kNodes = group.nodes.filter((node) => node.side === "right" && normalizedPrefix(node) === "K");
      const kRange = mileageRange(kNodes);
      return {
        spatialGroupId,
        displayOrder: group.displayOrder,
        nodes: group.nodes,
        kStartMileageM: kRange?.start ?? null,
        kEndMileageM: kRange?.end ?? null,
        widthPx: visualGroupWidth(group.nodes, kRange),
      };
    });
  }, [graph]);
  const trackStyle = useMemo(() => {
    const widths = layout.map((group) => `minmax(34px, ${group.widthPx}fr)`);
    return {
      gridTemplateColumns: widths.join(" "),
      minWidth: `${layout.length * 34}px`,
    };
  }, [layout]);
  const tracks = [
    { side: "left" as const, label: "左幅", prefix: "ZK" },
    { side: "right" as const, label: "右幅", prefix: "K" },
  ];
  const yardsByNode = useMemo(() => {
    const grouped = new Map<string, BeamYardPlan[]>();
    for (const yard of yards) {
      const nodeId = graph ? yardNodeId(yard, graph.nodes) : "";
      if (!nodeId) continue;
      grouped.set(nodeId, [...(grouped.get(nodeId) ?? []), yard]);
    }
    return grouped;
  }, [graph, yards]);

  if (!graph) return <div className="girder-sim-empty">请选择已确认项目主数据版本以生成线路图。</div>;

  function toggleConnectionNode(nodeId: string) {
    setConnectionNodes((current) => current.includes(nodeId) ? current.filter((item) => item !== nodeId) : [...current.slice(-1), nodeId]);
  }

  return (
    <section className="girder-sim-card" aria-label="项目线路图">
      <div className="girder-sim-card-heading">
        <div>
          <h3>项目线路图</h3>
          <p>固定按左右幅展示；AK、BK、B1K 等互通前缀属于节点，同一空间列不代表可横向通行。</p>
        </div>
        <span className={`girder-sim-status ${graph.status}`}>{graph.status === "ready" ? "线路可用" : graph.status === "warning" ? "存在提示" : "线路阻断"}</span>
      </div>
      {graph.diagnostics.length > 0 && (
        <div className="girder-sim-diagnostics">
          {graph.diagnostics.map((item) => <button type="button" className={diagnosticClass(item)} key={`${item.code}-${item.subject_id ?? item.entity_refs.join("-")}`} onClick={() => focusDiagnostic(item)}>{diagnosticLabel(item)}</button>)}
        </div>
      )}
      <div className="girder-sim-line-legend" aria-label="线路图图例">
        <LegendItem type="roadbed" label="路基" />
        <LegendItem type="bridge" label="桥梁" />
        <LegendItem type="tunnel" label="隧道" />
        <LegendItem type="connection" label="互通/连接" />
        <LegendItem type="yard" label="梁场" />
        <span className="girder-sim-scale-note">右幅 K 里程主轴｜路基压缩、桥隧增强显示</span>
      </div>
      {layout.length === 0 ? <div className="girder-sim-empty">当前版本没有可展示的分幅线路关系。</div> : (
        <div className="girder-sim-lines">
          <div className="girder-sim-line girder-sim-axis-line" aria-label="右幅K里程主轴">
            <strong><span>K里程</span></strong>
            <div className="girder-sim-mileage-axis-track" style={trackStyle}>
              {layout.map((group) => (
                <div
                  className={`girder-sim-mileage-axis-slot ${group.kStartMileageM == null ? "local" : ""}`}
                  data-axis-start-m={group.kStartMileageM ?? undefined}
                  key={`axis-${group.spatialGroupId}`}
                  title={group.kStartMileageM == null ? `${group.spatialGroupId} 暂无可比较的右幅 K 里程` : axisRangeLabel(group)}
                >
                  <span>{group.kStartMileageM == null ? `位${group.displayOrder}` : axisTickLabel(group)}</span>
                </div>
              ))}
            </div>
          </div>
          {tracks.map((track) => (
            <div className="girder-sim-line" key={track.side}>
              <strong><span>{track.label}</span><small>{track.prefix}</small></strong>
              <div className="girder-sim-line-track" style={trackStyle}>
                {layout.map((group) => {
                  const nodes = group.nodes.filter((node) => node.side === track.side);
                  const deployedYards = nodes.flatMap((node) => yardsByNode.get(node.node_id) ?? []);
                  return (
                    <div className="girder-sim-node-slot" key={`${track.side}-${group.spatialGroupId}`} data-spatial-group-id={group.spatialGroupId}>
                      <div className="girder-sim-node-labels">
                        {nodes.length === 0 ? <span className="girder-sim-slot-empty">该幅暂无工点</span> : nodes.map((node, nodeIndex) => {
                          const control = controlByNode.get(node.node_id);
                          const position = nodePositionPercent(node, nodes);
                          const lane = labelLane(group.displayOrder, nodeIndex);
                          return (
                            <button
                              type="button"
                              key={node.node_id}
                              data-entity-id={node.node_id}
                              className={`girder-sim-node-label lane-${lane} ${node.node_type} ${node.bridge_segment_kind ?? "whole"} ${control?.risk_status ?? ""} ${connectionNodes.includes(node.node_id) ? "selected" : ""}`}
                              style={{ left: `${position.center}%` }}
                              title={`${node.name}｜${node.node_id}｜${formatMileage(node)}`}
                              onClick={() => toggleConnectionNode(node.node_id)}
                            >
                              <span>{node.name}</span>
                              <small><b>{node.alignment_code ?? "缺前缀"}</b> {formatMileageRange(node)}{control && `｜最晚 ${control.latest_delivery_date}`}</small>
                              {control && <em>最晚 {control.latest_delivery_date}</em>}
                            </button>
                          );
                        })}
                      </div>
                      <div className="girder-sim-track-node">
                        {nodes.map((node) => {
                          const position = nodePositionPercent(node, nodes);
                          const className = `girder-sim-track-span ${node.node_type} ${node.bridge_segment_kind ?? "whole"} ${connectionNodes.includes(node.node_id) ? "selected" : ""}`;
                          return isLineOnlyNode(node.node_type) ? (
                            <button
                              type="button"
                              aria-label={`${node.name} ${formatMileageRange(node)}`}
                              className={className}
                              data-entity-id={`${node.node_id}:segment`}
                              key={`span-${node.node_id}`}
                              style={{ left: `${position.left}%`, width: `${position.width}%` }}
                              title={`${node.name}｜${formatMileageRange(node)}`}
                              onClick={() => toggleConnectionNode(node.node_id)}
                            />
                          ) : (
                            <span
                              aria-hidden="true"
                              className={className}
                              key={`span-${node.node_id}`}
                              style={{ left: `${position.left}%`, width: `${position.width}%` }}
                            />
                          );
                        })}
                        {nodes.filter((node) => !isLineOnlyNode(node.node_type)).map((node) => {
                          const position = nodePositionPercent(node, nodes);
                          return <span className={`girder-sim-track-marker ${node.node_type}`} key={node.node_id} style={{ left: `${position.center}%` }}><NodeTypeIcon type={node.node_type} /></span>;
                        })}
                      </div>
                      <div className="girder-sim-yard-markers">
                        {deployedYards.map((yard, yardIndex) => {
                          const node = nodes.find((item) => yardNodeId(yard, nodes) === item.node_id);
                          return (
                            <span
                              className="girder-sim-yard-marker"
                              key={yard.beam_yard_id}
                              data-entity-id={yard.beam_yard_id}
                              style={{ left: `${yardOffsetPercent(yard, node, nodes)}%`, top: `${6 + yardIndex * 28}px` }}
                              title={`${yard.name}｜${yard.alignment_code} ${formatMileageValue(yard.mileage_m)}`}
                            >
                              <Warehouse size={14} />
                              <span>{yard.name}<small>{yard.alignment_code} {formatMileageValue(yard.mileage_m)}</small></span>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
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

function LegendItem({ type, label }: { type: LineGraphNode["node_type"]; label: string }) {
  return <span className={`girder-sim-legend-item ${type}`}>{isLineOnlyNode(type) ? <span className={`girder-sim-legend-line ${type}`} /> : <NodeTypeIcon type={type} />}{label}</span>;
}

function NodeTypeIcon({ type }: { type: LineGraphNode["node_type"] }) {
  const props = { size: 15, strokeWidth: 2 };
  if (type === "roadbed") return <Route {...props} />;
  if (type === "yard") return <Warehouse {...props} />;
  if (type === "culvert") return <LandPlot {...props} />;
  return <Waypoints {...props} />;
}

function isLineOnlyNode(type: LineGraphNode["node_type"]): boolean {
  return type === "bridge" || type === "tunnel";
}

function labelLane(displayOrder: number, nodeIndex: number): 0 | 1 {
  return (displayOrder + nodeIndex) % 2 === 0 ? 0 : 1;
}

function segmentOrder(kind: LineGraphNode["bridge_segment_kind"]): number {
  if (kind === "approach_small") return 0;
  if (kind === "continuous") return 1;
  if (kind === "approach_large") return 2;
  return 0;
}

function formatMileage(node: LineGraphNode): string {
  if (node.start_mileage_m == null) return "缺里程";
  return formatMileageValue(node.start_mileage_m);
}

function formatMileageRange(node: LineGraphNode): string {
  if (node.start_mileage_m == null || node.end_mileage_m == null) return "缺里程";
  return `${formatMileageValue(node.start_mileage_m)}–${formatMileageValue(node.end_mileage_m)}`;
}

function formatMileageValue(value: number): string {
  const absolute = Math.abs(value);
  const kilometers = Math.floor(absolute / 1000);
  const meters = absolute - kilometers * 1000;
  return `${value < 0 ? "-" : ""}${kilometers}+${meters.toFixed(0).padStart(3, "0")}`;
}

function normalizedPrefix(node: LineGraphNode): string {
  return (node.alignment_code ?? "").trim().toUpperCase();
}

function mileageRange(nodes: LineGraphNode[]): { start: number; end: number } | null {
  const starts = nodes.map((node) => node.start_mileage_m).filter((value): value is number => value != null);
  const ends = nodes.map((node) => node.end_mileage_m).filter((value): value is number => value != null);
  if (!starts.length || !ends.length) return null;
  return { start: Math.min(...starts), end: Math.max(...ends) };
}

function nodePositionPercent(node: LineGraphNode, nodes: LineGraphNode[]): { left: number; width: number; center: number } {
  const range = mileageRange(nodes);
  if (!range || range.end <= range.start || node.start_mileage_m == null || node.end_mileage_m == null) {
    return { left: 2, width: 96, center: 50 };
  }
  const nodeStart = Math.min(node.start_mileage_m, node.end_mileage_m);
  const nodeEnd = Math.max(node.start_mileage_m, node.end_mileage_m);
  const left = Math.max(0, Math.min(100, ((nodeStart - range.start) / (range.end - range.start)) * 100));
  const right = Math.max(left, Math.min(100, ((nodeEnd - range.start) / (range.end - range.start)) * 100));
  const width = Math.max(2, right - left);
  return { left, width, center: Math.min(100, left + width / 2) };
}

function dominantNodeType(nodes: LineGraphNode[]): LineGraphNode["node_type"] | null {
  const priority: Record<LineGraphNode["node_type"], number> = {
    yard: 7,
    tunnel: 6,
    bridge: 5,
    culvert: 4,
    connection: 3,
    access: 2,
    roadbed: 1,
  };
  return nodes.reduce<LineGraphNode["node_type"] | null>((current, node) => (
    current == null || priority[node.node_type] > priority[current] ? node.node_type : current
  ), null);
}

function visualGroupWidth(nodes: LineGraphNode[], kRange: { start: number; end: number } | null): number {
  const type = dominantNodeType(nodes) ?? "roadbed";
  const localLength = Math.max(0, ...nodes.map((node) => (
    node.start_mileage_m != null && node.end_mileage_m != null ? Math.abs(node.end_mileage_m - node.start_mileage_m) : 0
  )));
  const length = Math.max(1, kRange ? kRange.end - kRange.start : localLength);
  const settings: Record<LineGraphNode["node_type"], { base: number; factor: number; min: number; max: number }> = {
    roadbed: { base: 70, factor: 1.3, min: 104, max: 180 },
    bridge: { base: 110, factor: 2.8, min: 156, max: 280 },
    tunnel: { base: 120, factor: 3.2, min: 176, max: 300 },
    yard: { base: 120, factor: 2.4, min: 150, max: 250 },
    culvert: { base: 95, factor: 2.0, min: 132, max: 220 },
    connection: { base: 105, factor: 2.2, min: 146, max: 240 },
    access: { base: 90, factor: 1.8, min: 126, max: 210 },
  };
  const setting = settings[type];
  return Math.round(Math.min(setting.max, Math.max(setting.min, setting.base + Math.sqrt(length) * setting.factor)));
}

function axisRangeLabel(group: SpatialGroupLayout): string {
  if (group.kStartMileageM == null || group.kEndMileageM == null) return `对应组 ${group.spatialGroupId}`;
  return `K${formatMileageValue(group.kStartMileageM)}–K${formatMileageValue(group.kEndMileageM)}`;
}

function axisTickLabel(group: SpatialGroupLayout): string {
  if (group.kStartMileageM == null) return `位${group.displayOrder}`;
  return `K${formatMileageValue(group.kStartMileageM)}`;
}

function yardOffsetPercent(yard: BeamYardPlan, node: LineGraphNode | undefined, nodes: LineGraphNode[]): number {
  const range = mileageRange(nodes);
  if (!range || range.start === range.end) return node ? nodePositionPercent(node, nodes).center : 50;
  const start = range.start;
  const end = range.end;
  const offset = ((yard.mileage_m - start) / (end - start)) * 100;
  return Math.min(92, Math.max(8, offset));
}
