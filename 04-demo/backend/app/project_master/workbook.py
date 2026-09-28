from __future__ import annotations

import hashlib
import json
import posixpath
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree
from zipfile import ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from ..contracts.project_master import (
    ParameterValue,
    ProjectMasterComponent,
    ProjectMasterImportIssue,
    ProjectMasterRoutePlacement,
    ProjectMasterSnapshot,
    ProjectMasterStructure,
    ProjectMasterWorkpoint,
    SourceEvidence,
)
from .definitions import DEFINITION_VERSION, schedule_support_for


TEMPLATE_VERSION = "1.2"
SUPPORTED_TEMPLATE_VERSIONS = {"1.0", "1.1", TEMPLATE_VERSION}
REQUIRED_SHEETS = ("填写说明", "工点信息", "结构物信息", "构件参数")
SHEETS = (*REQUIRED_SHEETS, "线路关系")
_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOCUMENT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WORKPOINT_COLUMNS = (
    ("workpoint_id", "工点ID"),
    ("workpoint_name", "工点名称"),
    ("workpoint_type", "工点类型"),
    ("alignment_code", "线路编码"),
    ("start_mileage_m", "起点里程(m)"),
    ("end_mileage_m", "终点里程(m)"),
    ("sort_order", "排序号"),
    ("remark", "备注"),
)
ROUTE_PLACEMENT_COLUMNS = (
    ("placement_id", "线路落位ID"),
    ("workpoint_id", "所属工点ID"),
    ("side", "幅别"),
    ("mileage_prefix", "里程前缀"),
    ("start_mileage_m", "起点里程(m)"),
    ("end_mileage_m", "终点里程(m)"),
    ("spatial_group_id", "空间对应组"),
    ("display_order", "展示顺序"),
)
STRUCTURE_COLUMNS = (
    ("structure_id", "结构物ID"),
    ("workpoint_id", "所属工点ID"),
    ("structure_name", "结构物名称"),
    ("structure_category", "结构类别"),
    ("structure_type", "结构类型"),
    ("side", "幅别"),
    ("section_code", "工区编码"),
    ("section_name", "工区名称"),
    ("control_level", "受控级别"),
    ("sort_order", "排序号"),
    ("remark", "备注"),
    ("param.span_index", "跨序号"),
    ("param.span_length_m", "跨径(m)"),
    ("param.bearing_from", "起点墩台"),
    ("param.bearing_to", "终点墩台"),
    ("param.span_expression", "联跨表达式"),
    ("param.main_pier_ids", "主墩ID"),
    ("param.segment_count", "节段数量"),
    ("param.beam_count_per_span", "每跨梁片数"),
)
COMPONENT_COLUMNS = (
    ("component_id", "构件ID"),
    ("structure_id", "所属结构物ID"),
    ("component_name", "构件名称"),
    ("component_type", "构件类型"),
    ("quantity", "工程量"),
    ("unit", "单位"),
    ("enabled", "是否启用"),
    ("sort_order", "排序号"),
    ("remark", "备注"),
    ("param.diameter_m", "直径(m)"),
    ("param.length_m", "长度(m)"),
    ("param.height_m", "高度(m)"),
    ("param.form", "结构形式"),
)


PAVEMENT_STRUCTURE_COLUMNS = tuple(("param." + code, label) for code, label in [
    ("start_chainage", "起点桩号（原文）"), ("end_chainage", "终点桩号（原文）"),
    ("construction_length_m", "确认净施工长度(m)"), ("width_m", "宽度(m)"),
    ("water_stable_thickness_m", "水稳厚度(m)"), ("water_stable_density_t_m3", "水稳密度(t/m³)"),
    ("roadbed_available_date", "路床最早可用日期"), ("quantity_basis_confirmed", "净量依据已确认（是/否）"),
    ("roadbed_handover_status", "路床移交状态（dated/handed_over/pending）"), ("roadbed_handover_note", "路床移交说明"),
    ("quantity_basis_note", "净量来源与扣除说明")])
PAVEMENT_COMPONENT_COLUMNS = (("param.thickness_m", "厚度(m；也可填20cm)"), ("param.density_t_m3", "密度(t/m³)"), ("param.quantity_basis", "数量依据 entered/geometric"), ("param.quantity_basis_note", "数量说明"))
STRUCTURE_COLUMNS += PAVEMENT_STRUCTURE_COLUMNS
COMPONENT_COLUMNS += PAVEMENT_COMPONENT_COLUMNS


