"""Readiness validation and path expansion for girder plan simulation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..contracts.girder_plan_simulation import (
    BeamYardPlan,
    ErectionLinePlan,
    GirderPlanReadiness,
    GirderPlanScenarioVersion,
    LineGraphSnapshot,
    ManualRoutePlan,
    ReadinessCheck,
    SimulationDiagnostic,
)
from .topology import resolve_path


@dataclass
class PreparedRoute:
    route: ManualRoutePlan
    yard: BeamYardPlan
    line: ErectionLinePlan
    deployment_node_id: str
    expanded_node_ids: list[str]
    segment_node_ids: dict[str, list[str]]
    segment_transfer_days: dict[str, int]
    dependencies_by_target: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class PreparedSimulation:
    readiness: GirderPlanReadiness
    routes: list[PreparedRoute]
    dependency_graph: dict[str, set[str]]


def validate_scenario(scenario: GirderPlanScenarioVersion, graph: LineGraphSnapshot) -> GirderPlanReadiness:
    return prepare_scenario(scenario, graph).readiness


def prepare_scenario(scenario: GirderPlanScenarioVersion, graph: LineGraphSnapshot) -> PreparedSimulation:
    diagnostics = list(graph.diagnostics)
    checks: list[ReadinessCheck] = []
    node_by_id = {node.node_id: node for node in graph.nodes}
    edge_by_id = {edge.edge_id: edge for edge in graph.edges}
    enabled_yards = [item for item in scenario.beam_yards if item.enabled]
    enabled_lines = [item for item in scenario.erection_lines if item.enabled]
    yards = {item.beam_yard_id: item for item in enabled_yards}
    lines = {item.erection_line_id: item for item in enabled_lines}
    routes = [item for item in scenario.route_plans]

    for object_type, identifiers in (
        ("beam_yard", [item.beam_yard_id for item in enabled_yards]),
        ("erection_line", [item.erection_line_id for item in enabled_lines]),
        ("route", [item.route_plan_id for item in routes]),
    ):
        for identifier, count in Counter(identifiers).items():
            if count > 1:
                diagnostics.append(
                    _diagnostic(
                        "STABLE_ID_DUPLICATED",
                        "blocking",
                        f"{object_type} 稳定标识 {identifier} 重复 {count} 次。",
                        object_type,
                        identifier,
                        "为方案内对象分配唯一稳定标识。",
                    )
                )
    for yard in enabled_yards:
        capacity_ids = [item.beam_type_id for item in yard.capacities]
        for beam_type_id, count in Counter(capacity_ids).items():
            if count > 1:
                diagnostics.append(
                    _diagnostic(
                        "BEAM_TYPE_CAPACITY_DUPLICATED",
                        "blocking",
                        f"梁场 {yard.beam_yard_id} 的梁型 {beam_type_id} 产能配置重复。",
                        "beam_type_capacity",
                        f"{yard.beam_yard_id}:{beam_type_id}",
                        "每个梁场的同一梁型只保留一条产能配置。",
                    )
                )

    if scenario.project_master_version_id != graph.project_master_version_id or scenario.line_graph_id != graph.line_graph_id:
        diagnostics.append(
            _diagnostic(
                "LINE_GRAPH_REFERENCE_STALE",
                "blocking",
                "方案引用的项目版本或线路图已变化。",
                "scenario_version",
                scenario.scenario_version_id,
                "基于最新已确认项目版本重新保存方案。",
            )
        )
    _check(bool(yards), "BEAM_YARD_PRESENT", "至少存在一个有效梁场。", checks, diagnostics, scenario.scenario_version_id)
    _check(bool(routes), "ROUTE_PRESENT", "至少存在一条人工架梁线路。", checks, diagnostics, scenario.scenario_version_id)

    lines_by_yard: dict[str, list[ErectionLinePlan]] = defaultdict(list)
    for line in enabled_lines:
        lines_by_yard[line.beam_yard_id].append(line)
        if line.beam_yard_id not in yards:
            diagnostics.append(
                _diagnostic(
                    "ERECTION_LINE_YARD_UNKNOWN",
                    "blocking",
                    f"架梁作业线 {line.erection_line_id} 引用了不存在或未启用的梁场 {line.beam_yard_id}。",
                    "erection_line",
                    line.erection_line_id,
                    "重新选择有效梁场或停用该作业线。",
                )
            )
        if line.daily_erection_capacity_pieces <= 0:
            diagnostics.append(
                _diagnostic(
                    "ERECTION_CAPACITY_NON_POSITIVE",
                    "blocking",
                    f"架梁线路“{line.erection_line_id}”的能力必须大于 0 片/天。",
                    "erection_line",
                    line.erection_line_id,
                    "录入大于 0 的片日架梁能力。",
                )
            )
    for yard_id in sorted(yards):
        yard_lines = lines_by_yard.get(yard_id, [])
        if len(yard_lines) != 1:
            diagnostics.append(
                _diagnostic(
                    "YARD_LINE_COUNT_INVALID",
                    "blocking",
                    f"梁场 {yard_id} 启用了 {len(yard_lines)} 条架梁作业线，首期要求每场恰好一线。",
                    "beam_yard",
                    yard_id,
                    "为该梁场保留且仅保留一条有效架梁作业线。",
                )
            )

    routes_by_yard: dict[str, list[ManualRoutePlan]] = defaultdict(list)
    for route in routes:
        routes_by_yard[route.beam_yard_id].append(route)
    for yard_id in sorted(yards):
        yard_routes = routes_by_yard.get(yard_id, [])
        if len(yard_routes) != 1:
            diagnostics.append(
                _diagnostic(
                    "YARD_ROUTE_COUNT_INVALID",
                    "blocking",
                    f"梁场 {yard_id} 配置了 {len(yard_routes)} 条人工架梁线路，首期要求每场恰好一条。",
                    "beam_yard",
                    yard_id,
                    "合并为一条固定人工顺序线路。",
                )
            )

    target_counts = Counter(target for route in routes for target in route.target_node_ids)
    required_targets = {node.node_id for node in graph.nodes if node.requires_erection}
    for target_id, count in sorted(target_counts.items()):
        if count > 1:
            diagnostics.append(
                _diagnostic(
                    "TARGET_DUPLICATE_ASSIGNMENT",
                    "blocking",
                    f"待架目标 {target_id} 被分配了 {count} 次。",
                    "bridge_side",
                    target_id,
                    "确保每个桥梁幅别只属于一个梁场线路。",
                )
            )
    for target_id in sorted(required_targets - set(target_counts)):
        diagnostics.append(
            _diagnostic(
                "TARGET_UNASSIGNED",
                "blocking",
                f"待架目标 {target_id} 尚未分配梁场线路。",
                "bridge_side",
                target_id,
                "将该桥梁幅别加入一条人工架梁线路。",
            )
        )

    owner_by_target = {
        target: route.route_plan_id
        for route in routes
        for target in route.target_node_ids
        if target_counts[target] == 1
    }
    prepared_routes: list[PreparedRoute] = []
    dependency_graph: dict[str, set[str]] = defaultdict(set)

    for route in routes:
        yard = yards.get(route.beam_yard_id)
        line = lines.get(route.erection_line_id)
        if yard is None:
            diagnostics.append(
                _diagnostic(
                    "ROUTE_YARD_UNKNOWN",
                    "blocking",
                    f"线路“{route.name}”引用了不存在或未启用的梁场。",
                    "route",
                    route.route_plan_id,
                    "重新选择有效梁场。",
                )
            )
            continue
        if line is None or line.beam_yard_id != yard.beam_yard_id:
            diagnostics.append(
                _diagnostic(
                    "ROUTE_LINE_UNKNOWN",
                    "blocking",
                    f"线路“{route.name}”引用的架梁作业线无效或不属于当前梁场。",
                    "route",
                    route.route_plan_id,
                    "重新选择当前梁场的有效架梁作业线。",
                )
            )
            continue
        deployment_node_id = _resolve_yard_node(yard, node_by_id)
        if deployment_node_id is None:
            diagnostics.append(
                _diagnostic(
                    "YARD_DEPLOYMENT_NODE_UNKNOWN",
                    "blocking",
                    f"梁场“{yard.name}”的线路 {yard.alignment_code}、里程 {yard.mileage_m:g} 无法唯一定位到线路图节点。",
                    "beam_yard",
                    yard.beam_yard_id,
                    "在线路图中重新选择部署节点。",
                )
            )
            continue
        if not route.confirmed:
            diagnostics.append(
                _diagnostic(
                    "ROUTE_ORDER_NOT_CONFIRMED",
                    "blocking",
                    f"线路“{route.name}”的人工顺序尚未确认。",
                    "route",
                    route.route_plan_id,
                    "确认桥梁幅别先后顺序后再计算。",
                )
            )

            continue
        expanded = [deployment_node_id]
        segment_nodes: dict[str, list[str]] = {}
        segment_transfer_days: dict[str, int] = {}
        previous = deployment_node_id
        previous_target: str | None = None
        for target_id in route.target_node_ids:
            target = node_by_id.get(target_id)
            if target is None or not target.requires_erection:
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_TARGET_INVALID",
                        "blocking",
                        f"线路“{route.name}”包含无效待架目标 {target_id}。",
                        "bridge_side",
                        target_id,
                        "只选择已识别梁型和片数的待架桥梁幅别。",
                    )
                )
                previous = target_id
                previous_target = target_id
                continue
            confirmed = next(
                (
                    item
                    for item in route.confirmed_paths
                    if item.from_target_node_id == previous and item.to_target_node_id == target_id
                ),
                None,
            )
            resolution = resolve_path(graph, previous, target_id, confirmed)
            if resolution.status == "unreachable":
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_SEGMENT_UNREACHABLE",
                        "blocking",
                        f"线路“{route.name}”的 {previous} → {target_id} 不可达。",
                        "route",
                        route.route_plan_id,
                        "补充真实连接关系或调整待架目标。",
                    )
                )
            elif resolution.status == "ambiguous":
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_PATH_AMBIGUOUS",
                        "blocking",
                        f"线路“{route.name}”的 {previous} → {target_id} 存在多条可达路径。",
                        "route",
                        route.route_plan_id,
                        "由用户选择并确认通行路径。",
                    )
                )
            elif resolution.status == "invalid_confirmation":
                diagnostics.append(
                    _diagnostic(
                        "ROUTE_PATH_CONFIRMATION_INVALID",
                        "blocking",
                        f"线路“{route.name}”保存的路径确认已失效。",
                        "route",
                        route.route_plan_id,
                        "基于当前线路图重新确认路径。",
                    )
                )
            else:
                segment_nodes[target_id] = resolution.node_ids
                segment_transfer_days[target_id] = sum(
                    edge_by_id[edge_id].transfer_days
                    for edge_id in resolution.edge_ids
                    if edge_id in edge_by_id
                )
                expanded.extend(resolution.node_ids[1:])
                if previous_target:
                    dependency_graph[target_id].add(previous_target)
                for passed_node_id in resolution.node_ids[:-1]:
                    owner_route = owner_by_target.get(passed_node_id)
                    if owner_route and owner_route != route.route_plan_id:
                        dependency_graph[target_id].add(passed_node_id)
            previous = target_id
            previous_target = target_id
        prepared_routes.append(
            PreparedRoute(
                route=route,
                yard=yard,
                line=line,
                deployment_node_id=deployment_node_id,
                expanded_node_ids=expanded,
                segment_node_ids=segment_nodes,
                segment_transfer_days=segment_transfer_days,
                dependencies_by_target={target: set(dependency_graph.get(target, set())) for target in route.target_node_ids},
            )
        )

    _validate_supply(prepared_routes, node_by_id, diagnostics)
    cycle = _find_cycle(dependency_graph)
    if cycle:
        diagnostics.append(
            _diagnostic(
                "CROSS_ROUTE_DEPENDENCY_CYCLE",
                "blocking",
                "架梁及通行依赖形成闭环：" + " → ".join(cycle),
                "dependency_graph",
                scenario.scenario_version_id,
                "调整人工顺序、梁场分配或确认通道以解除闭环。",
                cycle,
            )
        )

    status = "blocking" if any(item.severity == "blocking" for item in diagnostics) else (
        "warning" if diagnostics else "ready"
    )
    checks.extend(
        [
            ReadinessCheck(
                code="TARGET_ASSIGNMENT",
                status="blocking" if any(item.code in {"TARGET_DUPLICATE_ASSIGNMENT", "TARGET_UNASSIGNED"} for item in diagnostics) else "passed",
                message="所有待架桥梁幅别均应且只应分配一次。",
                entity_refs=sorted(required_targets),
            ),
            ReadinessCheck(
                code="ROUTE_TOPOLOGY",
                status="blocking" if any(item.code.startswith("ROUTE_") for item in diagnostics) else "passed",
                message="人工顺序之间的通行路径必须唯一或已由用户确认。",
                entity_refs=[item.route_plan_id for item in routes],
            ),
            ReadinessCheck(
                code="SUPPLY_AND_ERECTION_CAPACITY",
                status="blocking" if any(item.code in {"BEAM_TYPE_SUPPLY_MISSING", "ERECTION_CAPACITY_NON_POSITIVE"} for item in diagnostics) else "passed",
                message="每种梁型均有可用库存或生产能力，架梁能力大于零。",
                entity_refs=sorted(yards),
            ),
        ]
    )
    readiness = GirderPlanReadiness(
        status=status,
        checks=checks,
        diagnostics=diagnostics,
        expanded_routes={item.route.route_plan_id: item.expanded_node_ids for item in prepared_routes},
    )
    return PreparedSimulation(readiness=readiness, routes=prepared_routes, dependency_graph=dict(dependency_graph))


def _validate_supply(
    prepared_routes: list[PreparedRoute],
    node_by_id,
    diagnostics: list[SimulationDiagnostic],
) -> None:
    required_by_yard: dict[str, Counter[str]] = defaultdict(Counter)
    yard_by_id = {item.yard.beam_yard_id: item.yard for item in prepared_routes}
    for prepared in prepared_routes:
        for target_id in prepared.route.target_node_ids:
            node = node_by_id.get(target_id)
            if node:
                for demand in node.beam_demands:
                    required_by_yard[prepared.yard.beam_yard_id][demand.beam_type_id] += demand.pieces
    for yard_id, required in required_by_yard.items():
        capacity_by_type = {item.beam_type_id: item for item in yard_by_id[yard_id].capacities}
        for beam_type, pieces in required.items():
            capacity = capacity_by_type.get(beam_type)
            if capacity is None or (
                capacity.daily_capacity_pieces == 0 and capacity.initial_inventory_pieces < pieces
            ):
                diagnostics.append(
                    _diagnostic(
                        "BEAM_TYPE_SUPPLY_MISSING",
                        "blocking",
                        f"梁场 {yard_id} 的梁型 {beam_type} 需求 {pieces} 片，但库存与后续生产能力不足。",
                        "beam_type_capacity",
                        f"{yard_id}:{beam_type}",
                        "补充该梁型期初库存或片日产能。",
                    )
                )


def _find_cycle(graph: dict[str, set[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str]:
        if node in visiting:
            index = stack.index(node)
            return [*stack[index:], node]
        if node in visited:
            return []
        visiting.add(node)
        stack.append(node)
        for dependency in sorted(graph.get(node, set())):
            cycle = visit(dependency)
            if cycle:
                return cycle
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return []

    for node in sorted(graph):
        cycle = visit(node)
        if cycle:
            return cycle
    return []


def _resolve_yard_node(yard: BeamYardPlan, node_by_id) -> str | None:
    candidates = [
        node
        for node in node_by_id.values()
        if node.alignment_code == yard.alignment_code
        and node.start_mileage_m is not None
        and node.end_mileage_m is not None
        and min(node.start_mileage_m, node.end_mileage_m) <= yard.mileage_m <= max(node.start_mileage_m, node.end_mileage_m)
    ]
    exact_start = [node for node in candidates if node.start_mileage_m == yard.mileage_m]
    exact_start_preferred = [node for node in exact_start if node.side == "unknown" and not node.requires_erection]
    if len(exact_start_preferred) == 1:
        return exact_start_preferred[0].node_id
    if len(exact_start) == 1:
        return exact_start[0].node_id
    preferred = [node for node in candidates if node.side == "unknown" and not node.requires_erection]
    if len(preferred) == 1:
        return preferred[0].node_id
    if len(candidates) == 1:
        return candidates[0].node_id
    return None


def _check(
    condition: bool,
    code: str,
    message: str,
    checks: list[ReadinessCheck],
    diagnostics: list[SimulationDiagnostic],
    object_id: str,
) -> None:
    checks.append(ReadinessCheck(code=code, status="passed" if condition else "blocking", message=message, entity_refs=[object_id]))
    if not condition:
        diagnostics.append(_diagnostic(code, "blocking", message, "scenario_version", object_id, "补齐必要配置。"))


def _diagnostic(
    code: str,
    severity: str,
    message: str,
    object_type: str,
    object_id: str,
    suggestion: str,
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


__all__ = ["PreparedRoute", "PreparedSimulation", "prepare_scenario", "validate_scenario"]
