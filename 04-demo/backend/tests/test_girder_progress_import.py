from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.girder_planning.progress_import_service import import_progress_actuals


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "实绩"
    sheet.append([
        "记录类型",
        "梁场ID",
        "梁型",
        "累计生产",
        "盘点库存",
        "分跨任务ID",
        "状态",
        "实际开始日期",
        "实际完成日期",
        "已架梁片数",
        "架桥机ID",
        "工点ID",
        "实际开放日期",
    ])
    sheet.append(["库存", "Y1", "T梁", 20, 12, None, None, None, None, None, None, None, None])
    sheet.append(["架梁", None, None, None, None, "B1-L-S01", "已完成", "2026-07-01", "2026-07-03", 8, "M1", None, None])
    sheet.append(["通道", None, None, None, None, None, "开放", None, None, None, None, "B1-L", "2026-07-04"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_import_progress_actuals_parses_inventory_execution_and_passage() -> None:
    preview = import_progress_actuals(file_name="实绩.xlsx", content=_workbook_bytes())

    assert len(preview.yard_inventory_actuals) == 1
    assert preview.yard_inventory_actuals[0].source == "excel"
    assert preview.girder_execution_actuals[0].actual_finish_date.isoformat() == "2026-07-03"
    assert preview.girder_execution_actuals[0].erected_beam_count == 8
    assert preview.passage_actuals[0].status == "open"
    assert preview.diagnostics == []


def test_import_progress_actuals_keeps_invalid_rows_as_diagnostics() -> None:
    content = "记录类型,梁场ID,梁型,累计生产,盘点库存\n库存,Y1,T梁,not-a-number,2\n".encode("utf-8")

    preview = import_progress_actuals(file_name="实绩.csv", content=content)

    assert preview.yard_inventory_actuals == []
    assert preview.diagnostics[0].level == "error"
    assert preview.diagnostics[0].code == "GIRDER_PROGRESS_INVALID_ROW"
