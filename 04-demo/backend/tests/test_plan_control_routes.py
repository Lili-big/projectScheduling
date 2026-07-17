from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routers import plan_control  # noqa: E402
from app.services.plan_control_repository import PlanControlConflictError, PlanControlNotFoundError  # noqa: E402


@pytest.mark.parametrize(
    ("error", "expected"),
    [(PlanControlConflictError("版本冲突"), 409), (PlanControlNotFoundError("未找到"), 404)],
)
def test_plan_control_router_preserves_domain_status_codes(error, expected) -> None:
    mapped = plan_control.plan_control_http_error(error)
    assert mapped.status_code == expected
    assert mapped.detail == str(error)


def test_plan_control_router_keeps_all_six_operations() -> None:
    operations = {(method, route.path) for route in plan_control.router.routes for method in route.methods}
    assert len(operations) == 6
    assert ("POST", "/api/plan-control/baselines") in operations
    assert ("POST", "/api/plan-control/adjustments/{proposal_id}/adopt") in operations
