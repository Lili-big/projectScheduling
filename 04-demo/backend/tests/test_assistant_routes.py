from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routers import assistants  # noqa: E402
from app.models import (  # noqa: E402
    AiWorkpointResourceInitializationRequest,
    ResourceAssistantInitialRequest,
    ResourceAssistantResultsRequest,
    ResourceAssistantUpdatePlanRequest,
)
from app.services.process_library_service import default_scenario_with_process_library  # noqa: E402


def test_resource_assistant_value_error_maps_to_422(monkeypatch) -> None:
    monkeypatch.setattr(assistants, "compare_resource_plan_results", lambda _request: (_ for _ in ()).throw(ValueError("缺少结果")))
    with pytest.raises(HTTPException) as exc_info:
        assistants.compare_resource_plan_results_endpoint(ResourceAssistantResultsRequest(resource_plans=[], plan_results=[]))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "缺少结果"


def test_resource_assistant_illegal_update_maps_to_422(monkeypatch) -> None:
    monkeypatch.setattr(
        assistants,
        "update_resource_plan",
        lambda _request: (_ for _ in ()).throw(ValueError("未知资源类型")),
    )
    with pytest.raises(HTTPException) as exc_info:
        assistants.update_resource_plan_endpoint(ResourceAssistantUpdatePlanRequest(plan_id="plan-1"))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "未知资源类型"


def test_resource_assistant_initialization_materializes_the_current_project_master_version(monkeypatch) -> None:
    scenario = default_scenario_with_process_library()
    materialized = scenario.model_copy(update={"scenario_name": "project-master-projection"})
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        assistants,
        "_materialize_project_master",
        lambda incoming, _http_request: (materialized, []),
    )

    def capture(payload):
        captured["scenario"] = payload.scenario
        return "initialized"

    monkeypatch.setattr(assistants, "initialize_resource_assistant", capture)
    result = assistants.initialize_resource_assistant_endpoint(
        ResourceAssistantInitialRequest(scenario=scenario, target_workpoint_id="B1"),
        object(),
    )

    assert result == "initialized"
    assert captured["scenario"] is materialized


def test_ai_workpoint_resource_initialization_materializes_before_calling_service(monkeypatch) -> None:
    scenario = default_scenario_with_process_library().model_copy(update={"project_data_version_id": "pm-v1"})
    materialized = scenario.model_copy(update={"scenario_name": "materialized-project-master"})
    captured: dict[str, object] = {}
    monkeypatch.setattr(assistants, "_materialize_project_master", lambda incoming, _request: (materialized, []))

    def capture(incoming):
        captured["scenario"] = incoming
        return "initialized-workpoints"

    monkeypatch.setattr(assistants, "initialize_workpoint_resources", capture)
    result = assistants.initialize_workpoint_resources_endpoint(
        AiWorkpointResourceInitializationRequest(scenario=scenario),
        object(),
    )

    assert result == "initialized-workpoints"
    assert captured["scenario"] is materialized


def test_ai_workpoint_resource_initialization_maps_validation_and_llm_failures(monkeypatch) -> None:
    scenario = default_scenario_with_process_library().model_copy(update={"project_data_version_id": "pm-v1"})
    payload = AiWorkpointResourceInitializationRequest(scenario=scenario)
    monkeypatch.setattr(assistants, "_materialize_project_master", lambda incoming, _request: (incoming, []))
    monkeypatch.setattr(
        assistants,
        "initialize_workpoint_resources",
        lambda _scenario: (_ for _ in ()).throw(ValueError("invalid model batch")),
    )
    with pytest.raises(HTTPException) as validation_error:
        assistants.initialize_workpoint_resources_endpoint(payload, object())
    assert validation_error.value.status_code == 422

    monkeypatch.setattr(
        assistants,
        "initialize_workpoint_resources",
        lambda _scenario: (_ for _ in ()).throw(assistants.AiResourceAssistantLlmError("model unavailable")),
    )
    with pytest.raises(HTTPException) as llm_error:
        assistants.initialize_workpoint_resources_endpoint(payload, object())
    assert llm_error.value.status_code == 503
    assert llm_error.value.detail == "model unavailable"


def test_ai_workpoint_resource_initialization_preserves_project_master_http_errors(monkeypatch) -> None:
    scenario = default_scenario_with_process_library().model_copy(update={"project_data_version_id": "missing"})
    project_master_error = HTTPException(status_code=409, detail={"code": "PROJECT_MASTER_VERSION_NOT_FOUND"})
    monkeypatch.setattr(
        assistants,
        "_materialize_project_master",
        lambda _scenario, _request: (_ for _ in ()).throw(project_master_error),
    )
    with pytest.raises(HTTPException) as exc_info:
        assistants.initialize_workpoint_resources_endpoint(
            AiWorkpointResourceInitializationRequest(scenario=scenario),
            object(),
        )
    assert exc_info.value is project_master_error


def test_assistant_routes_keep_expected_status_contracts() -> None:
    paths = assistants.router.routes
    operations = {(next(iter(route.methods)), route.path) for route in paths}
    assert ("POST", "/api/ai-parameter-assistant/parse") in operations
    assert ("POST", "/api/ai-parameter-assistant/apply") in operations
    assert len([path for method, path in operations if path.startswith("/api/ai-resource-assistant/")]) == 7
