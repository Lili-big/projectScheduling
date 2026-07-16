from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..contracts import (
    GirderExecutionActual,
    GirderMachineActual,
    GirderProgressImportPreview,
    PassageActual,
    ValidationMessage,
    YardInventoryActual,
)
from .import_service import GirderImportError, _normalize_text, _read_rows


class GirderProgressImportError(ValueError):
    status_code = 422


_ALIASES: dict[str, tuple[str, ...]] = {
    "record_type": ("记录类型", "实绩类型", "类型", "type", "record_type"),
    "beam_yard_id": ("梁场ID", "梁场", "beam_yard_id"),
    "beam_type": ("梁型", "梁片类型", "beam_type"),
    "cumulative_produced": ("累计生产", "累计生产量", "cumulative_produced"),
    "opening_inventory_adjustment": ("期初调整", "期初库存调整", "opening_inventory_adjustment"),
    "observed_inventory": ("盘点库存", "实盘库存", "observed_inventory"),
    "span_task_id": ("分跨任务ID", "架梁任务ID", "span_task_id"),
    "status": ("状态", "实绩状态", "status"),
    "actual_route_id": ("实际路线ID", "路线ID", "actual_route_id"),
    "actual_start_date": ("实际开始日期", "开始日期", "actual_start_date"),
    "actual_finish_date": ("实际完成日期", "完成日期", "actual_finish_date"),
    "erected_beam_count": ("已架梁片数", "架梁片数", "erected_beam_count"),
    "erection_machine_id": ("架桥机ID", "架桥机", "erection_machine_id"),
    "position_workpoint_id": ("当前位置工点ID", "当前位置", "position_workpoint_id"),
    "availability_status": ("可用状态", "设备状态", "availability_status"),
    "expected_resume_date": ("预计恢复日期", "恢复日期", "expected_resume_date"),
    "reason": ("原因", "说明", "reason"),
    "workpoint_id": ("工点ID", "通道工点ID", "workpoint_id"),
    "actual_open_date": ("实际开放日期", "开放日期", "actual_open_date"),
    "restrictions": ("通行限制", "限制说明", "restrictions"),
}


def import_progress_actuals(*, file_name: str, content: bytes) -> GirderProgressImportPreview:
    try:
        rows, _ = _read_rows(file_name, content)
    except GirderImportError as exc:
        raise GirderProgressImportError(str(exc)) from exc
    if not rows:
        raise GirderProgressImportError("架梁实绩文件没有可读取的数据行。")
    header_index, headers = _find_headers(rows)
    indexes = _field_indexes(headers)
    if "record_type" not in indexes:
        raise GirderProgressImportError("架梁实绩文件缺少“记录类型/类型”列，无法区分库存、架梁、设备和通道实绩。")

    preview = GirderProgressImportPreview(source_file_name=file_name)
    for row_no, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        values = {field: _cell(row, index) for field, index in indexes.items()}
        if not any(value not in {None, ""} for value in values.values()):
            continue
        kind = _record_kind(values.get("record_type"), values)
        try:
            if kind == "inventory":
                preview.yard_inventory_actuals.append(_inventory(values, row_no))
            elif kind == "execution":
                preview.girder_execution_actuals.append(_execution(values, row_no))
            elif kind == "machine":
                preview.girder_machine_actuals.append(_machine(values, row_no))
            elif kind == "passage":
                preview.passage_actuals.append(_passage(values, row_no))
            else:
                preview.diagnostics.append(_message("error", "GIRDER_PROGRESS_UNKNOWN_TYPE", f"第 {row_no} 行记录类型无法识别。", f"row:{row_no}"))
        except ValueError as exc:
            preview.diagnostics.append(_message("error", "GIRDER_PROGRESS_INVALID_ROW", f"第 {row_no} 行无法导入：{exc}", f"row:{row_no}"))
    return preview


def _inventory(values: dict[str, Any], row_no: int) -> YardInventoryActual:
    return YardInventoryActual(
        beam_yard_id=_required(values, "beam_yard_id", row_no),
        beam_type=_required(values, "beam_type", row_no),
        cumulative_produced=_number(values.get("cumulative_produced"), "累计生产", row_no),
        opening_inventory_adjustment=_number(values.get("opening_inventory_adjustment"), "期初调整", row_no, default=0),
        observed_inventory=_number(values.get("observed_inventory"), "盘点库存", row_no),
        source="excel",
    )


