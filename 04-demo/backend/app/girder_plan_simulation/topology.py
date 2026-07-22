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
from ..contracts.project_master import (
    ProjectMasterRoutePlacement,
    ProjectMasterSnapshot,
    ProjectMasterStructure,
    ProjectMasterWorkpoint,
)
from ..girder_planning.fingerprints import stable_fingerprint, stable_id


@dataclass(frozen=True)
class PathResolution:
    status: str
    node_ids: list[str]
    edge_ids: list[str]
    alternatives: int = 0


@dataclass(frozen=True)
class RoutePlacementProjection:
    placement_id: str
    workpoint_id: str
    side: str
    mileage_prefix: str
    start_mileage_m: float | None
    end_mileage_m: float | None
    spatial_group_id: str
    display_order: int
    source: str


@dataclass(frozen=True)
class BridgeRouteSegmentProjection:
    kind: str
    start_mileage_m: float
    end_mileage_m: float
    structures: tuple[ProjectMasterStructure, ...]


def build_line_graph(
    *,
    project_id: str,
    project_master_version_id: str,
    snapshot: ProjectMasterSnapshot,
    connection_overrides: Iterable[LineGraphEdge] = (),
) -> LineGraphSnapshot:
    connection_overrides = tuple(connection_overrides)
    workpoint_by_id = {item.workpoint_id: item for item in snapshot.workpoints}
    projections, diagnostics = _route_projections(snapshot, project_master_version_id)
    nodes: list[LineGraphNode] = []
    nodes_by_projection: dict[str, list[LineGraphNode]] = {}

    for projection in projections:
        workpoint = workpoint_by_id.get(projection.workpoint_id)
        if workpoint is None:
            continue
        projected_nodes, node_diagnostics = _nodes_for_projection(workpoint, projection)
        nodes.extend(projected_nodes)
        nodes_by_projection[projection.placement_id] = projected_nodes
        diagnostics.extend(node_diagnostics)

    grouped: dict[tuple[str, str], list[tuple[RoutePlacementProjection, LineGraphNode]]] = defaultdict(list)
    for projection in projections:
        for node in nodes_by_projection.get(projection.placement_id, []):
            grouped[(projection.side, projection.mileage_prefix)].append((projection, node))

    edges: list[LineGraphEdge] = []
    for (side, mileage_prefix), entries in grouped.items():
        ordered = sorted(
            entries,
            key=lambda item: (
                item[0].display_order,
                float(item[1].start_mileage_m) if item[1].start_mileage_m is not None else float("inf"),
                item[1].sort_order,
                item[1].node_id,
            ),
        )
        for (previous, previous_node), (current, current_node) in zip(ordered, ordered[1:]):
            if previous_node.start_mileage_m is None or previous_node.end_mileage_m is None:
                continue
            if current_node.start_mileage_m is None or current_node.end_mileage_m is None:
                continue
            if previous.source == "explicit" and current.source == "explicit":
                if float(current_node.start_mileage_m) < float(previous_node.end_mileage_m):
                    diagnostics.append(
                        _diagnostic(
                            "MILEAGE_OVERLAP",
                            "blocking",
                            f"{_side_label(side)} {mileage_prefix} 的节点 {previous_node.node_id} 与 {current_node.node_id} 里程区间重叠。",
                            "route_placement",
                            current.placement_id,
                            "核对同一幅别、同一里程前缀内两个节点的真实起终点里程。",
                            refs=[previous_node.node_id, current_node.node_id, side, mileage_prefix],
                        )
                    )
                    continue
                if float(current_node.start_mileage_m) > float(previous_node.end_mileage_m):
                    if not _has_confirmed_override([previous_node], [current_node], connection_overrides):
                        diagnostics.append(
                            _diagnostic(
                                "LINE_GRAPH_GAP",
                                "blocking",
                                f"{_side_label(side)} {mileage_prefix} 的节点 {previous_node.node_id} 与 {current_node.node_id} 之间存在未确认断点。",
                                "route_gap",
                                f"{previous_node.node_id}:{current_node.node_id}",
                                "确认真实连接、方向和移动天数后作为方案级人工连接保存。",
                                refs=[previous_node.node_id, current_node.node_id, side, mileage_prefix],
                            )
                        )
                    continue
            edges.append(_edge(previous_node.node_id, current_node.node_id, "alignment_adjacency"))

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

    nodes.sort(
        key=lambda item: (
            item.display_order,
            item.side,
            item.sort_order,
            float(item.start_mileage_m) if item.start_mileage_m is not None else float("inf"),
            item.node_id,
        )
    )
    edges = _deduplicate_edges(edges)
    payload = {
        "projection_version": "girder-plan-line-graph/v3",
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


def _route_projections(
    snapshot: ProjectMasterSnapshot,
    project_master_version_id: str,
) -> tuple[list[RoutePlacementProjection], list[SimulationDiagnostic]]:
    diagnostics: list[SimulationDiagnostic] = []
    workpoint_by_id = {item.workpoint_id: item for item in snapshot.workpoints}
    explicit_by_workpoint: dict[str, list[ProjectMasterRoutePlacement]] = defaultdict(list)
    seen_explicit: set[tuple[str, str]] = set()
    for placement in sorted(snapshot.route_placements, key=lambda item: (item.display_order, item.placement_id)):
        workpoint = workpoint_by_id.get(placement.workpoint_id)
        if workpoint is None:
            diagnostics.append(
                _diagnostic(
                    "ROUTE_WORKPOINT_UNKNOWN",
                    "blocking",
                    f"线路落位 {placement.placement_id} 引用了不存在的工点 {placement.workpoint_id}。",
                    "route_placement",
                    placement.placement_id,
                    "重新导入包含有效工点引用的线路关系。",
                )
            )
            continue
        key = (placement.workpoint_id.casefold(), str(placement.side).casefold())
        if key in seen_explicit:
            diagnostics.append(
                _diagnostic(
                    "ROUTE_PLACEMENT_DUPLICATE",
                    "blocking",
                    f"工点 {placement.workpoint_id} 的 {placement.side} 幅存在重复线路落位。",
                    "route_placement",
                    placement.placement_id,
                    "同一工点同一幅别只保留一条线路落位。",
                )
            )
            continue
        seen_explicit.add(key)
        explicit_by_workpoint[placement.workpoint_id].append(placement)

    projections: list[RoutePlacementProjection] = []
    inferred_workpoints: list[str] = []
    for workpoint in sorted(snapshot.workpoints, key=lambda item: (item.sort_order, item.workpoint_id)):
        explicit = explicit_by_workpoint.get(workpoint.workpoint_id, [])
        if explicit:
            for placement in explicit:
                projection, placement_diagnostics = _explicit_projection(placement)
                diagnostics.extend(placement_diagnostics)
                if projection is not None:
                    projections.append(projection)
            continue
        sides = sorted({item.side for item in workpoint.structures if item.side in {"left", "right"}})
        if not sides:
            diagnostics.append(
                _diagnostic(
                    "ROUTE_SIDE_MISSING",
                    "blocking",
                    f"工点“{workpoint.workpoint_name}”缺少可确认的左/右幅归属。",
                    "workpoint",
                    workpoint.workpoint_id,
                    "在线路关系中补充 left/right 落位，或在结构物主数据中维护幅别。",
                )
            )
            continue
        inferred_workpoints.append(workpoint.workpoint_id)
        for side in sides:
            mileage_prefix = _inferred_mileage_prefix(workpoint.alignment_code, side)
            if not mileage_prefix:
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_MILEAGE_PREFIX_MISSING",
                        "blocking",
                        f"工点“{workpoint.workpoint_name}”{_side_label(side)}缺少里程前缀。",
                        "workpoint_side",
                        f"{workpoint.workpoint_id}:{side}",
                        "补充线路关系中的真实里程前缀。",
                    )
                )
                continue
            projections.append(
                RoutePlacementProjection(
                    placement_id=f"inferred:{workpoint.workpoint_id}:{side}",
                    workpoint_id=workpoint.workpoint_id,
                    side=side,
                    mileage_prefix=mileage_prefix,
                    start_mileage_m=workpoint.start_mileage_m,
                    end_mileage_m=workpoint.end_mileage_m,
                    spatial_group_id=f"inferred:{workpoint.workpoint_id}",
                    display_order=workpoint.sort_order,
                    source="inferred",
                )
            )
            if workpoint.start_mileage_m is None or workpoint.end_mileage_m is None:
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_MILEAGE_MISSING",
                        "blocking",
                        f"工点“{workpoint.workpoint_name}”{_side_label(side)}缺少起点或终点里程。",
                        "workpoint_side",
                        f"{workpoint.workpoint_id}:{side}",
                        "补充真实分幅里程；系统不会把缺失值按 0 处理。",
                    )
                )
            elif workpoint.end_mileage_m < workpoint.start_mileage_m:
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_MILEAGE_RANGE_INVALID",
                        "blocking",
                        f"工点“{workpoint.workpoint_name}”{_side_label(side)}的终点里程小于起点里程。",
                        "workpoint_side",
                        f"{workpoint.workpoint_id}:{side}",
                        "修正起终点里程后重新生成线路图。",
                    )
                )
    if inferred_workpoints:
        diagnostics.append(
            _diagnostic(
                "ROUTE_PLACEMENT_INFERRED",
                "warning",
                f"{len(inferred_workpoints)} 个工点缺少显式线路关系，当前按结构物幅别和稳定排序生成兼容双幅视图。",
                "project_master_version",
                project_master_version_id,
                "后续通过新版项目主数据“线路关系”表补充分幅里程和空间对应组。",
                refs=inferred_workpoints,
            )
        )
    return projections, diagnostics


