from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import MilestoneConstraint, PrecedenceLink, ProcessTemplate, ProductivityOption, Resource, ResourcePool, ScheduleInput, ScenarioCompareRequest, ScheduledTask, Task  # noqa: E402
from app.process_library_defaults import upgrade_process_library  # noqa: E402
from app.sample_data import (  # noqa: E402
    default_bridge,
    default_logic_rules,
    default_productivity_rules,
    default_resources,
)
from app.scenario import compare_scenarios, generate_schedule_input_from_scenario, solve_scenario  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.solver import _resource_path_metrics, _task_ids_for_milestone, solve_min_resources_schedule, solve_schedule  # noqa: E402
from app.wbs import calculate_duration, generate_wbs  # noqa: E402


def test_duration_calculation_uses_historical_days_per_pile() -> None:
    rotary = next(rule for rule in default_productivity_rules() if rule.id == "pile_rotary_regular")
    assert rotary.duration_method == "days_per_unit"
    assert rotary.quantity_source == "count"
    assert rotary.productivity_unit == "天/根"
    assert calculate_duration(1, rotary) == 3
    assert calculate_duration(2, rotary) == 6


def test_default_process_library_uses_historical_productivity_defaults() -> None:
    process_by_id = {process.id: process for process in default_scenario().process_library}

    assert process_by_id["pile_rotary_regular"].productivity_value == 3
    assert process_by_id["pile_rotary_regular"].productivity_unit == "天/根"
    assert process_by_id["pile_circulation"].productivity_value == 2
    assert process_by_id["pile_impact"].productivity_value == 2
    assert process_by_id["cap_standard"].productivity_value == 30
    assert process_by_id["pier_body_climbing_form"].productivity_unit == "天/节"
    assert process_by_id["pier_body_climbing_form"].quantity_source == "pier_height_m"
    assert process_by_id["pier_body_climbing_form"].productivity_options[0].standard_section_height_m == 4.5
    assert process_by_id["cast_in_place_continuous_zero_block"].productivity_value == 120
    assert process_by_id["bridge_deck_system_standard"].quantity_source == "deck_length_m"
    for process in process_by_id.values():
        assert sum(1 for option in process.productivity_options if option.is_default) == 1


def test_process_library_upgrade_replaces_previous_builtin_defaults_and_adds_missing_history() -> None:
    upgraded = upgrade_process_library(
        [
            ProcessTemplate(
                id="pile_rotary_regular",
                component_type="pile",
                process_name="旋挖钻成孔",
                method_id="rotary_drill",
                duration_method="units_per_day",
                quantity_source="pile_length_m",
                productivity_value=18,
                productivity_unit="m/天",
                resource_type="rotary_drill",
                is_default=True,
            ),
            ProcessTemplate(
                id="cap_standard",
                component_type="cap",
                process_name="承台施工",
                duration_method="fixed_days",
                quantity_source="count",
                productivity_value=8,
                productivity_unit="天/个",
                resource_type="cap_team",
                is_default=True,
            ),
        ]
    )
    process_by_id = {process.id: process for process in upgraded}

    assert process_by_id["pile_rotary_regular"].productivity_value == 3
    assert process_by_id["pile_rotary_regular"].quantity_source == "count"
    assert process_by_id["cap_standard"].productivity_value == 30
    assert process_by_id["precast_beam_standard"].productivity_unit == "天/片"
    assert process_by_id["cast_in_place_box_beam_standard"].productivity_value == 45
    for process in upgraded:
        default = next(option for option in process.productivity_options if option.is_default)
        assert process.duration_method == default.duration_method
        assert process.quantity_source == default.quantity_source
        assert process.productivity_value == default.productivity_value
        assert process.productivity_unit == default.productivity_unit


def test_default_wbs_generates_tasks_and_logic_links() -> None:
    wbs = generate_wbs(default_bridge(), default_productivity_rules(), default_logic_rules())
    task_ids = {task.id for task in wbs.tasks}
    assert "P01-PILE-01" in task_ids
    assert "P01-CAP" in task_ids
    assert "P01-BODY" in task_ids
    assert "P01-BEAM" in task_ids
    assert any(link.predecessor_id == "P01-CAP" and link.successor_id == "P01-BODY" for link in wbs.precedence_links)