def _execution(values: dict[str, Any], row_no: int) -> GirderExecutionActual:
    status = _status(values.get("status"), {"未开始": "not_started", "进行中": "in_progress", "已完成": "completed"}, "架梁状态", row_no)
    return GirderExecutionActual(
        span_task_id=_required(values, "span_task_id", row_no),
        status=status,
        actual_route_id=_optional_text(values.get("actual_route_id")),
        actual_start_date=_date_value(values.get("actual_start_date"), "实际开始日期", row_no),
        actual_finish_date=_date_value(values.get("actual_finish_date"), "实际完成日期", row_no),
        erected_beam_count=int(_number(values.get("erected_beam_count"), "已架梁片数", row_no, default=0)),
        erection_machine_id=_optional_text(values.get("erection_machine_id")),
    )


def _machine(values: dict[str, Any], row_no: int) -> GirderMachineActual:
    status = _status(
        values.get("availability_status"),
        {"可用": "available", "不可用": "unavailable", "检修": "maintenance"},
        "设备状态",
        row_no,
    )
    return GirderMachineActual(
        erection_machine_id=_required(values, "erection_machine_id", row_no),
        position_workpoint_id=_optional_text(values.get("position_workpoint_id")),
        availability_status=status,
        expected_resume_date=_date_value(values.get("expected_resume_date"), "预计恢复日期", row_no),
        reason=_optional_text(values.get("reason")),
    )


def _passage(values: dict[str, Any], row_no: int) -> PassageActual:
    status = _status(values.get("status"), {"关闭": "closed", "有条件开放": "conditional", "开放": "open"}, "通道状态", row_no)
    return PassageActual(
        workpoint_id=_required(values, "workpoint_id", row_no),
        status=status,
        actual_open_date=_date_value(values.get("actual_open_date"), "实际开放日期", row_no),
        restrictions=_optional_text(values.get("restrictions")),
    )


def _record_kind(value: Any, values: dict[str, Any]) -> str | None:
    text = _normalize_text(value)
    mapping = {
        "库存": "inventory",
        "梁场库存": "inventory",
        "inventory": "inventory",
        "架梁": "execution",
        "架梁实绩": "execution",
        "execution": "execution",
        "设备": "machine",
        "架桥机": "machine",
        "machine": "machine",
        "通道": "passage",
        "通行": "passage",
        "passage": "passage",
    }
    if text in mapping:
        return mapping[text]
    if values.get("span_task_id") not in {None, ""}:
        return "execution"
    if values.get("workpoint_id") not in {None, ""}:
        return "passage"
    if values.get("beam_yard_id") not in {None, ""}:
        return "inventory"
    if values.get("erection_machine_id") not in {None, ""}:
        return "machine"
    return None


def _find_headers(rows: list[list[Any]]) -> tuple[int, list[str]]:
    best_index = 0
    best_score = -1
    aliases = {_normalize_text(alias) for values in _ALIASES.values() for alias in values}
    for index, row in enumerate(rows[:20]):
        score = sum(_normalize_text(value) in aliases for value in row)
        if score > best_score:
            best_index, best_score = index, score
    return best_index, [str(value or "").strip() for value in rows[best_index]]


def _field_indexes(headers: list[str]) -> dict[str, int]:
    normalized = [_normalize_text(item) for item in headers]
    result: dict[str, int] = {}
    for field, aliases in _ALIASES.items():
        alias_set = {_normalize_text(alias) for alias in aliases}
        index = next((idx for idx, value in enumerate(normalized) if value in alias_set), None)
        if index is not None:
            result[field] = index
    return result


def _cell(row: list[Any], index: int) -> Any:
    return row[index] if index < len(row) else None


def _required(values: dict[str, Any], field: str, row_no: int) -> str:
    value = _optional_text(values.get(field))
    if not value:
        raise ValueError(f"缺少 {field}")
    return value


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value not in {None, ""} else ""
    return text or None


def _number(value: Any, label: str, row_no: int, *, default: float | None = None) -> float:
    if value in {None, ""}:
        if default is not None:
            return default
        raise ValueError(f"缺少 {label}")
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}不是数字") from exc


def _date_value(value: Any, label: str, row_no: int) -> date | None:
    if value in {None, ""}:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("/", "-")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{label}必须使用 YYYY-MM-DD") from exc


def _status(value: Any, chinese_mapping: dict[str, str], label: str, row_no: int) -> str:
    text = _normalize_text(value)
    mapping = {**{_normalize_text(key): value for key, value in chinese_mapping.items()}, **{value: value for value in chinese_mapping.values()}}
    if text not in mapping:
        raise ValueError(f"{label}值不支持")
    return mapping[text]


def _message(level: str, code: str, message: str, subject_id: str | None = None) -> ValidationMessage:
    return ValidationMessage(level=level, code=code, message=message, subject_id=subject_id)
