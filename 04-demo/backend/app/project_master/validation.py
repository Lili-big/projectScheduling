from __future__ import annotations

from uuid import uuid4
from datetime import date
import math
import re

from ..contracts.project_master import ProjectMasterImportIssue, ProjectMasterSnapshot
from .definitions import COMPONENT_TYPES, STRUCTURE_TYPES, WORKPOINT_TYPES


def validate_snapshot(snapshot: ProjectMasterSnapshot) -> list[ProjectMasterImportIssue]:
    issues: list[ProjectMasterImportIssue] = []
    _validate_unique_ids(snapshot, issues)
    _validate_route_placements(snapshot, issues)
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
            if workpoint.workpoint_type == "pavement":
                _validate_pavement_structure(structure, issues)
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
        if workpoint.workpoint_type == "pavement":
            _validate_pavement_overlaps(workpoint, issues)
    return issues


PAVEMENT_COMPONENT_TYPES = {"granular_base", "cement_stabilized_base", "asphalt_course"}


def resolve_roadbed_handover(properties):
    """One interpretation for master data, generated tasks and direct solve; no remark guessing."""
    raw_date = properties.get("roadbed_available_date")
    explicit = properties.get("roadbed_handover_status")
    status = explicit or ("dated" if raw_date else "pending")
    if status not in {"dated", "handed_over", "pending"}:
        raise ValueError("路床移交状态应为指定日期、已移交或移交待定。")
    available = None
    if raw_date:
        try: available = date.fromisoformat(str(raw_date)).isoformat()
        except (ValueError, TypeError): raise ValueError("路床移交日期应为有效的 YYYY-MM-DD。")
    if status == "dated" and available is None:
        raise ValueError("指定日期的施工段必须填写路床移交日期。")
    if status != "dated" and available is not None:
        raise ValueError("已移交或移交待定的施工段不应填写有效移交日期。")
    note = str(properties.get("roadbed_handover_note") or "").strip()
    if status == "pending" and not note:
        note = "移交日期未定，暂不可开工" if explicit else "尚未明确移交条件"
    return status, available, note


def roadbed_start_offset(properties, start_date, *, allow_pending=False):
    status, available, _ = resolve_roadbed_handover(properties)
    if status == "pending" and not allow_pending:
        raise ValueError("路床移交待定，暂不可开工。")
    return max(0, (date.fromisoformat(available) - start_date).days) if available else 0


def pavement_quantity_errors(properties, quantity, unit):
    """Shared by import diagnostics and scheduling; never infer a tonnage density."""
    errors = []
    if unit not in {"m", "m2", "m3", "t"}:
        errors.append(("PAVEMENT_UNIT_MISMATCH", "工程量单位必须为 m、m2、m3 或 t。"))
    basis = properties.get("quantity_basis")
    if basis not in {"entered", "geometric"}:
        errors.append(("PAVEMENT_DATA_INCOMPLETE", "请填写数量依据 entered 或 geometric。"))
    if properties.get("quantity_basis_confirmed") is not True or not properties.get("quantity_basis_note"):
        errors.append(("PAVEMENT_QUANTITY_BASIS_UNCONFIRMED", "请确认净量来源及扣除说明。"))
    dimensions = {}
    for field in ("construction_length_m", "width_m", "thickness_m"):
        # Length-based productivity does not use thickness to calculate duration.
        if unit == "m" and field == "thickness_m":
            continue
        try:
            value = float(properties[field])
            if not math.isfinite(value) or value <= 0:
                raise ValueError()
            dimensions[field] = value
        except (ValueError, TypeError, KeyError):
            errors.append(("PAVEMENT_DATA_INCOMPLETE", f"{field} 必须为正数。"))
    if quantity <= 0 or not math.isfinite(quantity):
        errors.append(("PAVEMENT_DATA_INCOMPLETE", "启用结构层工程量必须大于0。"))
    if basis == "geometric":
        if unit == "t":
            errors.append(("PAVEMENT_UNIT_MISMATCH", "吨数只能使用明确提供的工程量。"))
        elif unit in {"m", "m2", "m3"} and len(dimensions) == (2 if unit == "m" else 3):
            expected = dimensions["construction_length_m"]
            if unit in {"m2", "m3"}: expected *= dimensions["width_m"]
            if unit == "m3": expected *= dimensions["thickness_m"]
            if not math.isclose(quantity, expected, rel_tol=1e-6, abs_tol=1e-6):
                errors.append(("PAVEMENT_QUANTITY_BASIS_UNCONFIRMED", f"几何量为 {expected:g}{unit}，填报量为 {quantity:g}{unit}；请修正或改为 entered 并说明差异。"))
    return errors


