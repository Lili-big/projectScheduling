from __future__ import annotations

from collections import defaultdict

from ..contracts import (
    CompetingRouteOccurrence,
    ErectionOwnerOverride,
    ErectionOwnership,
    GirderExecutionActual,
    GirderWorkPoint,
    PassageConditionRef,
    ValidationMessage,
)
from ..contracts.project_master import ProjectMasterSnapshot
from .models import RouteOccurrence


def derive_route_workpoints(snapshot: ProjectMasterSnapshot) -> list[GirderWorkPoint]:
    """Derive stable route nodes from unified workpoint + side master data."""

    result: list[GirderWorkPoint] = []
    type_map = {"bridge": "bridge", "roadbed": "roadbed", "tunnel": "tunnel", "culvert": "culvert"}
    for workpoint in sorted(snapshot.workpoints, key=lambda item: (item.sort_order, item.workpoint_id)):
        sides = sorted(
            {item.side for item in workpoint.structures if item.side in {"left", "right"}},
            key=lambda item: {"left": 0, "right": 1}[item],
        )
        if workpoint.workpoint_type != "bridge" or not sides:
            sides = ["unknown"]
        for side in sides:
            side_structures = [
                item
                for item in workpoint.structures
                if side == "unknown" or item.side in {side, "shared", "none"}
            ]
            section = next((item for item in side_structures if item.section_code), None)
            derived_id = f"{workpoint.workpoint_id}:{side}"
            result.append(
                GirderWorkPoint(
                    workpoint_id=derived_id,
                    name=f"{workpoint.workpoint_name}·{_side_label(side)}" if side != "unknown" else workpoint.workpoint_name,
                    workpoint_type=type_map.get(workpoint.workpoint_type, "access"),
                    side=side,
                    mileage_start_m=workpoint.start_mileage_m or 0,
                    mileage_end_m=workpoint.end_mileage_m or workpoint.start_mileage_m or 0,
                    corridor_id=workpoint.alignment_code or "default",
                    bridge_id=workpoint.workpoint_id if workpoint.workpoint_type == "bridge" else None,
                    work_section_id=section.section_code if section else None,
                    requires_erection=workpoint.workpoint_type == "bridge",
                    rough_granularity=False,
                    linked_condition_refs=[
                        PassageConditionRef(
                            ref_type="upper_structure" if item.structure_category == "superstructure" else "structure",
                            entity_id=item.structure_id,
                        )
                        for item in side_structures
                    ],
                    properties={
                        "project_master_workpoint_id": workpoint.workpoint_id,
                        "project_master_side": side,
                    },
                )
            )
    return result


def _side_label(side: str) -> str:
    return {"left": "左幅", "right": "右幅", "unknown": "不分幅"}.get(side, side)


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
