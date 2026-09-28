from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.contracts import (  # noqa: E402
    GeneratedScheduleInput,
    PrecedenceLink,
    ProjectBridge,
    ProjectModel,
    ScheduleInput,
    ScheduleResult,
    ScheduledTask,
    StructureModel,
    WorkSection,
)
from app.main import app  # noqa: E402
from app.services.zpert_plan_export import ZpertPlanExportError, export_zpert_plan, product_date_to_zpert_time  # noqa: E402
from asgi_client import request  # noqa: E402


def test_product_date_matches_utc8_zebra_conversion() -> None:
    expected = int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp())
    assert product_date_to_zpert_time(date(2026, 3, 1)) == expected == 1772323200


def test_export_builds_wbs_duration_depends_and_start_times() -> None:
    document, file_name = export_zpert_plan(_project(), _generated(), _result())
    tasks = document["tasks"]
    by_name = {item["name"]: item for item in tasks}

    assert file_name == "样例大桥.json"
    assert [item["name"] for item in tasks] == [
        "样例大桥",
        "甲桥",
        "左幅",
        "0号墩",
        "钻孔桩",
        "承台",
        "1号墩",
        "墩身",
        "乙桥",
        "右幅",
        "2号墩",
        "盖梁",
    ]
    assert tasks[0] == {
        "id": 0,
        "name": "样例大桥",
        "level": 0,
        "ask_start_time": 1772323200,
    }
    assert by_name["甲桥"]["id"] == 1 and by_name["甲桥"]["parent_id"] == 0 and by_name["甲桥"]["level"] == 1
    assert by_name["左幅"]["parent_id"] == by_name["甲桥"]["id"] and by_name["左幅"]["level"] == 2
    assert by_name["0号墩"]["parent_id"] == by_name["左幅"]["id"] and by_name["0号墩"]["level"] == 3
    pile = by_name["钻孔桩"]
    cap = by_name["承台"]
    pier = by_name["墩身"]
    assert pile["level"] == 4 and pile["parent_id"] == by_name["0号墩"]["id"]
    assert pile["duration"] == 2 * 28800
    assert cap["duration"] == 3 * 28800
    assert cap["depends"] == f"{pile['id']}FS+5"
    assert pier["depends"] == f"{pile['id']}FF+4"
    assert "depends" not in pile
    assert pile["plan_start_time"] == pile["ask_start_time"] == 1772323200
    assert cap["plan_start_time"] == 1772323200 + 2 * 86400
    assert by_name["0号墩"]["plan_start_time"] == 1772323200
    assert by_name["1号墩"]["plan_start_time"] == 1772323200 + 86400
    for summary_name in ("甲桥", "左幅", "0号墩", "乙桥"):
        summary = by_name[summary_name]
        assert "duration" not in summary
        assert "depends" not in summary
        assert summary["ask_start_time"] == summary["plan_start_time"]
    assert by_name["乙桥"]["id"] > by_name["甲桥"]["id"]


def test_missing_section_hangs_structure_on_bridge() -> None:
    source = _result()
    pile = next(task for task in source.tasks if task.id == "pile")
    result = source.model_copy(update={"tasks": [pile.model_copy(update={"work_section_id": None})]})
    document, _file_name = export_zpert_plan(_project(), _generated(), result)
    names = [item["name"] for item in document["tasks"]]
    assert names == ["样例大桥", "甲桥", "0号墩", "钻孔桩"]
    by_name = {item["name"]: item for item in document["tasks"]}
    assert by_name["0号墩"]["level"] == 2 and by_name["0号墩"]["parent_id"] == by_name["甲桥"]["id"]
    assert by_name["钻孔桩"]["level"] == 3


def test_infeasible_or_empty_result_is_rejected() -> None:
    infeasible = _result().model_copy(update={"status": "INFEASIBLE"})
    try:
        export_zpert_plan(_project(), _generated(), infeasible)
    except ZpertPlanExportError as exc:
        assert "没有可导出" in str(exc)
    else:
        raise AssertionError("infeasible result should not export")
    empty = _result().model_copy(update={"tasks": []})
    try:
        export_zpert_plan(_project(), _generated(), empty)
    except ZpertPlanExportError:
        return
    raise AssertionError("empty result should not export")


