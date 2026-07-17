from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO

from openpyxl import Workbook

from app.girder_planning.import_service import import_workpoints
from app.models import ProjectBridge, ProjectDataVersion, ProjectModel, WorkSection


def _project_version() -> ProjectDataVersion:
    project = ProjectModel(
        project_id="P1",
        project_name="测试项目",
        start_date=date(2026, 1, 1),
        bridges=[
            ProjectBridge(
                id="B1",
                name="测试大桥",
                work_sections=[
                    WorkSection(id="B1-L", name="左幅", side="left"),
                    WorkSection(id="B1-R", name="右幅", side="right"),
                ],
            )
        ],
    )
    return ProjectDataVersion(
        project_data_version_id="pdv-1",
        project_id="P1",
        version_no=1,
        status="confirmed",
        project=project,
        input_fingerprint="fp",
        created_by="测试",
        created_at=datetime.now(timezone.utc),
    )


def _workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "架梁工点"
    sheet.append(["工点名称", "工点类型", "幅别", "起点里程", "终点里程", "走廊", "桥梁ID", "是否架梁", "关联工程"])
    sheet.append(["测试大桥", "桥梁", "双幅", "K1+000", "K1+500", "主线", "B1", "是", "structure:S1;milestone:M1"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_import_expands_both_to_left_right_and_keeps_authority_evidence() -> None:
    preview = import_workpoints(
        file_name="架梁工点.xlsx",
        content=_workbook_bytes(),
        project_version=_project_version(),
    )

    assert [(item.side, item.work_section_id) for item in preview.workpoints] == [("left", "B1-L"), ("right", "B1-R")]
    assert all(item.bridge_id == "B1" and item.requires_erection for item in preview.workpoints)
    assert all(len(item.linked_condition_refs) == 2 for item in preview.workpoints)
    assert any(item.authority_domain == "structure" and item.field_path.endswith("bridge_id") for item in preview.source_evidence)
    assert preview.field_conflicts == []


def test_import_unmapped_bridge_creates_blocking_conflict() -> None:
    content = "工点名称,工点类型,幅别,桥梁ID\n不存在大桥,桥梁,左幅,UNKNOWN\n".encode("utf-8")

    preview = import_workpoints(file_name="workpoints.csv", content=content, project_version=_project_version())

    assert preview.workpoints == []
    assert preview.field_conflicts[0].severity == "blocking"
    assert any(item.code == "GIRDER_BRIDGE_UNMAPPED" for item in preview.diagnostics)
