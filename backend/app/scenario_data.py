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
    UpperStructureComponent,
    UpperStructureLogicRule,
    WorkSection,
)
from .process_library_defaults import historical_default_process_library
from .sample_data import default_bridge


SCHEDULE_LOGIC_ONTOLOGY_PATH = Path(__file__).resolve().parent / "ontology" / "bridge_schedule_logic_ontology.v1.json"
CONTINUOUS_BEAM_STRUCTURE_CODE = "castInPlaceContinuousBoxGirder"
CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES = 18
DEFAULT_RESOURCE_MAX_QUANTITIES: dict[str, int] = {
    "rotary_drill": 10,
    "circulation_drill": 10,
    "impact_drill": 10,
    "manual_pile_team": 10,
    "cap_team": 10,
    "pier_body_team": 10,
    "cap_beam_team": 10,
}
PILE_EQUIPMENT_PARALLEL_RULE_DESCRIPTION = "设备型桩基资源：同一墩同一工艺默认最多由 1 台设备承担；设置为 0 表示不额外限制。"
MANUAL_PILE_PARALLEL_RULE_DESCRIPTION = "人工挖孔班组：同一墩内不设置最多参与设备数，默认仅受班组数量约束。"
BRIDGE_COMPLETION_MILESTONE_NAME = "下部及现浇结构施工完成"


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
        upper_structure_logic_rules=default_upper_structure_logic_rules(),
        resource_calendars=default_resource_calendars(),
        resource_pools=default_resource_pools(),
        milestones=default_milestones(),
        time_limit_seconds=10,
    )
    sync_bridge_completion_milestones(scenario)
    apply_resource_max_quantity_defaults(scenario)
    return scenario


def sync_bridge_completion_milestones(scenario: ScenarioInput) -> ScenarioInput:
    scenario.milestones = bridge_completion_milestones(scenario.project, scenario.milestones)
    return scenario


def bridge_completion_milestones(
    project: ProjectModel,
    existing_milestones: list[MilestoneConstraint] | None = None,
) -> list[MilestoneConstraint]:
    existing_bridge_milestones = [
        milestone
        for milestone in existing_milestones or []
        if milestone.scope_type == "bridge" and milestone.scope_id
    ]
    existing_by_bridge: dict[str, MilestoneConstraint] = {}
    for milestone in existing_bridge_milestones:
        existing_by_bridge.setdefault(milestone.scope_id or "", milestone)

    template = existing_bridge_milestones[0] if existing_bridge_milestones else None
    fallback_target_date = template.target_date if template else _default_bridge_completion_target_date(project.start_date)
    milestones: list[MilestoneConstraint] = []
    for bridge in sorted(project.bridges, key=lambda item: (item.order, item.name)):
        existing = existing_by_bridge.get(bridge.id)
        milestones.append(
            MilestoneConstraint(
                id=f"M-{bridge.id}-lower-cast-in-place-finish",
                name=BRIDGE_COMPLETION_MILESTONE_NAME,
                level="control",
                mode="hard",
                scope_type="bridge",
                scope_id=bridge.id,
                target_event="finish",
                target_date=existing.target_date if existing else fallback_target_date,
                penalty_per_day=0,
            )
        )
    return milestones


def _default_bridge_completion_target_date(start_date: date) -> date:
    return date(start_date.year + 2, 12, 31)


def apply_resource_max_quantity_defaults(scenario: ScenarioInput) -> ScenarioInput:
    continuous_t_count = _continuous_beam_t_structure_count(scenario)
    for pool in scenario.resource_pools:
        quantity = pool.quantity or 0
        if pool.resource_mode == "UNLIMITED":
            continue
        if pool.max_quantity is not None:
            pool.max_quantity = max(quantity, pool.max_quantity)
            continue
        if pool.type == "cast_in_place_continuous_beam_team":
            pool.max_quantity = max(quantity, continuous_t_count, 10)
        elif pool.type in DEFAULT_RESOURCE_MAX_QUANTITIES:
            pool.max_quantity = max(quantity, DEFAULT_RESOURCE_MAX_QUANTITIES[pool.type])
        else:
            pool.max_quantity = quantity
    return scenario


def _continuous_beam_t_structure_count(scenario: ScenarioInput) -> int:
    count = 0
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for uppers in _continuous_beam_groups(section.upper_structures):
                span_indices = sorted({upper.span_index for upper in uppers})
                count += _continuous_main_support_count(uppers, span_indices)
    return count


def _continuous_beam_groups(upper_structures: list[UpperStructureComponent]) -> list[list[UpperStructureComponent]]:
    groups: dict[int, list[UpperStructureComponent]] = {}
    for upper in upper_structures:
        if not _is_continuous_beam_upper(upper):
            continue
        groups.setdefault(_continuous_group_index(upper), []).append(upper)
    return [
        sorted(group, key=lambda item: item.span_index)
        for _, group in sorted(groups.items(), key=lambda item: (min(upper.span_index for upper in item[1]), item[0]))
    ]


def _is_continuous_beam_upper(upper: UpperStructureComponent) -> bool:
    if upper.properties.get("structure_code") == CONTINUOUS_BEAM_STRUCTURE_CODE:
        return True
    return any(keyword in upper.structure_type for keyword in ("连续", "刚构"))


def _continuous_group_index(upper: UpperStructureComponent) -> int:
    try:
        return int(upper.properties.get("group_index"))
    except (TypeError, ValueError):
        return upper.span_index


