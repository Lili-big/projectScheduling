from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.solver as legacy  # noqa: E402
from app.scheduling.solver import strategies  # noqa: E402


def test_strategy_modules_preserve_all_public_solver_entries() -> None:
    assert strategies.solve_schedule is legacy.solve_schedule
    assert strategies.solve_control_priority_schedule is legacy.solve_control_priority_schedule
    assert strategies.solve_min_resources_schedule is legacy.solve_min_resources_schedule
    assert strategies.solve_resource_cost_schedule is legacy.solve_resource_cost_schedule
