from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.girder_plan_simulation import (
    BeamDemand,
    BeamTypeCapacity,
    BeamYardPlan,
    CreateScenarioVersionRequest,
    ErectionLinePlan,
    GirderPlanSimulationParameters,
    LineGraphEdge,
    LineGraphNode,
    LineGraphSnapshot,
    ManualRoutePlan,
)
from app.girder_plan_simulation.repository import GirderPlanRepository
from app.girder_plan_simulation.validation import _resolve_yard_node, prepare_scenario
from girder_plan_simulation_fixture_helpers import continuous_route_snapshot, line_graph, scenario_request
from app.girder_plan_simulation.topology import build_line_graph


def test_ready_scenario_expands_intermediate_nodes_without_reordering(tmp_path) -> None:
    graph = line_graph()
    scenario = GirderPlanRepository(tmp_path / "state.json").create_scenario_version(scenario_request(graph))
    prepared = prepare_scenario(scenario, graph)
    assert prepared.readiness.status == "ready"
    assert prepared.readiness.expanded_routes["ROUTE-L"] == [
        "R0:left",
        "B1:left",
        "T1:left",
        "B2:left",
    ]


def test_segmented_bridge_route_targets_expand_continuous_structure_between_approaches(tmp_path) -> None:
    graph = build_line_graph(
        project_id="P1",
        project_master_version_id="PMV1",
        snapshot=continuous_route_snapshot(),
    )
    request = scenario_request(graph)
    request.route_plans[0].target_node_ids = [
        "B1:left:approach_small",
        "B1:left:approach_large",
        "B2:left",
    ]
    request.route_plans[1].target_node_ids = [
        "B1:right:approach_small",
        "B1:right:approach_large",
        "B2:right",
    ]
    scenario = GirderPlanRepository(tmp_path / "segmented.json").create_scenario_version(request)

    prepared = prepare_scenario(scenario, graph)

    assert prepared.readiness.status == "ready"
    assert prepared.readiness.expanded_routes["ROUTE-L"][:4] == [
        "R0:left",
        "B1:left:approach_small",
        "B1:left:continuous",
        "B1:left:approach_large",
    ]


def test_duplicate_and_unassigned_targets_block_calculation(tmp_path) -> None:
    graph = line_graph()
    request = scenario_request(graph)
    request.route_plans[1].target_node_ids = ["B1:left"]
    scenario = GirderPlanRepository(tmp_path / "state.json").create_scenario_version(request)
    readiness = prepare_scenario(scenario, graph).readiness
    codes = {item.code for item in readiness.diagnostics}
    assert readiness.status == "blocking"
    assert {"TARGET_DUPLICATE_ASSIGNMENT", "TARGET_UNASSIGNED"} <= codes


def test_zero_erection_capacity_and_missing_beam_supply_are_blocking(tmp_path) -> None:
    graph = line_graph()
    request = scenario_request(graph)
    request.erection_lines[0].daily_erection_capacity_pieces = 0
    request.beam_yards[0].capacities = []
    scenario = GirderPlanRepository(tmp_path / "state.json").create_scenario_version(request)
    codes = {item.code for item in prepare_scenario(scenario, graph).readiness.diagnostics}
    assert "ERECTION_CAPACITY_NON_POSITIVE" in codes
    assert "BEAM_TYPE_SUPPLY_MISSING" in codes


def test_each_enabled_yard_requires_exactly_one_line_route_and_unique_beam_types(tmp_path) -> None:
    graph = line_graph()
    request = scenario_request(graph)
    request.erection_lines = request.erection_lines[:1]
    request.route_plans.append(request.route_plans[0].model_copy(update={"route_plan_id": "ROUTE-L-2"}))
    request.beam_yards[0].capacities.append(request.beam_yards[0].capacities[0].model_copy())
    scenario = GirderPlanRepository(tmp_path / "cardinality.json").create_scenario_version(request)
    codes = {item.code for item in prepare_scenario(scenario, graph).readiness.diagnostics}
    assert {"YARD_LINE_COUNT_INVALID", "YARD_ROUTE_COUNT_INVALID", "BEAM_TYPE_CAPACITY_DUPLICATED"} <= codes


def test_yard_deployment_prefers_stable_node_and_legacy_location_must_be_unique() -> None:
    graph = line_graph()
    nodes = {item.node_id: item for item in graph.nodes}
    exact = scenario_request(graph).beam_yards[0]
    assert _resolve_yard_node(exact, nodes) == ("R0:left", "exact")

    legacy = exact.model_copy(update={"deployment_node_id": None, "alignment_code": "ZK", "mileage_m": 0})
    nodes["R0:right"].alignment_code = "ZK"
    assert _resolve_yard_node(legacy, nodes) == (None, "ambiguous")
    left_only = {node_id: node for node_id, node in nodes.items() if node.side == "left"}
    assert _resolve_yard_node(legacy, left_only) == ("R0:left", "legacy_unique")


