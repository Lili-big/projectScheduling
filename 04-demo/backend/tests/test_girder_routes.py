from __future__ import annotations

from datetime import date

from app.girder_planning.models import RouteOccurrence
from app.girder_planning.ownership import resolve_ownership


def _occurrence(route_id: str, arrival: date, sequence_index: int = 0) -> RouteOccurrence:
    return RouteOccurrence(
        route_id=route_id,
        route_node_id=f"{route_id}-node",
        workpoint_id="bridge:B1:left",
        bridge_id="B1",
        side="left",
        arrival_date=arrival,
        sequence_index=sequence_index,
    )


def test_shared_bridge_is_erected_once_and_later_route_is_competing_passage() -> None:
    ownerships, diagnostics = resolve_ownership(
        [_occurrence("route-1", date(2026, 1, 1)), _occurrence("route-2", date(2026, 1, 3))]
    )

    assert diagnostics == []
    assert len(ownerships) == 1
    assert ownerships[0].owner_route_id == "route-1"
    assert {item.route_id for item in ownerships[0].competing_occurrences} == {"route-1", "route-2"}


def test_same_day_arrival_blocks_without_manual_owner() -> None:
    ownerships, diagnostics = resolve_ownership(
        [_occurrence("route-1", date(2026, 1, 1)), _occurrence("route-2", date(2026, 1, 1))]
    )

    assert ownerships == []
    assert any(item.code == "GIRDER_OWNER_AMBIGUOUS" for item in diagnostics)
