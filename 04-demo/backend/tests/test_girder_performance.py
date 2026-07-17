from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models import (
    BeamYardConfig,
    ComponentModel,
    ErectionMachineConfig,
    GirderPlanningConfig,
    GirderRouteConfig,
    GirderRouteNode,
    GirderWorkPoint,
    PlanningScenarioVersion,
    ProjectBridge,
    ProjectDataVersion,
    ProjectModel,
    StructureModel,
    UpperStructureComponent,
    WorkSection,
)
from app.services.girder_schedule_adapter import build_girder_schedule
from app.services.process_library_service import default_scenario_with_process_library
from app.solver import solve_schedule


FIXTURE = Path(__file__).parent / "fixtures" / "girder_planning" / "performance-benchmark-v1.json"


def test_performance_fixture_declares_fixed_acceptance_shape() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert payload["materialization"] == "recipe"
    assert payload["counts"] == {
        "bridge_side_nodes": 50,
        "erection_spans": 300,
        "beam_yards": 2,
        "enabled_routes": 2,
        "schedule_tasks": 800,
    }
    assert payload["max_runtime_seconds"] == 600
    assert payload["runtime_verification"]["status"] == "verified"


def _performance_case() -> tuple[PlanningScenarioVersion, ProjectDataVersion]:
    base = default_scenario_with_process_library()
    start = base.project.start_date
    bridges: list[ProjectBridge] = []
    workpoints: list[GirderWorkPoint] = []
    for bridge_index in range(25):
        bridge_id = f"B{bridge_index + 1:03d}"
        sections: list[WorkSection] = []
        for side in ("left", "right"):
            section_id = f"{bridge_id}-{side[0].upper()}"
            structures = [
                StructureModel(
                    id=f"{section_id}-S{index + 1:02d}",
                    name=f"{bridge_id}-{side}-构造{index + 1}",
                    structure_type="pier",
                    order=index,
                    components=[
                        ComponentModel(
                            id=f"{section_id}-S{index + 1:02d}-CAP",
                            name="承台",
                            component_type="cap",
                            quantity=1,
                            quantity_label="1座",
                        )
                    ],
                )
                for index in range(10)
            ]
            uppers = [
                UpperStructureComponent(
                    id=f"{section_id}-SPAN{index + 1:02d}",
                    name=f"{bridge_id}-{side}-第{index + 1}跨",
                    structure_type="简支T梁",
                    side=side,
                    span_index=index + 1,
                    support_range=f"{index}#墩~{index + 1}#墩",
                    span_length_m=32,
                    beam_count_per_span=2,
                    span_group_expression=str(index + 1),
                    properties={"beam_type": "简支T梁"},
                )
                for index in range(6)
            ]
            sections.append(WorkSection(id=section_id, name=f"{bridge_id}-{side}", side=side, structures=structures, upper_structures=uppers))
            workpoints.append(
                GirderWorkPoint(
                    workpoint_id=f"bridge:{bridge_id}:{side}",
                    name=f"{bridge_id}-{side}",
                    workpoint_type="bridge",
                    side=side,
                    mileage_start_m=bridge_index * 1000 + (0 if side == "left" else 10),
                    mileage_end_m=bridge_index * 1000 + 100 + (0 if side == "left" else 10),
                    corridor_id="main",
                    bridge_id=bridge_id,
                    work_section_id=section_id,
                    requires_erection=True,
                )
            )
        bridges.append(ProjectBridge(id=bridge_id, name=bridge_id, order=bridge_index, work_sections=sections))
    project = ProjectModel(project_id="PERF", project_name="性能基准", start_date=start, bridges=bridges)
    scenario = base.model_copy(
        update={
            "scenario_id": "perf",
            "scenario_name": "性能基准",
            "project": project,
            "logic_rules": [],
            "upper_structure_logic_rules": [],
            "milestones": [],
            "time_limit_seconds": 30.0,
        }
    )
    route_nodes = [
        GirderRouteNode(route_node_id=f"r1-{index}", workpoint_id=item.workpoint_id, sequence_index=index)
        for index, item in enumerate(workpoints[:25])
    ]
    route_nodes_2 = [
        GirderRouteNode(route_node_id=f"r2-{index}", workpoint_id=item.workpoint_id, sequence_index=index)
        for index, item in enumerate(workpoints[25:])
    ]
    config = GirderPlanningConfig(
        enabled=True,
        beam_yards=[
            BeamYardConfig(
                beam_yard_id="yard-1",
                name="梁场1",
                mileage_m=0,
                side="both",
                corridor_id="main",
                production_start_date=start,
                daily_production_capacity=100,
                initial_inventory_by_type={"简支T梁": 1000},
            ),
            BeamYardConfig(
                beam_yard_id="yard-2",
                name="梁场2",
                mileage_m=25000,
                side="both",
                corridor_id="main",
                production_start_date=start,
                daily_production_capacity=100,
                initial_inventory_by_type={"简支T梁": 1000},
            ),
        ],
        erection_machines=[
            ErectionMachineConfig(erection_machine_id="machine-1", name="架桥机1", beam_yard_id="yard-1", available_date=start, daily_erection_capacity=10),
            ErectionMachineConfig(erection_machine_id="machine-2", name="架桥机2", beam_yard_id="yard-2", available_date=start, daily_erection_capacity=10),
        ],
        routes=[
            GirderRouteConfig(route_id="route-1", name="路线1", beam_yard_id="yard-1", erection_machine_id="machine-1", enabled=True, confirmed=True, nodes=route_nodes),
            GirderRouteConfig(route_id="route-2", name="路线2", beam_yard_id="yard-2", erection_machine_id="machine-2", enabled=True, confirmed=True, nodes=route_nodes_2),
        ],
        parameters={"post_erection_buffer_confirmed": True, "max_iterations": 2},
    )
    created_at = datetime.now(timezone.utc)
    scenario_version = PlanningScenarioVersion(
        scenario_version_id="sv-perf",
        scenario_id="perf",
        project_data_version_id="pdv-perf",
        version_no=1,
        status="specialty_confirmed",
        scenario=scenario,
        girder_planning=config,
        input_fingerprint="fp-perf",
        created_by="benchmark",
        created_at=created_at,
    )
    project_version = ProjectDataVersion(
        project_data_version_id="pdv-perf",
        project_id="PERF",
        version_no=1,
        status="confirmed",
        project=project,
        workpoints=workpoints,
        input_fingerprint="project-fp-perf",
        created_by="benchmark",
        created_at=created_at,
    )
    return scenario_version, project_version


@pytest.mark.skipif(os.getenv("RUN_GIRDER_PERFORMANCE") != "1", reason="完整性能基准需显式开启")
def test_performance_fixture_solves_under_ten_minutes() -> None:
    scenario_version, project_version = _performance_case()
    started = time.perf_counter()
    generated, girder = build_girder_schedule(scenario_version, project_version)
    adapter_seconds = time.perf_counter() - started
    solved = solve_schedule(generated.schedule_input)
    elapsed = time.perf_counter() - started

    assert len(generated.schedule_input.tasks) == 800
    assert len(girder.span_plans) == 300
    assert girder.status == "ready"
    assert solved.status in {"OPTIMAL", "FEASIBLE"}
    assert elapsed <= 600
    print({"adapter_seconds": round(adapter_seconds, 2), "total_seconds": round(elapsed, 2), "status": solved.status})
