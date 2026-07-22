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
    ProjectMasterRoutePlacement,
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


def explicit_route_snapshot() -> ProjectMasterSnapshot:
    snapshot = project_snapshot()
    placements: list[ProjectMasterRoutePlacement] = []
    for workpoint in snapshot.workpoints:
        sides = sorted({item.side for item in workpoint.structures if item.side in {"left", "right"}})
        for side in sides:
            placements.append(
                ProjectMasterRoutePlacement(
                    placement_id=f"RP-{workpoint.workpoint_id}-{side}",
                    workpoint_id=workpoint.workpoint_id,
                    side=side,
                    mileage_prefix="ZK" if side == "left" else "K",
                    start_mileage_m=workpoint.start_mileage_m,
                    end_mileage_m=workpoint.end_mileage_m,
                    spatial_group_id=f"SG-{workpoint.sort_order:03d}",
                    display_order=workpoint.sort_order,
                )
            )
    snapshot.route_placements = placements
    return snapshot


def continuous_route_snapshot() -> ProjectMasterSnapshot:
    snapshot = explicit_route_snapshot()
    bridge = next(item for item in snapshot.workpoints if item.workpoint_id == "B1")
    bridge.structures = []
    for side, lengths in (("left", (20, 30, 50)), ("right", (25, 35, 40))):
        for span_index, (kind, length, beam_type, beam_count) in enumerate(
            (
                ("simple_span", lengths[0], "T32", 4),
                ("continuous_unit", lengths[1], None, 0),
                ("simple_span", lengths[2], "T40", 6),
            ),
            start=1,
        ):
            structure_id = f"B1-{side}-S{span_index}"
            components = []
            if beam_type is not None:
                components.append(
                    ProjectMasterComponent(
                        component_id=f"{structure_id}-BEAM",
                        structure_id=structure_id,
                        component_name=f"{beam_type}预制梁",
                        component_type="precast_beam",
                        quantity=beam_count,
                        unit="片",
                        parameters=[ParameterValue(parameter_code="beam_type", value_type="text", value=beam_type)],
                    )
                )
            bridge.structures.append(
                ProjectMasterStructure(
                    structure_id=structure_id,
                    workpoint_id=bridge.workpoint_id,
                    structure_name=f"一号桥{side}第{span_index}段",
                    structure_category="superstructure",
                    structure_type=kind,
                    side=side,
                    sort_order=span_index,
                    parameters=[
                        ParameterValue(parameter_code="span_index", value_type="integer", value=span_index),
                        ParameterValue(parameter_code="span_length_m", value_type="number", value=length, unit="m"),
                        ParameterValue(
                            parameter_code="planned_finish_date",
                            value_type="date",
                            value=f"2026-0{span_index + 6}-01",
                        ),
                    ],
                    components=components,
                )
            )
    return snapshot


def line_graph():
    return build_line_graph(
        project_id="P1",
        project_master_version_id="PMV1",
        snapshot=explicit_route_snapshot(),
    )


def scenario_request(graph=None, *, scenario_id: str | None = None) -> CreateScenarioVersionRequest:
    graph = graph or line_graph()
    yards = [
        BeamYardPlan(
            beam_yard_id="Y-L",
            name="左线梁场",
            deployment_node_id="R0:left",
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
            deployment_node_id="R0:right",
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
        self.snapshot = snapshot or explicit_route_snapshot()

    def get_version_summary(self, version_id: str):
        if version_id != "PMV1":
            from app.project_master.repository import ProjectMasterNotFoundError

            raise ProjectMasterNotFoundError(f"项目主数据版本 {version_id} 不存在。")
        return SimpleNamespace(version_id=version_id, project_id="P1", status="confirmed")

    def load_snapshot(self, version_id: str) -> ProjectMasterSnapshot:
        self.get_version_summary(version_id)
        return self.snapshot.model_copy(deep=True)


def service(tmp_path: Path, snapshot: ProjectMasterSnapshot | None = None) -> GirderPlanSimulationService:
    project_service = SimpleNamespace(repository=FakeProjectMasterRepository(snapshot))
    return GirderPlanSimulationService(project_service, GirderPlanRepository(tmp_path / "girder-plan.json"))


def _workpoint(identifier: str, name: str, kind: str, start: float, end: float, order: int) -> ProjectMasterWorkpoint:
    structure_type = "tunnel_body" if kind == "tunnel" else "roadbed_section"
    return ProjectMasterWorkpoint(
        workpoint_id=identifier,
        workpoint_name=name,
        workpoint_type=kind,
        alignment_code="A",
        start_mileage_m=start,
        end_mileage_m=end,
        sort_order=order,
        structures=[
            ProjectMasterStructure(
                structure_id=f"{identifier}-{side}",
                workpoint_id=identifier,
                structure_name=f"{name}{side}",
                structure_category="route",
                structure_type=structure_type,
                side=side,
            )
            for side in ("left", "right")
        ],
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
