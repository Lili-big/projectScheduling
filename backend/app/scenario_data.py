from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import (
    ComponentModel,
    LogicRule,
    MilestoneConstraint,
    ProcessTemplate,
    ProjectBridge,
    ProjectModel,
    ResourceCalendar,
    ResourcePool,
    ScenarioInput,
    StructureModel,
    WorkSection,
)
from .sample_data import default_bridge


SCHEDULE_LOGIC_ONTOLOGY_PATH = Path(__file__).resolve().parent / "ontology" / "bridge_schedule_logic_ontology.v1.json"


def default_scenario() -> ScenarioInput:
    legacy_bridge = default_bridge()
    structures: list[StructureModel] = []

    for abutment in legacy_bridge.abutments:
        order = 0 if abutment.id == "A0" else 999
        components = _pile_components(
            structure_id=abutment.id,
            structure_name=abutment.name,
            pile_count=abutment.pile_count,
            pile_length_m=abutment.pile_length_m,
            pile_diameter_m=abutment.pile_diameter_m,
            method_id=abutment.pile_method,
        )
        if abutment.has_cap:
            components.append(
                ComponentModel(
                    id=f"{abutment.id}-CAP",
                    name=f"{abutment.name}-承台",
                    component_type="cap",
                    quantity=1,
                    quantity_label="1个",
                )
            )
        components.append(
            ComponentModel(
                id=f"{abutment.id}-BODY",
                name=f"{abutment.name}-桥台",
                component_type="abutment_body",
                quantity=1,
                quantity_label=f"{abutment.body_height_m:g}m",
                properties={"height_m": abutment.body_height_m},
            )
        )
        structures.append(
            StructureModel(
                id=abutment.id,
                name=abutment.name,
                structure_type="abutment",
                order=order,
                components=components,
            )
        )

    for pier in legacy_bridge.piers:
        structure_id = f"P{pier.pier_no:02d}"
        structure_name = f"{pier.pier_no}号墩"
        components = _pile_components(
            structure_id=structure_id,
            structure_name=structure_name,
            pile_count=pier.pile_count,
            pile_length_m=pier.pile_length_m,
            pile_diameter_m=pier.pile_diameter_m,
            method_id=pier.pile_method,
        )
        if pier.has_cap:
            components.append(
                ComponentModel(
                    id=f"{structure_id}-CAP",
                    name=f"{structure_name}-承台",
                    component_type="cap",
                    quantity=1,
                    quantity_label="1个",
                )
            )
        components.append(
            ComponentModel(
                id=f"{structure_id}-BODY",
                name=f"{structure_name}-墩柱",
                component_type="pier_body",
                quantity=pier.pier_height_m,
                quantity_label=f"{pier.pier_height_m:g}m",
                properties={"height_m": pier.pier_height_m},
            )
        )
        if pier.has_cap_beam:
            components.append(
                ComponentModel(
                    id=f"{structure_id}-BEAM",
                    name=f"{structure_name}-盖梁",
                    component_type="cap_beam",
                    quantity=1,
                    quantity_label="1个",
                )
            )
        structures.append(
            StructureModel(
                id=structure_id,
                name=structure_name,
                structure_type="pier",
                order=pier.pier_no,
                components=components,
            )
        )

    structures = sorted(structures, key=lambda item: item.order)
    project = ProjectModel(
        project_id="demo-project",
        project_name="桥梁下部结构场景化 CP-SAT 自动排程 Demo",
        start_date=legacy_bridge.start_date,
        bridges=[
            ProjectBridge(
                id="B1",
                name="青洛河1号大桥",
                order=1,
                work_sections=[
                    WorkSection(
                        id="WS-LOWER",
                        name="下部结构一工区",
                        order=1,
                        structures=structures,
                    )
                ],
            )
        ],
    )

    scenario = ScenarioInput(
        scenario_id="default-lower-structure",
        scenario_name="默认下部结构模拟方案",
        project=project,
        process_library=default_process_library(),
        logic_rules=default_scenario_logic_rules(),
        resource_calendars=default_resource_calendars(),
        resource_pools=default_resource_pools(),
        milestones=default_milestones(),
        time_limit_seconds=10,
    )
    apply_resource_max_quantity_defaults(scenario)
    return scenario


