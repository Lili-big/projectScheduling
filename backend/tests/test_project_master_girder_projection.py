from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.girder_planning.ownership import derive_route_workpoints  # noqa: E402
from app.project_master.workbook import parse_workbook  # noqa: E402
from project_master_fixture_helpers import valid_project_master_workbook  # noqa: E402


def test_route_workpoints_are_derived_from_workpoint_and_side() -> None:
    snapshot, issues, _ = parse_workbook(valid_project_master_workbook())
    assert not [item for item in issues if item.severity == "error"]
    workpoints = derive_route_workpoints(snapshot)
    by_id = {item.workpoint_id: item for item in workpoints}
    assert {"WP-B01:left", "WP-B01:right", "WP-R01:unknown", "WP-T01:unknown"} <= set(by_id)
    assert by_id["WP-B01:left"].bridge_id == "WP-B01"
    assert by_id["WP-B01:left"].side == "left"
    assert by_id["WP-B01:right"].work_section_id == "WS-R"
    assert by_id["WP-R01:unknown"].requires_erection is False
    assert all(item.properties["project_master_workpoint_id"] for item in workpoints)
