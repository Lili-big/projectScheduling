from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routers import assistants  # noqa: E402
from app.models import ResourceAssistantResultsRequest  # noqa: E402


def test_resource_assistant_value_error_maps_to_422(monkeypatch) -> None:
    monkeypatch.setattr(assistants, "compare_resource_plan_results", lambda _request: (_ for _ in ()).throw(ValueError("缺少结果")))
    with pytest.raises(HTTPException) as exc_info:
        assistants.compare_resource_plan_results_endpoint(ResourceAssistantResultsRequest(resource_plans=[], plan_results=[]))
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "缺少结果"


def test_assistant_routes_keep_expected_status_contracts() -> None:
    paths = assistants.router.routes
    operations = {(next(iter(route.methods)), route.path) for route in paths}
    assert ("POST", "/api/ai-parameter-assistant/parse") in operations
    assert ("POST", "/api/ai-parameter-assistant/apply") in operations
    assert len([path for method, path in operations if path.startswith("/api/ai-resource-assistant/")]) == 6
