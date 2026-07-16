from __future__ import annotations

from pathlib import Path

from app.models import (
    ConfirmProjectDataVersionRequest,
    ConfirmSpecialtyRequest,
    CreateIntegratedScheduleRequest,
    CreatePlanningScenarioVersionRequest,
    CreateProjectDataVersionRequest,
    GirderPlanningConfig,
    BeamYardConfig,
    ErectionMachineConfig,
    GirderRouteConfig,
    GirderRouteNode,
    GirderWorkPoint,
    ProjectBridge,
    ProjectModel,
    UpperStructureComponent,
    WorkSection,
)
from app.services.integrated_schedule import preview_girder_planning, solve_integrated_schedule
from app.services.plan_control_repository import PlanControlRepository
from app.services.process_library_service import default_scenario_with_process_library
from app.scenario import generate_schedule_input_from_scenario


def test_preview_and_integrated_snapshot_are_persisted(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "integrated.json")
    scenario = default_scenario_with_process_library()
    project_version = repository.create_project_data_version(
        CreateProjectDataVersionRequest(project=scenario.project, created_by="测试")
    )
    project_version = repository.confirm_project_data_version(
        project_version.project_data_version_id,
        ConfirmProjectDataVersionRequest(
            expected_input_fingerprint=project_version.input_fingerprint,
            confirmed_by="项目总工",
            confirmation_reason="数据已复核",
        ),
    )
    scenario_version = repository.create_planning_scenario_version(
        CreatePlanningScenarioVersionRequest(
            scenario=scenario,
            project_data_version_id=project_version.project_data_version_id,
            girder_planning=GirderPlanningConfig(enabled=False),
            created_by="测试",
        )
    )
    repository.confirm_specialty(
        scenario_version.scenario_version_id,
        ConfirmSpecialtyRequest(
            expected_input_fingerprint=scenario_version.input_fingerprint,
            confirmed_by="架梁专业",
            confirmation_reason="非架梁专项场景确认兼容分支",
        ),
    )

    preview = preview_girder_planning(scenario_version, project_version)
    assert preview.status in {"ready", "blocked"}

    snapshot = solve_integrated_schedule(
        CreateIntegratedScheduleRequest(
            scenario_version_id=scenario_version.scenario_version_id,
            expected_input_fingerprint=scenario_version.input_fingerprint,
        ),
        repository,
    )
    assert snapshot.integrated_snapshot_id
    assert snapshot.status in {"converged", "not_converged", "infeasible", "blocked"}
    assert repository.get_integrated_snapshot(snapshot.integrated_snapshot_id).input_fingerprint == snapshot.input_fingerprint


def test_girder_preview_generates_span_task_for_confirmed_route(tmp_path: Path) -> None:
    repository = PlanControlRepository(tmp_path / "girder-enabled.json")
    base = default_scenario_with_process_library()
    project = ProjectModel(
        project_id="project-girder",
        project_name="架梁联算样例",
        start_date=base.project.start_date,
        bridges=[
            ProjectBridge(
                id="B1",
                name="B1大桥",
                work_sections=[
                    WorkSection(
                        id="B1-L",
                        name="B1左幅",
                        side="left",
                        upper_structures=[
                            UpperStructureComponent(
                                id="B1-L-SPAN-1",
                                name="B1左幅第1跨",
                                structure_type="简支T梁",
                                side="left",
                                span_index=1,
                                support_range="0#台~1#墩",
                                span_length_m=32,
                                beam_count_per_span=4,
                                span_group_expression="1",
                            )
                        ],
                    )
                ],
            )
        ],
    )
    scenario = base.model_copy(update={"project": project})
    generated_with_girder = generate_schedule_input_from_scenario(scenario, include_girder_erection=True)
    assert any(task.component_type == "beam_erection" for task in generated_with_girder.schedule_input.tasks)
    workpoint = GirderWorkPoint(
        workpoint_id="bridge:B1:left",
        name="B1左幅",
        workpoint_type="bridge",
        side="left",
        mileage_start_m=1000,
        mileage_end_m=1100,
        corridor_id="main",
        bridge_id="B1",
        work_section_id="B1-L",
        requires_erection=True,
    )
    project_version = repository.create_project_data_version(
        CreateProjectDataVersionRequest(project=scenario.project, workpoints=[workpoint], created_by="测试")
    )
    project_version = repository.confirm_project_data_version(
        project_version.project_data_version_id,
        ConfirmProjectDataVersionRequest(
            expected_input_fingerprint=project_version.input_fingerprint,
            confirmed_by="项目总工",
            confirmation_reason="结构与幅别已复核",
        ),
    )
    config = GirderPlanningConfig(
        enabled=True,
        beam_yards=[
            BeamYardConfig(
                beam_yard_id="yard-1",
                name="一号梁场",
                mileage_m=0,
                corridor_id="main",
                production_start_date=scenario.project.start_date,
                daily_production_capacity=4,
            )
        ],
        erection_machines=[
            ErectionMachineConfig(
                erection_machine_id="machine-1",
                name="一号架桥机",
                beam_yard_id="yard-1",
                available_date=scenario.project.start_date,
                daily_erection_capacity=4,
            )
        ],
        routes=[
            GirderRouteConfig(
                route_id="route-1",
                name="一号线",
                beam_yard_id="yard-1",
                erection_machine_id="machine-1",
                enabled=True,
                confirmed=True,
                nodes=[GirderRouteNode(route_node_id="route-1-node-1", workpoint_id=workpoint.workpoint_id, sequence_index=0)],
            )
        ],
        parameters={"post_erection_buffer_confirmed": True},
    )
    scenario_version = repository.create_planning_scenario_version(
        CreatePlanningScenarioVersionRequest(
            scenario=scenario,
            project_data_version_id=project_version.project_data_version_id,
            girder_planning=config,
            created_by="测试",
        )
    )
    scenario_version = repository.confirm_specialty(
        scenario_version.scenario_version_id,
        ConfirmSpecialtyRequest(
            expected_input_fingerprint=scenario_version.input_fingerprint,
            confirmed_by="架梁专业",
            confirmation_reason="路线与架后通行缓冲已确认",
        ),
    )

    preview = preview_girder_planning(scenario_version, project_version)

    assert preview.status == "ready"
    assert len(preview.span_plans) == 1
    assert preview.span_plans[0].beam_count == 4

    snapshot = solve_integrated_schedule(
        CreateIntegratedScheduleRequest(
            scenario_version_id=scenario_version.scenario_version_id,
            expected_input_fingerprint=scenario_version.input_fingerprint,
        ),
        repository,
    )
    assert snapshot.status in {"converged", "not_converged", "infeasible", "blocked"}
    assert snapshot.girder_result is not None