def _explicit_projection(
    placement: ProjectMasterRoutePlacement,
) -> tuple[RoutePlacementProjection | None, list[SimulationDiagnostic]]:
    diagnostics: list[SimulationDiagnostic] = []
    if placement.side not in {"left", "right"}:
        diagnostics.append(
            _diagnostic(
                "ROUTE_SIDE_MISSING",
                "blocking",
                f"线路落位 {placement.placement_id} 缺少合法 left/right 幅别。",
                "route_placement",
                placement.placement_id,
                "修正线路关系幅别。",
            )
        )
        return None, diagnostics
    mileage_prefix = str(placement.mileage_prefix).strip().upper()
    if not mileage_prefix:
        diagnostics.append(
            _diagnostic(
                "ROUTE_MILEAGE_PREFIX_MISSING",
                "blocking",
                f"线路落位 {placement.placement_id} 缺少里程前缀。",
                "route_placement",
                placement.placement_id,
                "补充 ZK、K 或互通真实里程前缀。",
            )
        )
        return None, diagnostics
    if placement.start_mileage_m is None or placement.end_mileage_m is None:
        diagnostics.append(
            _diagnostic(
                "ROUTE_MILEAGE_MISSING",
                "blocking",
                f"线路落位 {placement.placement_id} 缺少起点或终点里程。",
                "route_placement",
                placement.placement_id,
                "补充真实分幅里程。",
            )
        )
    elif placement.end_mileage_m < placement.start_mileage_m:
        diagnostics.append(
            _diagnostic(
                "ROUTE_MILEAGE_RANGE_INVALID",
                "blocking",
                f"线路落位 {placement.placement_id} 的终点里程小于起点里程。",
                "route_placement",
                placement.placement_id,
                "修正线路关系中的起终点里程。",
            )
        )
    spatial_group_id = str(placement.spatial_group_id).strip()
    if not spatial_group_id:
        diagnostics.append(
            _diagnostic(
                "ROUTE_SPATIAL_GROUP_MISSING",
                "warning",
                f"线路落位 {placement.placement_id} 缺少空间对应组。",
                "route_placement",
                placement.placement_id,
                "补充源 Excel 同行或等价确认关系。",
            )
        )
        spatial_group_id = f"missing:{placement.placement_id}"
    return RoutePlacementProjection(
        placement_id=placement.placement_id,
        workpoint_id=placement.workpoint_id,
        side=placement.side,
        mileage_prefix=mileage_prefix,
        start_mileage_m=placement.start_mileage_m,
        end_mileage_m=placement.end_mileage_m,
        spatial_group_id=spatial_group_id,
        display_order=placement.display_order,
        source="explicit",
    ), diagnostics


