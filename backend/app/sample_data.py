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
    return [
        ProductivityRule(
            id="pile_rotary_regular",
            component_type="pile",
            process_name="旋挖钻 / 常规桩",
            group_name="常规桩",
            duration_method="units_per_day",
            quantity_source="pile_length_m",
            productivity_value=18,
            productivity_unit="m/天",
            resource_type="rotary_drill",
            is_default=True,
        ),
        ProductivityRule(
            id="pile_impact",
            component_type="pile",
            process_name="冲击钻",
            group_name="冲击钻",
            duration_method="units_per_day",
            quantity_source="pile_length_m",
            productivity_value=10,
            productivity_unit="m/天",
            resource_type="impact_drill",
        ),
        ProductivityRule(
            id="pile_manual",
            component_type="pile",
            process_name="人工挖孔",
            group_name="人工挖孔",
            duration_method="days_per_unit",
            quantity_source="pile_length_m",
            productivity_value=1,
            productivity_unit="天/m",
            resource_type="manual_pile_team",
        ),
        ProductivityRule(
            id="cap_standard",
            component_type="cap",
            process_name="承台",
            group_name="标准承台",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=8,
            productivity_unit="天/个",
            resource_type="cap_team",
            is_default=True,
        ),
        ProductivityRule(
            id="pier_body_standard",
            component_type="pier_body",
            process_name="墩身",
            group_name="标准墩身",
            duration_method="units_per_day",
            quantity_source="pier_height_m",
            productivity_value=1.2,
            productivity_unit="m/天",
            resource_type="pier_body_team",
            is_default=True,
        ),
        ProductivityRule(
            id="cap_beam_standard",
            component_type="cap_beam",
            process_name="盖梁",
            group_name="普通盖梁",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=7,
            productivity_unit="天/个",
            resource_type="cap_beam_team",
            is_default=True,
        ),
        ProductivityRule(
            id="abutment_body_standard",
            component_type="abutment_body",
            process_name="桥台",
            group_name="普通桥台",
            duration_method="fixed_days",
            quantity_source="count",
            productivity_value=10,
            productivity_unit="天/个",
            resource_type="abutment_team",
            is_default=True,
        ),
    ]


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
        Resource(id="impact_drill_1", name="冲击钻1", type="impact_drill"),
        Resource(id="manual_pile_team_1", name="人工挖孔班1", type="manual_pile_team"),
        Resource(id="cap_team_1", name="承台模板1", type="cap_team"),
        Resource(id="pier_body_team_1", name="墩身班组1", type="pier_body_team"),
        Resource(id="cap_beam_team_1", name="盖梁模板1", type="cap_beam_team"),
        Resource(id="abutment_team_1", name="桥台班组1", type="abutment_team"),
    ]
