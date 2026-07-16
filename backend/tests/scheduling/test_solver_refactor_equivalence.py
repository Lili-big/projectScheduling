from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.solver as legacy  # noqa: E402
from app.scheduling.solver import engine  # noqa: E402


def test_legacy_solver_module_is_the_engine_module_for_monkeypatch_equivalence() -> None:
    assert legacy is engine
    assert legacy.SCHEDULER_RANDOM_SEED == 0
    assert legacy.solve_schedule is engine.solve_schedule
