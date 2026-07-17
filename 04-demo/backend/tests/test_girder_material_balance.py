from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.models import (
    CreateProgressSnapshotRequest,
    GirderExecutionActual,
    GirderPlanningResult,
    ProgressEntry,
    YardInventoryActual,
    YardInventoryPoint,
)
from app.services.plan_control_repository import PlanControlRepository
from app.services.progress_forecast import PlanControlValidationError, create_baseline_plan, create_progress_snapshot
from plan_control_helpers import solved_baseline_request


def _girder_plan(tmp_path: Path):
    repository = PlanControlRepository(tmp_path / "material-balance.json")
    baseline = create_baseline_plan(solved_baseline_request(), repository)
    task = baseline.generated_snapshot.schedule_input.tasks[0].model_copy(
        update={
            "component_type": "beam_erection",
            "properties": {"beam_yard_id": "yard-1", "beam_type": "T梁"},
            "quantity": 4,
        }
    )
    generated = baseline.generated_snapshot.model_copy(
        update={"schedule_input": baseline.generated_snapshot.schedule_input.model_copy(update={"tasks": [task, *baseline.generated_snapshot.schedule_input.tasks[1:]]})}
    )
    girder = GirderPlanningResult(
        result_id="girder-material",
        status="ready",
        yard_inventory_series=[
            YardInventoryPoint(
                beam_yard_id="yard-1",
                beam_type="T梁",
                date=date(2026, 6, 30),
                opening_inventory=0,
                produced=0,
                consumed=0,
                closing_inventory=0,
            )
        ],
        input_fingerprint="girder-material-fp",
    )
    updated = baseline.model_copy(update={"plan_version_id": "plan-material", "version_no": 2, "generated_snapshot": generated, "girder_result_snapshot": girder})
    repository.add_plan_version(updated)
    return repository, updated, task


def test_material_balance_blocks_consumption_exceeding_opening_and_production(tmp_path: Path) -> None:
    repository, plan, task = _girder_plan(tmp_path)

    with pytest.raises(PlanControlValidationError, match="产耗库存不平衡"):
        create_progress_snapshot(
            CreateProgressSnapshotRequest(
                plan_version_id=plan.plan_version_id,
                status_date=date(2026, 7, 1),
                submitted_by="现场填报人",
                entries=[],
                girder_execution_actuals=[
                    GirderExecutionActual(
                        span_task_id=task.id,
                        status="completed",
                        actual_finish_date=date(2026, 7, 1),
                        erected_beam_count=2,
                    )
                ],
                yard_inventory_actuals=[
                    YardInventoryActual(
                        beam_yard_id="yard-1",
                        beam_type="T梁",
                        cumulative_produced=0,
                        observed_inventory=0,
                        opening_inventory_adjustment=0,
                    )
                ],
            ),
            repository,
        )


def test_material_balance_rejects_duplicate_yard_type_actuals(tmp_path: Path) -> None:
    repository, plan, _ = _girder_plan(tmp_path)
    actual = YardInventoryActual(beam_yard_id="yard-1", beam_type="T梁", cumulative_produced=0, observed_inventory=0, opening_inventory_adjustment=0)

    with pytest.raises(PlanControlValidationError, match="库存实绩重复"):
        create_progress_snapshot(
            CreateProgressSnapshotRequest(
                plan_version_id=plan.plan_version_id,
                status_date=date(2026, 7, 1),
                submitted_by="现场填报人",
                entries=[],
                yard_inventory_actuals=[actual, actual.model_copy(deep=True)],
            ),
            repository,
        )


def test_material_balance_rejects_completed_beam_quantity_over_plan(tmp_path: Path) -> None:
    repository, plan, task = _girder_plan(tmp_path)

    with pytest.raises(PlanControlValidationError, match="超过计划工程量"):
        create_progress_snapshot(
            CreateProgressSnapshotRequest(
                plan_version_id=plan.plan_version_id,
                status_date=date(2026, 7, 1),
                submitted_by="现场填报人",
                entries=[],
                girder_execution_actuals=[
                    GirderExecutionActual(
                        span_task_id=task.id,
                        status="completed",
                        actual_finish_date=date(2026, 7, 1),
                        erected_beam_count=5,
                    )
                ],
            ),
            repository,
        )
