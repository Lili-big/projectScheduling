from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.project_master.diff import diff_snapshots  # noqa: E402
from app.project_master.workbook import parse_workbook  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402


def test_diff_aligns_by_stable_id_and_detects_add_modify_delete() -> None:
    before, _, _ = parse_workbook(valid_project_master_workbook())
    after, _, _ = parse_workbook(valid_project_master_workbook(workpoint_name="新桥名"))
    after.workpoints.pop()
    after.workpoints[0].structures[0].remark = "复核"
    entries = diff_snapshots(before, after)
    assert any(item.change_type == "modified" and item.object_id == before.workpoints[0].workpoint_id for item in entries)
    assert any(item.change_type == "deleted" and item.object_id == before.workpoints[-1].workpoint_id for item in entries)
    assert any(item.field_name == "remark" for item in entries)


def test_first_version_is_all_added_and_formatting_does_not_change_fingerprint() -> None:
    snapshot, _, fingerprint = parse_workbook(valid_project_master_workbook())
    entries = diff_snapshots(None, snapshot)
    assert entries and all(item.change_type == "added" for item in entries)
    same, _, same_fingerprint = parse_workbook(valid_project_master_workbook())
    assert same.model_dump() == snapshot.model_dump()
    assert same_fingerprint == fingerprint