def create_template_bytes(engineering_domain: str = "bridge") -> bytes:
    workbook = Workbook()
    guide = workbook.active
    guide.title = "填写说明"
    guide.append(["template_version", TEMPLATE_VERSION])
    guide.append(["definition_version", DEFINITION_VERSION])
    guide.append(["导入语义", "每次上传均为当前项目完整主数据快照；不兼容旧桥梁/架梁工点模板。"])
    guide.append(["层级", "工点 → 结构物 → 构件参数；一座桥梁只维护一个工点，左右幅写在结构物 side。"])
    guide.append(["幅别", "left=左幅，right=右幅，shared=共用，none=不适用（桥梁正式结构慎用）。"])
    guide.append(["参数列", "类型特有参数使用 param.<parameter_code>，不得写 JSON。"])
    guide.append(["线路关系", "可选；每个工点每个幅别一行，同一空间对应组仅表示左右平行对齐，不自动形成通行连接。"])
    if engineering_domain == "pavement":
        guide.append(["路面填写", "工点类型 pavement；结构类别 pavement，结构类型 pavement_section；每段每幅独立ID。"])
        guide.append(["结构层", "granular_base=碎石；cement_stabilized_base=水稳；asphalt_course=沥青；sort_order 填实际由下至上层序。"])
        guide.append(["示例（非客户数据）", "K0+000～K0+800，扣除桥涵后净长760m；水稳20cm填写0.2m；数量依据 entered，净量确认是并说明来源。"])
        guide.append(["必填排程条件", "净长度、宽度、路床最早可用日期、净量确认与说明；每层厚度、数量、单位与依据。吨数必须明确提供。"])
        guide.append(["模板数据", "数据页留空，请填入本项目确认数据。养生和转场在场景页面单独确认。"])
    _style_sheet(guide)
    _append_data_sheet(workbook, "工点信息", WORKPOINT_COLUMNS)
    _append_data_sheet(workbook, "结构物信息", STRUCTURE_COLUMNS)
    _append_data_sheet(workbook, "构件参数", COMPONENT_COLUMNS)
    _append_data_sheet(workbook, "线路关系", ROUTE_PLACEMENT_COLUMNS)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def parse_workbook(content: bytes) -> tuple[ProjectMasterSnapshot, list[ProjectMasterImportIssue], str]:
    issues: list[ProjectMasterImportIssue] = []
    try:
        sheets = _read_xlsx_sheets(content)
    except Exception as exc:
        issue = _issue("error", "WORKBOOK_INVALID", "填写说明", None, None, f"Excel 文件无法读取：{exc}")
        return ProjectMasterSnapshot(), [issue], _fingerprint(ProjectMasterSnapshot())

    missing = [name for name in REQUIRED_SHEETS if name not in sheets]
    if missing:
        issues.append(
            _issue(
                "error",
                "SHEET_MISSING",
                "填写说明",
                None,
                None,
                f"缺少工作表：{'、'.join(missing)}。",
                "请使用当前统一项目主数据模板。",
            )
        )
        return ProjectMasterSnapshot(), issues, _fingerprint(ProjectMasterSnapshot())

    guide_rows = dict(sheets["填写说明"])
    first_row = guide_rows.get(1, ())
    template_version = _text(first_row[1] if len(first_row) > 1 else None)
    if template_version not in SUPPORTED_TEMPLATE_VERSIONS:
        issues.append(
            _issue(
                "error",
                "TEMPLATE_VERSION_UNSUPPORTED",
                "填写说明",
                1,
                "template_version",
                f"模板版本 {template_version or '空'} 不受支持，当前支持 1.0 和 {TEMPLATE_VERSION}。",
            )
        )

    workpoint_rows = _read_rows("工点信息", sheets["工点信息"], issues)
    structure_rows = _read_rows("结构物信息", sheets["结构物信息"], issues)
    component_rows = _read_rows("构件参数", sheets["构件参数"], issues)
    route_placement_rows = _read_rows("线路关系", sheets.get("线路关系", []), issues) if "线路关系" in sheets else []

    workpoints: list[ProjectMasterWorkpoint] = []
    workpoint_by_key: dict[str, ProjectMasterWorkpoint] = {}
    for row_no, row in workpoint_rows:
        object_id = _text(row.get("workpoint_id"))
        name = _text(row.get("workpoint_name"))
        workpoint_type = _text(row.get("workpoint_type")).lower()
        if not object_id or not name or not workpoint_type:
            issues.append(_issue("error", "REQUIRED_FIELD", "工点信息", row_no, None, "工点ID、工点名称和工点类型不能为空。"))
            continue
        try:
            item = ProjectMasterWorkpoint.model_construct(
                workpoint_id=object_id,
                workpoint_name=name,
                workpoint_type=workpoint_type,
                alignment_code=_optional_text(row.get("alignment_code")),
                start_mileage_m=_optional_float(row.get("start_mileage_m")),
                end_mileage_m=_optional_float(row.get("end_mileage_m")),
                sort_order=_non_negative_integer(row.get("sort_order"), 0),
                schedule_support=schedule_support_for(workpoint_type),
                remark=_optional_text(row.get("remark")),
                source=SourceEvidence.model_construct(
                    batch_id=None,
                    sheet_name="工点信息",
                    row_no=row_no,
                    column_name=None,
                ),
            )
        except Exception as exc:
            issues.append(_issue("error", "FIELD_TYPE_INVALID", "工点信息", row_no, None, str(exc), object_id=object_id))
            continue
        workpoints.append(item)
        workpoint_by_key[object_id.casefold()] = item

    route_placements: list[ProjectMasterRoutePlacement] = []
    for row_no, row in route_placement_rows:
        object_id = _text(row.get("placement_id"))
        parent_id = _text(row.get("workpoint_id"))
        if not object_id or not parent_id:
            issues.append(
                _issue(
                    "error",
                    "REQUIRED_FIELD",
                    "线路关系",
                    row_no,
                    None,
                    "线路落位ID和所属工点ID不能为空。",
                    object_kind="route_placement",
                    object_id=object_id or None,
                )
            )
            continue
        if parent_id.casefold() not in workpoint_by_key:
            issues.append(
                _issue(
                    "error",
                    "PARENT_WORKPOINT_NOT_FOUND",
                    "线路关系",
                    row_no,
                    "workpoint_id",
                    f"所属工点 {parent_id} 不存在。",
                    object_kind="route_placement",
                    object_id=object_id,
                )
            )
        try:
            placement = ProjectMasterRoutePlacement.model_construct(
                placement_id=object_id,
                workpoint_id=parent_id,
                side=_text(row.get("side")).lower(),
                mileage_prefix=_text(row.get("mileage_prefix")).upper(),
                start_mileage_m=_optional_float(row.get("start_mileage_m")),
                end_mileage_m=_optional_float(row.get("end_mileage_m")),
                spatial_group_id=_text(row.get("spatial_group_id")),
                display_order=_non_negative_integer(row.get("display_order"), 0),
                source=SourceEvidence.model_construct(
                    batch_id=None,
                    sheet_name="线路关系",
                    row_no=row_no,
                    column_name=None,
                ),
            )
        except Exception as exc:
            issues.append(
                _issue(
                    "error",
                    "FIELD_TYPE_INVALID",
                    "线路关系",
                    row_no,
                    None,
                    str(exc),
                    object_kind="route_placement",
                    object_id=object_id,
                )
            )
            continue
        route_placements.append(placement)

    structure_by_key: dict[str, ProjectMasterStructure] = {}
    for row_no, row in structure_rows:
        object_id = _text(row.get("structure_id"))
        parent_id = _text(row.get("workpoint_id"))
        if not object_id or not parent_id:
            issues.append(_issue("error", "REQUIRED_FIELD", "结构物信息", row_no, None, "结构物ID和所属工点ID不能为空。"))
            continue
        parent = workpoint_by_key.get(parent_id.casefold())
        if parent is None:
            issues.append(
                _issue(
                    "error",
                    "PARENT_WORKPOINT_NOT_FOUND",
                    "结构物信息",
                    row_no,
                    "workpoint_id",
                    f"所属工点 {parent_id} 不存在。",
                    object_kind="structure",
                    object_id=object_id,
                )
            )
            continue
        try:
            parameters = _parameters(row, "结构物信息", row_no)
            structure = ProjectMasterStructure.model_construct(
                structure_id=object_id,
                workpoint_id=parent.workpoint_id,
                structure_name=_text(row.get("structure_name")),
                structure_category=_text(row.get("structure_category")).lower(),
                structure_type=_text(row.get("structure_type")).lower(),
                side=_text(row.get("side")).lower(),
                section_code=_optional_text(row.get("section_code")),
                section_name=_optional_text(row.get("section_name")),
                control_level=_optional_text(row.get("control_level")),
                sort_order=_non_negative_integer(row.get("sort_order"), 0),
                remark=_optional_text(row.get("remark")),
                parameters=parameters,
                source=SourceEvidence.model_construct(
                    batch_id=None,
                    sheet_name="结构物信息",
                    row_no=row_no,
                    column_name=None,
                ),
            )
        except Exception as exc:
            issues.append(_issue("error", "FIELD_TYPE_INVALID", "结构物信息", row_no, None, str(exc), object_id=object_id))
            continue
        parent.structures.append(structure)
        structure_by_key[object_id.casefold()] = structure

    for row_no, row in component_rows:
        object_id = _text(row.get("component_id"))
        parent_id = _text(row.get("structure_id"))
        if not object_id or not parent_id:
            issues.append(_issue("error", "REQUIRED_FIELD", "构件参数", row_no, None, "构件ID和所属结构物ID不能为空。"))
            continue
        parent = structure_by_key.get(parent_id.casefold())
        if parent is None:
            issues.append(
                _issue(
                    "error",
                    "PARENT_STRUCTURE_NOT_FOUND",
                    "构件参数",
                    row_no,
                    "structure_id",
                    f"所属结构物 {parent_id} 不存在。",
                    object_kind="component",
                    object_id=object_id,
                )
            )
            continue
        try:
            component = ProjectMasterComponent.model_construct(
                component_id=object_id,
                structure_id=parent.structure_id,
                component_name=_text(row.get("component_name")),
                component_type=_text(row.get("component_type")).lower(),
                quantity=_non_negative_number(row.get("quantity")),
                unit=_text(row.get("unit")),
                enabled=_boolean(row.get("enabled"), True),
                sort_order=_non_negative_integer(row.get("sort_order"), 0),
                remark=_optional_text(row.get("remark")),
                parameters=_parameters(row, "构件参数", row_no),
                source=SourceEvidence.model_construct(
                    batch_id=None,
                    sheet_name="构件参数",
                    row_no=row_no,
                    column_name=None,
                ),
            )
        except Exception as exc:
            issues.append(_issue("error", "FIELD_TYPE_INVALID", "构件参数", row_no, None, str(exc), object_id=object_id))
            continue
        parent.components.append(component)

    # Cell values are normalized above and semantic validation runs immediately
    # after parsing. Avoid re-validating the complete 50k+ object tree here;
    # doing so dominates large-workbook import time without adding row-local
    # diagnostics beyond the checks already performed in this module.
    snapshot = ProjectMasterSnapshot.model_construct(
        workpoints=workpoints,
        route_placements=route_placements,
    )
    return snapshot, issues, _fingerprint(snapshot)