def test_pile_method_selects_impact_drill_rule() -> None:
    bridge = default_bridge()
    bridge.piers[0].pile_method = "impact_drill"
    wbs = generate_wbs(bridge, default_productivity_rules(), default_logic_rules())
    p01_piles = [task for task in wbs.tasks if task.id.startswith("P01-PILE")]

    assert {task.process_name for task in p01_piles} == {"冲击钻"}
    assert {task.duration_days for task in p01_piles} == {2}
    assert {task.compatible_resource_types[0] for task in p01_piles} == {"impact_drill"}


def test_missing_resource_returns_infeasible_without_solving() -> None:
    bridge = default_bridge()
    wbs = generate_wbs(bridge, default_productivity_rules(), default_logic_rules())
    resources = [resource for resource in default_resources() if resource.type != "cap_team"]
    result = solve_schedule(
        ScheduleInput(
            project_name=bridge.project_name,
            start_date=bridge.start_date,
            tasks=wbs.tasks,
            precedence_links=wbs.precedence_links,
            resources=resources,
        )
    )
    assert result.status == "INFEASIBLE"
    assert any(message.level == "error" and "承台" in message.message for message in result.validation)


def test_default_solver_satisfies_logic_and_resource_constraints() -> None:
    pytest.importorskip("ortools")
    bridge = default_bridge()
    wbs = generate_wbs(bridge, default_productivity_rules(), default_logic_rules())
    result = solve_schedule(
        ScheduleInput(
            project_name=bridge.project_name,
            start_date=bridge.start_date,
            tasks=wbs.tasks,
            precedence_links=wbs.precedence_links,
            resources=default_resources(),
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    by_task = {task.id: task for task in result.tasks}
    for link in wbs.precedence_links:
        assert by_task[link.successor_id].start_offset >= by_task[link.predecessor_id].end_offset + link.lag_days

    by_resource: dict[str, list] = {}
    for allocation in result.resource_allocations:
        by_resource.setdefault(allocation.resource_id, []).append(allocation)
    for allocations in by_resource.values():
        ordered = sorted(allocations, key=lambda item: item.start_offset)
        for previous, current in zip(ordered, ordered[1:]):
            assert current.start_offset >= previous.end_offset


def test_default_scenario_generates_schedule_input() -> None:
    generated = generate_schedule_input_from_scenario(default_scenario())

    assert not any(message.level == "error" for message in generated.validation)
    assert generated.schedule_input.tasks
    assert generated.schedule_input.resources
    assert generated.schedule_input.milestones
    assert any(task.bridge_id == "B1" and task.work_section_id == "WS-LOWER" for task in generated.schedule_input.tasks)


def test_default_scenario_sets_resource_max_quantity_from_component_counts() -> None:
    scenario = default_scenario()
    max_by_type = {pool.type: pool.max_quantity for pool in scenario.resource_pools}

    assert max_by_type["rotary_drill"] == 24
    assert max_by_type["manual_pile_team"] == 4
    assert max_by_type["cap_team"] == 14
    assert max_by_type["pier_body_team"] == 12
    assert max_by_type["cap_beam_team"] == 12
    assert max_by_type["abutment_team"] == 2


def test_resource_pool_max_quantity_defaults_to_quantity() -> None:
    pool = ResourcePool.model_validate({"id": "pool-team", "type": "team", "label": "班组", "quantity": 2})

    assert pool.max_quantity == 2


def test_schedule_input_uses_default_or_max_resource_quantity() -> None:
    scenario = default_scenario()
    scenario.resource_pools[0].quantity = 1
    scenario.resource_pools[0].max_quantity = 3

    default_generated = generate_schedule_input_from_scenario(scenario)
    max_generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)

    assert sum(1 for resource in default_generated.schedule_input.resources if resource.type == scenario.resource_pools[0].type) == 1
    assert sum(1 for resource in max_generated.schedule_input.resources if resource.type == scenario.resource_pools[0].type) == 3


def test_scenario_pile_method_selects_process_template() -> None:
    scenario = default_scenario()
    p01_pile = next(
        component
        for component in scenario.project.bridges[0].work_sections[0].structures[1].components
        if component.id == "P01-PILE-01"
    )
    p01_pile.method_id = "impact_drill"

    generated = generate_schedule_input_from_scenario(scenario)
    task = next(task for task in generated.schedule_input.tasks if task.id == "P01-PILE-01")

    assert task.productivity_rule_id == "pile_impact:pile_impact-default"
    assert task.duration_days == 2
    assert task.compatible_resource_types == ["impact_drill"]


def test_component_type_milestone_matches_all_components_of_that_type() -> None:
    scenario = default_scenario()
    generated = generate_schedule_input_from_scenario(scenario)
    cap_milestone = next(milestone for milestone in scenario.milestones if milestone.scope_id == "cap")
    scoped_task_ids = set(_task_ids_for_milestone(cap_milestone, generated.schedule_input.tasks))
    cap_task_ids = {task.id for task in generated.schedule_input.tasks if task.component_type == "cap"}

    assert scoped_task_ids == cap_task_ids
    assert len(scoped_task_ids) > 1


def test_component_productivity_group_overrides_process_default() -> None:
    scenario = default_scenario()
    rotary_process = next(process for process in scenario.process_library if process.method_id == "rotary_drill")
    rotary_process.productivity_options = [
        ProductivityOption(
            id="rotary-by-length",
            name="按桩长",
            duration_method="units_per_day",
            quantity_source="pile_length_m",
            productivity_value=18,
            productivity_unit="m/天",
            is_default=True,
        ),
        ProductivityOption(
            id="rotary-by-pile",
            name="按根计",
            duration_method="days_per_unit",
            quantity_source="count",
            productivity_value=2,
            productivity_unit="天/根",
        ),
    ]
    p01_pile = next(
        component
        for component in scenario.project.bridges[0].work_sections[0].structures[1].components
        if component.id == "P01-PILE-01"
    )
    p01_pile.productivity_option_id = "rotary-by-pile"

    generated = generate_schedule_input_from_scenario(scenario)
    task = next(task for task in generated.schedule_input.tasks if task.id == "P01-PILE-01")

    assert task.productivity_rule_id == "pile_rotary_regular:rotary-by-pile"
    assert task.quantity == 1
    assert task.quantity_label == "1根"
    assert task.duration_days == 2


def test_pier_body_days_per_section_uses_standard_section_height() -> None:
    scenario = default_scenario()
    p01_body = next(
        component
        for component in scenario.project.bridges[0].work_sections[0].structures[1].components
        if component.component_type == "pier_body"
    )
    p01_body.method_id = "climbing_form"

    generated = generate_schedule_input_from_scenario(scenario)
    task = next(task for task in generated.schedule_input.tasks if task.id == p01_body.id)

    assert task.productivity_rule_id == "pier_body_climbing_form:pier_body_climbing_form-default"
    assert task.quantity == p01_body.quantity
    assert task.quantity_label == p01_body.quantity_label
    assert task.duration_days == math.ceil(p01_body.quantity / 4.5) * 7


def test_pier_body_section_height_can_be_overridden_per_productivity_group() -> None:
    scenario = default_scenario()
    climbing = next(process for process in scenario.process_library if process.method_id == "climbing_form")
    option = climbing.productivity_options[0]
    option.standard_section_height_m = 3

    p01_body = next(
        component
        for component in scenario.project.bridges[0].work_sections[0].structures[1].components
        if component.component_type == "pier_body"
    )
    p01_body.method_id = "climbing_form"

    generated = generate_schedule_input_from_scenario(scenario)
    task = next(task for task in generated.schedule_input.tasks if task.id == p01_body.id)

    assert task.duration_days == math.ceil(p01_body.quantity / 3) * 7


def test_pier_body_m_per_day_uses_pier_height_quantity() -> None:
    scenario = default_scenario()
    climbing = next(process for process in scenario.process_library if process.method_id == "climbing_form")
    option = climbing.productivity_options[0]
    option.duration_method = "units_per_day"
    option.quantity_source = "pier_height_m"
    option.productivity_value = 2
    option.productivity_unit = "m/天"
    option.standard_section_height_m = None

    p01_body = next(
        component
        for component in scenario.project.bridges[0].work_sections[0].structures[1].components
        if component.component_type == "pier_body"
    )
    p01_body.method_id = "climbing_form"

    generated = generate_schedule_input_from_scenario(scenario)
    task = next(task for task in generated.schedule_input.tasks if task.id == p01_body.id)

    assert task.quantity == p01_body.quantity
    assert task.duration_days == math.ceil(p01_body.quantity / 2)


def test_scenario_solver_satisfies_ss_logic() -> None:
    pytest.importorskip("ortools")
    scenario = default_scenario()
    rule = next(rule for rule in scenario.logic_rules if rule.id == "pier_body_after_cap")
    rule.relationship = "SS"
    rule.lag_days = 2

    solved = solve_scenario(scenario)

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    by_task = {task.id: task for task in solved.result.tasks}
    ss_links = [
        link
        for link in solved.generated.schedule_input.precedence_links
        if link.source_rule_id == "pier_body_after_cap"
    ]
    assert ss_links
    for link in ss_links:
        assert by_task[link.successor_id].start_offset >= by_task[link.predecessor_id].start_offset + link.lag_days


def test_shortest_duration_allows_hard_milestone_lateness_with_error_diagnostic() -> None:
    pytest.importorskip("ortools")
    scenario = default_scenario()
    hard_milestone = scenario.milestones[0].model_copy(
        update={"target_date": scenario.project.start_date}
    )
    scenario.milestones = [hard_milestone]

    solved = solve_scenario(scenario)

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert solved.milestone_results[0].lateness_days > 0
    assert any(message.level == "error" and "强制里程碑目标" in message.message for message in solved.result.validation)


def test_soft_milestone_returns_lateness_and_penalty() -> None:
    pytest.importorskip("ortools")
    scenario = default_scenario()
    soft_milestone = scenario.milestones[2].model_copy(
        update={"target_date": scenario.project.start_date, "penalty_per_day": 7}
    )
    scenario.milestones = [soft_milestone]

    solved = solve_scenario(scenario)

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert solved.milestone_results[0].lateness_days > 0
    assert solved.milestone_results[0].penalty == solved.milestone_results[0].lateness_days * 7


def test_logic_links_are_hard_precedence_constraints() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        Task(
            id="A",
            name="前置任务",
            structure_id="S1",
            structure_name="1#墩",
            structure_type="pier",
            component_type="pile",
            process_name="前置",
            productivity_rule_id="r1",
            quantity=1,
            quantity_label="1个",
            duration_days=5,
            compatible_resource_types=["team"],
        ),
        Task(
            id="B",
            name="后续任务",
            structure_id="S1",
            structure_name="1#墩",
            structure_type="pier",
            component_type="cap",
            process_name="后续",
            productivity_rule_id="r2",
            quantity=1,
            quantity_label="1个",
            duration_days=5,
            compatible_resource_types=["team"],
        ),
    ]
    resources = [
        Resource(id="team-1", name="班组1", type="team"),
        Resource(id="team-2", name="班组2", type="team"),
    ]

    result = solve_schedule(
        ScheduleInput(
            project_name="逻辑硬约束测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="L-hard",
                    predecessor_id="A",
                    successor_id="B",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="hard-rule",
                    severity="error",
                )
            ],
            resources=resources,
            milestones=[
                MilestoneConstraint(
                    id="M-finish",
                    name="5天完工",
                    level="contract",
                    mode="hard",
                    scope_type="project",
                    target_event="finish",
                    target_date=date(2026, 1, 5),
                )
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    by_task = {task.id: task for task in result.tasks}
    assert by_task["B"].start_offset >= by_task["A"].end_offset
    assert any(message.level == "info" and "工艺逻辑关系均已满足" in message.message for message in result.validation)


def test_solver_prefers_same_resource_for_same_structure_and_craft() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        Task(
            id="B1-L-P03-PILE-01",
            name="3#墩-1#桩基",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=300,
            structure_id="B1-L-P03",
            structure_name="3#墩",
            structure_type="pier",
            component_type="pile",
            process_name="桩基",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1根",
            duration_days=2,
            compatible_resource_types=["rotary_drill"],
        ),
        Task(
            id="B1-L-P03-PILE-02",
            name="3#墩-2#桩基",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=301,
            structure_id="B1-L-P03",
            structure_name="3#墩",
            structure_type="pier",
            component_type="pile",
            process_name="桩基",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1根",
            duration_days=2,
            compatible_resource_types=["rotary_drill"],
        ),
    ]
    result = solve_schedule(
        ScheduleInput(
            project_name="同墩同工艺连续性测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="same-pier-order",
                    predecessor_id="B1-L-P03-PILE-01",
                    successor_id="B1-L-P03-PILE-02",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="manual",
                )
            ],
            resources=[
                Resource(id="rotary_drill_1", name="旋挖钻1", type="rotary_drill"),
                Resource(id="rotary_drill_2", name="旋挖钻2", type="rotary_drill"),
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    by_task = {task.id: task for task in result.tasks}
    assert by_task["B1-L-P03-PILE-01"].assigned_resource_id == by_task["B1-L-P03-PILE-02"].assigned_resource_id
    assert result.stats["continuity_metrics"]["same_structure_craft_split_count"] == 0


def test_continuity_metrics_report_side_switch_without_ordered_pier_jump() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        Task(
            id="B1-L-P02-PILE-01",
            name="左幅2#墩桩基",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=200,
            structure_id="B1-L-P02",
            structure_name="2#墩",
            structure_type="pier",
            component_type="pile",
            process_name="桩基",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["rotary_drill"],
        ),
        Task(
            id="B1-R-P06-PILE-01",
            name="右幅6#墩桩基",
            bridge_id="B1",
            work_section_id="WS-R",
            sequence_order=600,
            structure_id="B1-R-P06",
            structure_name="6#墩",
            structure_type="pier",
            component_type="pile",
            process_name="桩基",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["rotary_drill"],
        ),
    ]
    result = solve_schedule(
        ScheduleInput(
            project_name="跳幅不等于跳墩指标测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="jump-order",
                    predecessor_id="B1-L-P02-PILE-01",
                    successor_id="B1-R-P06-PILE-01",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="manual",
                )
            ],
            resources=[Resource(id="rotary_drill_1", name="旋挖钻1", type="rotary_drill")],
            time_limit_seconds=5,
        )
    )

    metrics = result.stats["continuity_metrics"]
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert metrics["jump_pier_count"] == 0
    assert metrics["side_switch_count"] == 1
    assert metrics["cross_side_jump_count"] == 0
    assert metrics["max_jump_distance"] == 0


