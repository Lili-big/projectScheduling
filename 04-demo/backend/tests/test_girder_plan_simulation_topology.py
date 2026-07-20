from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.girder_plan_simulation import ConnectionConfirmation, LineGraphEdge
from app.girder_plan_simulation.topology import build_line_graph, resolve_path
from girder_plan_simulation_fixture_helpers import project_snapshot


def test_line_graph_keeps_bridge_side_and_beam_type_demand() -> None:
    graph = build_line_graph(project_id="P1", project_master_version_id="PMV1", snapshot=project_snapshot())
    nodes = {item.node_id: item for item in graph.nodes}
    assert graph.status in {"ready", "warning"}
    demand = nodes["B1:left"].beam_demands[0]
    assert demand.beam_type_id == "T32"
    assert demand.beam_type_name == "T32"
    assert demand.span_count == 1
    assert demand.beam_count == 4
    assert demand.span_refs == ["B1-left"]
    assert nodes["B2:right"].beam_demands[0].beam_type_id == "T40"
    assert resolve_path(graph, "B1:left", "B2:left").node_ids == ["B1:left", "T1:unknown", "B2:left"]


def test_missing_mileage_is_blocking_and_never_becomes_zero() -> None:
    snapshot = project_snapshot()
    snapshot.workpoints[2].start_mileage_m = None
    graph = build_line_graph(project_id="P1", project_master_version_id="PMV1", snapshot=snapshot)
    assert graph.status == "blocking"
    assert any(item.code == "MILEAGE_MISSING" and item.object_id == "T1" for item in graph.diagnostics)
    assert next(item for item in graph.nodes if item.node_id == "T1:unknown").start_mileage_m is None


def test_parallel_side_paths_require_confirmation_when_not_unique() -> None:
    graph = build_line_graph(project_id="P1", project_master_version_id="PMV1", snapshot=project_snapshot())
    result = resolve_path(graph, "R0:unknown", "T1:unknown")
    assert result.status == "ambiguous"
    assert result.alternatives == 2


def test_gap_requires_audited_manual_connection_and_overlap_blocks() -> None:
    snapshot = project_snapshot()
    snapshot.workpoints[1].start_mileage_m = 120
    snapshot.workpoints[1].end_mileage_m = 200
    blocked = build_line_graph(project_id="P1", project_master_version_id="PMV1", snapshot=snapshot)
    assert any(item.code == "LINE_GRAPH_GAP" for item in blocked.diagnostics)
    override = LineGraphEdge(
        edge_id="MANUAL-R0-B1",
        from_node_id="R0:unknown",
        to_node_id="B1:left",
        direction="bidirectional",
        source="manual_connection",
        transfer_days=2,
        confirmation=ConnectionConfirmation(
            reason="现场便道可通行",
            confirmed_by="项目总工",
            confirmed_at=datetime.now(timezone.utc),
        ),
    )
    connected = build_line_graph(
        project_id="P1",
        project_master_version_id="PMV1",
        snapshot=snapshot,
        connection_overrides=[override],
    )
    assert not any(item.code == "LINE_GRAPH_GAP" and "R0:B1" in item.entity_refs for item in connected.diagnostics)
    assert any(item.edge_id == override.edge_id for item in connected.edges)

    overlap = project_snapshot()
    overlap.workpoints[1].start_mileage_m = 90
    graph = build_line_graph(project_id="P1", project_master_version_id="PMV1", snapshot=overlap)
    assert any(item.code == "MILEAGE_OVERLAP" for item in graph.diagnostics)
