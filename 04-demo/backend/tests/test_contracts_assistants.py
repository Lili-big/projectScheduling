from __future__ import annotations

import sys
from pathlib import Path


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
