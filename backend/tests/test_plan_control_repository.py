from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services.plan_control_repository import (  # noqa: E402
    PlanControlRepository,
    PlanControlRepositoryError,
)
from app.services.progress_forecast import create_baseline_plan  # noqa: E402
from app.services.progress_forecast import PlanControlValidationError  # noqa: E402
from plan_control_helpers import solved_baseline_request  # noqa: E402


def test_repository_persists_unicode_and_returns_active_plan(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "计划管控.json")
    baseline = create_baseline_plan(solved_baseline_request(), repository)

    restored = PlanControlRepository(repository.path).project_summary(baseline.project_id)

    assert restored.active_plan is not None
    assert restored.active_plan.plan_version_id == baseline.plan_version_id
    assert restored.active_plan.project_name == baseline.project_name
    assert "测试计划工程师" in repository.path.read_text(encoding="utf-8")


def test_repository_rejects_corrupted_store(tmp_path: Path) -> None:
    path = tmp_path / "plan-control.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(PlanControlRepositoryError, match="读取失败"):
        PlanControlRepository(path).load()


def test_baseline_rejects_mismatched_plan_result_and_increments_versions(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "plan-control.json")
    request = solved_baseline_request()
    mismatched = request.model_copy(deep=True)
    mismatched.resource_plan.scenario_id = "another-plan"
    with pytest.raises(PlanControlValidationError, match="标识不一致"):
        create_baseline_plan(mismatched, repository)

    first = create_baseline_plan(request, repository)
    second_request = solved_baseline_request()
    second_request.confirmation_reason = "重新确认另一执行基准"
    second = create_baseline_plan(second_request, repository)
    store = repository.load()

    assert first.version_no == 1
    assert second.version_no == 2
    assert repository.get_plan_version(first.plan_version_id).status == "superseded"
    assert repository.project_summary(first.project_id).active_plan.plan_version_id == second.plan_version_id
    assert len(store.plan_versions) == 2
