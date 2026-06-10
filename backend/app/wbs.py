from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .models import (
    AbutmentConfig,
    BridgeModel,
    ComponentType,
    LogicRule,
    PierConfig,
    PrecedenceLink,
    ProductivityRule,
    Task,
    ValidationMessage,
    WbsResponse,
)


PILE_RULE_BY_METHOD = {
    "rotary_drill": "pile_rotary_regular",
    "impact_drill": "pile_impact",
    "manual_pile": "pile_manual",
}


def calculate_duration(quantity: float, rule: ProductivityRule) -> int:
    if rule.duration_method == "units_per_day":
        return max(1, math.ceil(quantity / rule.productivity_value))
    if rule.duration_method == "days_per_unit":
        return max(1, math.ceil(quantity * rule.productivity_value))
    return max(1, math.ceil(rule.productivity_value))


def generate_wbs(
    bridge: BridgeModel,
    productivity_rules: list[ProductivityRule],
    logic_rules: list[LogicRule],
) -> WbsResponse:
    tasks: list[Task] = []
    validation: list[ValidationMessage] = []
    rules_by_id = {rule.id: rule for rule in productivity_rules}

    def require_rule(rule_id: str) -> ProductivityRule:
        rule = rules_by_id.get(rule_id)
        if not rule:
            raise ValueError(f"Missing productivity rule: {rule_id}")
        return rule

    for abutment in bridge.abutments:
        tasks.extend(_build_abutment_tasks(abutment, require_rule))

    for pier in bridge.piers:
        tasks.extend(_build_pier_tasks(pier, require_rule))

    links, link_messages = build_precedence_links(tasks, logic_rules)
    validation.extend(link_messages)
    validation.append(
        ValidationMessage(
            level="info",
            message=f"已生成 {len(tasks)} 个工作项和 {len(links)} 条工艺逻辑关系。",
        )
    )
    return WbsResponse(tasks=tasks, precedence_links=links, validation=validation)


def build_precedence_links(
    tasks: list[Task], logic_rules: list[LogicRule]
) -> tuple[list[PrecedenceLink], list[ValidationMessage]]:
    by_structure: dict[str, dict[ComponentType, list[Task]]] = defaultdict(lambda: defaultdict(list))
    structure_types: dict[str, str] = {}
    for task in tasks:
        by_structure[task.structure_id][task.component_type].append(task)
        structure_types[task.structure_id] = task.structure_type

    links: list[PrecedenceLink] = []
    messages: list[ValidationMessage] = []
    link_no = 1

    for structure_id, component_map in by_structure.items():
        structure_type = structure_types[structure_id]
        for rule in logic_rules:
            if rule.structure_type and rule.structure_type != structure_type:
                continue
            successors = component_map.get(rule.to_component, [])
            if not successors:
                continue

            selected_predecessors: list[Task] = []
            if rule.predecessor_strategy == "all":
                for candidate in rule.predecessor_candidates:
                    selected_predecessors.extend(component_map.get(candidate, []))
            else:
                for candidate in rule.predecessor_candidates:
                    candidate_tasks = component_map.get(candidate, [])
                    if candidate_tasks:
                        selected_predecessors = candidate_tasks
                        break

            if not selected_predecessors:
                structure_tasks = [task for typed_tasks in component_map.values() for task in typed_tasks]
                structure_label = _format_structure_label(structure_id, structure_tasks[0] if structure_tasks else None)
                messages.append(
                    ValidationMessage(
                        level="warning",
                        subject_id=structure_id,
                        message=(
                            f"{structure_label}的“{_component_type_label(rule.to_component)}”"
                            f"应用工艺逻辑“{_format_rule_label(rule)}”时，未找到前置工作项。"
                        ),
                    )
                )
                continue

            for successor in successors:
                for predecessor in selected_predecessors:
                    if predecessor.id == successor.id:
                        continue
                    links.append(
                        PrecedenceLink(
                            id=f"L{link_no:04d}",
                            predecessor_id=predecessor.id,
                            successor_id=successor.id,
                            relationship=rule.relationship,
                            lag_days=rule.lag_days,
                            source_rule_id=rule.id,
                            severity=rule.severity,
                        )
                    )
                    link_no += 1

    return links, messages


def _format_structure_label(structure_id: str, task: Task | None = None) -> str:
    if task is not None:
        return f"结构物“{task.structure_name}”（{_structure_id_hint(structure_id)}）"
    return f"结构物“{_structure_id_hint(structure_id)}”"


def _structure_id_hint(structure_id: str) -> str:
    parts = structure_id.split("-")
    if len(parts) >= 3:
        bridge = parts[0][1:] if parts[0].startswith("B") else parts[0]
        side = {"L": "左幅", "R": "右幅", "N": "不分幅"}.get(parts[1], parts[1])
        station = "-".join(parts[2:])
        structure_kind = "桥台" if station.upper().startswith("A") else "桥墩"
        return f"第 {bridge} 座桥 {side} {station} {structure_kind}"
    return structure_id


def _format_rule_label(rule: LogicRule) -> str:
    if rule.note:
        return rule.note.rstrip("。")
    predecessors = "、".join(_component_type_label(item) for item in rule.predecessor_candidates)
    return f"{_component_type_label(rule.to_component)}在{predecessors}之后施工"


