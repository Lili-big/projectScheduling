from __future__ import annotations

from pathlib import Path

from app.models import (
    ConfirmProjectDataVersionRequest,
    ConfirmSpecialtyRequest,
    CreateIntegratedScheduleRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    GirderPlanningConfig,
)
from app.services.integrated_schedule import solve_integrated_schedule
from app.services.plan_control_repository import PlanControlRepository
from app.services.process_library_service import default_scenario_with_process_library


def test_integrated_calculation_reuses_same_input_fingerprint(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "integrated-reuse.json")
    scenario = default_scenario_with_process_library()
    project = repository.create_project_data_version(
        CreateProjectDataVersionRequest(project=scenario.project, created_by="测试")
    )
    project = repository.confirm_project_data_version(
        project.project_data_version_id,
        ConfirmProjectDataVersionRequest(
            expected_input_fingerprint=project.input_fingerprint,
            confirmed_by="项目总工",
            confirmation_reason="已复核",
        ),
    )
    version = repository.create_planning_scenario_version(
        CreatePlanningScenarioVersionRequest(
            scenario=scenario,
            project_data_version_id=project.project_data_version_id,
            girder_planning=GirderPlanningConfig(enabled=False),
            created_by="测试",
        )
    )
    version = repository.confirm_specialty(
        version.scenario_version_id,
        ConfirmSpecialtyRequest(
            expected_input_fingerprint=version.input_fingerprint,
            confirmed_by="架梁专业",
            confirmation_reason="兼容分支",
        ),
    )
    request = CreateIntegratedScheduleRequest(
        scenario_version_id=version.scenario_version_id,
        expected_input_fingerprint=version.input_fingerprint,
    )

    first = solve_integrated_schedule(request, repository)
    second = solve_integrated_schedule(request, repository)

    assert second.integrated_snapshot_id == first.integrated_snapshot_id
    assert len(repository.load().integrated_calculation_snapshots) == 1
