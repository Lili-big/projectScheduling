from __future__ import annotations

from datetime import date

from app.models import GirderPlanningResult, GirderSpanPlan, ScheduleResult, ScheduledTask
from app.services.girder_schedule_adapter import apply_schedule_dates


def test_apply_schedule_dates_copies_solver_dates_back_to_span_plan() -> None:
    span = GirderSpanPlan(
        task_id="beam-1",
        bridge_id="B1",
        work_section_id="B1-L",
        span_id="span-1",
        route_id="route-1",
        beam_yard_id="yard-1",
        erection_machine_id="machine-1",
        beam_type="T",
        beam_count=4,
        earliest_start_date=date(2026, 1, 1),
    )
    result = GirderPlanningResult(
        result_id="girder-1",
        status="ready",
        span_plans=[span],
        input_fingerprint="fp",
    )
    task = ScheduledTask(
        id="beam-1",
        name="B1左幅第1跨架梁",
        bridge_id="B1",
        work_section_id="B1-L",
        component_id="span-1",
        structure_id="B1-L-SPAN-01",
        structure_name="B1左幅第1跨架梁",
        structure_type="upper_structure",
        component_type="beam_erection",
        process_name="简支梁架设",
        productivity_rule_id="girder-erection-daily-capacity",
        quantity=4,
        quantity_label="4片",
        duration_days=2,
        compatible_resource_types=["girder_erection_machine"],
        start_offset=3,
        end_offset=4,
        start_date=date(2026, 1, 4),
        finish_date=date(2026, 1, 5),
    )
    schedule = ScheduleResult(status="FEASIBLE", plan_start_date=date(2026, 1, 1), tasks=[task])

    updated = apply_schedule_dates(result, schedule)

    assert updated.span_plans[0].planned_start_date == date(2026, 1, 4)
    assert updated.span_plans[0].planned_finish_date == date(2026, 1, 5)