def _inferred_mileage_prefix(alignment_code: str | None, side: str) -> str:
    normalized = (alignment_code or "").strip().upper().replace(" ", "")
    if normalized in {"ZK/K", "K/ZK"}:
        return "ZK" if side == "left" else "K"
    return normalized


def _nodes_for_projection(
    workpoint: ProjectMasterWorkpoint,
    projection: RoutePlacementProjection,
) -> tuple[list[LineGraphNode], list[SimulationDiagnostic]]:
    diagnostics: list[SimulationDiagnostic] = []
    structures = [item for item in workpoint.structures if item.side == projection.side]
    demands = _beam_demands_for_structures(structures) if workpoint.workpoint_type == "bridge" else []
    requires_erection = bool(demands)
    whole_node = LineGraphNode(
        node_id=f"{workpoint.workpoint_id}:{projection.side}",
        project_master_workpoint_id=workpoint.workpoint_id,
        name=f"{workpoint.workpoint_name}·{_side_label(projection.side)}",
        node_type=_node_type(workpoint.workpoint_type),
        side=projection.side,
        alignment_code=projection.mileage_prefix,
        start_mileage_m=projection.start_mileage_m,
        end_mileage_m=projection.end_mileage_m,
        sort_order=workpoint.sort_order,
        spatial_group_id=projection.spatial_group_id,
        display_order=projection.display_order,
        placement_source=projection.source,
        requires_erection=requires_erection,
        beam_demands=demands,
        current_plan_finish_date=_current_plan_finish_for_structures(structures),
        source_refs=[item.structure_id for item in structures] or [workpoint.workpoint_id],
    )
    if workpoint.workpoint_type != "bridge":
        return [whole_node], diagnostics

    if workpoint.workpoint_type == "bridge" and not demands:
        diagnostics.append(
            _diagnostic(
                "BRIDGE_BEAM_DEMAND_MISSING",
                "warning",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}未识别到预制梁型及片数，不作为待架目标。",
                "bridge_side",
                f"{workpoint.workpoint_id}:{projection.side}",
                "在已确认项目主数据中补充预制梁构件或 beam_count_per_span 参数。",
            )
        )

    if not any(item.structure_type == "continuous_unit" for item in structures):
        return [whole_node], diagnostics

    segments, segment_diagnostics = _bridge_route_segments(workpoint, projection, structures)
    diagnostics.extend(segment_diagnostics)
    if segments is None:
        return [whole_node], diagnostics

    labels = {
        "approach_small": "小里程引桥段",
        "continuous": "连续结构段",
        "approach_large": "大里程引桥段",
    }
    nodes: list[LineGraphNode] = []
    for segment in segments:
        segment_demands = [] if segment.kind == "continuous" else _beam_demands_for_structures(segment.structures)
        nodes.append(
            LineGraphNode(
                node_id=f"{workpoint.workpoint_id}:{projection.side}:{segment.kind}",
                project_master_workpoint_id=workpoint.workpoint_id,
                name=f"{workpoint.workpoint_name}·{_side_label(projection.side)}·{labels[segment.kind]}",
                node_type="bridge",
                bridge_segment_kind=segment.kind,
                side=projection.side,
                alignment_code=projection.mileage_prefix,
                start_mileage_m=segment.start_mileage_m,
                end_mileage_m=segment.end_mileage_m,
                sort_order=workpoint.sort_order,
                spatial_group_id=projection.spatial_group_id,
                display_order=projection.display_order,
                placement_source=projection.source,
                requires_erection=bool(segment_demands),
                beam_demands=segment_demands,
                current_plan_finish_date=_current_plan_finish_for_structures(segment.structures),
                source_refs=[item.structure_id for item in segment.structures],
            )
        )
    return nodes, diagnostics