def _validate_pavement_structure(structure, issues):
    def add(code, message, obj=structure, severity="warning", field=None):
        source = obj.source
        issues.append(_issue(severity, code, source.sheet_name if source else "结构物信息", source.row_no if source else None, field, message, getattr(obj, "component_id", structure.structure_id)))
    params = {p.parameter_code: p.value for p in structure.parameters}
    if structure.structure_category != "pavement" or structure.side == "shared":
        add("PAVEMENT_REFERENCE_INVALID", "路面结构类别应为 pavement；幅别为 left/right/none。", severity="error")
    for field in ("start_chainage", "end_chainage"):
        if not params.get(field): add("PAVEMENT_DATA_INCOMPLETE", f"请填写 {field}。", field=f"param.{field}")
    pending = False
    try: pending = resolve_roadbed_handover(params)[0] == "pending"
    except ValueError as exc: add("PAVEMENT_ROADBED_INVALID", str(exc), severity="error")
    orders = [c.sort_order for c in structure.components if c.enabled]
    if len(orders) != len(set(orders)) or any(n <= 0 for n in orders):
        add("PAVEMENT_LAYER_ORDER_INVALID", "启用结构层需填写不重复的正整数层序（由下至上）。")
    if not structure.components: add("PAVEMENT_DATA_INCOMPLETE", "施工段尚未配置结构层。")
    for component in structure.components:
        if component.component_type not in PAVEMENT_COMPONENT_TYPES:
            add("PAVEMENT_REFERENCE_INVALID", "路面仅支持碎石、水稳、沥青结构层。", obj=component, severity="error")
        if component.enabled:
            properties = {**params, **{p.parameter_code: p.value for p in component.parameters}}
            for code, message in pavement_quantity_errors(properties, component.quantity, component.unit):
                add(code, message, obj=component)
            if pending:
                for key in ("construction_length_m", "width_m", "thickness_m"):
                    if component.unit == "m" and key == "thickness_m":
                        continue
                    if properties.get(key) not in (None, ""):
                        try:
                            value = float(properties[key])
                            if not math.isfinite(value) or value <= 0: raise ValueError()
                        except (ValueError, TypeError): add("PAVEMENT_DATA_INVALID", f"{key} 必须为正数。", obj=component, severity="error")
                if component.unit not in {"m", "m2", "m3", "t"}:
                    add("PAVEMENT_UNIT_MISMATCH", "结构层计量单位无效。", obj=component, severity="error")


def _validate_pavement_overlaps(workpoint, issues):
    ranges = []
    for structure in workpoint.structures:
        params = {p.parameter_code: p.value for p in structure.parameters}
        parsed = [re.fullmatch(r"([A-Za-z]*)(\d+)\+(\d+(?:\.\d+)?)", str(params.get(k, ""))) for k in ("start_chainage", "end_chainage")]
        if not all(parsed) or parsed[0][1].upper() != parsed[1][1].upper(): continue
        start, end = [float(p[2]) * 1000 + float(p[3]) for p in parsed]
        source = structure.source
        if end <= start:
            issues.append(_issue("error", "PAVEMENT_CHAINAGE_INVALID", "结构物信息", source.row_no if source else None, "param.end_chainage", "终点桩号应大于起点桩号。", structure.structure_id))
        for prefix, side, a, b in ranges:
            if prefix == parsed[0][1].upper() and side == structure.side and max(start, a) < min(end, b):
                issues.append(_issue("warning", "PAVEMENT_SECTION_OVERLAP", "结构物信息", source.row_no if source else None, "param.start_chainage", "同线路同幅施工段桩号范围重叠，请核对净量与施工范围。", structure.structure_id))
        ranges.append((parsed[0][1].upper(), structure.side, start, end))


