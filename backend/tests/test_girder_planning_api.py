from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

import app.main as main_module
from app.main import (
    confirm_project_data_version_endpoint,
    create_planning_scenario_version_endpoint,
    create_project_data_version_endpoint,
    validate_girder_planning_endpoint,
)
from app.models import (
    ConfirmProjectDataVersionRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    GirderPlanningConfig,
    ScenarioVersionReference,
)
from app.services.plan_control_repository import PlanControlRepository
from app.services.process_library_service import default_scenario_with_process_library


def test_project_confirmation_and_scenario_version_api(tmp_path: Path, monkeypatch) -> None:
    repository = PlanControlRepository(tmp_path / "girder-api.json")
    monkeypatch.setattr(main_module, "default_plan_control_repository", repository)
    scenario = default_scenario_with_process_library()

    project_version = create_project_data_version_endpoint(
        CreateProjectDataVersionRequest(project=scenario.project, created_by="测试")
    )

    with pytest.raises(HTTPException) as before_confirm:
        create_planning_scenario_version_endpoint(
            CreatePlanningScenarioVersionRequest(
                scenario=scenario,
                project_data_version_id=project_version.project_data_version_id,
                girder_planning=GirderPlanningConfig(enabled=False),
                created_by="测试",
            )
        )
    assert before_confirm.value.status_code == 409

    confirmed = confirm_project_data_version_endpoint(
        project_version.project_data_version_id,
        ConfirmProjectDataVersionRequest(
            expected_input_fingerprint=project_version.input_fingerprint,
            confirmed_by="项目总工",
            confirmation_reason="复核通过",
        ),
    )
    assert confirmed.status == "confirmed"

    saved = create_planning_scenario_version_endpoint(
        CreatePlanningScenarioVersionRequest(
            scenario=scenario,
            project_data_version_id=project_version.project_data_version_id,
            girder_planning=GirderPlanningConfig(enabled=False),
            created_by="测试",
        )
    )
    readiness = validate_girder_planning_endpoint(
        ScenarioVersionReference(
            scenario_version_id=saved.scenario_version_id,
            expected_input_fingerprint=saved.input_fingerprint,
        )
    )
    assert readiness.status == "ready"