def _component_type_label(component_type: ComponentType) -> str:
    labels: dict[ComponentType, str] = {
        "pile": "桩基",
        "cap": "承台",
        "spread_foundation": "扩大基础",
        "ground_tie_beam": "地系梁",
        "middle_tie_beam": "中系梁",
        "pier_body": "墩柱",
        "cap_beam": "盖梁",
        "abutment_body": "桥台台身",
    }
    return labels[component_type]


def _build_pier_tasks(pier: PierConfig, require_rule: Any) -> list[Task]:
    structure_id = f"P{pier.pier_no:02d}"
    structure_name = f"{pier.pier_no}号墩"
    tasks: list[Task] = []

    pile_rule = require_rule(PILE_RULE_BY_METHOD[pier.pile_method])
    for pile_no in range(1, pier.pile_count + 1):
        quantity = pier.pile_length_m
        tasks.append(
            Task(
                id=f"{structure_id}-PILE-{pile_no:02d}",
                name=f"{structure_name}-{pile_no}#桩基",
                structure_id=structure_id,
                structure_name=structure_name,
                structure_type="pier",
                component_type="pile",
                process_name=pile_rule.process_name,
                productivity_rule_id=pile_rule.id,
                quantity=quantity,
                quantity_label=_pile_label(pier.pile_diameter_m, pier.pile_length_m),
                duration_days=calculate_duration(quantity, pile_rule),
                compatible_resource_types=[pile_rule.resource_type],
            )
        )

    if pier.has_cap:
        cap_rule = require_rule("cap_standard")
        tasks.append(
            Task(
                id=f"{structure_id}-CAP",
                name=f"{structure_name}-承台",
                structure_id=structure_id,
                structure_name=structure_name,
                structure_type="pier",
                component_type="cap",
                process_name=cap_rule.process_name,
                productivity_rule_id=cap_rule.id,
                quantity=1,
                quantity_label="1个",
                duration_days=calculate_duration(1, cap_rule),
                compatible_resource_types=[cap_rule.resource_type],
            )
        )

    body_rule = require_rule("pier_body_standard")
    tasks.append(
        Task(
            id=f"{structure_id}-BODY",
            name=f"{structure_name}-墩身",
            structure_id=structure_id,
            structure_name=structure_name,
            structure_type="pier",
            component_type="pier_body",
            process_name=body_rule.process_name,
            productivity_rule_id=body_rule.id,
            quantity=pier.pier_height_m,
            quantity_label=f"{pier.pier_height_m:g}m",
            duration_days=calculate_duration(pier.pier_height_m, body_rule),
            compatible_resource_types=[body_rule.resource_type],
        )
    )

    if pier.has_cap_beam:
        beam_rule = require_rule("cap_beam_standard")
        tasks.append(
            Task(
                id=f"{structure_id}-BEAM",
                name=f"{structure_name}-盖梁",
                structure_id=structure_id,
                structure_name=structure_name,
                structure_type="pier",
                component_type="cap_beam",
                process_name=beam_rule.process_name,
                productivity_rule_id=beam_rule.id,
                quantity=1,
                quantity_label="1个",
                duration_days=calculate_duration(1, beam_rule),
                compatible_resource_types=[beam_rule.resource_type],
            )
        )

    return tasks


def _build_abutment_tasks(abutment: AbutmentConfig, require_rule: Any) -> list[Task]:
    tasks: list[Task] = []

    pile_rule = require_rule(PILE_RULE_BY_METHOD[abutment.pile_method])
    for pile_no in range(1, abutment.pile_count + 1):
        quantity = abutment.pile_length_m
        tasks.append(
            Task(
                id=f"{abutment.id}-PILE-{pile_no:02d}",
                name=f"{abutment.name}-{pile_no}#桩基",
                structure_id=abutment.id,
                structure_name=abutment.name,
                structure_type="abutment",
                component_type="pile",
                process_name=pile_rule.process_name,
                productivity_rule_id=pile_rule.id,
                quantity=quantity,
                quantity_label=_pile_label(abutment.pile_diameter_m, abutment.pile_length_m),
                duration_days=calculate_duration(quantity, pile_rule),
                compatible_resource_types=[pile_rule.resource_type],
            )
        )

    if abutment.has_cap:
        cap_rule = require_rule("cap_standard")
        tasks.append(
            Task(
                id=f"{abutment.id}-CAP",
                name=f"{abutment.name}-承台",
                structure_id=abutment.id,
                structure_name=abutment.name,
                structure_type="abutment",
                component_type="cap",
                process_name=cap_rule.process_name,
                productivity_rule_id=cap_rule.id,
                quantity=1,
                quantity_label="1个",
                duration_days=calculate_duration(1, cap_rule),
                compatible_resource_types=[cap_rule.resource_type],
            )
        )

    body_rule = require_rule("abutment_body_standard")
    tasks.append(
        Task(
            id=f"{abutment.id}-BODY",
            name=f"{abutment.name}-桥台",
            structure_id=abutment.id,
            structure_name=abutment.name,
            structure_type="abutment",
            component_type="abutment_body",
            process_name=body_rule.process_name,
            productivity_rule_id=body_rule.id,
            quantity=1,
            quantity_label=f"{abutment.body_height_m:g}m",
            duration_days=calculate_duration(1, body_rule),
            compatible_resource_types=[body_rule.resource_type],
        )
    )

    return tasks


def _pile_label(diameter_m: float, length_m: float) -> str:
    return f"直径{diameter_m:g}m，桩长{length_m:g}m"