def apply_resource_max_quantity_defaults(scenario: ScenarioInput) -> ScenarioInput:
    resource_type_counts = _component_counts_by_resource_type(scenario)
    for pool in scenario.resource_pools:
        component_count = resource_type_counts.get(pool.type)
        if component_count is not None:
            pool.max_quantity = max(pool.quantity, component_count)
        elif pool.max_quantity is None:
            pool.max_quantity = pool.quantity
    return scenario


def _component_counts_by_resource_type(scenario: ScenarioInput) -> dict[str, int]:
    counts: dict[str, int] = {}
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for structure in section.structures:
                for component in structure.components:
                    if not component.enabled or component.quantity <= 0:
                        continue
                    process = _default_process_for_component(component, scenario.process_library)
                    if process is None:
                        continue
                    counts[process.resource_type] = counts.get(process.resource_type, 0) + 1
    return counts


def _default_process_for_component(component: ComponentModel, process_library: list[ProcessTemplate]) -> ProcessTemplate | None:
    candidates = [process for process in process_library if process.component_type == component.component_type]
    if component.method_id:
        return next((process for process in candidates if process.id == component.method_id or process.method_id == component.method_id), None)
    return next((process for process in candidates if process.is_default), candidates[0] if candidates else None)


def default_process_library() -> list[ProcessTemplate]:
    return [
        ProcessTemplate(
            id="pile_rotary_regular",
            component_type="pile",
            process_name="旋挖钻成孔",
            method_id="rotary_drill",
            duration_method="units_per_day",
            quantity_source="pile_length_m",
            productivity_value=18,
            productivity_unit="m/天",
            resource_type="rotary_drill",
            is_default=True,
        ),
        ProcessTemplate(
            id="pile_impact",
            component_type="pile",
            process_name="冲击钻成孔",
            method_id="impact_drill",
            duration_method="units_per_day",
            quantity_source="pile_length_m",
            productivity_value=10,
            productivity_unit="m/天",
            resource_type="impact_drill",
        ),
        ProcessTemplate(
            id="pile_manual",
            component_type="pile",
            process_name="人工挖孔",
            method_id="manual_pile",
            duration_method="days_per_unit",
            quantity_source="pile_length_m",
            productivity_value=1,
            productivity_unit="天/m",
            resource_type="manual_pile_team",
        ),
        ProcessTemplate(
            id="cap_standard",
            component_type="cap",
            process_name="承台施工",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=8,
            productivity_unit="天/个",
            resource_type="cap_team",
            is_default=True,
        ),
        ProcessTemplate(
            id="spread_foundation_standard",
            component_type="spread_foundation",
            process_name="扩大基础施工",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=8,
            productivity_unit="天/个",
            resource_type="spread_foundation_team",
            is_default=True,
        ),
        ProcessTemplate(
            id="ground_tie_beam_standard",
            component_type="ground_tie_beam",
            process_name="地系梁施工",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=4,
            productivity_unit="天/个",
            resource_type="tie_beam_team",
            is_default=True,
        ),
        ProcessTemplate(
            id="pier_body_standard",
            component_type="pier_body",
            process_name="墩柱施工",
            duration_method="units_per_day",
            quantity_source="pier_height_m",
            productivity_value=1.2,
            productivity_unit="m/天",
            resource_type="pier_body_team",
            is_default=True,
        ),
        ProcessTemplate(
            id="middle_tie_beam_standard",
            component_type="middle_tie_beam",
            process_name="中系梁施工",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=4,
            productivity_unit="天/个",
            resource_type="tie_beam_team",
            is_default=True,
        ),
        ProcessTemplate(
            id="cap_beam_standard",
            component_type="cap_beam",
            process_name="盖梁施工",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=7,
            productivity_unit="天/个",
            resource_type="cap_beam_team",
            is_default=True,
        ),
        ProcessTemplate(
            id="abutment_body_standard",
            component_type="abutment_body",
            process_name="桥台施工",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=10,
            productivity_unit="天/个",
            resource_type="abutment_team",
            is_default=True,
        ),
    ]