def test_ambiguous_legacy_yard_deployment_returns_object_level_blocking_diagnostic(tmp_path) -> None:
    graph = line_graph()
    next(item for item in graph.nodes if item.node_id == "R0:right").alignment_code = "ZK"
    request = scenario_request(graph)
    request.beam_yards[0].deployment_node_id = None
    request.beam_yards[0].alignment_code = "ZK"
    scenario = GirderPlanRepository(tmp_path / "ambiguous-yard.json").create_scenario_version(request)

    readiness = prepare_scenario(scenario, graph).readiness
    diagnostic = next(item for item in readiness.diagnostics if item.code == "YARD_DEPLOYMENT_AMBIGUOUS")
    assert readiness.status == "blocking"
    assert diagnostic.object_id == "Y-L"
    assert diagnostic.severity == "blocking"
    assert diagnostic.suggestion


def test_cross_route_dependency_cycle_returns_explicit_chain(tmp_path) -> None:
    target_a = LineGraphNode(
        node_id="A:left", project_master_workpoint_id="A", name="A桥左幅", node_type="bridge", side="left",
        alignment_code="A", start_mileage_m=10, end_mileage_m=20, spatial_group_id="SG-A", display_order=1,
        placement_source="explicit", requires_erection=True,
        beam_demands=[BeamDemand(beam_type_id="T", beam_type_name="T", span_count=1, beam_count=1, span_refs=["A-SPAN-1"])],
    )
    target_b = LineGraphNode(
        node_id="B:left", project_master_workpoint_id="B", name="B桥左幅", node_type="bridge", side="left",
        alignment_code="B", start_mileage_m=10, end_mileage_m=20, spatial_group_id="SG-B", display_order=1,
        placement_source="explicit", requires_erection=True,
        beam_demands=[BeamDemand(beam_type_id="T", beam_type_name="T", span_count=1, beam_count=1, span_refs=["B-SPAN-1"])],
    )
    graph = LineGraphSnapshot(
        line_graph_id="LG-CYCLE", project_id="P1", project_master_version_id="PMV1", input_fingerprint="sha256:cycle",
        status="ready",
        nodes=[
            LineGraphNode(node_id="DA:unknown", name="A梁场", node_type="roadbed", alignment_code="A", start_mileage_m=0, end_mileage_m=1, spatial_group_id="SG-DA", display_order=0, placement_source="explicit"),
            LineGraphNode(node_id="DB:unknown", name="B梁场", node_type="roadbed", alignment_code="B", start_mileage_m=0, end_mileage_m=1, spatial_group_id="SG-DB", display_order=0, placement_source="explicit"),
            target_a, target_b,
        ],
        edges=[
            LineGraphEdge(edge_id="E1", from_node_id="DA:unknown", to_node_id="B:left"),
            LineGraphEdge(edge_id="E2", from_node_id="B:left", to_node_id="A:left"),
            LineGraphEdge(edge_id="E3", from_node_id="DB:unknown", to_node_id="A:left"),
        ],
    )
    request = CreateScenarioVersionRequest(
        project_id="P1", project_master_version_id="PMV1", line_graph_id=graph.line_graph_id,
        beam_yards=[
            BeamYardPlan(beam_yard_id="YA", name="YA", deployment_node_id="DA:unknown", alignment_code="A", mileage_m=0, production_start_date=date(2026, 1, 1), capacities=[BeamTypeCapacity(beam_type_id="T", daily_capacity_pieces=1, initial_inventory_pieces=1)]),
            BeamYardPlan(beam_yard_id="YB", name="YB", deployment_node_id="DB:unknown", alignment_code="B", mileage_m=0, production_start_date=date(2026, 1, 1), capacities=[BeamTypeCapacity(beam_type_id="T", daily_capacity_pieces=1, initial_inventory_pieces=1)]),
        ],
        erection_lines=[
            ErectionLinePlan(erection_line_id="LA", beam_yard_id="YA", available_date=date(2026, 1, 1), daily_erection_capacity_pieces=1),
            ErectionLinePlan(erection_line_id="LB", beam_yard_id="YB", available_date=date(2026, 1, 1), daily_erection_capacity_pieces=1),
        ],
        route_plans=[
            ManualRoutePlan(route_plan_id="RA", beam_yard_id="YA", erection_line_id="LA", name="RA", target_node_ids=["A:left"], confirmed=True),
            ManualRoutePlan(route_plan_id="RB", beam_yard_id="YB", erection_line_id="LB", name="RB", target_node_ids=["B:left"], confirmed=True),
        ],
        parameters=GirderPlanSimulationParameters(planning_horizon_end_date=date(2026, 2, 1)), created_by="tester",
    )
    scenario = GirderPlanRepository(tmp_path / "cycle.json").create_scenario_version(request)
    diagnostics = prepare_scenario(scenario, graph).readiness.diagnostics
    cycle = next(item for item in diagnostics if item.code == "CROSS_ROUTE_DEPENDENCY_CYCLE")
    assert cycle.severity == "blocking"
    assert cycle.entity_refs[0] == cycle.entity_refs[-1]
