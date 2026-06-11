from __future__ import annotations

from datetime import date

from .models import (
    AbutmentConfig,
    BridgeModel,
    LogicRule,
    PierConfig,
    ProductivityRule,
    Resource,
)
from .process_library_defaults import historical_default_process_library


def default_bridge() -> BridgeModel:
    piers = []
    for pier_no in range(1, 13):
        method = "manual_pile" if pier_no in {6, 7} else "rotary_drill"
        piers.append(
            PierConfig(
                pier_no=pier_no,
                pile_count=2,
                pile_length_m=36 if pier_no <= 3 else 50,
                pile_diameter_m=1.5,
                pier_height_m=7 + (pier_no % 4) * 1.5,
                pile_method=method,
            )
        )

    return BridgeModel(
        project_name="桥梁下部结构 CP-SAT 自动排程 Demo",
        start_date=date(2026, 6, 1),
        bridge_name="青岩河1号大桥",
        piers=piers,
        abutments=[
            AbutmentConfig(
                id="A0",
                name="0号台",
                pile_count=2,
                pile_length_m=30,
                pile_diameter_m=1.5,
                body_height_m=5,
                pile_method="rotary_drill",
            ),
            AbutmentConfig(
                id="A13",
                name="13号台",
                pile_count=2,
                pile_length_m=30,
                pile_diameter_m=1.5,
                body_height_m=5,
                pile_method="rotary_drill",
            ),
        ],
    )


def default_productivity_rules() -> list[ProductivityRule]:
    rules: list[ProductivityRule] = []
    for process in historical_default_process_library():
        option = next((item for item in process.productivity_options if item.is_default), process.productivity_options[0])
        rules.append(
            ProductivityRule(
                id=process.id,
                component_type=process.component_type,
                process_name=process.process_name,
                group_name=option.name,
                duration_method=option.duration_method,
                quantity_source=option.quantity_source,
                productivity_value=option.productivity_value,
                productivity_unit=option.productivity_unit,
                standard_section_height_m=option.standard_section_height_m,
                resource_type=process.resource_type,
                is_default=process.is_default,
            )
        )
    return rules


def default_logic_rules() -> list[LogicRule]:
    return [
        LogicRule(
            id="cap_after_piles",
            to_component="cap",
            predecessor_candidates=["pile"],
            predecessor_strategy="all",
            lag_days=3,
            note="承台在同一墩台全部桩基完成后施工。",
        ),
        LogicRule(
            id="pier_body_after_cap",
            structure_type="pier",
            to_component="pier_body",
            predecessor_candidates=["cap", "pile"],
            predecessor_strategy="first_available",
            lag_days=5,
            note="墩身优先以前置承台为准；无承台时回退到桩基。",
        ),
        LogicRule(
            id="cap_beam_after_pier_body",
            structure_type="pier",
            to_component="cap_beam",
            predecessor_candidates=["pier_body"],
            predecessor_strategy="first_available",
            lag_days=3,
            note="盖梁在墩身完成后施工。",
        ),
        LogicRule(
            id="abutment_body_after_cap",
            structure_type="abutment",
            to_component="abutment_body",
            predecessor_candidates=["cap", "pile"],
            predecessor_strategy="first_available",
            lag_days=5,
            note="桥台优先以前置承台为准；无承台时回退到桩基。",
        ),
    ]


def default_resources() -> list[Resource]:
    return [
        Resource(id="rotary_drill_1", name="旋挖钻1", type="rotary_drill"),
        Resource(id="rotary_drill_2", name="旋挖钻2", type="rotary_drill"),
        Resource(id="rotary_drill_3", name="旋挖钻3", type="rotary_drill"),
        Resource(id="circulation_drill_1", name="回旋钻1", type="circulation_drill"),
        Resource(id="impact_drill_1", name="冲击钻1", type="impact_drill"),
        Resource(id="manual_pile_team_1", name="人工挖孔班1", type="manual_pile_team"),
        Resource(id="cap_team_1", name="承台模板1", type="cap_team"),
        Resource(id="pier_body_team_1", name="墩身班组1", type="pier_body_team"),
        Resource(id="cap_beam_team_1", name="盖梁模板1", type="cap_beam_team"),
        Resource(id="abutment_team_1", name="桥台班组1", type="abutment_team"),
    ]
