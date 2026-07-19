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
