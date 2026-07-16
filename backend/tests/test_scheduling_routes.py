from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app  # noqa: E402
from asgi_client import json_request  # noqa: E402


def test_scheduling_router_exposes_demo_and_task_generation() -> None:
    scenario_status, scenario = json_request(app, "GET", "/api/demo-scenario")
    assert scenario_status == 200
    generated_status, generated = json_request(app, "POST", "/api/generate-schedule-input", scenario)
    assert generated_status == 200
    assert generated["schedule_input"]["tasks"]


def test_scheduling_router_keeps_validation_error_shape() -> None:
    status, response = json_request(app, "POST", "/api/solve-min-resources", {})
    assert status == 422
    assert "detail" in response


def test_scheduling_router_keeps_compatibility_endpoints() -> None:
    schema = app.openapi()["paths"]
    assert "post" in schema["/api/generate-wbs"]
    assert "post" in schema["/api/solve"]
