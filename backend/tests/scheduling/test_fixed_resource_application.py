from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.scenario as legacy  # noqa: E402
from app.scheduling.application import fixed_resource  # noqa: E402


def test_fixed_resource_application_exports_the_legacy_use_cases() -> None:
    assert fixed_resource.solve_scenario is legacy.solve_scenario
    assert fixed_resource.solve_ai_strict_fixed_resource_scenario is legacy.solve_ai_strict_fixed_resource_scenario
