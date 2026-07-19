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

from app.contracts import Resource, Task
from app.scheduling.solver.engine import _resource_candidates_by_task
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


def test_overlapping_shared_pool_candidate_generation_stays_linear_at_medium_scale() -> None:
    tasks = [_performance_task(index) for index in range(200)]
    resources = [
        *[
            _performance_resource(
                f"local-{index}", [f"WP-{index}"], exclusive=f"WP-{index}"
            )
            for index in range(20)
        ],
        _performance_resource("shared-even", [f"WP-{index}" for index in range(0, 20, 2)]),
        _performance_resource("shared-odd", [f"WP-{index}" for index in range(1, 20, 2)]),
        _performance_resource("shared-low", [f"WP-{index}" for index in range(10)]),
        _performance_resource("shared-high", [f"WP-{index}" for index in range(10, 20)]),
    ]

    started = time.perf_counter()
    candidates = _resource_candidates_by_task(tasks, resources)
    elapsed = time.perf_counter() - started

    assert len(candidates) == 200
    assert sum(len(items) for items in candidates.values()) == 600
    assert elapsed < 5
    print({"tasks": 200, "resources": len(resources), "candidates": 600, "elapsed_seconds": elapsed})


def _performance_task(index: int) -> Task:
    workpoint_id = f"WP-{index % 20}"
    return Task(
        id=f"TASK-{index}",
        name=f"任务 {index}",
        bridge_id=workpoint_id,
        structure_id=f"S-{index}",
        structure_name=f"结构 {index}",
        structure_type="pier",
        component_type="cap",
        process_name="承台施工",
        productivity_rule_id="cap-performance",
        quantity=1,
        quantity_label="1个",
        duration_days=1,
        compatible_resource_types=["cap_team"],
    )


def _performance_resource(
    pool_id: str, eligible_workpoint_ids: list[str], *, exclusive: str | None = None
) -> Resource:
    return Resource(
        id=f"{pool_id}-1",
        name=pool_id,
        type="cap_team",
        pool_id=pool_id,
        scope_mode="WORKPOINT_EXCLUSIVE" if exclusive else "PROJECT_SHARED",
        eligible_workpoint_ids=eligible_workpoint_ids,
        exclusive_workpoint_id=exclusive,
    )