def _continuous_main_support_count(uppers: list[UpperStructureComponent], span_indices: list[int]) -> int:
    configured = _continuous_list_setting(uppers, ["main_support_indices", "main_pier_indices"])
    if configured:
        return len(set(configured))
    if len(span_indices) < 2:
        return 0
    return max(span_indices) - min(span_indices)


def _continuous_int_setting(
    uppers: list[UpperStructureComponent],
    keys: list[str],
    *,
    default: int,
    minimum: int,
) -> int:
    value = _continuous_setting(uppers, keys)
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _continuous_list_setting(uppers: list[UpperStructureComponent], keys: list[str]) -> list[int]:
    value = _continuous_setting(uppers, keys)
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _continuous_setting(uppers: list[UpperStructureComponent], keys: list[str]) -> object:
    for upper in uppers:
        nested = upper.properties.get("continuous_beam")
        if isinstance(nested, dict):
            for key in keys:
                if key in nested and nested[key] is not None:
                    return nested[key]
        for key in keys:
            if key in upper.properties and upper.properties[key] is not None:
                return upper.properties[key]
    return None


def _default_process_for_component(component: ComponentModel, process_library: list[ProcessTemplate]) -> ProcessTemplate | None:
    candidates = [process for process in process_library if process.component_type == component.component_type]
    if component.method_id:
        return next((process for process in candidates if process.id == component.method_id or process.method_id == component.method_id), None)
    return next((process for process in candidates if process.is_default), candidates[0] if candidates else None)


def default_process_library() -> list[ProcessTemplate]:
    return historical_default_process_library()


def default_scenario_logic_rules() -> list[LogicRule]:
    data = json.loads(SCHEDULE_LOGIC_ONTOLOGY_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != "bridge-schedule-logic-ontology/v1":
        raise ValueError(f"工艺逻辑本体版本不支持: {data.get('schema_version')}")
    return [LogicRule.model_validate(item) for item in data.get("logic_rules", [])]


def default_upper_structure_logic_rules() -> list[UpperStructureLogicRule]:
    return [
        UpperStructureLogicRule(
            id="cast_in_place_box_beam_after_lower_structure",
            note="现浇箱梁在对应跨组墩台下部结构完成后开始。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_zero_block_after_main_pier_lower_structure",
            note="连续梁0号块在对应主墩下部结构完成后开始。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_side_straight_after_edge_lower_structure",
            note="连续梁边跨连续段在对应边跨墩台下部结构完成后开始。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_t_chain",
            note="连续梁T构内0号块和标准段按顺序施工。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_side_closure",
            max_finish_gap_days=7,
            note="连续梁边跨合龙段在边跨连续段和相邻T构完成后开始。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_middle_closure",
            max_finish_gap_days=7,
            note="连续梁中跨合龙段在相邻两个T构完成后开始。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_edge_before_middle_closure",
            note="连续梁默认边跨合龙先于中跨合龙。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_middle_closure_sequence",
            note="连续梁中跨合龙按配置顺序推进。",
        ),
    ]


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
        ResourcePool(
            id="pool-rotary-drill",
            type="rotary_drill",
            label="旋挖钻",
            quantity=1,
            max_quantity=10,
            cost_type="monthly_rental",
            incremental_unit_cost=180000,
            billing_period_days=30,
            same_structure_resource_binding=False,
            same_structure_parallel_limit=1,
            parallel_rule_description=PILE_EQUIPMENT_PARALLEL_RULE_DESCRIPTION,
        ),
        ResourcePool(
            id="pool-circulation-drill",
            type="circulation_drill",
            label="回旋钻",
            quantity=1,
            max_quantity=10,
            same_structure_resource_binding=False,
            same_structure_parallel_limit=1,
            parallel_rule_description=PILE_EQUIPMENT_PARALLEL_RULE_DESCRIPTION,
        ),
        ResourcePool(
            id="pool-impact-drill",
            type="impact_drill",
            label="冲击钻",
            quantity=1,
            max_quantity=10,
            same_structure_resource_binding=False,
            same_structure_parallel_limit=1,
            parallel_rule_description=PILE_EQUIPMENT_PARALLEL_RULE_DESCRIPTION,
        ),
        ResourcePool(
            id="pool-manual-pile",
            type="manual_pile_team",
            label="人工挖孔班组",
            quantity=1,
            max_quantity=10,
            parallel_rule_description=MANUAL_PILE_PARALLEL_RULE_DESCRIPTION,
        ),
        ResourcePool(id="pool-cap", type="cap_team", label="承台模板", quantity=1, max_quantity=10),
        ResourcePool(
            id="pool-pier-body",
            type="pier_body_team",
            label="墩柱模板",
            quantity=1,
            max_quantity=10,
            cost_type="one_time_purchase",
            incremental_unit_cost=90000,
        ),
        ResourcePool(
            id="pool-cap-beam",
            type="cap_beam_team",
            label="盖梁模板",
            quantity=1,
            max_quantity=10,
            cost_type="one_time_purchase",
            incremental_unit_cost=80000,
        ),
        ResourcePool(id="pool-cast-in-place-continuous-beam", type="cast_in_place_continuous_beam_team", label="连续梁班组", quantity=1, max_quantity=10),
    ]


def default_milestones() -> list[MilestoneConstraint]:
    return [
        MilestoneConstraint(
            id="M-B1-lower-cast-in-place-finish",
            name=BRIDGE_COMPLETION_MILESTONE_NAME,
            level="control",
            mode="hard",
            scope_type="bridge",
            scope_id="B1",
            target_event="finish",
            target_date=date(2028, 12, 31),
            penalty_per_day=0,
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
