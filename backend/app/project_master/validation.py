from __future__ import annotations

from uuid import uuid4

from ..contracts.project_master import ProjectMasterImportIssue, ProjectMasterSnapshot
from .definitions import COMPONENT_TYPES, STRUCTURE_TYPES, WORKPOINT_TYPES


def validate_snapshot(snapshot: ProjectMasterSnapshot) -> list[ProjectMasterImportIssue]:
    issues: list[ProjectMasterImportIssue] = []
    _validate_unique_ids(snapshot, issues)
    for workpoint in snapshot.workpoints:
        source = workpoint.source
        if workpoint.workpoint_type not in WORKPOINT_TYPES:
            issues.append(_issue("error", "WORKPOINT_TYPE_INVALID", source.sheet_name if source else "工点信息", source.row_no if source else None, "workpoint_type", f"不支持的工点类型 {workpoint.workpoint_type}。", workpoint.workpoint_id))
        if (workpoint.start_mileage_m is None) != (workpoint.end_mileage_m is None):
            issues.append(_issue("error", "MILEAGE_INCOMPLETE", source.sheet_name if source else "工点信息", source.row_no if source else None, "start_mileage_m", "起点里程和终点里程必须同时填写。", workpoint.workpoint_id))
        if workpoint.start_mileage_m is not None and workpoint.end_mileage_m is not None and workpoint.end_mileage_m < workpoint.start_mileage_m:
            issues.append(_issue("error", "MILEAGE_RANGE_INVALID", source.sheet_name if source else "工点信息", source.row_no if source else None, "end_mileage_m", "终点里程不得小于起点里程。", workpoint.workpoint_id))
        for structure in workpoint.structures:
            structure_source = structure.source
            if not structure.structure_name or not structure.structure_category or not structure.structure_type:
                issues.append(_issue("error", "REQUIRED_FIELD", structure_source.sheet_name if structure_source else "结构物信息", structure_source.row_no if structure_source else None, None, "结构物名称、类别和类型不能为空。", structure.structure_id))
            definition = STRUCTURE_TYPES.get(structure.structure_type)
            if definition is None:
                issues.append(_issue("error", "STRUCTURE_TYPE_INVALID", structure_source.sheet_name if structure_source else "结构物信息", structure_source.row_no if structure_source else None, "structure_type", f"不支持的结构类型 {structure.structure_type}。", structure.structure_id))
            elif workpoint.workpoint_type not in definition["workpoints"]:
                issues.append(_issue("error", "STRUCTURE_WORKPOINT_MISMATCH", structure_source.sheet_name if structure_source else "结构物信息", structure_source.row_no if structure_source else None, "structure_type", f"结构类型 {structure.structure_type} 不适用于 {workpoint.workpoint_type} 工点。", structure.structure_id))
            if structure.side not in {"left", "right", "shared", "none"}:
                issues.append(_issue("error", "STRUCTURE_SIDE_INVALID", structure_source.sheet_name if structure_source else "结构物信息", structure_source.row_no if structure_source else None, "side", f"幅别 {structure.side} 不合法，应为 left、right、shared 或 none。", structure.structure_id))
            if workpoint.workpoint_type == "bridge" and structure.side == "none":
                issues.append(_issue("error", "BRIDGE_SIDE_REQUIRED", structure_source.sheet_name if structure_source else "结构物信息", structure_source.row_no if structure_source else None, "side", "桥梁正式结构物必须填写 left、right 或 shared。", structure.structure_id))
            if workpoint.workpoint_type == "bridge" and not structure.section_code:
                issues.append(_issue("error", "BRIDGE_SECTION_REQUIRED", structure_source.sheet_name if structure_source else "结构物信息", structure_source.row_no if structure_source else None, "section_code", "桥梁排程结构物必须填写工区编码。", structure.structure_id))
            _validate_bridge_parameters(structure, issues)
            for component in structure.components:
                component_source = component.source
                if not component.component_name or not component.component_type or not component.unit:
                    issues.append(_issue("error", "REQUIRED_FIELD", component_source.sheet_name if component_source else "构件参数", component_source.row_no if component_source else None, None, "构件名称、类型和单位不能为空。", component.component_id))
                definition = COMPONENT_TYPES.get(component.component_type)
                if definition is None:
                    issues.append(_issue("error", "COMPONENT_TYPE_INVALID", component_source.sheet_name if component_source else "构件参数", component_source.row_no if component_source else None, "component_type", f"不支持的构件类型 {component.component_type}。", component.component_id))
                elif component.unit not in definition["units"]:
                    issues.append(_issue("warning", "COMPONENT_UNIT_UNUSUAL", component_source.sheet_name if component_source else "构件参数", component_source.row_no if component_source else None, "unit", f"单位 {component.unit} 不在构件类型 {component.component_type} 的推荐单位中。", component.component_id))
                if component.quantity == 0 and component.enabled:
                    issues.append(_issue("warning", "ZERO_QUANTITY", component_source.sheet_name if component_source else "构件参数", component_source.row_no if component_source else None, "quantity", "启用构件的工程量为 0，任务生成时将跳过或产生诊断。", component.component_id))
    return issues


