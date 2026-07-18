from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import app.scenario as legacy  # noqa: E402
from app.contracts import (  # noqa: E402
    ComponentModel,
    MinResourcesSolveRequest,
    ProcessTemplate,
    ResourcePool,
)
from app.scheduling.solver.engine import _resource_candidates_by_task  # noqa: E402
from workpoint_scope_test_support import (  # noqa: E402
    WORKPOINT_A,
    WORKPOINT_B,
    two_workpoint_scenario,
)


def test_release_gate_combines_exclusive_shared_and_below_current_minimum() -> None:
    scenario = two_workpoint_scenario(
        ResourcePool(
            id="pool-minimum",
            type="cap_team",
            label="最少资源班组",
            quantity=3,
            max_quantity=5,
            authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
        ),
        target_days=5,
    )
    scenario.process_library.extend(
        [
            ProcessTemplate(
                id="shared-serial-test",
                component_type="pier_body",
                process_name="共享串行施工",
                duration_method="fixed_days",
                quantity_source="count",
                productivity_value=2,
                productivity_unit="天/个",
                resource_type="pier_body_team",
                is_default=True,
            ),
            ProcessTemplate(
                id="exclusive-test",
                component_type="cap_beam",
                process_name="独享施工",
                duration_method="fixed_days",
                quantity_source="count",
                productivity_value=1,
                productivity_unit="天/个",
                resource_type="cap_beam_team",
                is_default=True,
            ),
        ]
    )
    for bridge in scenario.project.bridges:
        structure = bridge.work_sections[0].structures[0]
        structure.components.extend(
            [
                ComponentModel(
                    id=f"{bridge.id}-PIER-BODY",
                    name="共享串行构件",
                    component_type="pier_body",
                    quantity=1,
                    quantity_label="1个",
                ),
                ComponentModel(
                    id=f"{bridge.id}-CAP-BEAM",
                    name="独享构件",
                    component_type="cap_beam",
                    quantity=1,
                    quantity_label="1个",
                ),
            ]
        )
    scenario.resource_pools.extend(
        [
            ResourcePool(
                id="pool-shared-serial",
                type="pier_body_team",
                label="共享串行班组",
                quantity=1,
                max_quantity=1,
                authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
            ),
            ResourcePool(
                id="pool-exclusive",
                type="cap_beam_team",
                label="工点独享班组",
                scope_mode="WORKPOINT_EXCLUSIVE",
                quantity=1,
                max_quantity=1,
                authorized_workpoint_ids=[WORKPOINT_A, WORKPOINT_B],
            ),
        ]
    )

    solved = legacy.solve_min_resources_scenario(
        MinResourcesSolveRequest(scenario=scenario, fallback_target_days=5)
    )

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert not any(message.level == "error" for message in solved.generated.validation)

    tasks = solved.generated.schedule_input.tasks
    resources = solved.generated.schedule_input.resources
    candidates = _resource_candidates_by_task(tasks, resources)

    exclusive_tasks = [task for task in tasks if task.component_type == "cap_beam"]
    assert {task.bridge_id for task in exclusive_tasks} == {WORKPOINT_A, WORKPOINT_B}
    assert all(
        candidate.scope_mode == "WORKPOINT_EXCLUSIVE"
        and candidate.exclusive_workpoint_id == task.bridge_id
        for task in exclusive_tasks
        for candidate in candidates[task.id]
    )
    assert all(len(candidates[task.id]) == 1 for task in exclusive_tasks)

    shared_tasks = [task for task in tasks if task.component_type == "pier_body"]
    assert {task.bridge_id for task in shared_tasks} == {WORKPOINT_A, WORKPOINT_B}
    assert all(len(candidates[task.id]) == 1 for task in shared_tasks)
    assert len({candidates[task.id][0].id for task in shared_tasks}) == 1

    shared_resource_id = candidates[shared_tasks[0].id][0].id
    shared_allocations = sorted(
        [
            allocation
            for allocation in solved.result.resource_allocations
            if allocation.resource_id == shared_resource_id
        ],
        key=lambda allocation: allocation.start_offset,
    )
    assert len(shared_allocations) == 2
    assert shared_allocations[0].end_offset <= shared_allocations[1].start_offset

    diagnostics = solved.result.stats["resource_scope_diagnostics"]
    minimum_group = next(
        group for group in diagnostics["groups"] if group["source_pool_id"] == "pool-minimum"
    )
    assert minimum_group["current_quantity"] == 3
    assert minimum_group["recommended_quantity"] == 2
    assert diagnostics["project_shared_transfer_time_days"] == 0