def _bridge_route_segments(
    workpoint: ProjectMasterWorkpoint,
    projection: RoutePlacementProjection,
    structures: list[ProjectMasterStructure],
) -> tuple[tuple[BridgeRouteSegmentProjection, ...] | None, list[SimulationDiagnostic]]:
    relevant = [
        item
        for item in structures
        if item.structure_category in {"upper_structure", "superstructure"}
        or item.structure_type in {"simple_span", "precast_simply_supported_beam", "cast_in_place_unit", "continuous_unit"}
    ]
    subject_id = f"{workpoint.workpoint_id}:{projection.side}"
    refs = [subject_id, *[item.structure_id for item in relevant]]
    ordered: list[tuple[ProjectMasterStructure, int, float]] = []
    missing: list[str] = []
    for structure in relevant:
        parameters = _structure_parameters(structure)
        try:
            span_index = int(parameters.get("span_index"))
            span_length = float(parameters.get("span_length_m"))
        except (TypeError, ValueError):
            missing.append(structure.structure_id)
            continue
        if span_index <= 0 or span_length <= 0:
            missing.append(structure.structure_id)
            continue
        ordered.append((structure, span_index, span_length))
    if missing or len(ordered) != len(relevant):
        return None, [
            _diagnostic(
                "BRIDGE_SEGMENT_STRUCTURE_DATA_MISSING",
                "blocking",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}缺少可用于三段定位的跨序或正数结构长度。",
                "bridge_side",
                subject_id,
                "补充该幅全部上部结构的 span_index 和 span_length_m 后重新生成线路图。",
                refs=refs,
            )
        ]
    ordered.sort(key=lambda item: (item[1], item[0].sort_order, item[0].structure_id))
    continuous_positions = [index for index, (item, _, _) in enumerate(ordered) if item.structure_type == "continuous_unit"]
    blocks = 1 + sum(
        1
        for previous, current in zip(continuous_positions, continuous_positions[1:])
        if current != previous + 1
    )
    if blocks != 1:
        return None, [
            _diagnostic(
                "BRIDGE_SEGMENT_CONTINUOUS_BLOCK_AMBIGUOUS",
                "blocking",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}存在多个不相邻连续结构区块。",
                "bridge_side",
                subject_id,
                "确认多连续区块的路线分段口径后再生成线路图。",
                refs=refs,
            )
        ]
    first_continuous = continuous_positions[0]
    last_continuous = continuous_positions[-1]
    before = ordered[:first_continuous]
    continuous = ordered[first_continuous:last_continuous + 1]
    after = ordered[last_continuous + 1:]
    if not before or not after:
        return None, [
            _diagnostic(
                "BRIDGE_SEGMENT_APPROACH_MISSING",
                "blocking",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}的连续结构前后未同时识别到正长度引桥。",
                "bridge_side",
                subject_id,
                "补充连续结构两侧引桥，或确认该桥不适用首期三段式规则。",
                refs=refs,
            )
        ]
    continuous_structures = [item[0] for item in continuous]
    if any(_structure_precast_pieces(item) > 0 for item in continuous_structures):
        return None, [
            _diagnostic(
                "BRIDGE_SEGMENT_PRECAST_CONFLICT",
                "blocking",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}的连续结构区块包含预制梁需求。",
                "bridge_side",
                subject_id,
                "核对连续结构类型和预制梁构件归属，不得把连续结构自动转为片架设目标。",
                refs=refs,
            )
        ]
    if projection.start_mileage_m is None or projection.end_mileage_m is None:
        return None, [
            _diagnostic(
                "BRIDGE_SEGMENT_STRUCTURE_DATA_MISSING",
                "blocking",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}缺少三段定位所需的线路落位里程。",
                "bridge_side",
                subject_id,
                "补充该幅线路落位起终里程后重新生成线路图。",
                refs=refs,
            )
        ]
    route_length = float(projection.end_mileage_m) - float(projection.start_mileage_m)
    structure_length = sum(item[2] for item in ordered)
    if abs(route_length - structure_length) > 1.0:
        return None, [
            _diagnostic(
                "BRIDGE_SEGMENT_LENGTH_MISMATCH",
                "blocking",
                f"桥梁“{workpoint.workpoint_name}”{_side_label(projection.side)}结构累计长度 {structure_length:g}m 与线路落位长度 {route_length:g}m 相差超过 1m。",
                "bridge_side",
                subject_id,
                "核对该幅结构长度和线路落位里程；系统不会按比例拉伸分段。",
                refs=refs,
            )
        ]
    start = float(projection.start_mileage_m)
    small_end = start + sum(item[2] for item in before)
    continuous_end = small_end + sum(item[2] for item in continuous)
    return (
        BridgeRouteSegmentProjection("approach_small", start, small_end, tuple(item[0] for item in before)),
        BridgeRouteSegmentProjection("continuous", small_end, continuous_end, tuple(continuous_structures)),
        BridgeRouteSegmentProjection("approach_large", continuous_end, float(projection.end_mileage_m), tuple(item[0] for item in after)),
    ), []