def test_continuity_metrics_do_not_count_sparse_ordered_piers_as_jump() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        Task(
            id=f"B1-L-P{pier_no:02d}-PILE-01",
            name=f"左幅{pier_no}#墩人工挖孔桩",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=pier_no * 100,
            structure_id=f"B1-L-P{pier_no:02d}",
            structure_name=f"{pier_no}#墩",
            structure_type="pier",
            component_type="pile",
            process_name="人工挖孔",
            productivity_rule_id="pile_manual",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["manual_pile_team"],
        )
        for pier_no in (1, 3, 5)
    ]
    result = solve_schedule(
        ScheduleInput(
            project_name="稀疏墩号顺序不计跳墩测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="manual-pile-1-3",
                    predecessor_id="B1-L-P01-PILE-01",
                    successor_id="B1-L-P03-PILE-01",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="manual",
                ),
                PrecedenceLink(
                    id="manual-pile-3-5",
                    predecessor_id="B1-L-P03-PILE-01",
                    successor_id="B1-L-P05-PILE-01",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="manual",
                ),
            ],
            resources=[Resource(id="manual_pile_team_1", name="人工挖孔班1", type="manual_pile_team")],
            time_limit_seconds=5,
        )
    )

    metrics = result.stats["continuity_metrics"]
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert [step["location"] for step in metrics["resource_paths"][0]["path"]] == ["左幅1#墩", "左幅3#墩", "左幅5#墩"]
    assert metrics["jump_pier_count"] == 0
    assert metrics["max_jump_distance"] == 0