def _validate_unique_ids(snapshot: ProjectMasterSnapshot, issues: list[ProjectMasterImportIssue]) -> None:
    seen: dict[str, tuple[str, str]] = {}
    objects = []
    for workpoint in snapshot.workpoints:
        objects.append(("workpoint", workpoint.workpoint_id, workpoint.source))
        for structure in workpoint.structures:
            objects.append(("structure", structure.structure_id, structure.source))
            for component in structure.components:
                objects.append(("component", component.component_id, component.source))
    for kind, object_id, source in objects:
        key = object_id.casefold()
        if key in seen:
            previous_kind, previous_id = seen[key]
            issues.append(
                _issue(
                    "error",
                    "STABLE_ID_DUPLICATE",
                    source.sheet_name if source else "填写说明",
                    source.row_no if source else None,
                    None,
                    f"稳定标识 {object_id} 与已有 {previous_kind} {previous_id} 重复（不区分大小写）。",
                    object_id,
                )
            )
        else:
            seen[key] = (kind, object_id)


def _validate_bridge_parameters(structure, issues: list[ProjectMasterImportIssue]) -> None:
    parameters = {item.parameter_code: item.value for item in structure.parameters}
    required: dict[str, tuple[str, ...]] = {
        "simple_span": ("span_index", "span_length_m", "bearing_from", "bearing_to"),
        "cast_in_place_unit": ("span_index", "span_length_m", "bearing_from", "bearing_to", "span_expression"),
        "continuous_unit": (
            "span_index",
            "span_length_m",
            "bearing_from",
            "bearing_to",
            "span_expression",
            "main_pier_ids",
            "segment_count",
        ),
    }
    missing = [
        code
        for code in required.get(structure.structure_type, ())
        if parameters.get(code) is None or parameters.get(code) == ""
    ]
    if not missing:
        return
    source = structure.source
    issues.append(
        _issue(
            "error",
            "BRIDGE_PARAMETER_REQUIRED",
            source.sheet_name if source else "结构物信息",
            source.row_no if source else None,
            f"param.{missing[0]}",
            f"结构类型 {structure.structure_type} 缺少参数：{', '.join(missing)}。",
            structure.structure_id,
        )
    )


def _issue(severity: str, code: str, sheet: str, row_no: int | None, field: str | None, message: str, object_id: str | None) -> ProjectMasterImportIssue:
    return ProjectMasterImportIssue(
        issue_id=f"pmi-{uuid4().hex}",
        severity=severity,
        issue_code=code,
        sheet_name=sheet,
        row_no=row_no,
        field_name=field,
        object_id=object_id,
        message=message,
    )


__all__ = ["validate_snapshot"]
