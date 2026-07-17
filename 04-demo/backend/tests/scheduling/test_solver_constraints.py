from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.solver as legacy  # noqa: E402
from app.scheduling.solver.constraints import precedence, resources, workfaces  # noqa: E402


def test_constraint_modules_reference_the_single_engine_implementation() -> None:
    assert precedence._add_precedence_constraint is legacy._add_precedence_constraint
    assert resources._add_execution_constraints is legacy._add_execution_constraints
    assert workfaces._add_normal_workface_constraints is legacy._add_normal_workface_constraints
