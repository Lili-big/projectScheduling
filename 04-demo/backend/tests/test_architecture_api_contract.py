from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app.main import app  # noqa: E402
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
