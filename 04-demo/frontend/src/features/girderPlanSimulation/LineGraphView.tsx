import { useMemo, useState } from "react";
import { LandPlot, Warehouse, Waypoints } from "lucide-react";
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

type TrackDefinition = {
  side: "left" | "right";
  label: string;
  prefix: "ZK" | "K";
};

type BranchRoute = {
  prefix: string;
  nodes: LineGraphNode[];
};

export function LineGraphView({
  graph,
  controls = [],
  yards = [],
}: {
  graph: LineGraphSnapshot | null;
  controls?: WorkpointDeliveryControl[];
  yards?: BeamYardPlan[];
}) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
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
    const widths = layout.map((group) => `minmax(26px, ${group.widthPx}fr)`);
    return {
      gridTemplateColumns: widths.join(" "),
      minWidth: `${layout.length * 26}px`,
    };
  }, [layout]);
  const tracks: TrackDefinition[] = [
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
  const selectedNode = graph?.nodes.find((node) => node.node_id === selectedNodeId) ?? null;

  if (!graph) return <div className="girder-sim-empty">请选择已确认项目主数据版本以生成线路图。</div>;

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
        <LegendItem type="bridge" label="待架桥梁（引桥段）" />
        <span className="girder-sim-legend-item continuous"><span className="girder-sim-legend-line continuous" />连续结构（仅通行）</span>
        <LegendItem type="tunnel" label="隧道" />
        <LegendItem type="connection" label="互通/连接" />
        <LegendItem type="yard" label="梁场" />
        {selectedNode && <span className="girder-sim-selected-summary" title={selectedNode.name}>已选：{workpointDisplayName(selectedNode)}｜{segmentRoleLabel(selectedNode)}</span>}
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
                  const sideNodes = group.nodes.filter((node) => node.side === track.side);
                  const mainlineNodes = sideNodes.filter((node) => isMainlineNode(node, track));
                  const groupedBranches = branchRoutes(sideNodes, track);
                  const deployedYards = sideNodes.flatMap((node) => yardsByNode.get(node.node_id) ?? []);
                  return (
                    <div className={`girder-sim-node-slot ${mainlineNodes.some((node) => node.bridge_segment_kind != null) ? "has-segments" : ""}`} key={`${track.side}-${group.spatialGroupId}`} data-spatial-group-id={group.spatialGroupId}>
                      <div className="girder-sim-node-labels">
                        {mainlineNodes.map((node, nodeIndex) => {
                          const control = controlByNode.get(node.node_id);
                          const position = nodePositionPercent(node, mainlineNodes);
                          const lane = labelLane(group.displayOrder, nodeIndex, mainlineNodes.length);
                          return (
                            <span
                              key={node.node_id}
                              data-entity-id={node.node_id}
                              className={`girder-sim-node-label lane-${lane} ${node.node_type} ${node.bridge_segment_kind ?? "whole"} ${control?.risk_status ?? ""} ${selectedNodeId === node.node_id ? "selected" : ""}`}
                              style={{ left: `${position.center}%` }}
                              title={node.name}
                            >
                              <span>{workpointDisplayName(node)}</span>
                            </span>
                          );
                        })}
                      </div>
                      <div className="girder-sim-track-node">
                        {mainlineNodes.map((node) => {
                          const position = nodePositionPercent(node, mainlineNodes);
                          return (
                            <button
                              type="button"
                              aria-pressed={selectedNodeId === node.node_id}
                              aria-label={`${node.name}，${segmentRoleLabel(node)}`}
                              className={`girder-sim-track-span ${node.node_type} ${node.bridge_segment_kind ?? "whole"} ${selectedNodeId === node.node_id ? "selected" : ""}`}
                              data-entity-id={`${node.node_id}:segment`}
                              data-segment-kind={node.bridge_segment_kind ?? undefined}
                              key={`span-${node.node_id}`}
                              style={{ left: `${position.left}%`, width: `${position.width}%` }}
                              title={`${node.name}｜${formatMileageRange(node)}｜${segmentRoleLabel(node)}`}
                              onClick={() => setSelectedNodeId((current) => current === node.node_id ? null : node.node_id)}
                            />
                          );
                        })}
                        {mainlineNodes.filter((node) => !isLineOnlyNode(node.node_type)).map((node) => {
                          const position = nodePositionPercent(node, mainlineNodes);
                          return <span className={`girder-sim-track-marker ${node.node_type}`} key={node.node_id} style={{ left: `${position.center}%` }}><NodeTypeIcon type={node.node_type} /></span>;
                        })}
                      </div>
                      {groupedBranches.length > 0 && (
                        <div className="girder-sim-branch-layer" aria-label={`${track.label}互通支线`}>
                          {groupedBranches.map((branch, branchIndex) => (
                            <div className="girder-sim-branch-route" data-alignment-code={branch.prefix} key={`${track.side}-${group.spatialGroupId}-${branch.prefix}`}>
                              <span className="girder-sim-branch-connector" aria-hidden="true" />
                              <strong title={`${branch.prefix} 互通支线`}>{branch.prefix}</strong>
                              <div className="girder-sim-branch-track">
                                {branch.nodes.map((node, nodeIndex) => {
                                  const control = controlByNode.get(node.node_id);
                                  const position = nodePositionPercent(node, branch.nodes);
                                  const lane = twoLane(branchIndex, nodeIndex);
                                  return (
                                    <span
                                      className={`girder-sim-branch-label lane-${lane} ${control?.risk_status ?? ""}`}
                                      data-entity-id={node.node_id}
                                      key={`label-${node.node_id}`}
                                      style={{ left: `${position.center}%` }}
                                      title={node.name}
                                    >{workpointDisplayName(node)}</span>
                                  );
                                })}
                                {branch.nodes.map((node) => {
                                  const position = nodePositionPercent(node, branch.nodes);
                                  return (
                                    <button
                                      type="button"
                                      aria-pressed={selectedNodeId === node.node_id}
                                      aria-label={`${node.name}，${segmentRoleLabel(node)}`}
                                      className={`girder-sim-track-span ${node.node_type} ${node.bridge_segment_kind ?? "whole"} ${selectedNodeId === node.node_id ? "selected" : ""}`}
                                      data-entity-id={`${node.node_id}:branch-segment`}
                                      data-segment-kind={node.bridge_segment_kind ?? undefined}
                                      key={`branch-span-${node.node_id}`}
                                      style={{ left: `${position.left}%`, width: `${position.width}%` }}
                                      title={`${node.name}｜${formatMileageRange(node)}｜${segmentRoleLabel(node)}`}
                                      onClick={() => setSelectedNodeId((current) => current === node.node_id ? null : node.node_id)}
                                    />
                                  );
                                })}
                                {branch.nodes.filter((node) => !isLineOnlyNode(node.node_type)).map((node) => {
                                  const position = nodePositionPercent(node, branch.nodes);
                                  return <span className={`girder-sim-track-marker ${node.node_type}`} key={`branch-marker-${node.node_id}`} style={{ left: `${position.center}%` }}><NodeTypeIcon type={node.node_type} /></span>;
                                })}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                      <div
                        className="girder-sim-yard-markers"
                        style={{ minHeight: `${deployedYards.length === 0 ? 4 : Math.max(38, deployedYards.length * 28 + 10)}px` }}
                      >
                        {deployedYards.map((yard, yardIndex) => {
                          const node = sideNodes.find((item) => yardNodeId(yard, sideNodes) === item.node_id);
                          const positioningNodes = !node || isMainlineNode(node, track)
                            ? mainlineNodes
                            : groupedBranches.find((branch) => branch.nodes.includes(node))?.nodes ?? sideNodes;
                          return (
                            <span
                              className="girder-sim-yard-marker"
                              key={yard.beam_yard_id}
                              data-entity-id={yard.beam_yard_id}
                              style={{ left: `${yardOffsetPercent(yard, node, positioningNodes)}%`, top: `${6 + yardIndex * 28}px` }}
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
    </section>
  );
}

function LegendItem({ type, label }: { type: LineGraphNode["node_type"]; label: string }) {
  return <span className={`girder-sim-legend-item ${type}`}>{isLineOnlyNode(type) ? <span className={`girder-sim-legend-line ${type}`} /> : <NodeTypeIcon type={type} />}{label}</span>;
}

function NodeTypeIcon({ type }: { type: LineGraphNode["node_type"] }) {
  const props = { size: 15, strokeWidth: 2 };
  if (type === "yard") return <Warehouse {...props} />;
  if (type === "culvert") return <LandPlot {...props} />;
  return <Waypoints {...props} />;
}

function isLineOnlyNode(type: LineGraphNode["node_type"]): boolean {
  return type === "roadbed" || type === "bridge" || type === "tunnel";
}

function labelLane(displayOrder: number, nodeIndex: number, nodeCount: number): 0 | 1 | 2 {
  if (nodeCount >= 3) return (nodeIndex % 3) as 0 | 1 | 2;
  return twoLane(displayOrder, nodeIndex);
}

function twoLane(displayOrder: number, nodeIndex: number): 0 | 1 {
  return (displayOrder + nodeIndex) % 2 === 0 ? 0 : 1;
}

function segmentOrder(kind: LineGraphNode["bridge_segment_kind"]): number {
  if (kind === "approach_small") return 0;
  if (kind === "continuous") return 1;
  if (kind === "approach_large") return 2;
  return 0;
}

function workpointDisplayName(node: LineGraphNode): string {
  const sideSuffix = node.side === "left" ? "·左幅" : "·右幅";
  return node.name
    .replace(sideSuffix, "")
    .replace("·小里程引桥段", "·小引桥")
    .replace("·连续结构段", "·连续结构")
    .replace("·大里程引桥段", "·大引桥");
}

function segmentRoleLabel(node: LineGraphNode): string {
  return node.requires_erection ? "待架目标" : "运梁通道";
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

function isMainlineNode(node: LineGraphNode, track: TrackDefinition): boolean {
  const prefix = normalizedPrefix(node);
  return node.side === track.side && (prefix === track.prefix || prefix === "");
}

function branchRoutes(nodes: LineGraphNode[], track: TrackDefinition): BranchRoute[] {
  const grouped = new Map<string, LineGraphNode[]>();
  for (const node of nodes) {
    if (isMainlineNode(node, track)) continue;
    const prefix = normalizedPrefix(node);
    if (!prefix) continue;
    grouped.set(prefix, [...(grouped.get(prefix) ?? []), node]);
  }
  return [...grouped.entries()]
    .sort(([left], [right]) => left.localeCompare(right, "zh-CN", { numeric: true }))
    .map(([prefix, branchNodes]) => ({ prefix, nodes: branchNodes }));
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
    roadbed: { base: 40, factor: 0.5, min: 48, max: 88 },
    bridge: { base: 96, factor: 2.2, min: 118, max: 220 },
    tunnel: { base: 104, factor: 2.5, min: 128, max: 230 },
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
