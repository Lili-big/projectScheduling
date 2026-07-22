from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app.main import app  # noqa: E402
from app.contracts import LocalScenarioConfigResponse, LocalScenarioConfigSaveRequest  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from capture_architecture_baseline import _route_manifest  # noqa: E402


FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "architecture" / "backend-baseline.json"


def test_all_api_routes_match_the_frozen_openapi_contract() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["api"]
    current = _route_manifest(app)

    # 042 freezes the original 45 operations; later feature routers may add
    # operations but must not mutate those compatibility contracts.
    current_by_operation = {(item["method"], item["path"]): item for item in current}
    expected_by_operation = {(item["method"], item["path"]): item for item in expected["routes"]}
    assert len(current) >= 45
    assert {key: current_by_operation[key] for key in expected_by_operation} == expected_by_operation


def test_compatibility_routes_remain_available() -> None:
    routes = {(item["method"], item["path"]) for item in _route_manifest(app)}
    assert {("GET", "/api/demo"), ("POST", "/api/generate-wbs"), ("POST", "/api/solve")} <= routes


def test_resource_scope_reuses_the_five_existing_api_contracts() -> None:
    routes = _route_manifest(app)
    by_operation = {(item["method"], item["path"]): item for item in routes}
    expected = {
        ("PUT", "/api/local-scenario-config"): (
            "#/components/schemas/LocalScenarioConfigSaveRequest",
            "#/components/schemas/LocalScenarioConfigResponse",
        ),
        ("POST", "/api/generate-schedule-input"): (
            "#/components/schemas/ScenarioInput-Input",
            "#/components/schemas/GeneratedScheduleInput-Output",
        ),
        ("POST", "/api/solve-scenario"): (
            "#/components/schemas/ScenarioInput-Input",
            "#/components/schemas/ScenarioSolveResult-Output",
        ),
        ("POST", "/api/solve-min-resources"): (
            "#/components/schemas/MinResourcesSolveRequest",
            "#/components/schemas/ScenarioSolveResult-Output",
        ),
        ("POST", "/api/solve-resource-cost"): (
            "#/components/schemas/ResourceCostSolveRequest",
            "#/components/schemas/ScenarioSolveResult-Output",
        ),
        ("POST", "/api/ai-resource-assistant/update-plan"): (
            "#/components/schemas/ResourceAssistantUpdatePlanRequest",
            "#/components/schemas/ResourceAssistantUpdatePlanResponse",
        ),
    }

    for operation, (request_ref, response_ref) in expected.items():
        assert operation in by_operation
        route = by_operation[operation]
        assert route["request_schema"] == {"$ref": request_ref}
        assert route["responses"]["200"]["json_schema"] == {"$ref": response_ref}
        assert route["responses"]["422"]["json_schema"] == {
            "$ref": "#/components/schemas/HTTPValidationError"
        }
        assert sum(1 for item in routes if (item["method"], item["path"]) == operation) == 1


def test_workpoint_first_resource_fields_are_additive_on_existing_api_schemas() -> None:
    schemas = app.openapi()["components"]["schemas"]
    resource_pool_properties = schemas["ResourcePool"]["properties"]
    assistant_result_properties = schemas["ResourceAssistantPlanResult-Output"]["properties"]
    validation_properties = schemas["ValidationMessage"]["properties"]

    assert "workpoint_id" in resource_pool_properties
    assert {"input_resource_quantities", "resource_pool_quantities"} <= assistant_result_properties.keys()
    assert "ResourcePoolQuantityResult" in schemas
    assert "details" in validation_properties


def test_ai_resource_assistant_requires_one_target_workpoint_per_new_session() -> None:
    schemas = app.openapi()["components"]["schemas"]
    initial_request = schemas["ResourceAssistantInitialRequest"]
    plan = schemas["ResourceAssistantPlan"]

    assert "target_workpoint_id" in initial_request["required"]
    assert initial_request["properties"]["target_workpoint_id"]["minLength"] == 1
    assert {"target_workpoint_id", "target_workpoint_name"} <= plan["properties"].keys()
    assert "target_workpoint_id" not in plan.get("required", [])
    assert "target_workpoint_name" not in plan.get("required", [])


def test_ai_workpoint_resource_initializer_adds_a_scenario_only_secret_free_contract() -> None:
    routes = _route_manifest(app)
    by_operation = {(item["method"], item["path"]): item for item in routes}
    route = by_operation[("POST", "/api/ai-resource-assistant/initialize-workpoint-resources")]
    assert route["request_schema"] == {
        "$ref": "#/components/schemas/AiWorkpointResourceInitializationRequest"
    }
    assert route["responses"]["200"]["json_schema"] == {
        "$ref": "#/components/schemas/AiWorkpointResourceInitializationResponse"
    }

    schemas = app.openapi()["components"]["schemas"]
    request_schema = schemas["AiWorkpointResourceInitializationRequest"]
    response_schema = schemas["AiWorkpointResourceInitializationResponse"]
    assert request_schema["required"] == ["scenario"]
    assert set(request_schema["properties"]) == {"scenario"}
    serialized = json.dumps({"request": request_schema, "response": response_schema}).lower()
    assert "api_key" not in serialized
    assert "authorization" not in serialized


def test_local_scenario_config_contract_accepts_and_returns_empty_resource_pools() -> None:
    scenario = default_scenario()
    request = LocalScenarioConfigSaveRequest(
        process_library=scenario.process_library,
        logic_rules=scenario.logic_rules,
        upper_structure_logic_rules=scenario.upper_structure_logic_rules,
        resource_pools=[],
        milestones=scenario.milestones,
    )
    response = LocalScenarioConfigResponse(
        process_library=request.process_library,
        logic_rules=request.logic_rules,
        upper_structure_logic_rules=request.upper_structure_logic_rules,
        resource_pools=[],
        milestones=request.milestones,
    )

    assert request.resource_pools == []
    assert response.resource_pools == []
