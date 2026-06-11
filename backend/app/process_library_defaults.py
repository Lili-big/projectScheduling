from __future__ import annotations

import math

from .models import ProcessTemplate, ProductivityOption


def historical_default_process_library() -> list[ProcessTemplate]:
    return [
        _process("pile_rotary_regular", "pile", "旋挖钻", "rotary_drill", "days_per_unit", "count", 3, "天/根", "rotary_drill", True),
        _process("pile_circulation", "pile", "回旋钻", "circulation_drill", "days_per_unit", "count", 2, "天/根", "circulation_drill", False),
        _process("pile_impact", "pile", "冲击钻", "impact_drill", "days_per_unit", "count", 2, "天/根", "impact_drill", False),
        _process("pile_manual", "pile", "人工挖孔", "manual_pile", "days_per_unit", "pile_length_m", 1, "天/m", "manual_pile_team", False),
        _process("ground_tie_beam_standard", "ground_tie_beam", "桩系梁施工", None, "fixed_days", "count", 3, "天/个", "tie_beam_team", True),
        _process("cap_standard", "cap", "承台施工", None, "fixed_days", "count", 30, "天/个", "cap_team", True),
        _process("spread_foundation_standard", "spread_foundation", "扩大基础施工", None, "fixed_days", "count", 8, "天/个", "spread_foundation_team", True),
        _process("pier_body_standard", "pier_body", "整体式浇筑", "integral_casting", "fixed_days", "count", 20, "天/个", "pier_body_team", True),
        _process(
            "pier_body_climbing_form",
            "pier_body",
            "爬模施工",
            "climbing_form",
            "days_per_unit",
            "pier_height_m",
            7,
            "天/节",
            "pier_body_team",
            False,
            standard_section_height_m=4.5,
        ),
        _process(
            "pier_body_sliding_form",
            "pier_body",
            "滑模施工",
            "sliding_form",
            "days_per_unit",
            "pier_height_m",
            6,
            "天/节",
            "pier_body_team",
            False,
            standard_section_height_m=4.5,
        ),
        _process(
            "pier_body_turnover_form",
            "pier_body",
            "翻模施工",
            "turnover_form",
            "days_per_unit",
            "pier_height_m",
            12,
            "天/节",
            "pier_body_team",
            False,
            standard_section_height_m=4.5,
        ),
        _process("middle_tie_beam_standard", "middle_tie_beam", "中系梁施工", None, "fixed_days", "count", 4, "天/个", "tie_beam_team", True),
        _process("cap_beam_standard", "cap_beam", "盖梁施工", None, "fixed_days", "count", 10, "天/个", "cap_beam_team", True),
        _process("abutment_body_standard", "abutment_body", "桥台施工", None, "fixed_days", "count", 15, "天/个", "abutment_team", True),
        _process("precast_beam_standard", "precast_beam", "制梁", None, "fixed_days", "count", 35, "天/片", "precast_beam_team", True),
        _process("beam_erection_standard", "beam_erection", "架梁", None, "fixed_days", "count", 2, "天/片", "beam_erection_team", True),
        _process("cast_in_place_continuous_zero_block", "cast_in_place_continuous_beam", "0号块", "zero_block", "fixed_days", "count", 120, "天/块", "cast_in_place_continuous_beam_team", True),
        _process("cast_in_place_continuous_standard_segment", "cast_in_place_continuous_beam", "标准块", "standard_segment", "fixed_days", "count", 10, "天/块", "cast_in_place_continuous_beam_team", False),
        _process("cast_in_place_continuous_closure_segment", "cast_in_place_continuous_beam", "合拢段", "closure_segment", "fixed_days", "count", 30, "天/块", "cast_in_place_continuous_beam_team", False),
        _process("cast_in_place_continuous_straight_segment", "cast_in_place_continuous_beam", "直线段", "straight_segment", "fixed_days", "count", 35, "天/块", "cast_in_place_continuous_beam_team", False),
        _process("cast_in_place_box_beam_standard", "cast_in_place_box_beam", "现浇箱梁", None, "fixed_days", "count", 45, "天/联", "cast_in_place_box_beam_team", True),
        _process("steel_box_beam_standard", "steel_box_beam", "钢箱梁", None, "fixed_days", "count", 30, "天/片", "steel_box_beam_team", True),
        _process("bridge_deck_system_standard", "bridge_deck_system", "桥面系", None, "units_per_day", "deck_length_m", 30, "米/天", "bridge_deck_system_team", True),
    ]


