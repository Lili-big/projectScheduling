from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.solver as legacy  # noqa: E402
from app.scheduling.solver import diagnostics, milestones  # noqa: E402


def test_result_diagnostics_and_milestones_reference_the_engine() -> None:
    assert diagnostics._resource_path_metrics is legacy._resource_path_metrics
    assert milestones._critical_path_schedule is legacy._critical_path_schedule
    assert milestones.evaluate_milestones_from_scheduled_tasks is legacy.evaluate_milestones_from_scheduled_tasks
