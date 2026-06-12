from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import (
    ComponentModel,
    ComponentType,
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
CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE = "castInPlaceBoxGirder"


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
            for resource_type, task_count in _upper_structure_counts_by_resource_type(
                section.upper_structures,
                scenario.process_library,
            ).items():
                counts[resource_type] = counts.get(resource_type, 0) + task_count
    return counts


def _upper_structure_counts_by_resource_type(
    upper_structures: list[UpperStructureComponent],
    process_library: list[ProcessTemplate],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    box_count = len(_cast_in_place_box_beam_groups(upper_structures))
    _add_upper_count(counts, process_library, "cast_in_place_box_beam", None, box_count)

    method_counts: dict[str, int] = {}
    for uppers in _continuous_beam_groups(upper_structures):
        span_indices = sorted({upper.span_index for upper in uppers})
        main_support_count = _continuous_main_support_count(uppers, span_indices)
        if main_support_count <= 0:
            continue
        standard_cycles = _continuous_int_setting(
            uppers,
            ["standard_segment_cycles", "standard_block_cycles", "standard_blocks_per_side"],
            default=CONTINUOUS_BEAM_DEFAULT_STANDARD_SEGMENT_CYCLES,
            minimum=0,
        )
        method_counts["zero_block"] = method_counts.get("zero_block", 0) + main_support_count
        if standard_cycles > 0:
            method_counts["standard_segment"] = method_counts.get("standard_segment", 0) + main_support_count
        method_counts["straight_segment"] = method_counts.get("straight_segment", 0) + 2
        method_counts["closure_segment"] = method_counts.get("closure_segment", 0) + main_support_count + 1

    for process in process_library:
        if process.component_type != "cast_in_place_continuous_beam" or not process.method_id:
            continue
        task_count = method_counts.get(process.method_id, 0)
        if task_count:
            counts[process.resource_type] = counts.get(process.resource_type, 0) + task_count
    return counts


def _add_upper_count(
    counts: dict[str, int],
    process_library: list[ProcessTemplate],
    component_type: ComponentType,
    method_id: str | None,
    task_count: int,
) -> None:
    if task_count <= 0:
        return
    process = _default_process_for_component(
        ComponentModel(
            id="upper-count-probe",
            name="上部结构计数探针",
            component_type=component_type,
            quantity=1,
            method_id=method_id,
        ),
        process_library,
    )
    if process is not None:
        counts[process.resource_type] = counts.get(process.resource_type, 0) + task_count


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


def _cast_in_place_box_beam_groups(upper_structures: list[UpperStructureComponent]) -> list[list[UpperStructureComponent]]:
    groups: dict[int, list[UpperStructureComponent]] = {}
    for upper in upper_structures:
        if not _is_cast_in_place_box_beam_upper(upper):
            continue
        groups.setdefault(_upper_group_index(upper), []).append(upper)
    return [
        sorted(group, key=lambda item: item.span_index)
        for _, group in sorted(groups.items(), key=lambda item: (min(upper.span_index for upper in item[1]), item[0]))
    ]


def _is_cast_in_place_box_beam_upper(upper: UpperStructureComponent) -> bool:
    structure_code = upper.properties.get("structure_code")
    if structure_code == CAST_IN_PLACE_BOX_BEAM_STRUCTURE_CODE:
        return True
    return "现浇" in upper.structure_type and "箱梁" in upper.structure_type and not _is_continuous_beam_upper(upper)


def _upper_group_index(upper: UpperStructureComponent) -> int:
    try:
        return int(upper.properties.get("group_index"))
    except (TypeError, ValueError):
        return upper.span_index


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
            note="连续梁边跨合龙段在边跨连续段和相邻T构完成后开始。",
        ),
        UpperStructureLogicRule(
            id="continuous_beam_middle_closure",
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
        ResourcePool(id="pool-rotary-drill", type="rotary_drill", label="旋挖钻", quantity=3),
        ResourcePool(id="pool-circulation-drill", type="circulation_drill", label="回旋钻", quantity=1),
        ResourcePool(id="pool-impact-drill", type="impact_drill", label="冲击钻", quantity=1),
        ResourcePool(id="pool-manual-pile", type="manual_pile_team", label="人工挖孔班", quantity=1),
        ResourcePool(id="pool-cap", type="cap_team", label="承台模板", quantity=1),
        ResourcePool(id="pool-spread-foundation", type="spread_foundation_team", label="扩大基础班组", quantity=1),
        ResourcePool(id="pool-tie-beam", type="tie_beam_team", label="系梁班组", quantity=1),
        ResourcePool(id="pool-pier-body", type="pier_body_team", label="墩柱班组", quantity=1),
        ResourcePool(id="pool-cap-beam", type="cap_beam_team", label="盖梁模板", quantity=1),
        ResourcePool(id="pool-abutment", type="abutment_team", label="桥台班组", quantity=1),
        ResourcePool(id="pool-precast-beam", type="precast_beam_team", label="制梁台座", quantity=1),
        ResourcePool(id="pool-beam-erection", type="beam_erection_team", label="架梁班组", quantity=1),
        ResourcePool(id="pool-cast-in-place-continuous-beam", type="cast_in_place_continuous_beam_team", label="连续梁班组", quantity=1),
        ResourcePool(id="pool-cast-in-place-box-beam", type="cast_in_place_box_beam_team", label="现浇箱梁班组", quantity=1),
        ResourcePool(id="pool-steel-box-beam", type="steel_box_beam_team", label="钢箱梁班组", quantity=1),
        ResourcePool(id="pool-bridge-deck-system", type="bridge_deck_system_team", label="桥面系班组", quantity=1),
    ]


def default_milestones() -> list[MilestoneConstraint]:
    return [
        MilestoneConstraint(
            id="M-contract-finish",
            name="合同下部结构及上部现浇梁完工",
            level="contract",
            mode="hard",
            scope_type="bridge",
            scope_id="B1",
            target_event="finish",
            target_date=date(2028, 12, 31),
        ),
        MilestoneConstraint(
            id="M-control-ws-lower",
            name="下部结构及上部现浇梁强控节点",
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