def test_continuity_metrics_count_ranked_scope_skip_as_jump() -> None:
    start = date(2026, 1, 1)

    def manual_pile_task(pier_no: int, resource_no: int, start_offset: int) -> ScheduledTask:
        return ScheduledTask(
            id=f"B1-L-P{pier_no:02d}-PILE-01",
            name=f"左幅{pier_no}#墩人工挖孔桩",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=pier_no * 100,
            structure_id=f"B1-L-P{pier_no:02d}",
            structure_name=f"{pier_no}#墩",
            structure_type="pier",
            component_type="pile",
            process_name="人工挖孔",
            productivity_rule_id="pile_manual",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["manual_pile_team"],
            start_offset=start_offset,
            end_offset=start_offset + 1,
            start_date=start,
            finish_date=start,
            assigned_resource_id=f"manual_pile_team_{resource_no}",
            assigned_resource_name=f"人工挖孔班{resource_no}",
            assigned_resource_type="manual_pile_team",
            predecessor_ids=[],
        )

    metrics = _resource_path_metrics(
        [
            manual_pile_task(1, resource_no=1, start_offset=0),
            manual_pile_task(5, resource_no=1, start_offset=2),
            manual_pile_task(3, resource_no=2, start_offset=1),
        ]
    )

    assert metrics["jump_pier_count"] == 1
    assert metrics["max_jump_distance"] == 2
    assert metrics["jump_transition_details"][0]["from_location"] == "左幅1#墩"
    assert metrics["jump_transition_details"][0]["to_location"] == "左幅5#墩"
    assert metrics["jump_transition_details"][0]["jump_distance"] == 2