def _structure_parameters(structure: ProjectMasterStructure) -> dict[str, object]:
    return {item.parameter_code: item.value for item in structure.parameters}


def _structure_precast_pieces(structure: ProjectMasterStructure) -> int:
    enabled = [item for item in structure.components if item.enabled and item.component_type == "precast_beam"]
    if enabled:
        return sum(max(0, int(round(item.quantity))) for item in enabled)
    value = _structure_parameters(structure).get("beam_count_per_span")
    try:
        return max(0, int(value)) if value not in {None, ""} else 0
    except (TypeError, ValueError):
        return 0


def _build_line_graph_v1(
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
    return _beam_demands_for_structures(
        [structure for structure in structures if side == "unknown" or structure.side == side]
    )


def _beam_demands_for_structures(structures: Iterable[ProjectMasterStructure]) -> list[BeamDemand]:
    structures = list(structures)
    totals: dict[str, int] = defaultdict(int)
    refs: dict[str, list[str]] = defaultdict(list)
    for structure in structures:
        structure_parameters = {item.parameter_code: item.value for item in structure.parameters}
        contributed: set[str] = set()
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
            pieces = max(0, int(round(component.quantity)))
            totals[beam_type] += pieces
            if pieces > 0:
                contributed.add(beam_type)
        if not any(component.enabled and component.component_type == "precast_beam" for component in structure.components):
            count = structure_parameters.get("beam_count_per_span")
            if count not in {None, ""}:
                beam_type = str(
                    structure_parameters.get("beam_type_id")
                    or structure_parameters.get("beam_type")
                    or structure.structure_type
                    or "precast_beam"
                )
                pieces = max(0, int(count))
                totals[beam_type] += pieces
                if pieces > 0:
                    contributed.add(beam_type)
        for beam_type in contributed:
            refs[beam_type].append(structure.structure_id)
    return [
        BeamDemand(
            beam_type_id=beam_type,
            beam_type_name=beam_type,
            span_count=len(refs[beam_type]),
            beam_count=pieces,
            span_refs=refs[beam_type],
        )
        for beam_type, pieces in sorted(totals.items())
        if pieces > 0
    ]


def _current_plan_finish(workpoint: ProjectMasterWorkpoint) -> date | None:
    return _current_plan_finish_for_structures(workpoint.structures)


def _current_plan_finish_for_structures(structures: Iterable[ProjectMasterStructure]) -> date | None:
    values: list[date] = []
    for structure in structures:
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
    *,
    refs: list[str] | None = None,
) -> SimulationDiagnostic:
    return SimulationDiagnostic(
        code=code,
        severity=severity,
        message=message,
        object_type=object_type,
        object_id=object_id,
        entity_refs=refs or [object_id],
        suggestion=suggestion,
    )


__all__ = ["PathResolution", "build_line_graph", "resolve_path"]