def export_snapshot(snapshot: ProjectMasterSnapshot) -> bytes:
    workbook = load_workbook(BytesIO(create_template_bytes()))
    workpoint_sheet = workbook["工点信息"]
    structure_sheet = workbook["结构物信息"]
    component_sheet = workbook["构件参数"]
    route_placement_sheet = workbook["线路关系"]
    workpoint_headers = [code for code, _ in WORKPOINT_COLUMNS]
    structure_headers = [cell.value for cell in structure_sheet[1]]
    component_headers = [cell.value for cell in component_sheet[1]]
    for workpoint in snapshot.workpoints:
        workpoint_sheet.append(
            [
                workpoint.workpoint_id,
                workpoint.workpoint_name,
                workpoint.workpoint_type,
                workpoint.alignment_code,
                workpoint.start_mileage_m,
                workpoint.end_mileage_m,
                workpoint.sort_order,
                workpoint.remark,
            ]
        )
        for structure in workpoint.structures:
            values: dict[str, Any] = {
                "structure_id": structure.structure_id,
                "workpoint_id": workpoint.workpoint_id,
                "structure_name": structure.structure_name,
                "structure_category": structure.structure_category,
                "structure_type": structure.structure_type,
                "side": structure.side,
                "section_code": structure.section_code,
                "section_name": structure.section_name,
                "control_level": structure.control_level,
                "sort_order": structure.sort_order,
                "remark": structure.remark,
            }
            values.update({f"param.{item.parameter_code}": item.value for item in structure.parameters})
            structure_sheet.append([values.get(header) for header in structure_headers])
            for component in structure.components:
                component_values: dict[str, Any] = {
                    "component_id": component.component_id,
                    "structure_id": structure.structure_id,
                    "component_name": component.component_name,
                    "component_type": component.component_type,
                    "quantity": component.quantity,
                    "unit": component.unit,
                    "enabled": "是" if component.enabled else "否",
                    "sort_order": component.sort_order,
                    "remark": component.remark,
                }
                component_values.update({f"param.{item.parameter_code}": item.value for item in component.parameters})
                component_sheet.append([component_values.get(header) for header in component_headers])
    for placement in snapshot.route_placements:
        route_placement_sheet.append(
            [
                placement.placement_id,
                placement.workpoint_id,
                placement.side,
                placement.mileage_prefix,
                placement.start_mileage_m,
                placement.end_mileage_m,
                placement.spatial_group_id,
                placement.display_order,
            ]
        )
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def content_fingerprint(snapshot: ProjectMasterSnapshot) -> str:
    return _fingerprint(snapshot)


