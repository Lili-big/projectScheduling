"""Deterministic natural-day simulation for a fixed manual girder sequence."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from ..contracts.girder_plan_simulation import (
    BridgeErectionSchedule,
    DailyBeamConsumption,
    GirderPlanScenarioVersion,
    GirderPlanSimulationRun,
    LineGraphSnapshot,
    PlannedRouteRun,
    RouteDeliveryRequirement,
    SimulationDiagnostic,
    WorkpointDeliveryControl,
    YardInventoryLedgerEntry,
)
from ..girder_planning.fingerprints import stable_fingerprint
from .validation import PreparedRoute, PreparedSimulation, prepare_scenario


@dataclass
class _TargetState:
    target_node_id: str
    beam_type_counts: dict[str, int]
    remaining: Counter[str]
    start_date: date | None = None
    finish_date: date | None = None
    daily: list[DailyBeamConsumption] = field(default_factory=list)
    controlling_factors: set[str] = field(default_factory=set)


@dataclass
class _RouteState:
    prepared: PreparedRoute
    targets: list[_TargetState]
    target_index: int = 0
    waiting: Counter[str] = field(default_factory=Counter)


def simulate(
    scenario: GirderPlanScenarioVersion,
    graph: LineGraphSnapshot,
    *,
    prepared: PreparedSimulation | None = None,
    run_id: str | None = None,
    started_at: datetime | None = None,
) -> GirderPlanSimulationRun:
    prepared = prepared or prepare_scenario(scenario, graph)
    started_at = started_at or datetime.now(timezone.utc)
    run_id = run_id or f"gpsr-{uuid4().hex}"
    if prepared.readiness.status == "blocking":
        return _run(
            run_id=run_id,
            scenario=scenario,
            started_at=started_at,
            status="blocked",
            diagnostics=prepared.readiness.diagnostics,
        )

    node_by_id = {node.node_id: node for node in graph.nodes}
    route_states: list[_RouteState] = []
    owner_by_target: dict[str, str] = {}
    for item in prepared.routes:
        targets: list[_TargetState] = []
        for target_id in item.route.target_node_ids:
            node = node_by_id[target_id]
            counts = {demand.beam_type_id: demand.pieces for demand in node.beam_demands}
            targets.append(_TargetState(target_node_id=target_id, beam_type_counts=counts, remaining=Counter(counts)))
            owner_by_target[target_id] = item.route.route_plan_id
        route_states.append(_RouteState(prepared=item, targets=targets))

    inventories: dict[str, dict[str, int]] = {
        item.yard.beam_yard_id: {
            capacity.beam_type_id: capacity.initial_inventory_pieces for capacity in item.yard.capacities
        }
        for item in prepared.routes
    }
    capacities = {
        item.yard.beam_yard_id: {capacity.beam_type_id: capacity for capacity in item.yard.capacities}
        for item in prepared.routes
    }
    begin_dates = [
        min(item.prepared.yard.production_start_date, item.prepared.line.available_date)
        for item in route_states
    ]
    current = min(begin_dates)
    horizon = scenario.parameters.planning_horizon_end_date
    ledger: list[YardInventoryLedgerEntry] = []
    completed: dict[str, date] = {}

    while current <= horizon and any(state.target_index < len(state.targets) for state in route_states):
        opening = {yard_id: dict(values) for yard_id, values in inventories.items()}
        consumed_by_yard: dict[str, Counter[str]] = defaultdict(Counter)

        for route_state in sorted(route_states, key=lambda item: item.prepared.route.route_plan_id):
            if route_state.target_index >= len(route_state.targets):
                continue
            target = route_state.targets[route_state.target_index]
            prepared_route = route_state.prepared
            earliest, wait_reason = _earliest_date(route_state, target, completed, owner_by_target, scenario)
            if current < earliest:
                route_state.waiting[wait_reason] += 1
                target.controlling_factors.add(wait_reason)
                continue
            dependencies = prepared_route.dependencies_by_target.get(target.target_node_id, set())
            if any(dependency not in completed for dependency in dependencies):
                route_state.waiting["cross_route_passage"] += 1
                target.controlling_factors.add("cross_route_passage")
                continue

            remaining_capacity = prepared_route.line.daily_erection_capacity_pieces
            daily_total = 0
            for beam_type in sorted(target.remaining):
                if remaining_capacity <= 0:
                    break
                remaining = target.remaining[beam_type]
                if remaining <= 0:
                    continue
                available = opening[prepared_route.yard.beam_yard_id].get(beam_type, 0) - consumed_by_yard[
                    prepared_route.yard.beam_yard_id
                ][beam_type]
                erected = min(remaining, remaining_capacity, max(0, available))
                if erected <= 0:
                    continue
                target.remaining[beam_type] -= erected
                remaining_capacity -= erected
                daily_total += erected
                consumed_by_yard[prepared_route.yard.beam_yard_id][beam_type] += erected
                target.daily.append(DailyBeamConsumption(date=current, beam_type_id=beam_type, erected_pieces=erected))
            if daily_total == 0:
                route_state.waiting["supply"] += 1
                target.controlling_factors.add("supply")
                continue
            if target.start_date is None:
                target.start_date = current
                target.controlling_factors.add("line_available")
            if all(value <= 0 for value in target.remaining.values()):
                target.finish_date = current
                completed[target.target_node_id] = current
                route_state.target_index += 1

        for yard_id, beam_types in capacities.items():
            for beam_type, capacity in beam_types.items():
                opening_value = opening[yard_id].get(beam_type, 0)
                consumed = consumed_by_yard[yard_id][beam_type]
                produced = 0
                yard = next(item.yard for item in prepared.routes if item.yard.beam_yard_id == yard_id)
                if current >= yard.production_start_date:
                    produced = capacity.daily_capacity_pieces
                    if capacity.max_inventory_pieces is not None:
                        produced = min(produced, max(0, capacity.max_inventory_pieces - (opening_value - consumed)))
                closing = opening_value + produced - consumed
                if closing < 0:
                    raise RuntimeError("库存不变量被破坏：期末库存小于零。")
                inventories[yard_id][beam_type] = closing
                ledger.append(
                    YardInventoryLedgerEntry(
                        date=current,
                        beam_yard_id=yard_id,
                        beam_type_id=beam_type,
                        opening_inventory_pieces=opening_value,
                        produced_pieces=produced,
                        erected_pieces=consumed,
                        closing_inventory_pieces=closing,
                    )
                )
        current += timedelta(days=1)

    diagnostics = list(prepared.readiness.diagnostics)
    incomplete = [target for state in route_states for target in state.targets if target.finish_date is None]
    if incomplete:
        for target in incomplete:
            diagnostics.append(
                SimulationDiagnostic(
                    code="PLANNING_HORIZON_EXCEEDED",
                    severity="blocking",
                    message=f"规划时域结束时待架目标 {target.target_node_id} 尚未完成。",
                    object_type="bridge_side",
                    object_id=target.target_node_id,
                    entity_refs=[target.target_node_id],
                    suggestion="延长规划时域或补充受限梁型的生产/库存能力。",
                )
            )

    schedules = _bridge_schedules(route_states)
    route_runs = _route_runs(route_states)
    controls = _delivery_controls(scenario, graph, prepared.routes, schedules)
    status = "blocked" if incomplete else "calculated"
    return _run(
        run_id=run_id,
        scenario=scenario,
        started_at=started_at,
        status=status,
        bridge_schedules=schedules,
        inventory_ledger=ledger,
        route_runs=route_runs,
        workpoint_controls=controls,
        diagnostics=diagnostics,
    )


def _earliest_date(
    route_state: _RouteState,
    target: _TargetState,
    completed: dict[str, date],
    owner_by_target: dict[str, str],
    scenario: GirderPlanScenarioVersion,
) -> tuple[date, str]:
    prepared = route_state.prepared
    explicit_path_transfer_days = prepared.segment_transfer_days.get(target.target_node_id, 0)
    if route_state.target_index == 0:
        return (
            prepared.line.available_date
            + timedelta(days=prepared.line.first_erection_preparation_days + explicit_path_transfer_days),
            "line_available",
        )
    previous = route_state.targets[route_state.target_index - 1]
    assert previous.finish_date is not None
    previous_node = previous.target_node_id.rsplit(":", 1)
    current_node = target.target_node_id.rsplit(":", 1)
    side_switch = previous_node[0] == current_node[0] and previous_node[-1] != current_node[-1]
    transition_days = prepared.line.side_switch_days if side_switch else prepared.line.bridge_transfer_days
    transition_days = transition_days or scenario.parameters.default_transfer_days
    earliest = previous.finish_date + timedelta(days=max(1, transition_days, explicit_path_transfer_days))
    reason = "side_switch" if side_switch else "transfer"
    for dependency in prepared.dependencies_by_target.get(target.target_node_id, set()):
        if owner_by_target.get(dependency) == prepared.route.route_plan_id:
            continue
        finish = completed.get(dependency)
        if finish is not None:
            earliest = max(
                earliest,
                finish + timedelta(days=max(1, scenario.parameters.post_erection_passage_buffer_days)),
            )
            reason = "cross_route_passage"
    return earliest, reason


def _bridge_schedules(route_states: list[_RouteState]) -> list[BridgeErectionSchedule]:
    result: list[BridgeErectionSchedule] = []
    for route_state in route_states:
        for index, target in enumerate(route_state.targets):
            if target.start_date is None or target.finish_date is None:
                continue
            result.append(
                BridgeErectionSchedule(
                    target_node_id=target.target_node_id,
                    beam_yard_id=route_state.prepared.yard.beam_yard_id,
                    route_plan_id=route_state.prepared.route.route_plan_id,
                    sequence_index=index,
                    start_date=target.start_date,
                    finish_date=target.finish_date,
                    total_beam_count=sum(target.beam_type_counts.values()),
                    beam_type_counts=target.beam_type_counts,
                    daily_erection=target.daily,
                    controlling_factors=sorted(target.controlling_factors) or ["line_available"],
                )
            )
    return sorted(result, key=lambda item: (item.route_plan_id, item.sequence_index))


def _route_runs(route_states: list[_RouteState]) -> list[PlannedRouteRun]:
    result: list[PlannedRouteRun] = []
    for route_state in route_states:
        completed = [target for target in route_state.targets if target.start_date and target.finish_date]
        if not completed:
            continue
        result.append(
            PlannedRouteRun(
                route_plan_id=route_state.prepared.route.route_plan_id,
                beam_yard_id=route_state.prepared.yard.beam_yard_id,
                start_date=min(target.start_date for target in completed),
                finish_date=max(target.finish_date for target in completed),
                expanded_node_ids=route_state.prepared.expanded_node_ids,
                waiting_days_by_reason=dict(sorted(route_state.waiting.items())),
            )
        )
    return sorted(result, key=lambda item: item.route_plan_id)


def _delivery_controls(
    scenario: GirderPlanScenarioVersion,
    graph: LineGraphSnapshot,
    routes: list[PreparedRoute],
    schedules: list[BridgeErectionSchedule],
) -> list[WorkpointDeliveryControl]:
    node_by_id = {node.node_id: node for node in graph.nodes}
    schedule_by_target = {item.target_node_id: item for item in schedules}
    requirements: dict[str, list[RouteDeliveryRequirement]] = defaultdict(list)
    source_by_node: dict[tuple[str, str], tuple[str, int]] = {}
    for prepared in routes:
        for target_id in prepared.route.target_node_ids:
            schedule = schedule_by_target.get(target_id)
            if schedule is None:
                continue
            for node_id in prepared.segment_node_ids.get(target_id, [target_id]):
                node = node_by_id.get(node_id)
                if node is None or node.project_master_workpoint_id is None:
                    continue
                source, buffer_days = _control_rule(node, node_id == target_id, scenario)
                requirements[node_id].append(
                    RouteDeliveryRequirement(
                        route_plan_id=prepared.route.route_plan_id,
                        required_date=schedule.start_date,
                        buffer_days=buffer_days,
                        source=source,
                    )
                )
                source_by_node[(node_id, prepared.route.route_plan_id)] = (source, buffer_days)

    controls: list[WorkpointDeliveryControl] = []
    for node_id, items in requirements.items():
        node = node_by_id[node_id]
        candidates = [
            (item.required_date - timedelta(days=item.buffer_days), item)
            for item in items
        ]
        latest_delivery, controlling = min(candidates, key=lambda item: (item[0], item[1].route_plan_id))
        current_finish = node.current_plan_finish_date
        late_days = None if current_finish is None else max(0, (current_finish - latest_delivery).days)
        risk_status = "unknown" if current_finish is None else ("late" if current_finish > latest_delivery else "on_time")
        side = node.side if node.side in {"left", "right"} else "unknown"
        controls.append(
            WorkpointDeliveryControl(
                node_id=node_id,
                project_master_workpoint_id=node.project_master_workpoint_id,
                side=side,
                first_required_date=min(item.required_date for item in items),
                latest_delivery_date=latest_delivery,
                buffer_days=controlling.buffer_days,
                controlling_source=controlling.source,
                route_requirements=sorted(items, key=lambda item: (item.required_date, item.route_plan_id)),
                current_plan_finish_date=current_finish,
                late_days=late_days,
                risk_status=risk_status,
            )
        )
    return sorted(controls, key=lambda item: (item.latest_delivery_date, item.node_id))


def _control_rule(node, is_target: bool, scenario: GirderPlanScenarioVersion) -> tuple[str, int]:
    parameters = scenario.parameters
    if is_target and node.node_type == "bridge":
        return "erection_start", parameters.bridge_readiness_buffer_days
    if node.node_type == "roadbed":
        return "roadbed_passage", parameters.roadbed_passage_buffer_days
    if node.node_type == "tunnel":
        return "tunnel_passage", parameters.tunnel_passage_buffer_days
    if node.node_type == "bridge":
        return "post_erection_passage", parameters.post_erection_passage_buffer_days
    return "access_passage", parameters.access_passage_buffer_days


def _run(
    *,
    run_id: str,
    scenario: GirderPlanScenarioVersion,
    started_at: datetime,
    status: str,
    bridge_schedules=None,
    inventory_ledger=None,
    route_runs=None,
    workpoint_controls=None,
    diagnostics=None,
) -> GirderPlanSimulationRun:
    finished_at = datetime.now(timezone.utc)
    result_payload = {
        "scenario_version_id": scenario.scenario_version_id,
        "input_fingerprint": scenario.input_fingerprint,
        "status": status,
        "bridge_schedules": [item.model_dump(mode="json") for item in bridge_schedules or []],
        "inventory_ledger": [item.model_dump(mode="json") for item in inventory_ledger or []],
        "route_runs": [item.model_dump(mode="json") for item in route_runs or []],
        "workpoint_controls": [item.model_dump(mode="json") for item in workpoint_controls or []],
        "diagnostics": [item.model_dump(mode="json") for item in diagnostics or []],
    }
    return GirderPlanSimulationRun(
        run_id=run_id,
        scenario_version_id=scenario.scenario_version_id,
        project_master_version_id=scenario.project_master_version_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        input_fingerprint=scenario.input_fingerprint,
        result_fingerprint=stable_fingerprint(result_payload),
        bridge_schedules=bridge_schedules or [],
        inventory_ledger=inventory_ledger or [],
        route_runs=route_runs or [],
        workpoint_controls=workpoint_controls or [],
        diagnostics=diagnostics or [],
    )


__all__ = ["simulate"]