def test_continuity_metrics_do_not_count_same_pier_side_switch_as_jump() -> None:
    start = date(2026, 1, 1)

    def pile_task(side_code: str, side_name: str, pier_no: int, resource_no: int, start_offset: int) -> ScheduledTask:
        return ScheduledTask(
            id=f"B1-{side_code}-P{pier_no:02d}-PILE-01",
            name=f"{side_name}{pier_no}#墩桩基",
            bridge_id="B1",
            work_section_id=f"WS-{side_code}",
            sequence_order=pier_no * 100,
            structure_id=f"B1-{side_code}-P{pier_no:02d}",
            structure_name=f"{pier_no}#墩",
            structure_type="pier",
            component_type="pile",
            process_name="桩基",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["rotary_drill"],
            start_offset=start_offset,
            end_offset=start_offset + 1,
            start_date=start,
            finish_date=start,
            assigned_resource_id=f"rotary_drill_{resource_no}",
            assigned_resource_name=f"旋挖钻{resource_no}",
            assigned_resource_type="rotary_drill",
            predecessor_ids=[],
        )

    metrics = _resource_path_metrics(
        [
            pile_task("L", "左幅", 1, resource_no=1, start_offset=0),
            pile_task("R", "右幅", 1, resource_no=1, start_offset=1),
            pile_task("L", "左幅", 3, resource_no=2, start_offset=0),
        ]
    )

    assert metrics["jump_pier_count"] == 0
    assert metrics["side_switch_count"] == 1
    assert metrics["cross_side_jump_count"] == 0
    assert metrics["max_jump_distance"] == 0
    assert metrics["jump_transition_details"][0]["is_side_switch"] is True
    assert metrics["jump_transition_details"][0]["is_jump_pier"] is False


