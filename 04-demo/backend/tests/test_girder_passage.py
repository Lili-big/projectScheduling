from __future__ import annotations

from datetime import date, datetime, timezone

from app.girder_planning.passage_service import calculate_passage_releases
from app.models import (
    ErectionOwnership,
    GirderSpanPlan,
    GirderWorkPoint,
    ProjectDataVersion,
)
from app.services.process_library_service import default_scenario_with_process_library


def test_passage_date_takes_latest_of_erection_buffer_and_explicit_readiness() -> None:
    scenario = default_scenario_with_process_library()
    workpoint = GirderWorkPoint(
        workpoint_id="bridge:B1:left",
        name="B1左幅",
        workpoint_type="bridge",
        side="left",
        mileage_start_m=0,
        mileage_end_m=100,
        corridor_id="main",
        bridge_id="B1",
        work_section_id="B1-L",
        requires_erection=True,
        explicit_readiness_date=date(2026, 1, 10),
    )
    project_version = ProjectDataVersion(
        project_data_version_id="pdv-1",
        project_id=scenario.project.project_id,
        version_no=1,
        status="confirmed",
        project=scenario.project,
        workpoints=[workpoint],
        input_fingerprint="fp",
        created_by="测试",
        created_at=datetime.now(timezone.utc),
    )
    ownership = ErectionOwnership(
        bridge_id="B1",
        side="left",
        owner_route_id="route-1",
        owner_node_id="node-1",
        arrival_date=date(2026, 1, 1),
        resolution_source="earliest_arrival",
    )
    plan = GirderSpanPlan(
        task_id="span-1",
        bridge_id="B1",
        work_section_id="B1-L",
        span_id="span-1",
        route_id="route-1",
        beam_yard_id="yard-1",
        erection_machine_id="machine-1",
        beam_type="T",
        beam_count=4,
        earliest_start_date=date(2026, 1, 1),
        planned_finish_date=date(2026, 1, 5),
    )

    releases, diagnostics = calculate_passage_releases(
        project_version,
        [ownership],
        [plan],
        post_erection_buffer_days=2,
    )

    assert diagnostics == []
    assert releases[0].passable_date == date(2026, 1, 10)
    assert releases[0].controlling_source == "explicit_readiness"
