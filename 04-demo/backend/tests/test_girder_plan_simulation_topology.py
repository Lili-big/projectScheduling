from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.girder_plan_simulation import ConnectionConfirmation, LineGraphEdge  # noqa: E402
from app.contracts.project_master import ParameterValue  # noqa: E402
from app.contracts.project_master import ProjectMasterRoutePlacement  # noqa: E402
from app.girder_plan_simulation.topology import build_line_graph, resolve_path  # noqa: E402
from girder_plan_simulation_fixture_helpers import continuous_route_snapshot, explicit_route_snapshot, project_snapshot  # noqa: E402


def _graph(snapshot=None, *, overrides=()):
    return build_line_graph(
        project_id="P1",
        project_master_version_id="PMV1",
        snapshot=snapshot or explicit_route_snapshot(),
        connection_overrides=overrides,
    )


def test_explicit_line_graph_keeps_two_sides_prefixes_and_beam_demand() -> None:
    graph = _graph()
    nodes = {item.node_id: item for item in graph.nodes}

    assert graph.projection_version == "girder-plan-line-graph/v3"
    assert graph.status == "ready"
    assert {item.side for item in graph.nodes} == {"left", "right"}
    assert {item.alignment_code for item in graph.nodes if item.side == "left"} == {"ZK"}
    assert {item.alignment_code for item in graph.nodes if item.side == "right"} == {"K"}
    assert nodes["B1:left"].spatial_group_id == "SG-001"
    assert nodes["B1:left"].beam_demands[0].beam_type_id == "T32"
    assert nodes["B2:right"].beam_demands[0].beam_type_id == "T40"
    assert resolve_path(graph, "B1:left", "B2:left").node_ids == ["B1:left", "T1:left", "B2:left"]


def test_legacy_snapshot_infers_two_tracks_without_unknown_nodes() -> None:
    graph = _graph(project_snapshot())

    assert graph.status == "warning"
    assert all(item.side in {"left", "right"} for item in graph.nodes)
    assert {"R0:left", "R0:right", "T1:left", "T1:right"} <= {item.node_id for item in graph.nodes}
    assert all(item.placement_source == "inferred" for item in graph.nodes)
    inferred = next(item for item in graph.diagnostics if item.code == "ROUTE_PLACEMENT_INFERRED")
    assert set(inferred.entity_refs) == {"R0", "B1", "T1", "B2", "R3"}


def test_route_placement_change_updates_v2_line_graph_fingerprint() -> None:
    snapshot = explicit_route_snapshot()
    first = _graph(snapshot)
    snapshot.route_placements[0].spatial_group_id = "SG-CHANGED"
    second = _graph(snapshot)
    assert first.projection_version == "girder-plan-line-graph/v3"
    assert first.line_graph_id != second.line_graph_id
    assert first.input_fingerprint != second.input_fingerprint


def test_connector_prefixes_remain_node_attributes_and_single_side_stays_single() -> None:
    snapshot = explicit_route_snapshot()
    snapshot.route_placements = [
        placement
        for placement in snapshot.route_placements
        if not (placement.workpoint_id == "B1" and placement.side == "right")
    ]
    prefixes = {
        ("B1", "left"): "AK",
        ("B2", "left"): "BK",
        ("B2", "right"): "B1K",
    }
    for placement in snapshot.route_placements:
        placement.mileage_prefix = prefixes.get((placement.workpoint_id, placement.side), placement.mileage_prefix)

    graph = _graph(snapshot)
    nodes = {item.node_id: item for item in graph.nodes}
    assert nodes["B1:left"].alignment_code == "AK"
    assert "B1:right" not in nodes
    assert nodes["B2:left"].alignment_code == "BK"
    assert nodes["B2:right"].alignment_code == "B1K"
    assert {item.side for item in graph.nodes} == {"left", "right"}