def _append_data_sheet(workbook: Workbook, name: str, columns: tuple[tuple[str, str], ...]) -> None:
    sheet = workbook.create_sheet(name)
    sheet.append([code for code, _ in columns])
    sheet.append([label for _, label in columns])
    _style_sheet(sheet)


def _style_sheet(sheet: Any) -> None:
    sheet.freeze_panes = "A3" if sheet.title != "填写说明" else "A1"
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for index, column in enumerate(sheet.columns, start=1):
        width = max((len(str(cell.value or "")) for cell in column), default=10)
        sheet.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 12), 40)


def _read_rows(
    sheet_name: str,
    sheet_rows: list[tuple[int, tuple[Any, ...]]],
    issues: list[ProjectMasterImportIssue],
) -> list[tuple[int, dict[str, Any]]]:
    rows_by_number = dict(sheet_rows)
    headers = [_text(value) for value in rows_by_number.get(1, ())]
    if not headers or any(not header for header in headers):
        issues.append(_issue("error", "HEADER_INVALID", sheet_name, 1, None, "字段代码行存在空列或无法读取。"))
        return []
    rows: list[tuple[int, dict[str, Any]]] = []
    for row_no, values in sheet_rows:
        if row_no < 3:
            continue
        if all(value is None or _text(value) == "" for value in values):
            continue
        rows.append((row_no, {headers[index]: value for index, value in enumerate(values) if index < len(headers)}))
    return rows


