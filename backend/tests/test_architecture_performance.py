from __future__ import annotations

import json
import os
import runpy
import sys
import time
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.girder_schedule_adapter import build_girder_schedule
from app.solver import solve_schedule


FIXTURE = Path(__file__).parent / "fixtures" / "girder_planning" / "performance-benchmark-v1.json"


def test_architecture_performance_gate_uses_frozen_800_task_300_span_baseline() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["counts"]["schedule_tasks"] == 800
    assert payload["counts"]["erection_spans"] == 300
    assert payload["runtime_verification"]["status"] == "verified"
    assert payload["runtime_verification"]["measured_total_seconds"] > 0


@pytest.mark.skipif(os.getenv("RUN_ARCHITECTURE_PERFORMANCE") != "1", reason="完整架构性能基准需显式开启")
def test_typical_integrated_schedule_does_not_regress_over_ten_percent() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    baseline_seconds = float(payload["runtime_verification"]["measured_total_seconds"])
    namespace = runpy.run_path(str(Path(__file__).with_name("test_girder_performance.py")))
    scenario_version, project_version = namespace["_performance_case"]()

    started = time.perf_counter()
    generated, girder = build_girder_schedule(scenario_version, project_version)
    solved = solve_schedule(generated.schedule_input)
    elapsed = time.perf_counter() - started

    assert len(generated.schedule_input.tasks) == 800
    assert len(girder.span_plans) == 300
    assert solved.status in {"OPTIMAL", "FEASIBLE"}
    assert elapsed <= min(float(payload["max_runtime_seconds"]), baseline_seconds * 1.10)
    print({"baseline_seconds": baseline_seconds, "elapsed_seconds": round(elapsed, 2), "limit_seconds": round(baseline_seconds * 1.10, 2)})
