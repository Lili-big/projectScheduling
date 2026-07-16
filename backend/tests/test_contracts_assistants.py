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