def _read_xlsx_sheets(content: bytes) -> dict[str, list[tuple[int, tuple[Any, ...]]]]:
    """Read the four import sheets directly from OOXML.

    openpyxl is retained for template generation and export, while direct XML
    streaming keeps large import validation within the product's 30-second
    target. The reader handles shared/inline strings, booleans, cached formula
    values, ISO dates and Excel serial dates.
    """
    with ZipFile(BytesIO(content)) as archive:
        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships_root.findall(f"{{{_PACKAGE_REL_NS}}}Relationship")
        }
        date_1904 = workbook_root.find(f"{{{_SPREADSHEET_NS}}}workbookPr")
        uses_1904_epoch = date_1904 is not None and date_1904.attrib.get("date1904") in {"1", "true"}
        shared_strings = _read_shared_strings(archive)
        date_style_ids = _read_date_style_ids(archive)
        result: dict[str, list[tuple[int, tuple[Any, ...]]]] = {}
        sheets_root = workbook_root.find(f"{{{_SPREADSHEET_NS}}}sheets")
        if sheets_root is None:
            return result
        for sheet in sheets_root.findall(f"{{{_SPREADSHEET_NS}}}sheet"):
            name = sheet.attrib.get("name", "")
            if name not in SHEETS:
                continue
            relationship_id = sheet.attrib.get(f"{{{_DOCUMENT_REL_NS}}}id")
            target = relationships.get(relationship_id or "")
            if not target:
                continue
            path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            result[name] = _read_xlsx_sheet(
                archive,
                path,
                shared_strings=shared_strings,
                date_style_ids=date_style_ids,
                uses_1904_epoch=uses_1904_epoch,
            )
        return result


def _read_shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.iter(f"{{{_SPREADSHEET_NS}}}t"))
        for item in root.findall(f"{{{_SPREADSHEET_NS}}}si")
    ]


