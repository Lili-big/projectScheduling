from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.bootstrap import create_app  # noqa: E402
from app.project_master.repository import ProjectMasterRepository  # noqa: E402
from app.project_master.service import ProjectMasterService  # noqa: E402
from asgi_client import request  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402
from test_project_master_api import _json, _upload  # noqa: E402


def test_version_list_current_detail_workpoints_and_export(tmp_path: Path) -> None:
    app = create_app()
    app.state.project_master_service = ProjectMasterService(ProjectMasterRepository(tmp_path / "master.db"))
    _, _, body = _upload(app, valid_project_master_workbook())
    version_id = _json(body)["created_version_id"]

    status, _, body = request(app, "GET", "/api/projects/demo/project-master/versions?page=1&page_size=10")
    assert status == 200
    assert _json(body)["total"] == 1

    status, _, body = request(app, "GET", f"/api/project-master/versions/{version_id}")
    assert status == 200
    assert _json(body)["diff_counts"]["added"] > 0

    status, _, body = request(
        app,
        "POST",
        f"/api/project-master/versions/{version_id}/confirm",
        {"confirmed_by": "reviewer", "expected_current_version_id": None, "acknowledge_warning_codes": []},
    )
    assert status == 200

    status, _, body = request(app, "GET", "/api/projects/demo/project-master/versions/current")
    assert status == 200 and _json(body)["version_id"] == version_id

    status, _, body = request(
        app,
        "GET",
        f"/api/project-master/versions/{version_id}/workpoints?page=1&page_size=1&workpoint_type=bridge",
    )
    page = _json(body)
    assert status == 200 and page["page_size"] == 1 and page["items"][0]["workpoint_type"] == "bridge"

    workpoint_id = page["items"][0]["workpoint_id"]
    status, _, body = request(app, "GET", f"/api/project-master/versions/{version_id}/workpoints/{workpoint_id}")
    detail = _json(body)
    assert status == 200 and detail["structures"]
    assert detail["source"]["sheet_name"] == "工点信息"

    status, headers, body = request(app, "GET", f"/api/project-master/versions/{version_id}/export")
    assert status == 200 and len(body) > 1000
    assert "filename*=UTF-8" in headers["content-disposition"]

    status, _, body = request(app, "GET", "/api/projects/missing/project-master/versions/current")
    assert status == 404
    assert _json(body)["detail"]["code"] == "PROJECT_MASTER_NOT_FOUND"


def test_task_view_display_map_is_batched_minimal_complete_and_bounded(tmp_path: Path) -> None:
    app = create_app()
    app.state.project_master_service = ProjectMasterService(ProjectMasterRepository(tmp_path / "master.db"))
    _, _, body = _upload(app, valid_project_master_workbook())
    version_id = _json(body)["created_version_id"]
    endpoint = f"/api/project-master/versions/{version_id}/task-view-display-map"

    status, _, body = request(
        app,
        "POST",
        endpoint,
        {"workpoint_ids": ["WP-R01", "WP-B01", "WP-R01", " "]},
    )
    payload = _json(body)
    assert status == 200
    assert payload["project_data_version_id"] == version_id
    assert [item["workpoint_id"] for item in payload["workpoints"]] == ["WP-B01", "WP-R01"]
    bridge = payload["workpoints"][0]
    assert bridge["workpoint_name"] == "一号特大桥"
    assert [section["work_section_id"] for section in bridge["work_sections"]] == [
        "WS-C:none",
        "WS-L:left",
        "WS-R:right",
    ]
    assert bridge["work_sections"][1]["work_section_name"] == "左幅工区"
    assert not ({"components", "parameters", "source", "structures"} & set(bridge))
    assert not ({"components", "parameters", "source"} & set(bridge["work_sections"][0]))

    status, _, body = request(app, "POST", endpoint, {"workpoint_ids": []})
    assert status == 200 and _json(body)["workpoints"] == []

    status, _, body = request(app, "POST", endpoint, {"workpoint_ids": ["WP-MISSING"]})
    assert status == 404 and _json(body)["detail"]["code"] == "PROJECT_MASTER_NOT_FOUND"

    status, _, body = request(
        app,
        "POST",
        "/api/project-master/versions/pmv-missing/task-view-display-map",
        {"workpoint_ids": ["WP-B01"]},
    )
    assert status == 404 and _json(body)["detail"]["code"] == "PROJECT_MASTER_NOT_FOUND"

    status, _, body = request(app, "POST", endpoint, {"workpoint_ids": ["WP-B01"] * 500})
    assert status == 200 and [item["workpoint_id"] for item in _json(body)["workpoints"]] == ["WP-B01"]

    status, _, _ = request(app, "POST", endpoint, {"workpoint_ids": ["WP-B01"] * 501})
    assert status == 422