def upgrade_process_library(process_library: list[ProcessTemplate], defaults: list[ProcessTemplate] | None = None) -> list[ProcessTemplate]:
    canonical_defaults = defaults or historical_default_process_library()
    defaults_by_id = {process.id: process for process in canonical_defaults}
    upgraded: list[ProcessTemplate] = []
    seen_ids: set[str] = set()

    for process in process_library:
        next_process = _validated_copy(process)
        canonical = defaults_by_id.get(next_process.id)
        if canonical is not None and _matches_previous_builtin_default(next_process):
            next_process = _validated_copy(canonical)
        upgraded.append(next_process)
        seen_ids.add(next_process.id)

    for process in canonical_defaults:
        if process.id not in seen_ids:
            upgraded.append(_validated_copy(process))

    return _sort_process_library(upgraded)


_COMPONENT_TYPE_ORDER = {
    "pile": 0,
    "cap": 1,
    "spread_foundation": 2,
    "ground_tie_beam": 3,
    "pier_body": 4,
    "middle_tie_beam": 5,
    "cap_beam": 6,
    "abutment_body": 7,
    "precast_beam": 8,
    "beam_erection": 9,
    "cast_in_place_continuous_beam": 10,
    "cast_in_place_box_beam": 11,
    "steel_box_beam": 12,
    "bridge_deck_system": 13,
}


_PREVIOUS_BUILTIN_DEFAULTS: dict[str, tuple[str, str, float, str]] = {
    "pile_rotary_regular": ("units_per_day", "pile_length_m", 18, "m/天"),
    "pile_impact": ("units_per_day", "pile_length_m", 10, "m/天"),
    "pile_manual": ("days_per_unit", "pile_length_m", 1, "天/m"),
    "cap_standard": ("fixed_days", "count", 8, "天/个"),
    "spread_foundation_standard": ("fixed_days", "count", 8, "天/个"),
    "ground_tie_beam_standard": ("fixed_days", "count", 4, "天/个"),
    "pier_body_standard": ("units_per_day", "pier_height_m", 1.2, "m/天"),
    "pier_body_climbing_form": ("fixed_days", "count", 7, "天/节"),
    "pier_body_sliding_form": ("fixed_days", "count", 6, "天/节"),
    "pier_body_turnover_form": ("fixed_days", "count", 12, "天/节"),
    "middle_tie_beam_standard": ("fixed_days", "count", 4, "天/个"),
    "cap_beam_standard": ("fixed_days", "count", 7, "天/个"),
    "abutment_body_standard": ("fixed_days", "count", 10, "天/个"),
}


def _process(
    process_id: str,
    component_type: str,
    process_name: str,
    method_id: str | None,
    duration_method: str,
    quantity_source: str,
    productivity_value: float,
    productivity_unit: str,
    resource_type: str,
    is_default: bool,
    standard_section_height_m: float | None = None,
) -> ProcessTemplate:
    return ProcessTemplate.model_validate(
        {
            "id": process_id,
            "component_type": component_type,
            "process_name": process_name,
            "method_id": method_id,
            "duration_method": duration_method,
            "quantity_source": quantity_source,
            "productivity_value": productivity_value,
            "productivity_unit": productivity_unit,
            "resource_type": resource_type,
            "productivity_options": [
                {
                    "id": f"{process_id}-default",
                    "name": "默认工效",
                    "duration_method": duration_method,
                    "quantity_source": quantity_source,
                    "productivity_value": productivity_value,
                    "productivity_unit": productivity_unit,
                    "standard_section_height_m": standard_section_height_m,
                    "is_default": True,
                }
            ],
            "applicability": {"source": "historical_default"},
            "is_default": is_default,
        }
    )


def _validated_copy(process: ProcessTemplate) -> ProcessTemplate:
    return ProcessTemplate.model_validate(process.model_dump(mode="json"))


def _sort_process_library(process_library: list[ProcessTemplate]) -> list[ProcessTemplate]:
    return [
        item
        for _, item in sorted(
            enumerate(process_library),
            key=lambda indexed: (_COMPONENT_TYPE_ORDER.get(indexed[1].component_type, 999), indexed[0]),
        )
    ]


def _matches_previous_builtin_default(process: ProcessTemplate) -> bool:
    previous = _PREVIOUS_BUILTIN_DEFAULTS.get(process.id)
    if previous is None:
        return False
    if len(process.productivity_options) != 1:
        return False
    option = _default_productivity_option(process)
    current = (
        option.duration_method,
        option.quantity_source,
        option.productivity_value,
        option.productivity_unit,
    )
    return (
        current[0] == previous[0]
        and current[1] == previous[1]
        and math.isclose(current[2], previous[2], rel_tol=0, abs_tol=1e-9)
        and current[3] == previous[3]
    )


def _default_productivity_option(process: ProcessTemplate) -> ProductivityOption:
    return next((option for option in process.productivity_options if option.is_default), process.productivity_options[0])
