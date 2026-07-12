from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.main as main_module  # noqa: E402
from app.main import create_baseline_plan_endpoint, create_forecast_endpoint, get_plan_control_project_endpoint  # noqa: E402
from app.models import CreateForecastRequest  # noqa: E402
from app.services.plan_control_repository import (  # noqa: E402
    PlanControlConflictError,
    default_plan_control_repository,
)
from plan_control_helpers import solved_baseline_request  # noqa: E402


def test_plan_control_baseline_and_project_summary_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    request = solved_baseline_request()

    baseline = create_baseline_plan_endpoint(request)
    assert baseline.version_no == 1

    summary = get_plan_control_project_endpoint(request.scenario.scenario_id)
    assert summary.active_plan is not None
    assert summary.active_plan.plan_version_id == baseline.plan_version_id


def test_plan_control_api_rejects_unsolved_plan(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    request = solved_baseline_request()
    request.plan_result.result = None

    with pytest.raises(HTTPException) as exc_info:
        create_baseline_plan_endpoint(request)

    assert exc_info.value.status_code == 422
    assert "可行或最优" in str(exc_info.value.detail)


def test_plan_control_api_maps_not_found_conflict_and_storage_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(default_plan_control_repository, "path", tmp_path / "plan-control.json")
    with pytest.raises(HTTPException) as not_found:
        create_forecast_endpoint(CreateForecastRequest(plan_version_id="missing", progress_snapshot_id="missing"))
    assert not_found.value.status_code == 404

    def raise_conflict(_request):
        raise PlanControlConflictError("输入已经过期")

    monkeypatch.setattr(main_module, "create_forecast", raise_conflict)
    with pytest.raises(HTTPException) as conflict:
        create_forecast_endpoint(CreateForecastRequest(plan_version_id="plan", progress_snapshot_id="snapshot"))
    assert conflict.value.status_code == 409

    storage_directory = tmp_path / "store-directory"
    storage_directory.mkdir()
    monkeypatch.setattr(default_plan_control_repository, "path", storage_directory)
    with pytest.raises(HTTPException) as unavailable:
        get_plan_control_project_endpoint("project")
    assert unavailable.value.status_code == 503
