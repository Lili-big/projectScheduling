from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.solver as legacy  # noqa: E402
from app.contracts import ResourcePool  # noqa: E402
from app.scenario import solve_scenario  # noqa: E402
from app.scheduling.solver import diagnostics, milestones  # noqa: E402
from workpoint_scope_test_support import (  # noqa: E402
    WORKPOINT_A,
    WORKPOINT_B,
    two_workpoint_scenario,
)


def test_result_diagnostics_and_milestones_reference_the_engine() -> None:
    assert diagnostics._resource_path_metrics is legacy._resource_path_metrics
    assert milestones._critical_path_schedule is legacy._critical_path_schedule
    assert milestones.evaluate_milestones_from_scheduled_tasks is legacy.evaluate_milestones_from_scheduled_tasks


def test_result_scope_diagnostics_trace_workpoint_scope_and_zero_day_transfer() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        )
    )

    solved = solve_scenario(scenario)
    payload = solved.result.stats["resource_scope_diagnostics"]

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert payload["rule_version"] == "workpoint-resource-scope/v1"
    assert payload["project_shared_transfer_time_days"] == 0
    assert payload["groups"] == [
        {
            "resource_pool_id": "pool-cap",
            "source_pool_id": "pool-cap",
            "label": "承台班组",
            "resource_type": "cap_team",
            "scope_mode": "PROJECT_SHARED",
            "workpoint_id": None,
            "eligible_workpoint_ids": [WORKPOINT_A, WORKPOINT_B],
            "inheritance_source": "global",
            "current_quantity": 1,
            "recommended_quantity": 1,
            "max_quantity": 2,
        }
    ]
    assert {item["workpoint_id"] for item in payload["allocations"]} == {WORKPOINT_A, WORKPOINT_B}
    assert all(item["scope_mode"] == "PROJECT_SHARED" for item in payload["allocations"])