def test_export_route_returns_attachment_json() -> None:
    payload = {
        "project": _project().model_dump(mode="json"),
        "generated": _generated().model_dump(mode="json"),
        "result": _result().model_dump(mode="json"),
    }
    status, headers, body = request(app, "POST", "/api/zpert-plan/export", payload)
    assert status == 200
    disposition = headers["content-disposition"]
    assert disposition.startswith("attachment;filename=\"")
    assert "filename*=UTF-8''" in disposition
    assert disposition.split("filename*=UTF-8''", 1)[1].endswith(".json")
    document = json.loads(body.decode("utf-8"))
    assert document["tasks"][0]["name"] == "样例大桥"
    assert document["tasks"][4]["duration"] == 57600

    payload["result"]["status"] = "INFEASIBLE"
    rejected, _headers, error_body = request(app, "POST", "/api/zpert-plan/export", payload)
    assert rejected == 422
    assert json.loads(error_body.decode("utf-8"))["detail"]["code"] == "ZPERT_PLAN_NOT_EXPORTABLE"


def _project() -> ProjectModel:
    return ProjectModel(
        project_id="P1",
        project_name="样例大桥",
        start_date=date(2026, 3, 1),
        bridges=[
            ProjectBridge(
                id="B2",
                name="乙桥",
                order=2,
                work_sections=[
                    WorkSection(
                        id="S2",
                        name="右幅",
                        order=1,
                        structures=[StructureModel(id="P2", name="2号墩", structure_type="pier", order=1)],
                    )
                ],
            ),
            ProjectBridge(
                id="B1",
                name="甲桥",
                order=1,
                work_sections=[
                    WorkSection(
                        id="S1",
                        name="左幅",
                        order=1,
                        structures=[
                            StructureModel(id="P0", name="0号墩", structure_type="pier", order=1),
                            StructureModel(id="P1", name="1号墩", structure_type="pier", order=2),
                        ],
                    )
                ],
            ),
        ],
    )


def _generated() -> GeneratedScheduleInput:
    return GeneratedScheduleInput(
        schedule_input=ScheduleInput(
            project_name="样例大桥",
            start_date=date(2026, 3, 1),
            tasks=[],
            precedence_links=[
                PrecedenceLink(id="L1", predecessor_id="pile", successor_id="cap", relationship="FS", lag_days=5, source_rule_id="r1"),
                PrecedenceLink(id="L2", predecessor_id="missing", successor_id="pier", relationship="FS", lag_days=1, source_rule_id="r2"),
                PrecedenceLink(id="L3", predecessor_id="pile", successor_id="pier", relationship="FF", lag_days=4, source_rule_id="r3"),
            ],
            resources=[],
        )
    )


def _result() -> ScheduleResult:
    return ScheduleResult(
        status="FEASIBLE",
        plan_start_date=date(2026, 3, 1),
        tasks=[
            _task("beam", "盖梁", "B2", "S2", "P2", "2号墩", 1, 1, date(2026, 3, 4)),
            _task("pier", "墩身", "B1", "S1", "P1", "1号墩", 1, 4, date(2026, 3, 2)),
            _task("cap", "承台", "B1", "S1", "P0", "0号墩", 2, 3, date(2026, 3, 3)),
            _task("pile", "钻孔桩", "B1", "S1", "P0", "0号墩", 1, 2, date(2026, 3, 1)),
        ],
    )


def _task(task_id: str, name: str, bridge_id: str, section_id: str, structure_id: str, structure_name: str, sequence: int, duration: int, start: date) -> ScheduledTask:
    return ScheduledTask(
        id=task_id,
        name=name,
        bridge_id=bridge_id,
        work_section_id=section_id,
        sequence_order=sequence,
        structure_id=structure_id,
        structure_name=structure_name,
        structure_type="pier",
        component_type="pile",
        process_name=name,
        productivity_rule_id="rule",
        quantity=1,
        quantity_label="项",
        duration_days=duration,
        start_offset=0,
        end_offset=duration,
        start_date=start,
        finish_date=start,
    )