def test_continuity_metrics_do_not_count_abutment_span_as_jump_pier() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        Task(
            id="B1-L-A00-BODY",
            name="左幅0#桥台台身",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=0,
            structure_id="B1-L-A00",
            structure_name="0#桥台",
            structure_type="abutment",
            component_type="abutment_body",
            process_name="桥台施工",
            productivity_rule_id="abutment",
            quantity=1,
            quantity_label="1个",
            duration_days=1,
            compatible_resource_types=["abutment_team"],
        ),
        Task(
            id="B1-L-A24-BODY",
            name="左幅24#桥台台身",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=2400,
            structure_id="B1-L-A24",
            structure_name="24#桥台",
            structure_type="abutment",
            component_type="abutment_body",
            process_name="桥台施工",
            productivity_rule_id="abutment",
            quantity=1,
            quantity_label="1个",
            duration_days=1,
            compatible_resource_types=["abutment_team"],
        ),
    ]
    result = solve_schedule(
        ScheduleInput(
            project_name="桥台路径不计跳墩测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="abutment-order",
                    predecessor_id="B1-L-A00-BODY",
                    successor_id="B1-L-A24-BODY",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="manual",
                )
            ],
            resources=[Resource(id="abutment_team_1", name="桥台班组1", type="abutment_team")],
            time_limit_seconds=5,
        )
    )

    metrics = result.stats["continuity_metrics"]
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert metrics["jump_pier_count"] == 0
    assert metrics["cross_side_jump_count"] == 0
    assert metrics["max_jump_distance"] == 0
    assert metrics["jump_transition_details"] == []


