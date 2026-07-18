from __future__ import annotations

from typing import Any


DEFINITION_VERSION = "project-master/v1"

WORKPOINT_TYPES: dict[str, dict[str, Any]] = {
    "bridge": {"display_name": "桥梁", "schedule_support": "bridge_supported"},
    "roadbed": {"display_name": "路基", "schedule_support": "not_supported"},
    "tunnel": {"display_name": "隧道", "schedule_support": "not_supported"},
    "culvert": {"display_name": "涵洞", "schedule_support": "not_supported"},
    "interchange": {"display_name": "互通", "schedule_support": "not_supported"},
    "service_area": {"display_name": "服务区", "schedule_support": "not_supported"},
    "station_yard": {"display_name": "场站", "schedule_support": "not_supported"},
    "access_road": {"display_name": "便道", "schedule_support": "not_supported"},
    "other": {"display_name": "其他", "schedule_support": "not_supported"},
}

STRUCTURE_TYPES: dict[str, dict[str, Any]] = {
    "bridge_abutment": {"category": "substructure", "workpoints": ["bridge"], "side_rule": "bridge"},
    "bridge_pier": {"category": "substructure", "workpoints": ["bridge"], "side_rule": "bridge"},
    "simple_span": {"category": "superstructure", "workpoints": ["bridge"], "side_rule": "split"},
    "cast_in_place_unit": {"category": "superstructure", "workpoints": ["bridge"], "side_rule": "split"},
    "continuous_unit": {"category": "superstructure", "workpoints": ["bridge"], "side_rule": "split"},
    "roadbed_section": {"category": "earthwork", "workpoints": ["roadbed"], "side_rule": "optional"},
    "tunnel_body": {"category": "tunnel_body", "workpoints": ["tunnel"], "side_rule": "optional"},
    "culvert_body": {"category": "drainage", "workpoints": ["culvert"], "side_rule": "optional"},
    "other": {"category": "other", "workpoints": list(WORKPOINT_TYPES), "side_rule": "optional"},
}

COMPONENT_TYPES: dict[str, dict[str, Any]] = {
    "pile": {"display_name": "桩基", "units": ["根", "m"]},
    "cap": {"display_name": "承台", "units": ["个", "m3"]},
    "tie_beam": {"display_name": "系梁", "units": ["个", "m3"]},
    "pier_body": {"display_name": "墩身", "units": ["个", "根", "m"]},
    "abutment_body": {"display_name": "桥台", "units": ["个", "m3"]},
    "cap_beam": {"display_name": "盖梁", "units": ["个", "m3"]},
    "precast_beam": {"display_name": "预制梁", "units": ["片", "榀"]},
    "cast_in_place_box_beam": {"display_name": "现浇箱梁", "units": ["联", "m"]},
    "cast_in_place_continuous_beam": {"display_name": "连续梁节段", "units": ["段", "块"]},
    "other": {"display_name": "其他", "units": ["个", "项", "m", "m2", "m3"]},
}

PARAMETER_DEFINITIONS: dict[tuple[str, str], dict[str, Any]] = {
    ("structure", "span_length_m"): {"value_type": "number", "unit": "m"},
    ("structure", "bearing_from"): {"value_type": "text", "unit": None},
    ("structure", "bearing_to"): {"value_type": "text", "unit": None},
    ("structure", "span_expression"): {"value_type": "text", "unit": None},
    ("structure", "main_pier_ids"): {"value_type": "text", "unit": None},
    ("structure", "segment_count"): {"value_type": "integer", "unit": None},
    ("structure", "span_index"): {"value_type": "integer", "unit": None},
    ("structure", "beam_count_per_span"): {"value_type": "integer", "unit": "片"},
    ("component", "diameter_m"): {"value_type": "number", "unit": "m"},
    ("component", "length_m"): {"value_type": "number", "unit": "m"},
    ("component", "height_m"): {"value_type": "number", "unit": "m"},
    ("component", "form"): {"value_type": "text", "unit": None},
}


def schedule_support_for(workpoint_type: str) -> str:
    definition = WORKPOINT_TYPES.get(workpoint_type, WORKPOINT_TYPES["other"])
    return str(definition["schedule_support"])
