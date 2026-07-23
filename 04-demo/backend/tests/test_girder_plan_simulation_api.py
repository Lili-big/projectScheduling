from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routers.girder_plan_simulation import (
    confirm_run_endpoint,
    create_run_endpoint,
    create_scenario_endpoint,
    get_line_graph_endpoint,
    get_run_endpoint,
    validate_scenario_endpoint,
)
from app.contracts.girder_plan_simulation import (
    ConfirmSimulationRunRequest,
    CreateSimulationRunRequest,
    ExpectedFingerprintRequest,
)
from girder_plan_simulation_fixture_helpers import continuous_route_snapshot, scenario_request, service


def _request(tmp_path, snapshot=None):
    state = SimpleNamespace(girder_plan_simulation_service=service(tmp_path, snapshot))
    return SimpleNamespace(app=SimpleNamespace(state=state))


def test_full_api_journey_keeps_independent_state(tmp_path) -> None:
    request = _request(tmp_path)
    graph = get_line_graph_endpoint("PMV1", request)
    assert graph.projection_version == "girder-plan-line-graph/v3"
    assert {item.side for item in graph.nodes} == {"left", "right"}
    scenario_payload = scenario_request(graph)
    scenario = create_scenario_endpoint(scenario_payload, request)

    readiness = validate_scenario_endpoint(
        scenario.scenario_version_id,
        ExpectedFingerprintRequest(expected_input_fingerprint=scenario.input_fingerprint),
        request,
    )
    assert readiness.status == "ready"

    run = create_run_endpoint(
        CreateSimulationRunRequest(
            scenario_version_id=scenario.scenario_version_id,
            expected_input_fingerprint=scenario.input_fingerprint,
        ),
        request,
    )
    assert run.status == "calculated"
    assert run.bridge_schedules[0].target_node_id == "B1:left"
    assert run.workpoint_controls
    assert get_run_endpoint(run.run_id, request).result_fingerprint == run.result_fingerprint

    reuse = create_run_endpoint(
        CreateSimulationRunRequest(
            scenario_version_id=scenario.scenario_version_id,
            expected_input_fingerprint=scenario.input_fingerprint,
        ),
        request,
    )
    assert reuse.reused_from_run_id == run.run_id

    confirmed = confirm_run_endpoint(
        run.run_id,
        ConfirmSimulationRunRequest(
            expected_input_fingerprint=scenario.input_fingerprint,
            confirmed_by="项目总工",
            confirmation_reason="固定顺序方案复核通过",
        ),
        request,
    )
    assert confirmed.status == "confirmed"
    assert list(tmp_path.rglob("*")) == [tmp_path / "girder-plan.json"]


def test_api_rejects_missing_or_stale_inputs(tmp_path) -> None:
    request = _request(tmp_path)
    with pytest.raises(HTTPException) as missing:
        get_line_graph_endpoint("UNKNOWN", request)
    assert missing.value.status_code == 404

    graph = get_line_graph_endpoint("PMV1", request)
    scenario = create_scenario_endpoint(scenario_request(graph), request)
    with pytest.raises(HTTPException) as stale:
        validate_scenario_endpoint(
            scenario.scenario_version_id,
            ExpectedFingerprintRequest(expected_input_fingerprint="sha256:stale"),
            request,
        )
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "SCENARIO_INPUT_FINGERPRINT_STALE"


def test_legacy_line_projection_is_marked_stale_without_deleting_history(tmp_path) -> None:
    simulation_service = service(tmp_path)
    graph = simulation_service.get_line_graph("PMV1")
    payload = scenario_request(graph)
    payload.line_graph_id = "lgs-legacy-v1"
    legacy = simulation_service.repository.create_scenario_version(payload)

    refreshed = simulation_service.get_scenario(legacy.scenario_version_id)
    assert refreshed.status == "stale"
    assert "双幅线路图" in (refreshed.stale_reason or "")
    assert simulation_service.repository.get_scenario_version(legacy.scenario_version_id).status == "stale"


def test_api_returns_object_level_diagnostics_for_blocked_plan(tmp_path) -> None:
    request = _request(tmp_path)
    graph = get_line_graph_endpoint("PMV1", request)
    payload = scenario_request(graph)
    payload.route_plans[1].target_node_ids = []
    scenario = create_scenario_endpoint(payload, request)
    readiness = validate_scenario_endpoint(
        scenario.scenario_version_id,
        ExpectedFingerprintRequest(expected_input_fingerprint=scenario.input_fingerprint),
        request,
    )
    assert readiness.status == "blocking"
    diagnostic = next(item for item in readiness.diagnostics if item.code == "TARGET_UNASSIGNED")
    assert diagnostic.object_type == "bridge_side"
    assert diagnostic.object_id
    assert diagnostic.suggestion


