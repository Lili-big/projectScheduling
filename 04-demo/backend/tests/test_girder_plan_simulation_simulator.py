from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.girder_plan_simulation.repository import GirderPlanRepository
from app.girder_plan_simulation.simulator import simulate
from app.girder_plan_simulation.validation import prepare_scenario
from girder_plan_simulation_fixture_helpers import line_graph, scenario_request


def _run(tmp_path):
    graph = line_graph()
    scenario = GirderPlanRepository(tmp_path / "state.json").create_scenario_version(scenario_request(graph))
    prepared = prepare_scenario(scenario, graph)
    return simulate(scenario, graph, prepared=prepared)


def test_daily_simulation_preserves_inventory_and_manual_order(tmp_path) -> None:
    run = _run(tmp_path)
    assert run.status == "calculated"
    by_route = {}
    for item in run.bridge_schedules:
        by_route.setdefault(item.route_plan_id, []).append(item)
    assert [item.target_node_id for item in by_route["ROUTE-L"]] == ["B1:left", "B2:left"]
    assert [item.target_node_id for item in by_route["ROUTE-R"]] == ["B1:right", "B2:right"]
    assert by_route["ROUTE-L"][0].start_date == date(2026, 8, 1)
    assert by_route["ROUTE-R"][0].start_date == date(2026, 8, 1)
    for point in run.inventory_ledger:
        assert point.closing_inventory_pieces == (
            point.opening_inventory_pieces + point.produced_pieces - point.erected_pieces
        )
        assert point.closing_inventory_pieces >= 0


def test_production_on_day_d_is_only_available_on_next_day(tmp_path) -> None:
    run = _run(tmp_path)
    schedule = next(item for item in run.bridge_schedules if item.target_node_id == "B2:left")
    assert schedule.start_date == date(2026, 8, 2)
    t40_day_one = next(
        item
        for item in run.inventory_ledger
        if item.beam_yard_id == "Y-L" and item.beam_type_id == "T40" and item.date == date(2026, 8, 1)
    )
    assert (t40_day_one.opening_inventory_pieces, t40_day_one.produced_pieces, t40_day_one.erected_pieces) == (0, 4, 0)


def test_delivery_control_uses_earliest_shared_route_and_reports_unknown_plan_risk(tmp_path) -> None:
    run = _run(tmp_path)
    controls = {item.node_id: item for item in run.workpoint_controls if item.node_id.startswith("T1:")}
    assert set(controls) == {"T1:left", "T1:right"}
    for side, route_id in (("left", "ROUTE-L"), ("right", "ROUTE-R")):
        tunnel = controls[f"T1:{side}"]
        assert tunnel.first_required_date == date(2026, 8, 2)
        assert tunnel.latest_delivery_date == date(2026, 7, 31)
        assert {item.route_plan_id for item in tunnel.route_requirements} == {route_id}
        assert tunnel.risk_status == "unknown"
        assert tunnel.late_days is None


def test_reducing_erection_capacity_changes_dates_deterministically(tmp_path) -> None:
    graph = line_graph()
    request = scenario_request(graph)
    for line in request.erection_lines:
        line.daily_erection_capacity_pieces = 2
    scenario = GirderPlanRepository(tmp_path / "state.json").create_scenario_version(request)
    first = simulate(scenario, graph)
    second = simulate(scenario, graph)
    assert first.result_fingerprint == second.result_fingerprint
    bridge = next(item for item in first.bridge_schedules if item.target_node_id == "B1:left")
    assert bridge.start_date == date(2026, 8, 1)
    assert bridge.finish_date == date(2026, 8, 2)


def test_confirmed_connection_transfer_days_delay_first_erection(tmp_path) -> None:
    graph = line_graph()
    edge = next(item for item in graph.edges if {item.from_node_id, item.to_node_id} == {"R0:left", "B1:left"})
    edge.transfer_days = 2
    scenario = GirderPlanRepository(tmp_path / "transfer.json").create_scenario_version(scenario_request(graph))
    run = simulate(scenario, graph)
    left = next(item for item in run.bridge_schedules if item.target_node_id == "B1:left")
    right = next(item for item in run.bridge_schedules if item.target_node_id == "B1:right")
    assert left.start_date == date(2026, 8, 3)
    assert right.start_date == date(2026, 8, 1)
