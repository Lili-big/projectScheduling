from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.scenario as legacy  # noqa: E402
from app.scheduling.application.comparison import compare_scenarios  # noqa: E402


def test_comparison_application_exports_the_single_comparison_implementation() -> None:
    assert compare_scenarios is legacy.compare_scenarios