def _read_date_style_ids(archive: ZipFile) -> set[int]:
    if "xl/styles.xml" not in archive.namelist():
        return set()
    root = ElementTree.fromstring(archive.read("xl/styles.xml"))
    custom_formats = {
        int(item.attrib["numFmtId"]): item.attrib.get("formatCode", "")
        for item in root.findall(f".//{{{_SPREADSHEET_NS}}}numFmt")
    }
    date_number_formats = set(range(14, 23)) | {45, 46, 47}
    for number_format_id, format_code in custom_formats.items():
        normalized = format_code.lower().replace('"', "")
        if any(token in normalized for token in ("yy", "dd", "hh", "ss")):
            date_number_formats.add(number_format_id)
    cell_formats = root.find(f"{{{_SPREADSHEET_NS}}}cellXfs")
    if cell_formats is None:
        return set()
    return {
        index
        for index, item in enumerate(cell_formats.findall(f"{{{_SPREADSHEET_NS}}}xf"))
        if int(item.attrib.get("numFmtId", "0")) in date_number_formats
    }


def _read_xlsx_sheet(
    archive: ZipFile,
    path: str,
    *,
    shared_strings: list[str],
    date_style_ids: set[int],
    uses_1904_epoch: bool,
) -> list[tuple[int, tuple[Any, ...]]]:
    result: list[tuple[int, tuple[Any, ...]]] = []
    row_tag = f"{{{_SPREADSHEET_NS}}}row"
    cell_tag = f"{{{_SPREADSHEET_NS}}}c"
    with archive.open(path) as stream:
        for _, element in ElementTree.iterparse(stream, events=("end",)):
            if element.tag != row_tag:
                continue
            row_number = int(element.attrib.get("r", len(result) + 1))
            values: list[Any] = []
            for cell in element.findall(cell_tag):
                column_index = _column_index(cell.attrib.get("r", "A1"))
                if len(values) <= column_index:
                    values.extend([None] * (column_index + 1 - len(values)))
                values[column_index] = _xlsx_cell_value(
                    cell,
                    shared_strings=shared_strings,
                    date_style_ids=date_style_ids,
                    uses_1904_epoch=uses_1904_epoch,
                )
            result.append((row_number, tuple(values)))
            element.clear()
    return result


def _column_index(reference: str) -> int:
    value = 0
    for character in reference:
        if not character.isalpha():
            break
        value = value * 26 + ord(character.upper()) - ord("A") + 1
    return max(0, value - 1)


def _xlsx_cell_value(
    cell: Any,
    *,
    shared_strings: list[str],
    date_style_ids: set[int],
    uses_1904_epoch: bool,
) -> Any:
    data_type = cell.attrib.get("t", "n")
    if data_type == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{{{_SPREADSHEET_NS}}}t"))
    value_element = cell.find(f"{{{_SPREADSHEET_NS}}}v")
    if value_element is None or value_element.text is None:
        return None
    raw = value_element.text
    if data_type == "s":
        index = int(raw)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    if data_type == "b":
        return raw == "1"
    if data_type == "d":
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw
    if data_type in {"str", "e"}:
        return raw
    try:
        number = float(raw)
    except ValueError:
        return raw
    style_id = int(cell.attrib.get("s", "0"))
    if style_id in date_style_ids:
        epoch = datetime(1904, 1, 1) if uses_1904_epoch else datetime(1899, 12, 30)
        return epoch + timedelta(days=number)
    return int(number) if number.is_integer() else number


def _parameters(row: dict[str, Any], sheet_name: str, row_no: int) -> list[ParameterValue]:
    result: list[ParameterValue] = []
    for index, (key, raw) in enumerate(row.items()):
        if not key.startswith("param.") or raw is None or _text(raw) == "":
            continue
        code = key[6:]
        value_type, value = _typed_value(raw)
        if code == "quantity_basis_confirmed":
            value_type, value = "boolean", _boolean(raw, False)
        elif code == "thickness_m" and isinstance(raw, str) and raw.strip().lower().endswith("cm"):
            value_type, value = "number", float(raw.strip()[:-2]) / 100
        result.append(
            ParameterValue.model_construct(
                parameter_code=code,
                value_type=value_type,
                value=value,
                sort_order=index,
                source=SourceEvidence.model_construct(
                    sheet_name=sheet_name,
                    row_no=row_no,
                    column_name=key,
                    batch_id=None,
                ),
            )
        )
    return result


