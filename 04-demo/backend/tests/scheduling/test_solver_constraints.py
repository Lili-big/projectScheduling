from __future__ import annotations

import sys
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_ROOT))

import app.solver as legacy  # noqa: E402
from app.contracts import ComponentModel, Resource, ScheduleInput, StructureModel, Task  # noqa: E402
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.scheduling.solver.constraints import precedence, resources, workfaces  # noqa: E402
from app.scheduling.solver.engine import _resource_candidates_by_task, _validate_resource_coverage  # noqa: E402


def test_constraint_modules_reference_the_single_engine_implementation() -> None:
    assert precedence._add_precedence_constraint is legacy._add_precedence_constraint
    assert resources._add_execution_constraints is legacy._add_execution_constraints
    assert workfaces._add_normal_workface_constraints is legacy._add_normal_workface_constraints


def test_missing_abutment_pool_does_not_serialize_independent_tasks() -> None:
    pytest.importorskip("ortools")
    scenario = default_scenario()
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = [_abutment_body_structure(1), _abutment_body_structure(2)]
    section.upper_structures = []
    scenario.logic_rules = []
    scenario.upper_structure_logic_rules = []
    scenario.milestones = []
    scenario.time_limit_seconds = 5
    assert all(pool.type != "abutment_team" for pool in scenario.resource_pools)

    generated = generate_schedule_input_from_scenario(scenario)
    result = legacy.solve_schedule(generated.schedule_input)
    abutment_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "abutment_body"]
    scheduled_abutments = [task for task in result.tasks if task.component_type == "abutment_body"]

    assert len(abutment_tasks) == 2
    assert all(task.compatible_resource_types == [] for task in abutment_tasks)
    assert all(resource.type != "abutment_team" for resource in generated.schedule_input.resources)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 15
    assert all(allocation.resource_type != "abutment_team" for allocation in result.resource_allocations)
    assert len(scheduled_abutments) == 2
    assert {task.start_offset for task in scheduled_abutments} == {0}
    assert all(task.assigned_resource_id is None for task in scheduled_abutments)


def test_candidates_use_explicit_scope_fields_without_parsing_resource_id() -> None:
    task_a = _scoped_task("TASK-A", "WP-A")
    task_b = _scoped_task("TASK-B", "WP-B")
    resources = [
        Resource(
            id="opaque-resource-alpha",
            name="甲工点独享资源",
            type="cap_team",
            pool_id="pool-cap",
            scope_mode="WORKPOINT_EXCLUSIVE",
            eligible_workpoint_ids=["WP-A"],
            exclusive_workpoint_id="WP-A",
        ),
        Resource(
            id="WP-A-looking-but-b-owned",
            name="乙工点独享资源",
            type="cap_team",
            pool_id="pool-cap",
            scope_mode="WORKPOINT_EXCLUSIVE",
            eligible_workpoint_ids=["WP-B"],
            exclusive_workpoint_id="WP-B",
        ),
    ]

    candidates = _resource_candidates_by_task([task_a, task_b], resources)

    assert [resource.id for resource in candidates[task_a.id]] == ["opaque-resource-alpha"]
    assert [resource.id for resource in candidates[task_b.id]] == ["WP-A-looking-but-b-owned"]


def test_scoped_limited_resource_blocks_missing_or_unauthorized_task_workpoint() -> None:
    scoped_resource = Resource(
        id="resource-1",
        name="受限资源",
        type="cap_team",
        pool_id="pool-cap",
        scope_mode="PROJECT_SHARED",
        eligible_workpoint_ids=["WP-A"],
    )
    missing = _scoped_task("TASK-MISSING", None)
    unauthorized = _scoped_task("TASK-B", "WP-B")
    candidates = _resource_candidates_by_task([missing, unauthorized], [scoped_resource])

    validation = _validate_resource_coverage([missing, unauthorized], candidates, [scoped_resource])

    assert candidates == {missing.id: [], unauthorized.id: []}
    assert len(validation) == 2
    assert all(message.level == "error" for message in validation)
    assert all(message.code == "RESOURCE_SCOPE_NO_LEGAL_CANDIDATE" for message in validation)


@pytest.mark.parametrize(
    ("pool_changes", "expected_reason"),
    [
        pytest.param({"enabled": False}, "未启用", id="disabled"),
        pytest.param({"resource_mode": "UNLIMITED"}, "设置为默认充足", id="unlimited"),
        pytest.param({"quantity": 0, "max_quantity": 0}, "资源上限为 0", id="max-quantity-zero"),
    ],
)
def test_explicit_unavailable_resource_states_keep_default_sufficient_warning(
    pool_changes: dict[str, object],
    expected_reason: str,
) -> None:
    scenario = default_scenario()
    pool = next(pool for pool in scenario.resource_pools if pool.type == "cap_team")
    for field, value in pool_changes.items():
        setattr(pool, field, value)

    generated = generate_schedule_input_from_scenario(scenario)
    cap_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cap"]
    expected_warning = (
        f'资源“{pool.label}”{expected_reason}，相关工作项按资源默认充足处理，不产生资源等待。'
    )

    assert cap_tasks
    assert all(task.compatible_resource_types == [] for task in cap_tasks)
    assert all(resource.pool_id != pool.id for resource in generated.schedule_input.resources)
    assert all(message.level != "error" for message in generated.validation)
    assert any(
        message.level == "warning" and message.subject_id == pool.id and message.message == expected_warning
        for message in generated.validation
    )


def test_shared_resource_is_serial_across_authorized_workpoints_with_zero_transfer() -> None:
    pytest.importorskip("ortools")
    tasks = [_scoped_task("TASK-A", "WP-A", duration_days=5), _scoped_task("TASK-B", "WP-B", duration_days=5)]
    result = legacy.solve_shortest_duration_schedule(
        ScheduleInput(
            project_name="共享资源串行",
            start_date=default_scenario().project.start_date,
            tasks=tasks,
            precedence_links=[],
            resources=[
                Resource(
                    id="shared-resource",
                    name="共享资源",
                    type="cap_team",
                    pool_id="pool-cap",
                    scope_mode="PROJECT_SHARED",
                    eligible_workpoint_ids=["WP-A", "WP-B"],
                )
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 10
    assert len(result.resource_allocations) == 2
    assert result.stats["resource_scope_diagnostics"]["project_shared_transfer_time_days"] == 0


def _abutment_body_structure(index: int) -> StructureModel:
    return StructureModel(
        id=f"STRUCTURE-{index}",
        name=f"Structure {index}",
        structure_type="abutment",
        order=index,
        components=[
            ComponentModel(
                id=f"COMPONENT-{index}",
                name=f"Component {index}",
                component_type="abutment_body",
                quantity=1,
                quantity_label="1个",
            )
        ],
    )


def _scoped_task(task_id: str, bridge_id: str | None, *, duration_days: int = 1) -> Task:
    return Task(
        id=task_id,
        name=task_id,
        bridge_id=bridge_id,
        structure_id=f"S-{task_id}",
        structure_name=task_id,
        structure_type="pier",
        component_type="cap",
        process_name="承台施工",
        productivity_rule_id="cap-test",
        quantity=1,
        quantity_label="1个",
        duration_days=duration_days,
        compatible_resource_types=["cap_team"],
    )