def test_missing_route_side_and_one_to_many_spatial_group_keep_object_evidence() -> None:
    missing_side = project_snapshot()
    missing_side.workpoints[0].structures = []
    missing_graph = _graph(missing_side)
    diagnostic = next(item for item in missing_graph.diagnostics if item.code == "ROUTE_SIDE_MISSING")
    assert diagnostic.object_id == "R0"
    assert diagnostic.severity == "blocking"

    one_to_many = explicit_route_snapshot()
    b1_left = next(item for item in one_to_many.route_placements if item.workpoint_id == "B1" and item.side == "left")
    b2_left = next(item for item in one_to_many.route_placements if item.workpoint_id == "B2" and item.side == "left")
    b2_left.spatial_group_id = b1_left.spatial_group_id
    graph = _graph(one_to_many)
    assert {item.node_id for item in graph.nodes if item.spatial_group_id == b1_left.spatial_group_id} >= {"B1:left", "B2:left"}


def test_missing_mileage_is_blocking_and_never_becomes_zero() -> None:
    snapshot = project_snapshot()
    snapshot.workpoints[2].start_mileage_m = None
    graph = _graph(snapshot)

    assert graph.status == "blocking"
    assert any(item.code == "ROUTE_MILEAGE_MISSING" and item.object_id == "T1:left" for item in graph.diagnostics)
    assert next(item for item in graph.nodes if item.node_id == "T1:left").start_mileage_m is None


def test_parallel_tracks_are_unique_and_spatial_groups_do_not_create_cross_edges() -> None:
    graph = _graph()

    assert resolve_path(graph, "R0:left", "T1:left").status == "unique"
    assert resolve_path(graph, "R0:right", "T1:right").status == "unique"
    assert resolve_path(graph, "R0:left", "R0:right").status == "unreachable"
    assert not any({item.from_node_id, item.to_node_id} == {"R0:left", "R0:right"} for item in graph.edges)


