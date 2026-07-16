from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.common import DEFAULT_OBJECTIVE_TERM_WEIGHTS  # noqa: E402
from app.scheduling.solver.objectives.control import _objective_weights_for_config  # noqa: E402
from app.scheduling.solver.objectives.duration import CONTROL_MAKESPAN_WEIGHT  # noqa: E402
from app.scheduling.solver.objectives.resource_idle import RESOURCE_IDLE_WEIGHT  # noqa: E402


def test_objective_modules_preserve_configured_default_weights() -> None:
    assert CONTROL_MAKESPAN_WEIGHT == DEFAULT_OBJECTIVE_TERM_WEIGHTS["makespan_and_soft_milestone"]
    assert RESOURCE_IDLE_WEIGHT == DEFAULT_OBJECTIVE_TERM_WEIGHTS["resource_idle"]
    assert callable(_objective_weights_for_config)
