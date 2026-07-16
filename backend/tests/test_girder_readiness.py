from __future__ import annotations

from datetime import date, datetime, timezone

from app.girder_planning.validation import validate_girder_planning
from app.models import (
    BeamYardConfig,
    ErectionMachineConfig,
    GirderPlanningConfig,
    GirderPlanningParameters,
    GirderRouteConfig,
    GirderRouteNode,
    GirderWorkPoint,
    PlanningScenarioVersion,
    ProjectDataVersion,
)
from app.services.process_library_service import default_scenario_with_process_library


def _versions() -> tuple[ProjectDataVersion, PlanningScenarioVersion]:
    scenario = default_scenario_with_process_library()
    workpoint = GirderWorkPoint(
        workpoint_id="bridge:B1:left",
        name="青洛河1号大桥",
        workpoint_type="bridge",
        side="left",
        mileage_start_m=1000,
        mileage_end_m=1200,
        corridor_id="main",
        bridge_id="B1",
        work_section_id="WS-LOWER",
        requires_erection=True,
    )
    project_version = ProjectDataVersion(
        project_data_version_id="pdv-1",
        project_id=scenario.project.project_id,
        version_no=1,
        status="confirmed",
        project=scenario.project,
        workpoints=[workpoint],
        input_fingerprint="project-fp",
        created_by="测试",
        created_at=datetime.now(timezone.utc),
    )
    yards = [
        BeamYardConfig(beam_yard_id=f"yard-{index}", name=f"梁场{index}", mileage_m=index * 100, side="left", corridor_id="main", production_start_date=date(2026, 1, 1), daily_production_capacity=4)
        for index in (1, 2)
    ]
    machines = [
        ErectionMachineConfig(erection_machine_id=f"machine-{index}", name=f"架桥机{index}", beam_yard_id=f"yard-{index}", available_date=date(2026, 1, 1), daily_erection_capacity=1)
        for index in (1, 2)
    ]
    routes = [
        GirderRouteConfig(
            route_id=f"route-{index}",
            name=f"路线{index}",
            beam_yard_id=f"yard-{index}",
            erection_machine_id=f"machine-{index}",
            enabled=True,
            confirmed=True,
            nodes=[GirderRouteNode(route_node_id=f"route-{index}-node-1", workpoint_id=workpoint.workpoint_id, sequence_index=0)],
        )
        for index in (1, 2)
    ]
    config = GirderPlanningConfig(
        enabled=True,
        beam_yards=yards,
        erection_machines=machines,
        routes=routes,
        parameters=GirderPlanningParameters(post_erection_passage_buffer_days=2, post_erection_buffer_confirmed=True),
    )
    scenario_version = PlanningScenarioVersion(
        scenario_version_id="sv-1",
        scenario_id=scenario.scenario_id,
        project_data_version_id=project_version.project_data_version_id,
        version_no=1,
        scenario=scenario,
        girder_planning=config,
        input_fingerprint="scenario-fp",
        created_by="测试",
        created_at=datetime.now(timezone.utc),
    )
    return project_version, scenario_version


def test_readiness_allows_shared_bridge_across_routes_and_requires_unique_line_per_yard() -> None:
    project_version, scenario_version = _versions()

    readiness = validate_girder_planning(scenario_version, project_version)

    assert readiness.status == "ready"
    assert next(item for item in readiness.checks if item.code == "BRIDGE_ROUTE_COVERAGE").status == "passed"


def test_readiness_blocks_missing_coverage_and_two_lines_in_one_yard() -> None:
    project_version, scenario_version = _versions()
    first = scenario_version.girder_planning.routes[0]
    second = scenario_version.girder_planning.routes[1].model_copy(
        update={"beam_yard_id": first.beam_yard_id, "nodes": []}
    )
    scenario_version.girder_planning.routes = [first.model_copy(update={"nodes": []}), second]

    readiness = validate_girder_planning(scenario_version, project_version)

    assert readiness.status == "blocking"
    assert next(item for item in readiness.checks if item.code == "ONE_ACTIVE_LINE_PER_YARD").status == "blocking"
    assert next(item for item in readiness.checks if item.code == "BRIDGE_ROUTE_COVERAGE").status == "blocking"