def test_gap_requires_audited_manual_connection_and_true_overlap_blocks() -> None:
    snapshot = explicit_route_snapshot()
    target = next(item for item in snapshot.route_placements if item.workpoint_id == "B1" and item.side == "left")
    target.start_mileage_m = 120
    blocked = _graph(snapshot)
    assert any(item.code == "LINE_GRAPH_GAP" and {"R0:left", "B1:left"} <= set(item.entity_refs) for item in blocked.diagnostics)

    override = LineGraphEdge(
        edge_id="MANUAL-R0-B1",
        from_node_id="R0:left",
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
    connected = _graph(snapshot, overrides=[override])
    assert not any(item.code == "LINE_GRAPH_GAP" and {"R0:left", "B1:left"} <= set(item.entity_refs) for item in connected.diagnostics)
    assert any(item.edge_id == override.edge_id for item in connected.edges)

    overlap = explicit_route_snapshot()
    overlap_target = next(item for item in overlap.route_placements if item.workpoint_id == "B1" and item.side == "left")
    overlap_target.start_mileage_m = 90
    graph = _graph(overlap)
    assert any(item.code == "MILEAGE_OVERLAP" and {"R0:left", "B1:left"} <= set(item.entity_refs) for item in graph.diagnostics)


def test_different_mileage_prefixes_on_same_side_are_not_compared_or_auto_connected() -> None:
    snapshot = explicit_route_snapshot()
    target = next(item for item in snapshot.route_placements if item.workpoint_id == "B1" and item.side == "left")
    target.mileage_prefix = "BK"
    target.start_mileage_m = 50
    target.end_mileage_m = 150

    graph = _graph(snapshot)

    assert not any(item.code == "MILEAGE_OVERLAP" and "B1:left" in item.entity_refs for item in graph.diagnostics)
    assert not any({item.from_node_id, item.to_node_id} == {"R0:left", "B1:left"} for item in graph.edges)


def test_duplicate_explicit_side_is_blocking_and_keeps_first_node_stable() -> None:
    snapshot = explicit_route_snapshot()
    snapshot.route_placements.append(
        ProjectMasterRoutePlacement.model_construct(
            placement_id="RP-B1-left-duplicate",
            workpoint_id="B1",
            side="left",
            mileage_prefix="ZK",
            start_mileage_m=100,
            end_mileage_m=200,
            spatial_group_id="SG-duplicate",
            display_order=1,
        )
    )

    graph = _graph(snapshot)

    assert any(item.code == "ROUTE_PLACEMENT_DUPLICATE" for item in graph.diagnostics)
    assert [item.node_id for item in graph.nodes].count("B1:left") == 1


def test_continuous_bridge_projects_three_segment_nodes_per_side_with_scoped_demands() -> None:
    graph = _graph(continuous_route_snapshot())
    nodes = {item.node_id: item for item in graph.nodes}

    assert graph.status == "ready"
    assert graph.projection_version == "girder-plan-line-graph/v3"
    for side, boundaries in (("left", (100, 120, 150, 200)), ("right", (100, 125, 160, 200))):
        small = nodes[f"B1:{side}:approach_small"]
        continuous = nodes[f"B1:{side}:continuous"]
        large = nodes[f"B1:{side}:approach_large"]
        assert [small.start_mileage_m, small.end_mileage_m, continuous.end_mileage_m, large.end_mileage_m] == list(boundaries)
        assert small.bridge_segment_kind == "approach_small"
        assert continuous.bridge_segment_kind == "continuous"
        assert large.bridge_segment_kind == "approach_large"
        assert small.requires_erection and large.requires_erection
        assert not continuous.requires_erection
        assert [(item.beam_type_id, item.beam_count) for item in small.beam_demands] == [("T32", 4)]
        assert [(item.beam_type_id, item.beam_count) for item in large.beam_demands] == [("T40", 6)]
        assert continuous.beam_demands == []
        assert continuous.current_plan_finish_date.isoformat() == "2026-08-01"
        assert resolve_path(graph, small.node_id, large.node_id).node_ids == [small.node_id, continuous.node_id, large.node_id]
    assert "B1:left" not in nodes and "B1:right" not in nodes
    assert nodes["B2:left"].bridge_segment_kind is None


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("missing_length", "BRIDGE_SEGMENT_STRUCTURE_DATA_MISSING"),
        ("ambiguous_blocks", "BRIDGE_SEGMENT_CONTINUOUS_BLOCK_AMBIGUOUS"),
        ("missing_approach", "BRIDGE_SEGMENT_APPROACH_MISSING"),
        ("length_mismatch", "BRIDGE_SEGMENT_LENGTH_MISMATCH"),
        ("precast_conflict", "BRIDGE_SEGMENT_PRECAST_CONFLICT"),
    ],
)
def test_continuous_bridge_segmentation_failures_are_object_level_blocking(case: str, expected_code: str) -> None:
    snapshot = continuous_route_snapshot()
    bridge = next(item for item in snapshot.workpoints if item.workpoint_id == "B1")
    right = sorted((item for item in bridge.structures if item.side == "right"), key=lambda item: item.sort_order)

    if case == "missing_length":
        right[1].parameters = [item for item in right[1].parameters if item.parameter_code != "span_length_m"]
    elif case == "ambiguous_blocks":
        for structure, index, length in zip(right, (1, 2, 3), (20, 20, 20)):
            _replace_parameter(structure, "span_index", index, "integer")
            _replace_parameter(structure, "span_length_m", length, "number")
        second_continuous = right[1].model_copy(deep=True)
        second_continuous.structure_id = "B1-right-S4-CONT"
        second_continuous.sort_order = 4
        _replace_parameter(second_continuous, "span_index", 4, "integer")
        final_simple = right[2].model_copy(deep=True)
        final_simple.structure_id = "B1-right-S5"
        final_simple.sort_order = 5
        _replace_parameter(final_simple, "span_index", 5, "integer")
        bridge.structures.extend([second_continuous, final_simple])
    elif case == "missing_approach":
        bridge.structures.remove(right[0])
    elif case == "length_mismatch":
        _replace_parameter(right[2], "span_length_m", 42, "number")
    elif case == "precast_conflict":
        right[1].components = [right[0].components[0].model_copy(deep=True)]

    graph = _graph(snapshot)
    diagnostic = next(item for item in graph.diagnostics if item.code == expected_code)
    assert graph.status == "blocking"
    assert diagnostic.object_id == "B1:right"
    assert diagnostic.entity_refs
    assert diagnostic.suggestion
    assert any(item.node_id == "B1:right" for item in graph.nodes)


def _replace_parameter(structure, code: str, value, value_type: str) -> None:
    structure.parameters = [item for item in structure.parameters if item.parameter_code != code]
    structure.parameters.append(ParameterValue(parameter_code=code, value_type=value_type, value=value))