def default_scenario_logic_rules() -> list[LogicRule]:
    data = json.loads(SCHEDULE_LOGIC_ONTOLOGY_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != "bridge-schedule-logic-ontology/v1":
        raise ValueError(f"工艺逻辑本体版本不支持: {data.get('schema_version')}")
    return [LogicRule.model_validate(item) for item in data.get("logic_rules", [])]


def default_resource_calendars() -> list[ResourceCalendar]:
    return [
        ResourceCalendar(
            id="continuous",
            name="连续自然日",
            working_weekdays=[0, 1, 2, 3, 4, 5, 6],
            blackout_dates=[],
        )
    ]


def default_resource_pools() -> list[ResourcePool]:
    return [
        ResourcePool(id="pool-rotary-drill", type="rotary_drill", label="旋挖钻", quantity=3),
        ResourcePool(id="pool-impact-drill", type="impact_drill", label="冲击钻", quantity=1),
        ResourcePool(id="pool-manual-pile", type="manual_pile_team", label="人工挖孔班", quantity=1),
        ResourcePool(id="pool-cap", type="cap_team", label="承台模板", quantity=1),
        ResourcePool(id="pool-spread-foundation", type="spread_foundation_team", label="扩大基础班组", quantity=1),
        ResourcePool(id="pool-tie-beam", type="tie_beam_team", label="系梁班组", quantity=1),
        ResourcePool(id="pool-pier-body", type="pier_body_team", label="墩柱班组", quantity=1),
        ResourcePool(id="pool-cap-beam", type="cap_beam_team", label="盖梁模板", quantity=1),
        ResourcePool(id="pool-abutment", type="abutment_team", label="桥台班组", quantity=1),
    ]


def default_milestones() -> list[MilestoneConstraint]:
    return [
        MilestoneConstraint(
            id="M-contract-finish",
            name="合同下部结构完工",
            level="contract",
            mode="hard",
            scope_type="bridge",
            scope_id="B1",
            target_event="finish",
            target_date=date(2028, 12, 31),
        ),
        MilestoneConstraint(
            id="M-control-ws-lower",
            name="下部结构强控节点",
            level="control",
            mode="hard",
            scope_type="bridge",
            scope_id="B1",
            target_event="finish",
            target_date=date(2028, 12, 15),
        ),
        MilestoneConstraint(
            id="M-internal-cap",
            name="承台内部目标",
            level="internal",
            mode="soft",
            scope_type="component",
            scope_id="cap",
            target_event="finish",
            target_date=date(2027, 5, 25),
            penalty_per_day=20,
        ),
    ]


def _pile_components(
    structure_id: str,
    structure_name: str,
    pile_count: int,
    pile_length_m: float,
    pile_diameter_m: float,
    method_id: str,
) -> list[ComponentModel]:
    return [
        ComponentModel(
            id=f"{structure_id}-PILE-{pile_no:02d}",
            name=f"{structure_name}-{pile_no}#桩基",
            component_type="pile",
            quantity=pile_length_m,
            quantity_label=_pile_label(pile_diameter_m, pile_length_m),
            method_id=method_id,
            properties={"pile_no": pile_no, "diameter_m": pile_diameter_m, "length_m": pile_length_m},
        )
        for pile_no in range(1, pile_count + 1)
    ]


def _pile_label(diameter_m: float, length_m: float) -> str:
    return f"直径{diameter_m:g}m，桩长{length_m:g}m"
