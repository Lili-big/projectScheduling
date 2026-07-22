from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from time import perf_counter

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
from app.girder_plan_simulation.simulator import simulate
from app.girder_plan_simulation.validation import prepare_scenario


FIXTURE = Path(__file__).parent / "fixtures" / "girder_plan_simulation" / "performance.json"


def test_performance_fixture_is_deterministic_and_under_ten_seconds(tmp_path) -> None:
    settings = json.loads(FIXTURE.read_text(encoding="utf-8"))
    graph, request = _performance_case(settings["generator"])
    scenario = GirderPlanRepository(tmp_path / "performance.json").create_scenario_version(request)
    fingerprints = []
    elapsed = []
    for _ in range(settings["runs"]):
        started = perf_counter()
        prepared = prepare_scenario(scenario, graph)
        assert prepared.readiness.status == "ready"
        run = simulate(scenario, graph, prepared=prepared)
        elapsed.append(perf_counter() - started)
        fingerprints.append(run.result_fingerprint)
        assert run.status == "calculated"
        assert len(run.bridge_schedules) == settings["generator"]["bridge_side_target_count"]
        assert len(run.workpoint_controls) >= settings["generator"]["bridge_side_target_count"]
    assert max(elapsed) < settings["max_elapsed_seconds_per_run"]
    assert len(set(fingerprints)) == 1


def _performance_case(settings):
    nodes = []
    edges = []
    yards = []
    lines = []
    routes = []
    nodes_per_alignment = settings["workpoint_count"] // settings["beam_yard_count"]
    targets_per_alignment = settings["bridge_side_target_count"] // settings["beam_yard_count"]
    for yard_index in range(settings["beam_yard_count"]):
        alignment = f"A{yard_index}"
        alignment_nodes = []
        for index in range(nodes_per_alignment):
            target = index < targets_per_alignment
            node_id = f"{alignment}-N{index}:left" if target else f"{alignment}-N{index}:unknown"
            node = LineGraphNode(
                node_id=node_id,
                project_master_workpoint_id=f"{alignment}-N{index}",
                name=node_id,
                node_type="bridge" if target else "roadbed",
                side="left" if target else "unknown",
                alignment_code=alignment,
                start_mileage_m=index * 100,
                end_mileage_m=(index + 1) * 100,
                spatial_group_id=f"{alignment}-SG-{index}",
                display_order=index,
                placement_source="explicit",
                requires_erection=target,
                beam_demands=[BeamDemand(
                    beam_type_id="T32",
                    beam_type_name="T32",
                    span_count=1,
                    beam_count=settings["pieces_per_target"],
                    span_refs=[f"{alignment}-SPAN-{index}"],
                )] if target else [],
            )
            nodes.append(node)
            alignment_nodes.append(node)
        for index in range(len(alignment_nodes) - 1):
            edges.append(
                LineGraphEdge(
                    edge_id=f"{alignment}-E{index}",
                    from_node_id=alignment_nodes[index].node_id,
                    to_node_id=alignment_nodes[index + 1].node_id,
                )
            )
        yard_id = f"Y{yard_index}"
        line_id = f"L{yard_index}"
        yards.append(
            BeamYardPlan(
                beam_yard_id=yard_id,
                name=yard_id,
                alignment_code=alignment,
                mileage_m=alignment_nodes[-1].start_mileage_m,
                production_start_date=date(2026, 1, 1),
                capacities=[BeamTypeCapacity(beam_type_id="T32", daily_capacity_pieces=4, initial_inventory_pieces=4)],
            )
        )
        lines.append(
            ErectionLinePlan(
                erection_line_id=line_id,
                beam_yard_id=yard_id,
                available_date=date(2026, 1, 1),
                daily_erection_capacity_pieces=4,
                bridge_transfer_days=1,
            )
        )
        routes.append(
            ManualRoutePlan(
                route_plan_id=f"R{yard_index}",
                beam_yard_id=yard_id,
                erection_line_id=line_id,
                name=f"R{yard_index}",
                target_node_ids=[item.node_id for item in reversed(alignment_nodes[:targets_per_alignment])],
                confirmed=True,
            )
        )
    graph = LineGraphSnapshot(
        line_graph_id="LG-PERFORMANCE",
        project_id="PERF",
        project_master_version_id="PMV-PERF",
        input_fingerprint="sha256:performance",
        status="ready",
        nodes=nodes,
        edges=edges,
    )
    request = CreateScenarioVersionRequest(
        project_id="PERF",
        project_master_version_id="PMV-PERF",
        line_graph_id=graph.line_graph_id,
        beam_yards=yards,
        erection_lines=lines,
        route_plans=routes,
        parameters=GirderPlanSimulationParameters(planning_horizon_end_date=date(2027, 12, 31)),
        created_by="performance-test",
    )
    return graph, request
