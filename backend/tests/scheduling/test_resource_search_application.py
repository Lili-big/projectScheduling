from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.scenario as legacy  # noqa: E402
from app.scheduling.application import resource_search  # noqa: E402


def test_resource_search_application_exports_minimum_and_cost_use_cases() -> None:
    assert resource_search.solve_min_resources_scenario is legacy.solve_min_resources_scenario
    assert resource_search.solve_resource_cost_scenario is legacy.solve_resource_cost_scenario
