from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from app.contracts.girder_plan_simulation import (
    BeamTypeCapacity,
    BeamYardPlan,
    CreateScenarioVersionRequest,
    ErectionLinePlan,
    GirderPlanSimulationParameters,
    ManualRoutePlan,
)
from app.contracts.project_master import (
    ParameterValue,
    ProjectMasterComponent,
    ProjectMasterSnapshot,
    ProjectMasterStructure,
    ProjectMasterWorkpoint,
)
from app.girder_plan_simulation.repository import GirderPlanRepository
from app.girder_plan_simulation.service import GirderPlanSimulationService
from app.girder_plan_simulation.topology import build_line_graph


def project_snapshot() -> ProjectMasterSnapshot:
    return ProjectMasterSnapshot(
        workpoints=[
            _workpoint("R0", "起点路基", "roadbed", 0, 100, 0),
            _bridge("B1", "一号桥", 100, 200, 1, "T32"),
            _workpoint("T1", "共用隧道", "tunnel", 200, 300, 2),
            _bridge("B2", "二号桥", 300, 400, 3, "T40"),
            _workpoint("R3", "终点路基", "roadbed", 400, 500, 4),
        ]
    )


def line_graph():
    return build_line_graph(
        project_id="P1",
        project_master_version_id="PMV1",
        snapshot=project_snapshot(),
    )


def scenario_request(graph=None, *, scenario_id: str | None = None) -> CreateScenarioVersionRequest:
    graph = graph or line_graph()
    yards = [
        BeamYardPlan(
            beam_yard_id="Y-L",
            name="左线梁场",
            alignment_code="A",
            mileage_m=0,
            production_start_date=date(2026, 8, 1),
            capacities=[
                BeamTypeCapacity(beam_type_id="T32", daily_capacity_pieces=4, initial_inventory_pieces=4),
                BeamTypeCapacity(beam_type_id="T40", daily_capacity_pieces=4, initial_inventory_pieces=0),
            ],
        ),
        BeamYardPlan(
            beam_yard_id="Y-R",
            name="右线梁场",
            alignment_code="A",
            mileage_m=0,
            production_start_date=date(2026, 8, 1),
            capacities=[
                BeamTypeCapacity(beam_type_id="T32", daily_capacity_pieces=4, initial_inventory_pieces=4),
                BeamTypeCapacity(beam_type_id="T40", daily_capacity_pieces=4, initial_inventory_pieces=0),
            ],
        ),
    ]
    lines = [
        ErectionLinePlan(
            erection_line_id="EL-L",
            beam_yard_id="Y-L",
            available_date=date(2026, 8, 1),
            daily_erection_capacity_pieces=4,
            bridge_transfer_days=1,
        ),
        ErectionLinePlan(
            erection_line_id="EL-R",
            beam_yard_id="Y-R",
            available_date=date(2026, 8, 1),
            daily_erection_capacity_pieces=4,
            bridge_transfer_days=1,
        ),
    ]
    routes = [
        ManualRoutePlan(
            route_plan_id="ROUTE-L",
            beam_yard_id="Y-L",
            erection_line_id="EL-L",
            name="左线顺序",
            target_node_ids=["B1:left", "B2:left"],
            confirmed=True,
        ),
        ManualRoutePlan(
            route_plan_id="ROUTE-R",
            beam_yard_id="Y-R",
            erection_line_id="EL-R",
            name="右线顺序",
            target_node_ids=["B1:right", "B2:right"],
            confirmed=True,
        ),
    ]
    return CreateScenarioVersionRequest(
        scenario_id=scenario_id,
        project_id="P1",
        project_master_version_id="PMV1",
        line_graph_id=graph.line_graph_id,
        beam_yards=yards,
        erection_lines=lines,
        route_plans=routes,
        parameters=GirderPlanSimulationParameters(planning_horizon_end_date=date(2026, 12, 31)),
        created_by="测试计划工程师",
    )


def scenario_version(tmp_path: Path, request: CreateScenarioVersionRequest | None = None):
    repository = GirderPlanRepository(tmp_path / "girder-plan.json")
    return repository.create_scenario_version(request or scenario_request())


class FakeProjectMasterRepository:
    def __init__(self, snapshot: ProjectMasterSnapshot | None = None) -> None:
        self.snapshot = snapshot or project_snapshot()

    def get_version_summary(self, version_id: str):
        if version_id != "PMV1":
            from app.project_master.repository import ProjectMasterNotFoundError

            raise ProjectMasterNotFoundError(f"项目主数据版本 {version_id} 不存在。")
        return SimpleNamespace(version_id=version_id, project_id="P1", status="confirmed")

    def load_snapshot(self, version_id: str) -> ProjectMasterSnapshot:
        self.get_version_summary(version_id)
        return self.snapshot.model_copy(deep=True)


def service(tmp_path: Path) -> GirderPlanSimulationService:
    project_service = SimpleNamespace(repository=FakeProjectMasterRepository())
    return GirderPlanSimulationService(project_service, GirderPlanRepository(tmp_path / "girder-plan.json"))


def _workpoint(identifier: str, name: str, kind: str, start: float, end: float, order: int) -> ProjectMasterWorkpoint:
    return ProjectMasterWorkpoint(
        workpoint_id=identifier,
        workpoint_name=name,
        workpoint_type=kind,
        alignment_code="A",
        start_mileage_m=start,
        end_mileage_m=end,
        sort_order=order,
    )


def _bridge(identifier: str, name: str, start: float, end: float, order: int, beam_type: str) -> ProjectMasterWorkpoint:
    structures = []
    for side in ("left", "right"):
        structure_id = f"{identifier}-{side}"
        structures.append(
            ProjectMasterStructure(
                structure_id=structure_id,
                workpoint_id=identifier,
                structure_name=f"{name}{side}",
                structure_category="upper_structure",
                structure_type="precast_simply_supported_beam",
                side=side,
                sort_order=0,
                components=[
                    ProjectMasterComponent(
                        component_id=f"{structure_id}-BEAM",
                        structure_id=structure_id,
                        component_name=f"{beam_type}预制梁",
                        component_type="precast_beam",
                        quantity=4,
                        unit="片",
                        parameters=[ParameterValue(parameter_code="beam_type", value_type="text", value=beam_type)],
                    )
                ],
            )
        )
    return ProjectMasterWorkpoint(
        workpoint_id=identifier,
        workpoint_name=name,
        workpoint_type="bridge",
        alignment_code="A",
        start_mileage_m=start,
        end_mileage_m=end,
        sort_order=order,
        structures=structures,
    )
