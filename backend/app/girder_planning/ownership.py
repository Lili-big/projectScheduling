from __future__ import annotations

from collections import defaultdict

from ..models import (
    CompetingRouteOccurrence,
    ErectionOwnerOverride,
    ErectionOwnership,
    GirderExecutionActual,
    ValidationMessage,
)
from .models import RouteOccurrence


def resolve_ownership(
    occurrences: list[RouteOccurrence],
    *,
    overrides: list[ErectionOwnerOverride] | None = None,
    actuals: list[GirderExecutionActual] | None = None,
) -> tuple[list[ErectionOwnership], list[ValidationMessage]]:
    grouped: dict[tuple[str, str], list[RouteOccurrence]] = defaultdict(list)
    for item in occurrences:
        if item.bridge_id and item.arrival_date:
            grouped[(item.bridge_id, item.side)].append(item)
    override_by_key = {(item.bridge_id, item.side): item for item in overrides or []}
    actual_route_by_task = {item.span_task_id: item.actual_route_id for item in actuals or [] if item.actual_route_id}
    ownerships: list[ErectionOwnership] = []
    diagnostics: list[ValidationMessage] = []

    for (bridge_id, side), candidates in sorted(grouped.items()):
        ordered = sorted(candidates, key=lambda item: (item.arrival_date, item.sequence_index, item.route_id, item.route_node_id))
        override = override_by_key.get((bridge_id, side))
        selected = None
        source = "earliest_arrival"
        actual_route = next((route for task_id, route in actual_route_by_task.items() if bridge_id in task_id and route), None)
        if actual_route:
            selected = next((item for item in ordered if item.route_id == actual_route), None)
            source = "actual_fact"
        elif override:
            selected = next((item for item in ordered if item.route_id == override.owner_route_id), None)
            source = "manual_override"
            if selected is None:
                diagnostics.append(_message("error", "GIRDER_OWNER_OVERRIDE_INVALID", f"桥梁 {bridge_id}:{side} 的人工归属路线未经过该桥梁。", bridge_id))
                continue
        if selected is None:
            first_date = ordered[0].arrival_date
            earliest_routes = {item.route_id for item in ordered if item.arrival_date == first_date}
            if len(earliest_routes) > 1:
                diagnostics.append(_message("error", "GIRDER_OWNER_AMBIGUOUS", f"桥梁 {bridge_id}:{side} 有多条路线同日最早到达，必须人工指定唯一归属。", bridge_id))
                continue
            selected = ordered[0]
        ownerships.append(
            ErectionOwnership(
                bridge_id=bridge_id,
                side=side,
                owner_route_id=selected.route_id,
                owner_node_id=selected.route_node_id,
                arrival_date=selected.arrival_date,
                resolution_source=source,
                competing_occurrences=[
                    CompetingRouteOccurrence(route_id=item.route_id, route_node_id=item.route_node_id, arrival_date=item.arrival_date)
                    for item in ordered
                ],
            )
        )
    return ownerships, diagnostics


def _message(level: str, code: str, message: str, *refs: str) -> ValidationMessage:
    return ValidationMessage(level=level, code=code, message=message, subject_id=refs[0] if refs else None, entity_refs=list(refs))