def _validate_route_placements(
    snapshot: ProjectMasterSnapshot,
    issues: list[ProjectMasterImportIssue],
) -> None:
    workpoint_ids = {item.workpoint_id.casefold() for item in snapshot.workpoints}
    seen: dict[tuple[str, str], str] = {}
    for placement in snapshot.route_placements:
        source = placement.source
        sheet = source.sheet_name if source else "线路关系"
        row_no = source.row_no if source else None
        if placement.workpoint_id.casefold() not in workpoint_ids:
            issues.append(
                _issue(
                    "error",
                    "PARENT_WORKPOINT_NOT_FOUND",
                    sheet,
                    row_no,
                    "workpoint_id",
                    f"线路落位所属工点 {placement.workpoint_id} 不存在。",
                    placement.placement_id,
                )
            )
        if placement.side not in {"left", "right"}:
            issues.append(
                _issue(
                    "error",
                    "ROUTE_SIDE_INVALID",
                    sheet,
                    row_no,
                    "side",
                    f"线路落位幅别 {placement.side} 不合法，应为 left 或 right。",
                    placement.placement_id,
                )
            )
        duplicate_key = (placement.workpoint_id.casefold(), str(placement.side).casefold())
        if duplicate_key in seen:
            issues.append(
                _issue(
                    "error",
                    "ROUTE_PLACEMENT_DUPLICATE",
                    sheet,
                    row_no,
                    "side",
                    f"工点 {placement.workpoint_id} 的 {placement.side} 幅存在重复线路落位。",
                    placement.placement_id,
                )
            )
        else:
            seen[duplicate_key] = placement.placement_id
        if not str(placement.mileage_prefix).strip():
            issues.append(
                _issue(
                    "error",
                    "ROUTE_MILEAGE_PREFIX_MISSING",
                    sheet,
                    row_no,
                    "mileage_prefix",
                    "线路落位里程前缀不能为空。",
                    placement.placement_id,
                )
            )
        if not str(placement.spatial_group_id).strip():
            issues.append(
                _issue(
                    "error",
                    "ROUTE_SPATIAL_GROUP_MISSING",
                    sheet,
                    row_no,
                    "spatial_group_id",
                    "线路落位空间对应组不能为空。",
                    placement.placement_id,
                )
            )
        if (placement.start_mileage_m is None) != (placement.end_mileage_m is None):
            issues.append(
                _issue(
                    "error",
                    "ROUTE_MILEAGE_INCOMPLETE",
                    sheet,
                    row_no,
                    "start_mileage_m",
                    "线路落位起点和终点里程必须同时填写。",
                    placement.placement_id,
                )
            )
        if (
            placement.start_mileage_m is not None
            and placement.end_mileage_m is not None
            and placement.end_mileage_m < placement.start_mileage_m
        ):
            issues.append(
                _issue(
                    "error",
                    "ROUTE_MILEAGE_RANGE_INVALID",
                    sheet,
                    row_no,
                    "end_mileage_m",
                    "线路落位终点里程不得小于起点里程。",
                    placement.placement_id,
                )
            )


def _validate_unique_ids(snapshot: ProjectMasterSnapshot, issues: list[ProjectMasterImportIssue]) -> None:
    seen: dict[str, tuple[str, str]] = {}
    objects = []
    for workpoint in snapshot.workpoints:
        objects.append(("workpoint", workpoint.workpoint_id, workpoint.source))
        for structure in workpoint.structures:
            objects.append(("structure", structure.structure_id, structure.source))
            for component in structure.components:
                objects.append(("component", component.component_id, component.source))
    for placement in snapshot.route_placements:
        objects.append(("route_placement", placement.placement_id, placement.source))
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
