from __future__ import annotations

from datetime import date, timedelta

from ..models import ErectionOwnership, GirderPlanningConfig, PassageReleaseResult, ProjectDataVersion, RouteRun
from .models import RouteOccurrence


def simulate_routes(
    project_version: ProjectDataVersion,
    config: GirderPlanningConfig,
    *,
    ownerships: list[ErectionOwnership] | None = None,
    passage_releases: list[PassageReleaseResult] | None = None,
    owner_finish_by_workpoint: dict[str, date] | None = None,
) -> tuple[list[RouteOccurrence], list[RouteRun]]:
    workpoint_by_id = {item.workpoint_id: item for item in project_version.workpoints}
    yard_by_id = {item.beam_yard_id: item for item in config.beam_yards}
    machine_by_id = {item.erection_machine_id: item for item in config.erection_machines}
    ownership_by_key = {(item.bridge_id, item.side): item for item in ownerships or []}
    passage_by_id = {item.workpoint_id: item for item in passage_releases or []}
    finish_by_workpoint = owner_finish_by_workpoint or {}
    occurrences: list[RouteOccurrence] = []
    runs: list[RouteRun] = []

    for route in sorted((item for item in config.routes if item.enabled), key=lambda item: item.route_id):
        yard = yard_by_id.get(route.beam_yard_id)
        machine = machine_by_id.get(route.erection_machine_id)
        if yard is None or machine is None:
            continue
        current = max(yard.production_start_date, machine.available_date)
        start = current
        waiting_days = 0
        event_refs: list[str] = []
        ordered_nodes = sorted(route.nodes, key=lambda item: item.sequence_index)
        for index, node in enumerate(ordered_nodes):
            if index:
                current += timedelta(days=node.connection_days if node.connection_days is not None else config.parameters.default_transfer_days)
            workpoint = workpoint_by_id.get(node.workpoint_id)
            if workpoint is None:
                continue
            key = (workpoint.bridge_id, workpoint.side)
            owner = ownership_by_key.get(key) if workpoint.bridge_id else None
            passage = passage_by_id.get(workpoint.workpoint_id)
            is_owner = owner is not None and owner.owner_route_id == route.route_id and owner.owner_node_id == node.route_node_id
            if not is_owner and passage and passage.passable_date and current < passage.passable_date:
                waiting_days += (passage.passable_date - current).days
                current = passage.passable_date
            arrival = current
            if workpoint.bridge_id:
                occurrences.append(
                    RouteOccurrence(
                        route_id=route.route_id,
                        route_node_id=node.route_node_id,
                        workpoint_id=workpoint.workpoint_id,
                        bridge_id=workpoint.bridge_id,
                        side=workpoint.side,
                        arrival_date=arrival,
                        sequence_index=node.sequence_index,
                    )
                )
            if is_owner and workpoint.workpoint_id in finish_by_workpoint:
                current = max(current, finish_by_workpoint[workpoint.workpoint_id])
            event_refs.append(node.route_node_id)
        runs.append(
            RouteRun(
                route_id=route.route_id,
                beam_yard_id=route.beam_yard_id,
                erection_machine_id=route.erection_machine_id,
                start_date=start,
                finish_date=current,
                waiting_days=waiting_days,
                event_refs=event_refs,
            )
        )
    return occurrences, runs
