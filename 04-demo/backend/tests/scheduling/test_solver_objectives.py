from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.common import DEFAULT_OBJECTIVE_TERM_WEIGHTS  # noqa: E402
from app.scheduling.solver.objectives.control import _objective_weights_for_config  # noqa: E402
from app.scheduling.solver.objectives.duration import CONTROL_MAKESPAN_WEIGHT  # noqa: E402
from app.scheduling.solver.objectives.resource_idle import RESOURCE_IDLE_WEIGHT  # noqa: E402
from app.scheduling.solver.engine import solve_control_priority_schedule_once, solve_min_resources_schedule  # noqa: E402
from workpoint_scope_test_support import two_workpoint_scenario, WORKPOINT_A, WORKPOINT_B  # noqa: E402
from app.contracts import ResourcePool  # noqa: E402
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402


def test_objective_modules_preserve_configured_default_weights() -> None:
    assert CONTROL_MAKESPAN_WEIGHT == DEFAULT_OBJECTIVE_TERM_WEIGHTS["makespan_and_soft_milestone"]
    assert RESOURCE_IDLE_WEIGHT == DEFAULT_OBJECTIVE_TERM_WEIGHTS["resource_idle"]
    assert callable(_objective_weights_for_config)


def test_unified_fixed_resource_objective_disables_resource_organization_terms() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            quantity=1,
            max_quantity=2,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        ),
        target_days=10,
    )
    schedule_input = generate_schedule_input_from_scenario(scenario).schedule_input

    result = solve_control_priority_schedule_once(
        schedule_input,
        enforce_hard_milestones=True,
        relax_target_constraints=True,
        optimization_stage="unified_fixed_resource",
    )

    gates = result.stats["objective_modeling_gates"]
    assert result.stats["objective_priority"] == ["max_target_delay_days", "makespan_days"]
    assert gates["resource_idle"]["modeling_enabled"] is False
    assert result.stats["resource_organization_analysis"]
    assert result.stats["continuity_metrics"]


def test_global_minimum_resource_objective_uses_count_then_makespan() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-cap",
            type="cap_team",
            label="承台班组",
            quantity=3,
            max_quantity=4,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        ),
        target_days=5,
    )
    schedule_input = generate_schedule_input_from_scenario(scenario, use_max_resources=True).schedule_input

    result = solve_min_resources_schedule(schedule_input, fallback_target_days=5)

    assert result.stats["global_objective_priority"] == ["resource_count", "makespan_days"]
    assert result.stats["candidate_total_quantity"] == 2
    assert result.stats["candidate_makespan_days"] == 5
    assert result.stats["search_lower_bounds"] == {"pool-cap": 0}
