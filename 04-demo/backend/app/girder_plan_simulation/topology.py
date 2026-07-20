"""Build and query the route topology used by girder plan simulation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from ..contracts.girder_plan_simulation import (
    BeamDemand,
    ConfirmedPathSegment,
    LineGraphEdge,
    LineGraphNode,
    LineGraphSnapshot,
    SimulationDiagnostic,
)
from ..contracts.project_master import ProjectMasterSnapshot, ProjectMasterStructure, ProjectMasterWorkpoint
from ..girder_planning.fingerprints import stable_fingerprint, stable_id


@dataclass(frozen=True)
class PathResolution:
    status: str
    node_ids: list[str]
    edge_ids: list[str]
    alternatives: int = 0


def build_line_graph(
    *,
    project_id: str,
    project_master_version_id: str,
    snapshot: ProjectMasterSnapshot,
    connection_overrides: Iterable[LineGraphEdge] = (),
) -> LineGraphSnapshot:
    connection_overrides = tuple(connection_overrides)
    nodes: list[LineGraphNode] = []
    diagnostics: list[SimulationDiagnostic] = []
    nodes_by_workpoint: dict[str, list[LineGraphNode]] = {}

    for workpoint in snapshot.workpoints:
        workpoint_nodes, workpoint_diagnostics = _nodes_for_workpoint(workpoint)
        nodes.extend(workpoint_nodes)
        nodes_by_workpoint[workpoint.workpoint_id] = workpoint_nodes
        diagnostics.extend(workpoint_diagnostics)

    grouped: dict[str, list[ProjectMasterWorkpoint]] = defaultdict(list)
    for workpoint in snapshot.workpoints:
        if not workpoint.alignment_code:
            diagnostics.append(
                _diagnostic(
                    "ALIGNMENT_MISSING",
                    "blocking",
                    f"工点“{workpoint.workpoint_name}”缺少线路编码。",
                    "workpoint",
                    workpoint.workpoint_id,
                    "补充线路编码后重新生成线路图。",
                )
            )
            continue
        if workpoint.start_mileage_m is None or workpoint.end_mileage_m is None:
            diagnostics.append(
                _diagnostic(
                    "MILEAGE_MISSING",
                    "blocking",
                    f"工点“{workpoint.workpoint_name}”缺少起点或终点里程。",
                    "workpoint",
                    workpoint.workpoint_id,
                    "补充真实里程；系统不会把缺失值按 0 处理。",
                )
            )
            continue
        if workpoint.end_mileage_m < workpoint.start_mileage_m:
            diagnostics.append(
                _diagnostic(
                    "MILEAGE_RANGE_INVALID",
                    "blocking",
                    f"工点“{workpoint.workpoint_name}”的终点里程小于起点里程。",
                    "workpoint",
                    workpoint.workpoint_id,
                    "修正起终点里程后重新生成线路图。",
                )
            )
            continue
        grouped[workpoint.alignment_code].append(workpoint)

    edges: list[LineGraphEdge] = []
    for alignment_code, workpoints in grouped.items():
        ordered = sorted(
            workpoints,
            key=lambda item: (float(item.start_mileage_m), float(item.end_mileage_m), item.sort_order, item.workpoint_id),
        )
        for previous, current in zip(ordered, ordered[1:]):
            previous_nodes = nodes_by_workpoint.get(previous.workpoint_id, [])
            current_nodes = nodes_by_workpoint.get(current.workpoint_id, [])
            if float(current.start_mileage_m) < float(previous.end_mileage_m):
                diagnostics.append(
                    _diagnostic(
                        "MILEAGE_OVERLAP",
                        "blocking",
                        f"线路 {alignment_code} 的工点 {previous.workpoint_id} 与 {current.workpoint_id} 里程区间重叠。",
                        "alignment",
                        alignment_code,
                        "核对两个工点的真实起终点里程。",
                    )
                )
                continue
            if float(current.start_mileage_m) > float(previous.end_mileage_m):
                if not _has_confirmed_override(previous_nodes, current_nodes, connection_overrides):
                    diagnostics.append(
                        _diagnostic(
                            "LINE_GRAPH_GAP",
                            "blocking",
                            f"线路 {alignment_code} 的工点 {previous.workpoint_id} 与 {current.workpoint_id} 之间存在未确认断点。",
                            "alignment_gap",
                            f"{previous.workpoint_id}:{current.workpoint_id}",
                            "确认真实连接、方向和移动天数后作为方案级人工连接保存。",
                        )
                    )
                continue
            connections = _compatible_node_pairs(
                previous_nodes,
                current_nodes,
            )
            for left, right in connections:
                edges.append(_edge(left.node_id, right.node_id, "alignment_adjacency"))

    node_ids = {node.node_id for node in nodes}
    for override in connection_overrides:
        if override.from_node_id not in node_ids or override.to_node_id not in node_ids:
            diagnostics.append(
                _diagnostic(
                    "CONNECTION_OVERRIDE_NODE_UNKNOWN",
                    "blocking",
                    f"人工连接 {override.edge_id} 引用了不存在的节点。",
                    "edge",
                    override.edge_id,
                    "重新选择线路图中的有效节点。",
                )
            )
            continue
        if override.confirmation is None:
            diagnostics.append(
                _diagnostic(
                    "MANUAL_CONNECTION_CONFIRMATION_REQUIRED",
                    "blocking",
                    f"人工连接 {override.edge_id} 缺少确认人、原因或确认时间。",
                    "edge",
                    override.edge_id,
                    "补充人工连接确认记录。",
                )
            )
            continue
        edges.append(override.model_copy(update={"source": "manual_connection"}))

    edges = _deduplicate_edges(edges)
    payload = {
        "project_id": project_id,
        "project_master_version_id": project_master_version_id,
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "edges": [edge.model_dump(mode="json") for edge in edges],
    }
    fingerprint = stable_fingerprint(payload)
    status = "blocking" if any(item.severity == "blocking" for item in diagnostics) else (
        "warning" if diagnostics else "ready"
    )
    return LineGraphSnapshot(
        line_graph_id=stable_id("lgs", payload),
        project_id=project_id,
        project_master_version_id=project_master_version_id,
        input_fingerprint=fingerprint,
        status=status,
        nodes=nodes,
        edges=edges,
        diagnostics=diagnostics,
    )


def _has_confirmed_override(
    left_nodes: list[LineGraphNode],
    right_nodes: list[LineGraphNode],
    overrides: tuple[LineGraphEdge, ...],
) -> bool:
    left_ids = {node.node_id for node in left_nodes}
    right_ids = {node.node_id for node in right_nodes}
    return any(
        override.confirmation is not None
        and (
            (override.from_node_id in left_ids and override.to_node_id in right_ids)
            or (override.to_node_id in left_ids and override.from_node_id in right_ids)
        )
        for override in overrides
    )


def resolve_path(
    graph: LineGraphSnapshot,
    from_node_id: str,
    to_node_id: str,
    confirmed: ConfirmedPathSegment | None = None,
) -> PathResolution:
    if from_node_id == to_node_id:
        return PathResolution("unique", [from_node_id], [])
    if confirmed is not None:
        return _resolve_confirmed_path(graph, from_node_id, to_node_id, confirmed)

    adjacency = _adjacency(graph)
    if from_node_id not in adjacency or to_node_id not in adjacency:
        return PathResolution("unreachable", [], [])
    queue = deque([(from_node_id, [from_node_id], [])])
    shortest_length: int | None = None
    solutions: list[tuple[list[str], list[str]]] = []
    visited_depth: dict[str, int] = {from_node_id: 0}
    while queue and len(solutions) < 2:
        node_id, node_path, edge_path = queue.popleft()
        depth = len(edge_path)
        if shortest_length is not None and depth >= shortest_length:
            continue
        for next_node, edge_id in adjacency[node_id]:
            if next_node in node_path:
                continue
            next_nodes = [*node_path, next_node]
            next_edges = [*edge_path, edge_id]
            if next_node == to_node_id:
                shortest_length = len(next_edges) if shortest_length is None else shortest_length
                if len(next_edges) == shortest_length:
                    solutions.append((next_nodes, next_edges))
                continue
            next_depth = len(next_edges)
            if next_depth <= visited_depth.get(next_node, next_depth):
                visited_depth[next_node] = next_depth
                queue.append((next_node, next_nodes, next_edges))
    if not solutions:
        return PathResolution("unreachable", [], [])
    if len(solutions) > 1:
        return PathResolution("ambiguous", solutions[0][0], solutions[0][1], alternatives=len(solutions))
    return PathResolution("unique", solutions[0][0], solutions[0][1], alternatives=1)


def _resolve_confirmed_path(
    graph: LineGraphSnapshot,
    from_node_id: str,
    to_node_id: str,
    confirmed: ConfirmedPathSegment,
) -> PathResolution:
    if confirmed.from_target_node_id != from_node_id or confirmed.to_target_node_id != to_node_id:
        return PathResolution("invalid_confirmation", [], [])
    edge_by_id = {edge.edge_id: edge for edge in graph.edges}
    current = from_node_id
    nodes = [current]
    for edge_id in confirmed.edge_ids:
        edge = edge_by_id.get(edge_id)
        if edge is None:
            return PathResolution("invalid_confirmation", [], [])
        if edge.from_node_id == current and edge.direction in {"forward", "bidirectional"}:
            current = edge.to_node_id
        elif edge.to_node_id == current and edge.direction in {"reverse", "bidirectional"}:
            current = edge.from_node_id
        else:
            return PathResolution("invalid_confirmation", [], [])
        nodes.append(current)
    if current != to_node_id:
        return PathResolution("invalid_confirmation", [], [])
    return PathResolution("confirmed", nodes, list(confirmed.edge_ids), alternatives=1)


def _nodes_for_workpoint(workpoint: ProjectMasterWorkpoint) -> tuple[list[LineGraphNode], list[SimulationDiagnostic]]:
    diagnostics: list[SimulationDiagnostic] = []
    node_type = _node_type(workpoint.workpoint_type)
    plan_finish = _current_plan_finish(workpoint)
    if workpoint.workpoint_type != "bridge":
        return [
            LineGraphNode(
                node_id=f"{workpoint.workpoint_id}:unknown",
                project_master_workpoint_id=workpoint.workpoint_id,
                name=workpoint.workpoint_name,
                node_type=node_type,
                side="unknown",
                alignment_code=workpoint.alignment_code,
                start_mileage_m=workpoint.start_mileage_m,
                end_mileage_m=workpoint.end_mileage_m,
                sort_order=workpoint.sort_order,
                current_plan_finish_date=plan_finish,
                source_refs=[workpoint.workpoint_id],
            )
        ], diagnostics

    sides = sorted({structure.side for structure in workpoint.structures if structure.side in {"left", "right"}})
    if not sides:
        sides = ["unknown"]
    nodes: list[LineGraphNode] = []
    for side in sides:
        demands = _beam_demands(workpoint.structures, side)
        requires_erection = bool(demands)
        if not demands:
            diagnostics.append(
                _diagnostic(
                    "BRIDGE_BEAM_DEMAND_MISSING",
                    "warning",
                    f"桥梁“{workpoint.workpoint_name}”{_side_label(side)}未识别到预制梁型及片数，不作为待架目标。",
                    "bridge_side",
                    f"{workpoint.workpoint_id}:{side}",
                    "在已确认项目主数据中补充预制梁构件或 beam_count_per_span 参数。",
                )
            )
        nodes.append(
            LineGraphNode(
                node_id=f"{workpoint.workpoint_id}:{side}",
                project_master_workpoint_id=workpoint.workpoint_id,
                name=f"{workpoint.workpoint_name}·{_side_label(side)}",
                node_type="bridge",
                side=side,
                alignment_code=workpoint.alignment_code,
                start_mileage_m=workpoint.start_mileage_m,
                end_mileage_m=workpoint.end_mileage_m,
                sort_order=workpoint.sort_order,
                requires_erection=requires_erection,
                beam_demands=demands,
                current_plan_finish_date=plan_finish,
                source_refs=[
                    structure.structure_id
                    for structure in workpoint.structures
                    if side == "unknown" or structure.side == side
                ],
            )
        )
    return nodes, diagnostics


def _beam_demands(structures: list[ProjectMasterStructure], side: str) -> list[BeamDemand]:
    totals: dict[str, int] = defaultdict(int)
    for structure in structures:
        if side != "unknown" and structure.side != side:
            continue
        structure_parameters = {item.parameter_code: item.value for item in structure.parameters}
        for component in structure.components:
            if not component.enabled or component.component_type != "precast_beam":
                continue
            component_parameters = {item.parameter_code: item.value for item in component.parameters}
            beam_type = str(
                component_parameters.get("beam_type_id")
                or component_parameters.get("beam_type")
                or structure_parameters.get("beam_type_id")
                or structure_parameters.get("beam_type")
                or structure.structure_type
                or "precast_beam"
            )
            totals[beam_type] += max(0, int(round(component.quantity)))
        if not any(component.enabled and component.component_type == "precast_beam" for component in structure.components):
            count = structure_parameters.get("beam_count_per_span")
            if count not in {None, ""}:
                beam_type = str(
                    structure_parameters.get("beam_type_id")
                    or structure_parameters.get("beam_type")
                    or structure.structure_type
                    or "precast_beam"
                )
                totals[beam_type] += max(0, int(count))
    return [
        BeamDemand(
            beam_type_id=beam_type,
            beam_type_name=beam_type,
            span_count=1,
            beam_count=pieces,
            span_refs=[structure.structure_id for structure in structures if side == "unknown" or structure.side == side],
        )
        for beam_type, pieces in sorted(totals.items())
        if pieces > 0
    ]


def _current_plan_finish(workpoint: ProjectMasterWorkpoint) -> date | None:
    values: list[date] = []
    for structure in workpoint.structures:
        for parameter in structure.parameters:
            if parameter.parameter_code not in {"current_plan_finish_date", "planned_finish_date"}:
                continue
            try:
                values.append(date.fromisoformat(str(parameter.value)))
            except ValueError:
                continue
    return max(values) if values else None


def _compatible_node_pairs(left: list[LineGraphNode], right: list[LineGraphNode]) -> list[tuple[LineGraphNode, LineGraphNode]]:
    pairs = [
        (source, target)
        for source in left
        for target in right
        if source.side == target.side or source.side == "unknown" or target.side == "unknown"
    ]
    return pairs or [(source, target) for source in left for target in right]


def _edge(from_node_id: str, to_node_id: str, source: str) -> LineGraphEdge:
    payload = [from_node_id, to_node_id, source]
    return LineGraphEdge(
        edge_id=stable_id("lge", payload),
        from_node_id=from_node_id,
        to_node_id=to_node_id,
        source=source,
        direction="bidirectional",
        transfer_days=0,
    )


def _deduplicate_edges(edges: list[LineGraphEdge]) -> list[LineGraphEdge]:
    by_key: dict[tuple[str, str], LineGraphEdge] = {}
    for edge in edges:
        key = tuple(sorted((edge.from_node_id, edge.to_node_id)))
        by_key[key] = edge
    return sorted(by_key.values(), key=lambda edge: edge.edge_id)


def _adjacency(graph: LineGraphSnapshot) -> dict[str, list[tuple[str, str]]]:
    adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph.edges:
        if edge.direction in {"forward", "bidirectional"}:
            adjacency[edge.from_node_id].append((edge.to_node_id, edge.edge_id))
        if edge.direction in {"reverse", "bidirectional"}:
            adjacency[edge.to_node_id].append((edge.from_node_id, edge.edge_id))
    for values in adjacency.values():
        values.sort()
    return adjacency


def _node_type(value: str) -> str:
    return {
        "roadbed": "roadbed",
        "bridge": "bridge",
        "tunnel": "tunnel",
        "culvert": "culvert",
        "access_road": "access",
    }.get(value, "connection")


def _side_label(side: str) -> str:
    return {"left": "左幅", "right": "右幅", "shared": "共用", "unknown": "未分幅"}.get(side, side)


def _diagnostic(
    code: str,
    severity: str,
    message: str,
    object_type: str,
    object_id: str,
    suggestion: str,
) -> SimulationDiagnostic:
    return SimulationDiagnostic(
        code=code,
        severity=severity,
        message=message,
        object_type=object_type,
        object_id=object_id,
        entity_refs=[object_id],
        suggestion=suggestion,
    )


__all__ = ["PathResolution", "build_line_graph", "resolve_path"]
