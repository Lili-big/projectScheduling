from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import app.models as legacy  # noqa: E402
from app.contracts import assistants  # noqa: E402


def test_assistant_contracts_keep_identity_and_status_schema() -> None:
    assert assistants.AiParameterApplyRequest is legacy.AiParameterApplyRequest
    assert assistants.ResourceAssistantPlanResult is legacy.ResourceAssistantPlanResult
    schema = assistants.ResourceAssistantPlanResult.model_json_schema()
    assert "plan_status" in schema["properties"]
    assert "optimization_stages" in schema["properties"]


def test_resource_assistant_workpoint_scope_contract_is_required_for_new_requests_and_optional_for_history() -> None:
    request_schema = assistants.ResourceAssistantInitialRequest.model_json_schema()
    plan_schema = assistants.ResourceAssistantPlan.model_json_schema()

    assert "target_workpoint_id" in request_schema["required"]
    assert {"target_workpoint_id", "target_workpoint_name"} <= plan_schema["properties"].keys()
    assert "target_workpoint_id" not in plan_schema.get("required", [])


def test_resource_assistant_update_plan_keeps_legacy_and_scoped_updates() -> None:
    legacy_request = assistants.ResourceAssistantUpdatePlanRequest(
        plan_id="plan-legacy",
        resource_updates={"rotary_drill": 3},
    )
    scoped_request = assistants.ResourceAssistantUpdatePlanRequest(
        plan_id="plan-scoped",
        scoped_resource_updates=[
            {
                "resource_pool_id": "pool-drill",
                "workpoint_id": "WP-A",
                "quantity": 2,
            }
        ],
    )

    assert legacy_request.resource_updates == {"rotary_drill": 3}
    assert legacy_request.scoped_resource_updates == []
    assert scoped_request.scoped_resource_updates[0].workpoint_id == "WP-A"
    assert scoped_request.scoped_resource_updates[0].quantity == 2
    assert assistants.ScopedResourceQuantityUpdate is legacy.ScopedResourceQuantityUpdate

    schema = assistants.ResourceAssistantUpdatePlanRequest.model_json_schema()
    assert {"resource_updates", "scoped_resource_updates"} <= schema["properties"].keys()
    scoped_schema = assistants.ScopedResourceQuantityUpdate.model_json_schema()
    assert set(scoped_schema["properties"]) == {"resource_pool_id", "workpoint_id", "quantity"}
    assert {"scope_mode", "authorized_workpoint_ids", "workpoint_overrides"}.isdisjoint(
        scoped_schema["properties"]
    )
    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        assistants.ScopedResourceQuantityUpdate.model_validate(
            {
                "resource_pool_id": "pool-drill",
                "workpoint_id": "WP-A",
                "quantity": 2,
                "scope_mode": "PROJECT_SHARED",
            }
        )


def test_resource_assistant_plan_result_adds_pool_scoped_quantities_without_removing_legacy_map() -> None:
    pool_result = assistants.ResourcePoolQuantityResult(
        resource_pool_id="pool-shared-one",
        resource_type="rotary_drill",
        scope_mode="PROJECT_SHARED",
        current_quantity=2,
        recommended_quantity=3,
        max_quantity=4,
        eligible_workpoint_ids=["WP-B", "WP-A", "WP-B"],
    )
    local_result = assistants.ResourcePoolQuantityResult(
        resource_pool_id="pool-local-a",
        resource_type="rotary_drill",
        scope_mode="WORKPOINT_EXCLUSIVE",
        workpoint_id="WP-A",
        current_quantity=0,
        recommended_quantity=1,
        max_quantity=2,
        eligible_workpoint_ids=["WP-A"],
    )

    assert pool_result.eligible_workpoint_ids == ["WP-A", "WP-B"]
    assert local_result.workpoint_id == "WP-A"
    schema = assistants.ResourceAssistantPlanResult.model_json_schema()
    assert {"input_resource_quantities", "resource_pool_quantities"} <= schema["properties"].keys()
    assert assistants.ResourcePoolQuantityResult is legacy.ResourcePoolQuantityResult


def test_ai_workpoint_resource_initialization_contract_is_scenario_only_and_exports_summary() -> None:
    request_schema = assistants.AiWorkpointResourceInitializationRequest.model_json_schema()
    response_schema = assistants.AiWorkpointResourceInitializationResponse.model_json_schema()

    assert request_schema["required"] == ["scenario"]
    assert set(request_schema["properties"]) == {"scenario"}
    assert {
        "project_data_version_id",
        "input_fingerprint",
        "resource_pools_to_add",
        "summary",
        "llm_config_status",
        "diagnostics",
    } == set(response_schema["properties"])
    assert assistants.AiWorkpointResourceInitializationRequest is legacy.AiWorkpointResourceInitializationRequest
    assert assistants.AiWorkpointResourceInitializationResponse is legacy.AiWorkpointResourceInitializationResponse


def test_ai_workpoint_resource_recommendation_requires_positive_consistent_quantities() -> None:
    recommendation = assistants.AiWorkpointResourceRecommendation.model_validate(
        {
            "workpoint_id": "WP-A",
            "resources": [
                {
                    "resource_type": "rotary_drill",
                    "quantity": 2,
                    "max_quantity": 3,
                    "reason": "two active pile fronts",
                }
            ],
        }
    )

    assert recommendation.resources[0].quantity == 2
    with pytest.raises(ValueError):
        assistants.AiResourceQuantityRecommendation.model_validate(
            {"resource_type": "rotary_drill", "quantity": 0, "max_quantity": 1, "reason": ""}
        )
    with pytest.raises(ValueError, match="max_quantity"):
        assistants.AiResourceQuantityRecommendation.model_validate(
            {"resource_type": "rotary_drill", "quantity": 2, "max_quantity": 1, "reason": ""}
        )
    with pytest.raises(ValueError, match="duplicate resource_type"):
        assistants.AiWorkpointResourceRecommendation.model_validate(
            {
                "workpoint_id": "WP-A",
                "resources": [
                    {"resource_type": "rotary_drill", "quantity": 1, "max_quantity": 1, "reason": ""},
                    {"resource_type": "rotary_drill", "quantity": 1, "max_quantity": 1, "reason": ""},
                ],
            }
        )


def test_ai_workpoint_resource_initialization_openapi_keeps_secret_fields_out() -> None:
    contract = (
        BACKEND_ROOT.parents[1]
        / "03-requirements/specs/059-ai-batch-resource-initialization/contracts/ai-workpoint-resource-initialization.openapi.yaml"
    ).read_text(encoding="utf-8")

    assert "/api/ai-resource-assistant/initialize-workpoint-resources:" in contract
    request_section = contract.split("AiWorkpointResourceInitializationRequest:", 1)[1].split(
        "AiWorkpointResourceInitializationResponse:", 1
    )[0]
    assert "required: [scenario]" in request_section
    assert "api_key" not in request_section.lower()
    assert "authorization" not in request_section.lower()