def test_min_resource_solver_uses_fallback_target_days() -> None:
    pytest.importorskip("ortools")
    result = solve_min_resources_schedule(_min_resource_test_input(max_resources=2), fallback_target_days=5)

    recommended = result.stats["recommended_resource_counts"][0]
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 5
    assert recommended["recommended_quantity"] == 2
    assert recommended["max_quantity"] == 2


def test_min_resource_solver_requires_target_duration() -> None:
    pytest.importorskip("ortools")
    result = solve_min_resources_schedule(_min_resource_test_input(max_resources=2))

    assert result.status == "MODEL_INVALID"
    assert any(message.level == "error" and "固定工期" in message.message for message in result.validation)


def test_min_resource_solver_reports_infeasible_when_max_resources_cannot_meet_target() -> None:
    pytest.importorskip("ortools")
    result = solve_min_resources_schedule(_min_resource_test_input(max_resources=1), fallback_target_days=5)

    assert result.status == "INFEASIBLE"
    assert result.stats["reason"] == "resource_upper_bound_or_deadline_infeasible"
    assert result.stats["fixed_duration_precheck_failed"] is True
    assert any("资源最大数量后仍不可行" in message.message for message in result.validation)
    assert any("工艺逻辑关键路径" in message.message for message in result.validation)
    assert any("至少需要约" in message.message for message in result.validation)


def test_min_resource_solver_enforces_hard_milestone_target() -> None:
    pytest.importorskip("ortools")
    schedule_input = _min_resource_test_input(max_resources=2)
    schedule_input.milestones = [
        MilestoneConstraint(
            id="M-hard",
            name="强制完工目标",
            mode="hard",
            scope_type="project",
            target_event="finish",
            target_date=date(2026, 1, 4),
        )
    ]

    result = solve_min_resources_schedule(schedule_input)

    assert result.status == "INFEASIBLE"
    assert result.stats["reason"] == "resource_upper_bound_or_deadline_infeasible"
    assert result.stats["fixed_duration_precheck_failed"] is True


def test_compare_scenarios_returns_best_result() -> None:
    pytest.importorskip("ortools")
    solved = solve_scenario(default_scenario())
    response = compare_scenarios(ScenarioCompareRequest(results=[solved]))

    assert response.best_scenario_id == solved.scenario_id
    assert response.summaries[0]["total_days"] == solved.result.objective_days


def _min_resource_test_input(max_resources: int) -> ScheduleInput:
    tasks = [
        Task(
            id=f"T{index}",
            name=f"任务{index}",
            structure_id=f"S{index}",
            structure_name=f"{index}#墩",
            structure_type="pier",
            component_type="pile",
            process_name="施工",
            productivity_rule_id="rule",
            quantity=1,
            quantity_label="1个",
            duration_days=5,
            compatible_resource_types=["team"],
        )
        for index in range(1, 3)
    ]
    return ScheduleInput(
        project_name="最少资源测试",
        start_date=date(2026, 1, 1),
        tasks=tasks,
        precedence_links=[],
        resources=[
            Resource(id=f"team_{index}", name=f"班组{index}", type="team", pool_id="pool-team", pool_label="班组")
            for index in range(1, max_resources + 1)
        ],
        time_limit_seconds=5,
    )