def _typed_value(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return "boolean", value
    if isinstance(value, int):
        return "integer", value
    if isinstance(value, float):
        return "number", value
    if isinstance(value, (date, datetime)):
        return "date", value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return "text", _text(value)


def _fingerprint(snapshot: ProjectMasterSnapshot) -> str:
    payload: list[dict[str, Any]] = []
    for workpoint in sorted(snapshot.workpoints, key=lambda item: item.workpoint_id.casefold()):
        workpoint_data = workpoint.model_dump(exclude={"source", "structures"}, mode="json")
        structures: list[dict[str, Any]] = []
        for structure in sorted(workpoint.structures, key=lambda item: item.structure_id.casefold()):
            structure_data = structure.model_dump(exclude={"source", "components", "parameters"}, mode="json")
            structure_data["parameters"] = _canonical_parameters(structure.parameters)
            components: list[dict[str, Any]] = []
            for component in sorted(structure.components, key=lambda item: item.component_id.casefold()):
                component_data = component.model_dump(exclude={"source", "parameters"}, mode="json")
                component_data["parameters"] = _canonical_parameters(component.parameters)
                components.append(component_data)
            structure_data["components"] = components
            structures.append(structure_data)
        workpoint_data["structures"] = structures
        payload.append(workpoint_data)
    fingerprint_payload: Any = payload
    if snapshot.route_placements:
        fingerprint_payload = {
            "workpoints": payload,
            "route_placements": [
                placement.model_dump(exclude={"source"}, mode="json")
                for placement in sorted(
                    snapshot.route_placements,
                    key=lambda item: item.placement_id.casefold(),
                )
            ],
        }
    encoded = json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _canonical_parameters(parameters: list[ParameterValue]) -> list[dict[str, Any]]:
    return [
        parameter.model_dump(exclude={"source", "sort_order"}, mode="json")
        for parameter in sorted(parameters, key=lambda item: item.parameter_code.casefold())
    ]


def _issue(
    severity: str,
    code: str,
    sheet: str,
    row_no: int | None,
    field: str | None,
    message: str,
    suggestion: str | None = None,
    *,
    object_kind: str | None = None,
    object_id: str | None = None,
) -> ProjectMasterImportIssue:
    return ProjectMasterImportIssue(
        issue_id=f"pmi-{uuid4().hex}",
        severity=severity,
        issue_code=code,
        sheet_name=sheet,
        row_no=row_no,
        field_name=field,
        object_kind=object_kind,
        object_id=object_id,
        message=message,
        suggestion=suggestion,
    )


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text or None


def _number(value: Any) -> float:
    if value is None or _text(value) == "":
        raise ValueError("工程量不能为空。")
    return float(value)


def _non_negative_number(value: Any) -> float:
    number = _number(value)
    if number < 0:
        raise ValueError(f"{value} 不能小于 0。")
    return number


def _optional_float(value: Any) -> float | None:
    if value is None or _text(value) == "":
        return None
    return float(value)


def _integer(value: Any, default: int) -> int:
    if value is None or _text(value) == "":
        return default
    number = float(value)
    if not number.is_integer():
        raise ValueError(f"{value} 不是整数。")
    return int(number)


def _non_negative_integer(value: Any, default: int) -> int:
    number = _integer(value, default)
    if number < 0:
        raise ValueError(f"{value} 不能小于 0。")
    return number


def _boolean(value: Any, default: bool) -> bool:
    if value is None or _text(value) == "":
        return default
    if isinstance(value, bool):
        return value
    normalized = _text(value).casefold()
    if normalized in {"是", "true", "1", "yes"}:
        return True
    if normalized in {"否", "false", "0", "no"}:
        return False
    raise ValueError(f"{value} 不是合法布尔值，请填写是或否。")


__all__ = [
    "COMPONENT_COLUMNS",
    "REQUIRED_SHEETS",
    "ROUTE_PLACEMENT_COLUMNS",
    "SHEETS",
    "STRUCTURE_COLUMNS",
    "TEMPLATE_VERSION",
    "SUPPORTED_TEMPLATE_VERSIONS",
    "WORKPOINT_COLUMNS",
    "content_fingerprint",
    "create_template_bytes",
    "export_snapshot",
    "parse_workbook",
]