def test_stale_run_and_blank_confirmation_are_not_confirmable(tmp_path) -> None:
    request = _request(tmp_path)
    graph = get_line_graph_endpoint("PMV1", request)
    scenario = create_scenario_endpoint(scenario_request(graph), request)
    run = create_run_endpoint(
        CreateSimulationRunRequest(
            scenario_version_id=scenario.scenario_version_id,
            expected_input_fingerprint=scenario.input_fingerprint,
        ),
        request,
    )
    request.app.state.girder_plan_simulation_service.repository.set_scenario_status(
        scenario.scenario_version_id,
        "stale",
        stale_reason="测试输入已变化。",
    )
    with pytest.raises(HTTPException) as stale:
        confirm_run_endpoint(
            run.run_id,
            ConfirmSimulationRunRequest(
                expected_input_fingerprint=scenario.input_fingerprint,
                confirmed_by="项目总工",
                confirmation_reason="待确认",
            ),
            request,
        )
    assert stale.value.status_code == 409
    assert stale.value.detail["code"] == "SCENARIO_STALE"

    with pytest.raises(ValidationError):
        ConfirmSimulationRunRequest(
            expected_input_fingerprint=scenario.input_fingerprint,
            confirmed_by="   ",
            confirmation_reason="   ",
        )


def test_v3_segmented_graph_does_not_reuse_legacy_whole_bridge_target(tmp_path) -> None:
    request = _request(tmp_path, continuous_route_snapshot())
    graph = get_line_graph_endpoint("PMV1", request)
    assert graph.projection_version == "girder-plan-line-graph/v3"
    assert any(item.bridge_segment_kind == "continuous" for item in graph.nodes)

    scenario = create_scenario_endpoint(scenario_request(graph), request)
    readiness = validate_scenario_endpoint(
        scenario.scenario_version_id,
        ExpectedFingerprintRequest(expected_input_fingerprint=scenario.input_fingerprint),
        request,
    )

    assert readiness.status == "blocking"
    assert any(item.code == "ROUTE_TARGET_INVALID" and item.object_id == "B1:left" for item in readiness.diagnostics)


def test_length_difference_keeps_segmented_api_journey_ready_and_graph_changes_stale(tmp_path) -> None:
    snapshot = continuous_route_snapshot()
    bridge = next(item for item in snapshot.workpoints if item.workpoint_id == "B1")
    right_large = max((item for item in bridge.structures if item.side == "right"), key=lambda item: item.sort_order)
    next(item for item in right_large.parameters if item.parameter_code == "span_length_m").value = 42
    request = _request(tmp_path, snapshot)

    graph = get_line_graph_endpoint("PMV1", request)

    assert graph.status == "ready"
    assert not any(item.code == "BRIDGE_SEGMENT_LENGTH_MISMATCH" for item in graph.diagnostics)
    assert sum(item.bridge_segment_kind is not None for item in graph.nodes) == 6

    payload = scenario_request(graph)
    payload.route_plans[0].target_node_ids = [
        "B1:left:approach_small",
        "B1:left:approach_large",
        "B2:left",
    ]
    payload.route_plans[1].target_node_ids = [
        "B1:right:approach_small",
        "B1:right:approach_large",
        "B2:right",
    ]
    scenario = create_scenario_endpoint(payload, request)
    readiness = validate_scenario_endpoint(
        scenario.scenario_version_id,
        ExpectedFingerprintRequest(expected_input_fingerprint=scenario.input_fingerprint),
        request,
    )

    assert readiness.status == "ready"
    run = create_run_endpoint(
        CreateSimulationRunRequest(
            scenario_version_id=scenario.scenario_version_id,
            expected_input_fingerprint=scenario.input_fingerprint,
        ),
        request,
    )
    assert run.status == "calculated"
    assert any(item.target_node_id == "B1:left:approach_small" for item in run.bridge_schedules)

    simulation_service = request.app.state.girder_plan_simulation_service
    changed = next(
        item
        for item in simulation_service.project_master_service.repository.snapshot.route_placements
        if item.workpoint_id == "B1" and item.side == "left"
    )
    changed.spatial_group_id = "SG-UPDATED"
    refreshed = simulation_service.get_scenario(scenario.scenario_version_id)
    assert refreshed.status == "stale"
    assert "线路图" in (refreshed.stale_reason or "")
