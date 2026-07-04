from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.scenario as scenario_module  # noqa: E402
import app.solver as solver_module  # noqa: E402
from app.models import ComponentModel, MilestoneConstraint, PrecedenceLink, ProcessTemplate, ProductivityOption, ProjectBridge, ProjectModel, Resource, ResourceCostSolveRequest, ResourcePool, ScheduleInput, ScheduleStrategyConfig, ScenarioCompareRequest, ScenarioInput, ScheduledTask, StructureModel, Task, TaskOverride, UpperStructureComponent, UpperStructureLogicRule, ValidationMessage, WorkSection  # noqa: E402
from app.models import MilestoneResult, ScheduleResult  # noqa: E402
from app.process_library_defaults import upgrade_process_library  # noqa: E402
from app.sample_data import (  # noqa: E402
    default_bridge,
    default_logic_rules,
    default_productivity_rules,
    default_resources,
)
from app.scenario import compare_scenarios, generate_schedule_input_from_scenario, solve_resource_cost_scenario, solve_scenario  # noqa: E402
from app.scenario_data import apply_resource_max_quantity_defaults, default_scenario  # noqa: E402
from app.services.bridge_import_service import import_local_bridge_params  # noqa: E402
from app.solver import _resource_path_metrics, _task_ids_for_milestone, solve_capacity_shortest_schedule, solve_min_resources_schedule, solve_resource_cost_schedule, solve_schedule  # noqa: E402
from app.wbs import calculate_duration, generate_wbs  # noqa: E402


def test_schedule_strategy_merges_objective_term_defaults_and_ignores_legacy_balance_target() -> None:
    config = ScheduleStrategyConfig(enable_balance_objective=True)

    assert set(config.objective_terms) == {
        "control_node_late",
        "control_buffer_risk",
        "risk_related_control_wait",
        "resource_workload_balance",
        "resource_idle",
        "resource_path_continuity",
        "makespan_and_soft_milestone",
    }
    assert config.enable_balance_objective is False
    assert config.objective_terms["control_node_late"].weight == 1_000_000_000

    legacy_config = ScheduleStrategyConfig(
        enable_balance_objective=True,
        objective_terms={"normal_balance": {"enabled": True, "weight": 7}},
    )

    assert legacy_config.enable_balance_objective is False
    assert "normal_balance" not in legacy_config.objective_terms

    disabled_zero_weight = ScheduleStrategyConfig(objective_terms={"resource_idle": {"enabled": False, "weight": 0}})
    assert disabled_zero_weight.objective_terms["resource_idle"].weight == 0
    assert disabled_zero_weight.objective_terms["resource_idle"].enabled is False

    deprecated_spatial = ScheduleStrategyConfig(
        objective_terms={"spatial_resource_assignment": {"enabled": True, "weight": 1}}
    )
    assert "spatial_resource_assignment" not in deprecated_spatial.objective_terms

    deprecated_same_structure = ScheduleStrategyConfig(
        objective_terms={"same_structure_craft_split": {"enabled": False, "weight": 1}}
    )
    assert "same_structure_craft_split" not in deprecated_same_structure.objective_terms


def test_schedule_strategy_rejects_invalid_objective_term_config() -> None:
    with pytest.raises(ValidationError, match="unknown objective_terms"):
        ScheduleStrategyConfig(objective_terms={"unknown_term": {"enabled": True, "weight": 1}})

    with pytest.raises(ValidationError, match="less than or equal"):
        ScheduleStrategyConfig(objective_terms={"resource_idle": {"enabled": True, "weight": 1_000_000_001}})

    with pytest.raises(ValidationError, match="at least one objective term must be enabled"):
        ScheduleStrategyConfig(
            objective_terms={
                "control_node_late": {"enabled": False, "weight": 1},
                "control_buffer_risk": {"enabled": False, "weight": 1},
                "risk_related_control_wait": {"enabled": False, "weight": 1},
                "resource_workload_balance": {"enabled": False, "weight": 1},
                "resource_idle": {"enabled": False, "weight": 1},
                "resource_path_continuity": {"enabled": False, "weight": 1},
                "makespan_and_soft_milestone": {"enabled": False, "weight": 1},
            }
        )


def _objective_terms_with_only(enabled_term: str, weight: int) -> dict[str, dict[str, bool | int]]:
    term_ids = [
        "control_node_late",
        "control_buffer_risk",
        "risk_related_control_wait",
        "makespan_and_soft_milestone",
        "resource_path_continuity",
        "resource_idle",
        "resource_workload_balance",
    ]
    return {
        term_id: {"enabled": term_id == enabled_term, "weight": weight if term_id == enabled_term else 1}
        for term_id in term_ids
    }


def test_duration_calculation_uses_fixed_days_per_pile() -> None:
    rotary = next(rule for rule in default_productivity_rules() if rule.id == "pile_rotary_regular")
    assert rotary.duration_method == "fixed_days"
    assert rotary.quantity_source == "count"
    assert rotary.productivity_unit == "天/根"
    assert calculate_duration(1, rotary) == 3
    assert calculate_duration(2, rotary) == 3


def test_default_process_library_uses_historical_productivity_defaults() -> None:
    process_by_id = {process.id: process for process in default_scenario().process_library}

    assert process_by_id["pile_rotary_regular"].productivity_value == 3
    assert process_by_id["pile_rotary_regular"].duration_method == "fixed_days"
    assert process_by_id["pile_rotary_regular"].productivity_unit == "天/根"
    assert process_by_id["pile_circulation"].productivity_value == 2
    assert process_by_id["pile_impact"].productivity_value == 2
    assert process_by_id["cap_standard"].productivity_value == 30
    assert process_by_id["pier_body_climbing_form"].productivity_unit == "天/节"
    assert process_by_id["pier_body_climbing_form"].quantity_source == "pier_height_m"
    assert process_by_id["pier_body_climbing_form"].productivity_options[0].standard_section_height_m == 4.5
    assert process_by_id["pier_body_climbing_form"].is_default is True
    assert process_by_id["pier_body_standard"].is_default is False
    assert process_by_id["cast_in_place_continuous_zero_block"].productivity_value == 120
    assert process_by_id["cast_in_place_continuous_standard_segment"].duration_method == "days_per_unit"
    assert process_by_id["bridge_deck_system_standard"].quantity_source == "deck_length_m"
    for process in process_by_id.values():
        assert sum(1 for option in process.productivity_options if option.is_default) == 1


def test_pile_days_per_pile_unit_normalizes_to_fixed_days() -> None:
    process = ProcessTemplate(
        id="pile-custom",
        component_type="pile",
        process_name="自定义桩基",
        method_id="rotary_drill",
        duration_method="days_per_unit",
        quantity_source="count",
        productivity_value=3,
        productivity_unit="天/根",
        resource_type="rotary_drill",
        is_default=True,
    )

    assert process.duration_method == "fixed_days"
    assert process.quantity_source == "count"
    assert process.productivity_options[0].duration_method == "fixed_days"
    assert process.productivity_options[0].quantity_source == "count"


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
            ProcessTemplate(
                id="cast_in_place_continuous_standard_segment",
                component_type="cast_in_place_continuous_beam",
                process_name="标准块",
                method_id="standard_segment",
                duration_method="fixed_days",
                quantity_source="count",
                productivity_value=10,
                productivity_unit="天/块",
                resource_type="cast_in_place_continuous_beam_team",
                is_default=False,
            ),
        ]
    )
    process_by_id = {process.id: process for process in upgraded}

    assert process_by_id["pile_rotary_regular"].productivity_value == 3
    assert process_by_id["pile_rotary_regular"].duration_method == "fixed_days"
    assert process_by_id["pile_rotary_regular"].quantity_source == "count"
    assert process_by_id["cap_standard"].productivity_value == 30
    assert process_by_id["precast_beam_standard"].productivity_unit == "天/片"
    assert process_by_id["cast_in_place_box_beam_standard"].productivity_value == 45
    assert process_by_id["cast_in_place_continuous_standard_segment"].duration_method == "days_per_unit"
    assert process_by_id["pier_body_climbing_form"].is_default is True
    assert process_by_id["pier_body_standard"].is_default is False
    for process in upgraded:
        default = next(option for option in process.productivity_options if option.is_default)
        assert process.duration_method == default.duration_method
        assert process.quantity_source == default.quantity_source
        assert process.productivity_value == default.productivity_value
        assert process.productivity_unit == default.productivity_unit


def test_pier_body_without_selected_method_uses_climbing_form_by_default() -> None:
    scenario = default_scenario()
    body = next(
        component
        for bridge in scenario.project.bridges
        for section in bridge.work_sections
        for structure in section.structures
        for component in structure.components
        if component.component_type == "pier_body"
    )
    assert body.method_id is None

    generated = generate_schedule_input_from_scenario(scenario)
    task = next(task for task in generated.schedule_input.tasks if task.component_id == body.id)

    assert task.process_name == "爬模施工"
    assert task.productivity_rule_id == "pier_body_climbing_form:pier_body_climbing_form-default"


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


def test_missing_resource_is_treated_as_unlimited_with_warning() -> None:
    pytest.importorskip("ortools")
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
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert any(message.level == "warning" and "默认充足" in message.message for message in result.validation)


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


def test_solver_returns_repeatable_schedule_for_same_input(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("ortools")
    monkeypatch.setenv("SCHEDULER_SEARCH_WORKERS", "1")
    schedule_input = ScheduleInput(
        project_name="repeatability",
        start_date=date(2026, 1, 1),
        tasks=[_solver_task(f"T{index}", f"Task {index}", 2, "crew") for index in range(1, 7)],
        precedence_links=[],
        resources=[
            Resource(id="crew_2", name="Crew 2", type="crew"),
            Resource(id="crew_1", name="Crew 1", type="crew"),
        ],
        time_limit_seconds=5,
    )

    results = [solve_schedule(schedule_input) for _ in range(5)]
    signatures = [
        tuple((task.id, task.start_offset, task.end_offset, task.assigned_resource_id) for task in result.tasks)
        for result in results
    ]

    assert all(result.status in {"OPTIMAL", "FEASIBLE"} for result in results)
    assert len(set(signatures)) == 1
    assert results[0].stats["random_seed"] == 0
    assert results[0].stats["search_workers"] == 1


def test_solver_uses_configured_search_workers_in_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("ortools")
    monkeypatch.setenv("SCHEDULER_SEARCH_WORKERS", "2")

    result = solve_schedule(
        ScheduleInput(
            project_name="configured-workers",
            start_date=date(2026, 1, 1),
            tasks=[_solver_task("T1", "Task 1", 1, "crew")],
            precedence_links=[],
            resources=[Resource(id="crew_1", name="Crew 1", type="crew")],
            schedule_strategy=ScheduleStrategyConfig(strategy="shortest_duration"),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.stats["search_workers"] == 2


def test_capacity_shortest_matches_named_resource_shortest_on_simple_parallel_case() -> None:
    pytest.importorskip("ortools")
    schedule_input = _min_resource_test_input(max_resources=2).model_copy(
        update={"schedule_strategy": ScheduleStrategyConfig(strategy="shortest_duration")}
    )

    named = solve_schedule(schedule_input)
    capacity = solve_capacity_shortest_schedule(schedule_input)

    assert named.status in {"OPTIMAL", "FEASIBLE"}
    assert capacity.status in {"OPTIMAL", "FEASIBLE"}
    assert capacity.objective_days == named.objective_days
    assert capacity.milestone_results == named.milestone_results
    assert capacity.stats["performance_path"] == "capacity_fast_path"


def test_solver_supports_finish_based_relationships() -> None:
    pytest.importorskip("ortools")
    result = solve_schedule(
        ScheduleInput(
            project_name="关系测试",
            start_date=date(2026, 1, 1),
            tasks=[
                _solver_task("A", "前置A", 5, "crew_a"),
                _solver_task("B", "后续B", 2, "crew_b"),
                _solver_task("C", "前置C", 5, "crew_c"),
                _solver_task("D", "后续D", 2, "crew_d"),
            ],
            precedence_links=[
                PrecedenceLink(
                    id="L-FF",
                    predecessor_id="A",
                    successor_id="B",
                    relationship="FF",
                    lag_days=3,
                    source_rule_id="test_ff",
                ),
                PrecedenceLink(
                    id="L-SF",
                    predecessor_id="C",
                    successor_id="D",
                    relationship="SF",
                    lag_days=4,
                    source_rule_id="test_sf",
                ),
            ],
            resources=[
                Resource(id="crew_a_1", name="A班", type="crew_a"),
                Resource(id="crew_b_1", name="B班", type="crew_b"),
                Resource(id="crew_c_1", name="C班", type="crew_c"),
                Resource(id="crew_d_1", name="D班", type="crew_d"),
            ],
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    by_task = {task.id: task for task in result.tasks}
    assert by_task["B"].end_offset >= by_task["A"].end_offset + 3
    assert by_task["B"].start_offset < by_task["A"].end_offset + 3
    assert by_task["D"].end_offset >= by_task["C"].start_offset + 4
    assert by_task["D"].start_offset < by_task["C"].end_offset + 4


def test_default_scenario_generates_schedule_input() -> None:
    generated = generate_schedule_input_from_scenario(default_scenario())

    assert not any(message.level == "error" for message in generated.validation)
    assert generated.schedule_input.tasks
    assert generated.schedule_input.resources
    assert generated.schedule_input.milestones
    assert any(task.bridge_id == "B1" and task.work_section_id == "WS-LOWER" for task in generated.schedule_input.tasks)


def test_default_scenario_has_one_completion_milestone_per_bridge() -> None:
    scenario = default_scenario()

    assert len(scenario.milestones) == len(scenario.project.bridges) == 1
    milestone = scenario.milestones[0]
    assert milestone.name == "下部及现浇结构施工完成"
    assert milestone.scope_type == "bridge"
    assert milestone.scope_id == scenario.project.bridges[0].id
    assert milestone.target_event == "finish"
    assert milestone.mode == "hard"


def test_bridge_milestone_scope_does_not_promote_all_lower_tasks_to_control_targets() -> None:
    scenario = _parallel_fixed_resource_scenario(target_days=10, current_resources=1, max_resources=2)

    generated = generate_schedule_input_from_scenario(scenario)
    scoped_ids = set(_task_ids_for_milestone(scenario.milestones[0], generated.schedule_input.tasks))
    scoped_tasks = [task for task in generated.schedule_input.tasks if task.id in scoped_ids]

    assert scoped_tasks
    assert any(task.control_level == "normal" for task in scoped_tasks)
    assert not all(task.control_level in {"control", "key"} for task in scoped_tasks)


def test_continuous_beam_upper_structures_generate_t_groups_and_closure_logic() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=4, standard_cycles=2)
    generated = generate_schedule_input_from_scenario(scenario)

    continuous_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_continuous_beam"]
    links = generated.schedule_input.precedence_links

    assert not any(message.level == "error" for message in generated.validation)
    assert len(continuous_tasks) == 19
    assert not any("第" in task.name for task in continuous_tasks)
    assert sum(1 for task in continuous_tasks if "0号块" in task.name) == 4
    standard_tasks = [task for task in continuous_tasks if "标准段2块" in task.name]
    assert len(standard_tasks) == 8
    assert sum(1 for task in standard_tasks if "左侧标准段" in task.name) == 4
    assert sum(1 for task in standard_tasks if "右侧标准段" in task.name) == 4
    assert {task.quantity for task in standard_tasks} == {2}
    assert {task.quantity_label for task in standard_tasks} == {"2块"}
    assert {task.duration_days for task in standard_tasks} == {20}
    assert sum(1 for task in continuous_tasks if "边跨连续段" in task.name) == 2
    assert sum(1 for task in continuous_tasks if "边跨合龙段" in task.name) == 2
    assert sum(1 for task in continuous_tasks if "中跨合龙" in task.name) == 3

    left_straight = _task_named(continuous_tasks, "左幅连续梁1#墩T构-边跨连续段")
    left_closure = _task_named(continuous_tasks, "左幅连续梁1#墩T构-边跨合龙段")
    first_t_left_standard = _task_named(continuous_tasks, "左幅连续梁1#墩T构-左侧标准段2块")
    first_t_right_standard = _task_named(continuous_tasks, "左幅连续梁1#墩T构-右侧标准段2块")
    second_t_left_standard = _task_named(continuous_tasks, "左幅连续梁2#墩T构-左侧标准段2块")
    mid_1 = _task_named(continuous_tasks, "中跨合龙1")
    mid_2 = _task_named(continuous_tasks, "中跨合龙2")
    mid_3 = _task_named(continuous_tasks, "中跨合龙3")

    assert _has_link(links, left_straight.id, left_closure.id, "continuous_beam_side_closure")
    assert _has_link(links, first_t_left_standard.id, left_closure.id, "continuous_beam_side_closure")
    assert _has_link(links, first_t_right_standard.id, mid_1.id, "continuous_beam_middle_closure")
    assert _has_link(links, second_t_left_standard.id, mid_1.id, "continuous_beam_middle_closure")
    assert _has_link(links, left_closure.id, mid_1.id, "continuous_beam_edge_before_middle_closure")
    assert _has_link(links, left_closure.id, mid_2.id, "continuous_beam_edge_before_middle_closure")
    assert _has_link(links, mid_1.id, mid_2.id, "continuous_beam_middle_closure_sequence")
    assert _has_link(links, mid_3.id, mid_2.id, "continuous_beam_middle_closure_sequence")
    assert all(
        link.max_finish_gap_days == 7
        for link in links
        if link.source_rule_id in {"continuous_beam_side_closure", "continuous_beam_middle_closure"}
    )


def test_continuous_beam_tasks_are_control_when_generated_from_structure_params() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    section = scenario.project.bridges[0].work_sections[0]
    for upper in section.upper_structures:
        upper.control_level = "normal"

    generated = generate_schedule_input_from_scenario(scenario)
    continuous_tasks = [
        task
        for task in generated.schedule_input.tasks
        if task.component_type == "cast_in_place_continuous_beam"
    ]

    assert continuous_tasks
    assert {task.control_level for task in continuous_tasks} == {"control"}


def test_continuous_beam_standard_segment_duration_uses_block_count_when_process_is_legacy_fixed_days() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=18)
    process = next(process for process in scenario.process_library if process.id == "cast_in_place_continuous_standard_segment")
    process.duration_method = "fixed_days"
    process.quantity_source = "count"
    process.productivity_value = 10
    process.productivity_unit = "天/块"
    for option in process.productivity_options:
        option.duration_method = "fixed_days"
        option.quantity_source = "count"
        option.productivity_value = 10
        option.productivity_unit = "天/块"

    generated = generate_schedule_input_from_scenario(scenario)

    standard_tasks = [
        task
        for task in generated.schedule_input.tasks
        if task.productivity_rule_id.startswith("cast_in_place_continuous_standard_segment:")
    ]
    assert standard_tasks
    assert {task.quantity for task in standard_tasks} == {18}
    assert {task.duration_days for task in standard_tasks} == {180}


def test_continuous_beam_task_override_selects_productivity_option_for_derived_task() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=18)
    process = next(process for process in scenario.process_library if process.id == "cast_in_place_continuous_standard_segment")
    process.productivity_options.append(
        ProductivityOption(
            id="continuous-standard-fast",
            name="fast",
            duration_method="days_per_unit",
            quantity_source="count",
            productivity_value=5,
            productivity_unit="days/block",
        )
    )
    scenario.task_overrides = {
        "B1-L-CB-G01-T01-P01-STD-L": TaskOverride(
            method_id="standard_segment",
            productivity_option_id="continuous-standard-fast",
        ),
        "B1-L-CB-G01-T01-P01-STD-R": TaskOverride(
            method_id="standard_segment",
            productivity_option_id="continuous-standard-fast",
        )
    }

    generated = generate_schedule_input_from_scenario(scenario)
    target = next(task for task in generated.schedule_input.tasks if task.id == "B1-L-CB-G01-T01-P01-STD-L")
    target_peer = next(task for task in generated.schedule_input.tasks if task.id == "B1-L-CB-G01-T01-P01-STD-R")
    other_t = next(task for task in generated.schedule_input.tasks if task.id == "B1-L-CB-G01-T02-P02-STD-L")

    assert target.productivity_rule_id == "cast_in_place_continuous_standard_segment:continuous-standard-fast"
    assert target.quantity == 18
    assert target.duration_days == 90
    assert target_peer.duration_days == 90
    assert other_t.duration_days == 180


def test_continuous_beam_middle_closure_order_is_configurable() -> None:
    scenario = _scenario_with_continuous_beam(
        main_pier_count=4,
        standard_cycles=1,
        middle_closure_order="right_to_left",
    )
    generated = generate_schedule_input_from_scenario(scenario)
    continuous_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_continuous_beam"]
    links = generated.schedule_input.precedence_links
    mid_1 = _task_named(continuous_tasks, "中跨合龙1")
    mid_2 = _task_named(continuous_tasks, "中跨合龙2")
    mid_3 = _task_named(continuous_tasks, "中跨合龙3")

    assert _has_link(links, mid_3.id, mid_2.id, "continuous_beam_middle_closure_sequence")
    assert _has_link(links, mid_2.id, mid_1.id, "continuous_beam_middle_closure_sequence")
    assert not _has_link(links, mid_1.id, mid_2.id, "continuous_beam_middle_closure_sequence")


def test_continuous_beam_right_side_task_names_do_not_include_span_group_label() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    section = scenario.project.bridges[0].work_sections[0]
    section.side = "right"
    section.name = "右幅结构参数"
    for upper in section.upper_structures or []:
        upper.side = "right"

    generated = generate_schedule_input_from_scenario(scenario)

    continuous_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_continuous_beam"]
    task_names = {task.name for task in continuous_tasks}
    assert "右幅连续梁1#墩T构-0号块" in task_names
    assert "右幅连续梁1#墩T构-边跨连续段" in task_names
    assert not any("第" in task.name for task in continuous_tasks)


def test_continuous_beam_resource_max_quantity_counts_t_structures() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=4, standard_cycles=2)

    apply_resource_max_quantity_defaults(scenario)

    max_by_type = {pool.type: pool.max_quantity for pool in scenario.resource_pools}
    assert max_by_type["cast_in_place_continuous_beam_team"] == 10


def test_simple_beam_erection_is_not_generated_in_current_phase() -> None:
    scenario = _scenario_with_single_upper_span(
        structure_type="简支T梁",
        structure_code="precastTGirder",
        support_range="1#墩~2#墩",
    )
    generated = generate_schedule_input_from_scenario(scenario)

    assert not any(task.component_type == "beam_erection" for task in generated.schedule_input.tasks)
    assert not any(link.source_rule_id == "simple_beam_after_lower_structure" for link in generated.schedule_input.precedence_links)


def test_cast_in_place_box_beam_waits_for_corresponding_lower_structures() -> None:
    scenario = _scenario_with_single_upper_span(
        structure_type="现浇箱梁",
        structure_code="castInPlaceBoxGirder",
        support_range="1#墩~2#墩",
    )
    generated = generate_schedule_input_from_scenario(scenario)
    box_task = next(task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_box_beam")
    links = [
        link
        for link in generated.schedule_input.precedence_links
        if link.successor_id == box_task.id and link.source_rule_id == "cast_in_place_box_beam_after_lower_structure"
    ]

    assert {link.predecessor_id for link in links} == {"P01-BODY", "P02-BODY"}


def test_continuous_beam_zero_block_and_side_straight_wait_for_lower_structures() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = [
        _abutment_structure(0),
        _pier_body_structure(1),
        _pier_body_structure(2),
        _pier_body_structure(3),
    ]
    generated = generate_schedule_input_from_scenario(scenario)
    continuous_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_continuous_beam"]
    zero_block = _task_named(continuous_tasks, "左幅连续梁1#墩T构-0号块")
    left_straight = _task_named(continuous_tasks, "左幅连续梁1#墩T构-边跨连续段")
    right_straight = _task_named(continuous_tasks, "左幅连续梁2#墩T构-边跨连续段")

    assert _has_link(
        generated.schedule_input.precedence_links,
        "P01-BODY",
        zero_block.id,
        "continuous_beam_zero_block_after_main_pier_lower_structure",
    )
    assert _has_link(
        generated.schedule_input.precedence_links,
        "A00-BODY",
        left_straight.id,
        "continuous_beam_side_straight_after_edge_lower_structure",
    )
    assert _has_link(
        generated.schedule_input.precedence_links,
        "P03-BODY",
        right_straight.id,
        "continuous_beam_side_straight_after_edge_lower_structure",
    )


def test_continuous_beam_lower_anchor_prefers_pier_body_before_cap_when_no_cap_beam() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = [
        _abutment_structure(0),
        _pier_lower_structure(1),
        _pier_lower_structure(2),
        _pier_lower_structure(3),
    ]

    generated = generate_schedule_input_from_scenario(scenario)
    continuous_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_continuous_beam"]
    zero_block = _task_named(continuous_tasks, "左幅连续梁1#墩T构-0号块")
    predecessors = {
        link.predecessor_id
        for link in generated.schedule_input.precedence_links
        if link.successor_id == zero_block.id
        and link.source_rule_id == "continuous_beam_zero_block_after_main_pier_lower_structure"
    }

    assert "P01-BODY" in predecessors
    assert "P01-CAP" not in predecessors
    assert "P01-PILE-01" not in predecessors


def test_continuous_beam_left_and_right_standard_segments_solve_synchronously() -> None:
    pytest.importorskip("ortools")
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)
    schedule_input = generated.schedule_input.model_copy(
        update={"schedule_strategy": ScheduleStrategyConfig(strategy="shortest_duration")}
    )

    result = solve_schedule(schedule_input)
    by_name = {task.name: task for task in result.tasks}
    left_standard = by_name["左幅连续梁1#墩T构-左侧标准段1块"]
    right_standard = by_name["左幅连续梁1#墩T构-右侧标准段1块"]

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert left_standard.start_offset == right_standard.start_offset
    assert left_standard.end_offset == right_standard.end_offset
    assert left_standard.assigned_resource_id is not None
    assert right_standard.assigned_resource_id is None


def test_continuous_beam_closure_predecessor_finish_gap_is_limited() -> None:
    pytest.importorskip("ortools")
    result = solve_schedule(
        ScheduleInput(
            project_name="closure-gap",
            start_date=date(2026, 1, 1),
            tasks=[
                _solver_task("A", "边跨连续段", 1, "").model_copy(update={"compatible_resource_types": []}),
                _solver_task("B", "相邻T构边跨侧标准段", 20, "").model_copy(update={"compatible_resource_types": []}),
                _solver_task("C", "边跨合龙段", 1, "").model_copy(
                    update={
                        "component_type": "cast_in_place_continuous_beam",
                        "structure_type": "continuous_beam",
                        "compatible_resource_types": [],
                        "properties": {"continuous_task_type": "side_closure_segment"},
                    }
                ),
            ],
            precedence_links=[
                PrecedenceLink(
                    id="A-C",
                    predecessor_id="A",
                    successor_id="C",
                    lag_days=0,
                    source_rule_id="continuous_beam_side_closure",
                    max_finish_gap_days=7,
                ),
                PrecedenceLink(
                    id="B-C",
                    predecessor_id="B",
                    successor_id="C",
                    lag_days=0,
                    source_rule_id="continuous_beam_side_closure",
                    max_finish_gap_days=7,
                ),
            ],
            resources=[],
            milestones=[],
            schedule_strategy=ScheduleStrategyConfig(strategy="shortest_duration"),
            time_limit_seconds=5,
        )
    )
    by_id = {task.id: task for task in result.tasks}

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert abs(by_id["A"].end_offset - by_id["B"].end_offset) <= 7


def test_upper_structure_logic_relationship_and_lag_are_configurable() -> None:
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = [_pier_body_structure(1), _pier_body_structure(2)]
    scenario.upper_structure_logic_rules = [
        UpperStructureLogicRule(
            id="continuous_beam_zero_block_after_main_pier_lower_structure",
            relationship="SS",
            lag_days=4,
        ),
        UpperStructureLogicRule(
            id="continuous_beam_t_chain",
            relationship="FS",
            lag_days=2,
        ),
    ]

    generated = generate_schedule_input_from_scenario(scenario)

    continuous_tasks = [task for task in generated.schedule_input.tasks if task.component_type == "cast_in_place_continuous_beam"]
    zero_block = _task_named(continuous_tasks, "左幅连续梁1#墩T构-0号块")
    standard_segment = _task_named(continuous_tasks, "左幅连续梁1#墩T构-左侧标准段1块")
    zero_block_link = next(
        link
        for link in generated.schedule_input.precedence_links
        if link.successor_id == zero_block.id
        and link.source_rule_id == "continuous_beam_zero_block_after_main_pier_lower_structure"
    )
    t_chain_link = next(
        link
        for link in generated.schedule_input.precedence_links
        if link.predecessor_id == zero_block.id
        and link.successor_id == standard_segment.id
        and link.source_rule_id == "continuous_beam_t_chain"
    )

    assert zero_block_link.relationship == "SS"
    assert zero_block_link.lag_days == 4
    assert t_chain_link.relationship == "FS"
    assert t_chain_link.lag_days == 2


def test_imported_scenario_logic_source_rules_are_visible_active_rules() -> None:
    scenario = import_local_bridge_params(default_scenario()).scenario
    generated = generate_schedule_input_from_scenario(scenario)

    visible_rule_ids = {rule.id for rule in scenario.logic_rules}
    visible_rule_ids.update(scenario_module.UPPER_STRUCTURE_LOGIC_RULE_IDS)
    generated_rule_ids = {link.source_rule_id for link in generated.schedule_input.precedence_links}

    assert generated_rule_ids <= visible_rule_ids
    assert "simple_beam_after_lower_structure" not in generated_rule_ids


def test_default_scenario_sets_resource_max_quantity_from_business_defaults() -> None:
    scenario = default_scenario()
    quantity_by_type = {pool.type: pool.quantity for pool in scenario.resource_pools}
    max_by_type = {pool.type: pool.max_quantity for pool in scenario.resource_pools}

    assert set(max_by_type) == {
        "rotary_drill",
        "circulation_drill",
        "impact_drill",
        "manual_pile_team",
        "cap_team",
        "pier_body_team",
        "cap_beam_team",
        "cast_in_place_continuous_beam_team",
    }
    assert all(quantity == 1 for quantity in quantity_by_type.values())
    assert all(max_quantity == 10 for max_quantity in max_by_type.values())


def test_resource_pool_max_quantity_defaults_to_quantity() -> None:
    pool = ResourcePool.model_validate({"id": "pool-team", "type": "team", "label": "班组", "quantity": 2})

    assert pool.max_quantity == 2


def test_unlimited_resource_pool_does_not_require_quantity() -> None:
    pool = ResourcePool.model_validate({"id": "pool-team", "type": "team", "label": "班组", "resource_mode": "UNLIMITED", "quantity": None})

    assert pool.resource_mode == "UNLIMITED"
    assert pool.quantity is None
    assert pool.max_quantity is None


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


def test_all_unlimited_resources_do_not_generate_resource_waiting() -> None:
    pytest.importorskip("ortools")
    scenario = _small_resource_scenario()
    for pool in scenario.resource_pools:
        pool.resource_mode = "UNLIMITED"

    generated = generate_schedule_input_from_scenario(scenario)
    result = solve_schedule(generated.schedule_input)

    assert generated.schedule_input.resources == []
    assert all(not task.compatible_resource_types for task in generated.schedule_input.tasks)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.resource_allocations == []
    assert not any(message.level == "error" and "资源" in message.message for message in result.validation)


def test_limited_rotary_drill_caps_parallel_pile_tasks() -> None:
    pytest.importorskip("ortools")
    scenario = _small_resource_scenario()
    _set_all_resource_modes(scenario, "UNLIMITED")
    rotary = _resource_pool(scenario, "rotary_drill")
    rotary.resource_mode = "LIMITED"
    rotary.quantity = 2
    rotary.max_quantity = 2

    result = solve_scenario(scenario).result
    rotary_allocations = [allocation for allocation in result.resource_allocations if allocation.resource_type == "rotary_drill"]

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert rotary_allocations
    assert _max_parallel_allocations(rotary_allocations) <= 2


def test_limited_cap_formwork_serializes_cap_tasks() -> None:
    pytest.importorskip("ortools")
    scenario = _small_resource_scenario()
    _set_all_resource_modes(scenario, "UNLIMITED")
    cap_pool = _resource_pool(scenario, "cap_team")
    cap_pool.resource_mode = "LIMITED"
    cap_pool.quantity = 1
    cap_pool.max_quantity = 1

    solved = solve_scenario(scenario)
    cap_allocations = [allocation for allocation in solved.result.resource_allocations if allocation.resource_type == "cap_team"]

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert cap_allocations
    assert _max_parallel_allocations(cap_allocations) <= 1


def test_switching_resource_to_unlimited_releases_constraint() -> None:
    pytest.importorskip("ortools")
    limited = _small_resource_scenario()
    _set_all_resource_modes(limited, "UNLIMITED")
    limited_cap = _resource_pool(limited, "cap_team")
    limited_cap.resource_mode = "LIMITED"
    limited_cap.quantity = 1
    limited_cap.max_quantity = 1

    unlimited = limited.model_copy(deep=True)
    unlimited_cap = _resource_pool(unlimited, "cap_team")
    unlimited_cap.resource_mode = "UNLIMITED"

    limited_result = solve_scenario(limited).result
    unlimited_result = solve_scenario(unlimited).result
    unlimited_cap_tasks = [task for task in unlimited_result.tasks if task.component_type == "cap"]

    assert limited_result.status in {"OPTIMAL", "FEASIBLE"}
    assert unlimited_result.status in {"OPTIMAL", "FEASIBLE"}
    assert unlimited_result.objective_days is not None
    assert limited_result.objective_days is not None
    assert unlimited_result.objective_days < limited_result.objective_days
    assert all(task.assigned_resource_id is None for task in unlimited_cap_tasks)


def test_missing_key_resource_pool_warns_and_uses_unlimited_strategy() -> None:
    pytest.importorskip("ortools")
    scenario = _small_resource_scenario()
    scenario.resource_pools = [pool for pool in scenario.resource_pools if pool.type != "cap_team"]

    solved = solve_scenario(scenario)
    cap_tasks = [task for task in solved.generated.schedule_input.tasks if task.component_type == "cap"]

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert cap_tasks
    assert all(task.compatible_resource_types == [] for task in cap_tasks)
    assert any(message.level == "warning" and "未配置" in message.message for message in solved.diagnostics)


def test_noncritical_component_can_opt_into_limited_resource_pool() -> None:
    pytest.importorskip("ortools")
    scenario = _abutment_resource_scenario()
    scenario.resource_pools.append(
        ResourcePool(
            id="pool-abutment",
            type="abutment_team",
            label="桥台班组",
            quantity=1,
            max_quantity=1,
        )
    )

    solved = solve_scenario(scenario)
    abutment_tasks = [task for task in solved.generated.schedule_input.tasks if task.component_type == "abutment_body"]
    abutment_allocations = [allocation for allocation in solved.result.resource_allocations if allocation.resource_type == "abutment_team"]

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert len(abutment_tasks) == 2
    assert {tuple(task.compatible_resource_types) for task in abutment_tasks} == {("abutment_team",)}
    assert _max_parallel_allocations(abutment_allocations) <= 1


def test_component_type_milestone_matches_all_components_of_that_type() -> None:
    scenario = default_scenario()
    generated = generate_schedule_input_from_scenario(scenario)
    cap_milestone = MilestoneConstraint(
        id="M-cap",
        name="承台完成目标",
        mode="soft",
        scope_type="component",
        scope_id="cap",
        target_date=scenario.project.start_date,
    )
    scoped_task_ids = set(_task_ids_for_milestone(cap_milestone, generated.schedule_input.tasks))
    cap_task_ids = {task.id for task in generated.schedule_input.tasks if task.component_type == "cap"}

    assert scoped_task_ids == cap_task_ids
    assert len(scoped_task_ids) > 1


def test_bridge_milestone_matches_lower_structure_and_cast_in_place_beams_only() -> None:
    scenario = _scenario_with_mixed_upper_structures()
    generated = generate_schedule_input_from_scenario(scenario)
    bridge_milestone = next(milestone for milestone in scenario.milestones if milestone.scope_type == "bridge")
    scoped_tasks = [
        task
        for task in generated.schedule_input.tasks
        if task.id in set(_task_ids_for_milestone(bridge_milestone, generated.schedule_input.tasks))
    ]
    scoped_component_types = {task.component_type for task in scoped_tasks}

    assert "pier_body" in scoped_component_types
    assert "abutment_body" in scoped_component_types
    assert "cast_in_place_box_beam" in scoped_component_types
    assert "cast_in_place_continuous_beam" in scoped_component_types
    assert "beam_erection" not in scoped_component_types


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
            duration_method="fixed_days",
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


def test_fixed_resource_shortest_marks_hard_milestone_lateness_infeasible_but_keeps_schedule() -> None:
    pytest.importorskip("ortools")
    scenario = default_scenario()
    hard_milestone = scenario.milestones[0].model_copy(
        update={"target_date": scenario.project.start_date}
    )
    scenario.milestones = [hard_milestone]

    solved = solve_scenario(scenario)

    assert solved.result.status == "INFEASIBLE"
    assert solved.result.tasks
    assert solved.result.resource_allocations
    assert solved.milestone_results[0].lateness_days > 0
    assert any(message.level == "error" and "强制里程碑目标" in message.message for message in solved.result.validation)
    assert solved.result.objective_breakdown["solve_mode"] == "fixed_resources_shortest_control_balanced"
    assert solved.result.objective_breakdown["resource_recommendation_status"] == "critical_path_infeasible"


def test_fixed_resource_shortest_returns_resource_increment_recommendation_when_resources_can_meet_target() -> None:
    pytest.importorskip("ortools")
    solved = solve_scenario(_parallel_fixed_resource_scenario(target_days=5, current_resources=1, max_resources=3))

    assert solved.result.status == "INFEASIBLE"
    assert solved.result.tasks
    assert solved.result.objective_breakdown["resource_recommendation_status"] == "recommended_resources_verified"
    recommended = solved.result.objective_breakdown["recommended_resource_counts"][0]
    assert recommended["current_quantity"] == 1
    assert recommended["recommended_quantity"] == 2
    assert recommended["added_quantity"] == 1
    assert recommended["max_quantity"] == 3
    assert solved.result.objective_breakdown["schedule_source"] == "current_resources_capacity_shortest"
    assert solved.result.objective_breakdown["performance_path"] == "capacity_fast_path_resource_recommendation"
    assert solved.result.objective_breakdown["skipped_named_refinement_reason"] == "current_resources_late_hard_milestone"
    assert "control_priority_analysis" not in solved.result.stats
    assert len(solved.alternative_results) == 1
    alternative = solved.alternative_results[0]
    assert alternative.role == "minimum_resources"
    assert alternative.result.status in {"OPTIMAL", "FEASIBLE"}
    assert alternative.result.stats["schedule_source"] == "minimum_resources_control_priority_balanced"
    assert alternative.result.stats["recommended_schedule_source"] == "minimum_resources_control_priority_balanced"
    assert alternative.result.stats["recommended_resource_counts"][0]["added_quantity"] == 1
    assert len(alternative.generated.schedule_input.resources) == 2
    assert {allocation.resource_id for allocation in alternative.result.resource_allocations} <= {"cap_team_1", "cap_team_2"}


def test_fixed_resource_recommendation_matches_direct_min_resource_solver() -> None:
    pytest.importorskip("ortools")
    scenario = _parallel_fixed_resource_scenario(target_days=5, current_resources=1, max_resources=3)
    direct_generated = generate_schedule_input_from_scenario(scenario, use_max_resources=True)
    direct = solve_min_resources_schedule(direct_generated.schedule_input)
    solved = solve_scenario(scenario)

    direct_recommended = {
        item["resource_pool_id"]: item["recommended_quantity"]
        for item in direct.stats["recommended_resource_counts"]
    }
    fixed_recommended = {
        item["resource_pool_id"]: item["recommended_quantity"]
        for item in solved.result.objective_breakdown["recommended_resource_counts"]
    }

    assert direct.status in {"OPTIMAL", "FEASIBLE"}
    assert solved.result.objective_breakdown["resource_recommendation_status"] == "recommended_resources_verified"
    assert fixed_recommended == direct_recommended
    assert len(solved.alternative_results) == 1
    assert len(solved.alternative_results[0].generated.schedule_input.resources) == sum(direct_recommended.values())


def test_fixed_resource_minimum_candidate_reruns_refinement_before_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")
    original_refinement = scenario_module.solve_control_priority_schedule
    refinement_calls: list[dict[str, object]] = []

    def tracking_refinement(schedule_input: ScheduleInput, **kwargs: object) -> ScheduleResult:
        refinement_calls.append(kwargs)
        return original_refinement(schedule_input, **kwargs)

    monkeypatch.setattr(scenario_module, "solve_control_priority_schedule", tracking_refinement)

    solved = solve_scenario(_parallel_fixed_resource_scenario(target_days=5, current_resources=1, max_resources=3))

    assert refinement_calls
    assert any(call.get("baseline_result") is not None and call.get("warm_start_result") is not None for call in refinement_calls)
    alternative = solved.alternative_results[0]
    assert alternative.result.status in {"OPTIMAL", "FEASIBLE"}
    assert alternative.result.stats["schedule_source"] == "minimum_resources_control_priority_balanced"
    assert alternative.result.objective_breakdown["minimum_resource_refinement_status"] in {"OPTIMAL", "FEASIBLE"}


def test_fixed_resource_minimum_candidate_keeps_verified_schedule_when_refinement_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")

    def failed_refinement(schedule_input: ScheduleInput, **_: object) -> ScheduleResult:
        return ScheduleResult(
            status="UNKNOWN",
            plan_start_date=schedule_input.start_date,
            validation=[
                ValidationMessage(
                    level="warning",
                    message="minimum resource refinement timed out",
                )
            ],
        )

    monkeypatch.setattr(scenario_module, "solve_control_priority_schedule", failed_refinement)

    solved = solve_scenario(_parallel_fixed_resource_scenario(target_days=5, current_resources=1, max_resources=3))

    assert solved.result.objective_breakdown["resource_recommendation_status"] == "recommended_resources_verified"
    assert solved.result.objective_breakdown["recommended_schedule_source"] == "minimum_resources_refinement_fallback"
    alternative = solved.alternative_results[0]
    assert alternative.result.status in {"OPTIMAL", "FEASIBLE"}
    assert alternative.result.stats["schedule_source"] == "minimum_resources_refinement_fallback"
    assert alternative.result.stats["minimum_resource_refinement_status"] == "UNKNOWN"
    assert alternative.result.stats["recommended_resource_counts"][0]["added_quantity"] == 1


def test_fixed_resource_late_current_skips_control_refinement_but_keeps_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _parallel_fixed_resource_scenario(target_days=5, current_resources=1, max_resources=3)
    scenario.time_limit_seconds = 5
    call_limits: list[tuple[str, float]] = []

    def late_result(schedule_input: ScheduleInput) -> ScheduleResult:
        milestone = schedule_input.milestones[0]
        return ScheduleResult(
            status="FEASIBLE",
            objective_days=10,
            plan_start_date=schedule_input.start_date,
            plan_finish_date=schedule_input.start_date + timedelta(days=9),
            milestone_results=[
                MilestoneResult(
                    **milestone.model_dump(),
                    actual_date=schedule_input.start_date + timedelta(days=9),
                    actual_offset=10,
                    lateness_days=5,
                    status="late",
                )
            ],
        )

    def fake_capacity_shortest(schedule_input: ScheduleInput) -> ScheduleResult:
        call_limits.append(("capacity", schedule_input.time_limit_seconds))
        return late_result(schedule_input)

    def fake_control_priority(schedule_input: ScheduleInput, **_: object) -> ScheduleResult:
        call_limits.append(("control", schedule_input.time_limit_seconds))
        return late_result(schedule_input)

    def fake_min_resources(schedule_input: ScheduleInput, fallback_target_days: int | None = None) -> ScheduleResult:
        call_limits.append(("min_resources", schedule_input.time_limit_seconds))
        return ScheduleResult(
            status="INFEASIBLE",
            plan_start_date=schedule_input.start_date,
            stats={
                "reason": "resource_upper_bound_or_deadline_infeasible",
                "resource_capacity_lower_bounds": [],
                "fallback_target_days": fallback_target_days,
            },
        )

    monkeypatch.setattr(scenario_module, "solve_capacity_shortest_schedule", fake_capacity_shortest)
    monkeypatch.setattr(scenario_module, "solve_control_priority_schedule", fake_control_priority)
    monkeypatch.setattr(scenario_module, "solve_min_resources_schedule", fake_min_resources)
    monkeypatch.setattr(
        scenario_module,
        "_critical_path_schedule",
        lambda schedule_input: {
            "status": "OK",
            "objective_days": 4,
            "plan_finish_date": schedule_input.start_date + timedelta(days=3),
            "milestone_results": [],
        },
    )

    solve_scenario(scenario)

    assert ("capacity", 5) in call_limits
    assert ("min_resources", 5) in call_limits
    assert not any(label == "control" for label, _ in call_limits)
    assert all(limit == 5 for _, limit in call_limits)


def test_fixed_resource_shortest_does_not_recommend_max_when_upper_bound_is_infeasible() -> None:
    pytest.importorskip("ortools")
    solved = solve_scenario(_parallel_fixed_resource_scenario(target_days=5, current_resources=1, max_resources=1))

    assert solved.result.status == "INFEASIBLE"
    assert solved.result.objective_breakdown["resource_recommendation_status"] == "resource_upper_bound_infeasible"
    assert solved.result.objective_breakdown["recommended_resource_counts"] == []
    upper_bounds = solved.result.objective_breakdown["resource_upper_bound_counts"]
    assert upper_bounds[0]["current_quantity"] == 1
    assert upper_bounds[0]["upper_bound_quantity"] == 1
    lower_bounds = solved.result.objective_breakdown["resource_capacity_lower_bounds"]
    assert lower_bounds[0]["required_minimum"] == 2
    assert lower_bounds[0]["exceeds_upper_bound"] is True
    assert solved.alternative_results == []


def test_fixed_resource_shortest_reports_critical_path_infeasible_without_resource_increment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")
    min_resource_calls = 0

    def fake_min_resources(schedule_input: ScheduleInput, fallback_target_days: int | None = None) -> ScheduleResult:
        nonlocal min_resource_calls
        min_resource_calls += 1
        return ScheduleResult(status="UNKNOWN", plan_start_date=schedule_input.start_date)

    monkeypatch.setattr(scenario_module, "solve_min_resources_schedule", fake_min_resources)
    solved = solve_scenario(_parallel_fixed_resource_scenario(target_days=4, current_resources=1, max_resources=2))

    assert solved.result.status == "INFEASIBLE"
    assert solved.result.objective_breakdown["resource_recommendation_status"] == "critical_path_infeasible"
    assert solved.result.objective_breakdown["recommended_resource_counts"] == []
    assert solved.alternative_results == []
    assert min_resource_calls == 0
    assert any("增加资源也无法满足" in message.message for message in solved.result.validation)


def test_fixed_resource_shortest_outputs_control_balanced_result_when_hard_milestone_is_met() -> None:
    pytest.importorskip("ortools")
    solved = solve_scenario(_parallel_fixed_resource_scenario(target_days=10, current_resources=1, max_resources=2))

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert solved.result.objective_breakdown["solve_mode"] == "fixed_resources_shortest_control_balanced"
    assert solved.result.objective_breakdown["hard_milestone_feasible"] is True
    assert solved.result.objective_breakdown["schedule_source"] == "current_resources_control_priority_balanced"
    assert solved.result.objective_breakdown["performance_path"] == "capacity_fast_path_named_refinement"
    assert solved.result.objective_breakdown["warm_start_used"] is True
    assert solved.result.stats["warm_start_used"] is True
    assert "control_priority_analysis" in solved.result.stats
    assert "normal_balance_metrics" in solved.result.stats
    assert solved.alternative_results == []
    assert all(milestone.lateness_days == 0 for milestone in solved.result.milestone_results if milestone.mode == "hard")


def test_soft_milestone_returns_lateness_and_penalty() -> None:
    pytest.importorskip("ortools")
    scenario = default_scenario()
    soft_milestone = MilestoneConstraint(
        id="M-soft",
        name="提醒目标",
        mode="soft",
        scope_type="project",
        target_event="finish",
        target_date=scenario.project.start_date,
        penalty_per_day=7,
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
                    name="5天参考完工",
                    level="contract",
                    mode="soft",
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


def test_solver_reports_same_structure_split_as_diagnostic_only() -> None:
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
    assigned_resource_ids = {
        by_task["B1-L-P03-PILE-01"].assigned_resource_id,
        by_task["B1-L-P03-PILE-02"].assigned_resource_id,
    }
    expected_split_count = max(0, len(assigned_resource_ids) - 1)
    assert result.stats["continuity_metrics"]["same_structure_craft_split_count"] == expected_split_count
    assert "same_structure_craft_split_penalty" not in result.objective_breakdown
    assert "same_structure_craft_split_weight" not in result.stats["continuity_objective"]


def test_same_structure_drill_parallel_rule_comes_from_resource_config() -> None:
    pytest.importorskip("ortools")
    tasks = _same_pier_pile_tasks("rotary_drill")
    start = date(2026, 1, 1)

    unconfigured_result = solve_schedule(
        ScheduleInput(
            project_name="unconfigured rotary can parallel",
            start_date=start,
            tasks=tasks,
            precedence_links=[],
            resources=[
                Resource(id="rotary_1", name="旋挖钻1", type="rotary_drill"),
                Resource(id="rotary_2", name="旋挖钻2", type="rotary_drill"),
            ],
            time_limit_seconds=5,
        )
    )

    configured_result = solve_schedule(
        ScheduleInput(
            project_name="configured rotary same pier rule",
            start_date=start,
            tasks=tasks,
            precedence_links=[],
            resources=[
                Resource(
                    id="rotary_1",
                    name="旋挖钻1",
                    type="rotary_drill",
                    same_structure_resource_binding=False,
                    same_structure_parallel_limit=1,
                ),
                Resource(
                    id="rotary_2",
                    name="旋挖钻2",
                    type="rotary_drill",
                    same_structure_resource_binding=False,
                    same_structure_parallel_limit=1,
                ),
            ],
            time_limit_seconds=5,
        )
    )

    assert unconfigured_result.status in {"OPTIMAL", "FEASIBLE"}
    assert unconfigured_result.objective_days == 5
    assert len({task.assigned_resource_id for task in unconfigured_result.tasks}) == 2

    assert configured_result.status in {"OPTIMAL", "FEASIBLE"}
    assert configured_result.objective_days == 10
    assert len({task.assigned_resource_id for task in configured_result.tasks}) == 1


def test_same_structure_parallel_limit_caps_total_participating_resources() -> None:
    pytest.importorskip("ortools")
    result = solve_schedule(
        ScheduleInput(
            project_name="same pier at most two participating resources",
            start_date=date(2026, 1, 1),
            tasks=_same_pier_pile_tasks("rotary_drill", count=6),
            precedence_links=[],
            resources=[
                Resource(
                    id=f"rotary_{index}",
                    name=f"旋挖钻{index}",
                    type="rotary_drill",
                    same_structure_parallel_limit=2,
                )
                for index in range(1, 9)
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 15
    assert len({task.assigned_resource_id for task in result.tasks}) <= 2


def test_same_structure_parallel_limit_zero_means_unlimited() -> None:
    pytest.importorskip("ortools")
    result = solve_schedule(
        ScheduleInput(
            project_name="same pier explicit unlimited",
            start_date=date(2026, 1, 1),
            tasks=_same_pier_pile_tasks("rotary_drill"),
            precedence_links=[],
            resources=[
                Resource(id="rotary_1", name="旋挖钻1", type="rotary_drill", same_structure_parallel_limit=0),
                Resource(id="rotary_2", name="旋挖钻2", type="rotary_drill", same_structure_parallel_limit=0),
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 5
    assert len({task.assigned_resource_id for task in result.tasks}) == 2


def test_legacy_same_structure_binding_without_limit_is_limit_one() -> None:
    pytest.importorskip("ortools")
    result = solve_schedule(
        ScheduleInput(
            project_name="legacy same pier binding",
            start_date=date(2026, 1, 1),
            tasks=_same_pier_pile_tasks("rotary_drill"),
            precedence_links=[],
            resources=[
                Resource(id="rotary_1", name="旋挖钻1", type="rotary_drill", same_structure_resource_binding=True),
                Resource(id="rotary_2", name="旋挖钻2", type="rotary_drill", same_structure_resource_binding=True),
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 10
    assert len({task.assigned_resource_id for task in result.tasks}) == 1


def test_manual_pile_team_allows_same_structure_parallel_without_extra_limit() -> None:
    pytest.importorskip("ortools")
    result = solve_schedule(
        ScheduleInput(
            project_name="manual pile parallel",
            start_date=date(2026, 1, 1),
            tasks=_same_pier_pile_tasks("manual_pile_team"),
            precedence_links=[],
            resources=[
                Resource(id="manual_1", name="人工挖孔班1", type="manual_pile_team"),
                Resource(id="manual_2", name="人工挖孔班2", type="manual_pile_team"),
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 5
    assert len({task.assigned_resource_id for task in result.tasks}) == 2


def test_capacity_model_enforces_configured_same_structure_parallel_limit() -> None:
    pytest.importorskip("ortools")
    result = solve_capacity_shortest_schedule(
        ScheduleInput(
            project_name="capacity same pier parallel limit",
            start_date=date(2026, 1, 1),
            tasks=_same_pier_pile_tasks("rotary_drill", count=6),
            precedence_links=[],
            resources=[
                Resource(
                    id=f"rotary_{index}",
                    name=f"旋挖钻{index}",
                    type="rotary_drill",
                    pool_id="pool-rotary",
                    pool_label="旋挖钻",
                    same_structure_parallel_limit=2,
                )
                for index in range(1, 9)
            ],
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 15


def test_default_pile_resource_parallel_rules_are_configuration_fields() -> None:
    scenario = default_scenario()
    pool_by_type = {pool.type: pool for pool in scenario.resource_pools}

    for resource_type in {"rotary_drill", "circulation_drill", "impact_drill"}:
        assert pool_by_type[resource_type].same_structure_resource_binding is False
        assert pool_by_type[resource_type].same_structure_parallel_limit == 1
        assert pool_by_type[resource_type].parallel_rule_description
    assert pool_by_type["manual_pile_team"].same_structure_resource_binding is False
    assert pool_by_type["manual_pile_team"].same_structure_parallel_limit is None
    assert pool_by_type["manual_pile_team"].parallel_rule_description

    resources, validation = scenario_module.expand_resource_pools(scenario.resource_pools)
    assert validation == []
    rotary = next(resource for resource in resources if resource.type == "rotary_drill")
    manual = next(resource for resource in resources if resource.type == "manual_pile_team")
    assert rotary.same_structure_resource_binding is False
    assert rotary.same_structure_parallel_limit == 1
    assert manual.same_structure_resource_binding is False
    assert manual.same_structure_parallel_limit is None


def test_control_priority_balances_workload_across_fixed_rotary_resources() -> None:
    pytest.importorskip("ortools")
    tasks = [
        Task(
            id=f"B1-L-P{index:02d}-PILE-01",
            name=f"{index}# pier pile",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=index,
            structure_id=f"B1-L-P{index:02d}",
            structure_name=f"{index}# pier",
            structure_type="pier",
            component_type="pile",
            process_name="pile",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1",
            duration_days=3,
            compatible_resource_types=["rotary_drill"],
        )
        for index in range(1, 13)
    ]

    result = solve_schedule(
        ScheduleInput(
            project_name="fixed-rotary-balance",
            start_date=date(2026, 1, 1),
            tasks=tasks,
            precedence_links=[],
            resources=[
                Resource(id=f"rotary_drill_{index}", name=f"Rotary {index}", type="rotary_drill")
                for index in range(1, 7)
            ],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                objective_terms=_objective_terms_with_only("resource_workload_balance", 100),
            ),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    rotary_resources = [
        item
        for item in result.stats["resource_organization_analysis"]["resources"]
        if item["resource_type"] == "rotary_drill"
    ]
    workloads = [item["active_days"] for item in rotary_resources]
    assert len(rotary_resources) == 6
    assert all(workload > 0 for workload in workloads)
    assert max(workloads) - min(workloads) <= 3
    assert result.objective_breakdown["resource_workload_balance_penalty"] <= 3


def test_control_priority_reports_resource_idle_penalty_for_forced_gap() -> None:
    pytest.importorskip("ortools")
    rotary_first = _solver_task("A-rotary", "rotary first", 1, "rotary_drill")
    blocker = _solver_task("B-blocker", "blocking work", 20, "other_team")
    rotary_last = _solver_task("C-rotary", "rotary last", 1, "rotary_drill")

    result = solve_schedule(
        ScheduleInput(
            project_name="resource-idle-gap",
            start_date=date(2026, 1, 1),
            tasks=[rotary_first, blocker, rotary_last],
            precedence_links=[
                PrecedenceLink(
                    id="first-before-blocker",
                    predecessor_id=rotary_first.id,
                    successor_id=blocker.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                ),
                PrecedenceLink(
                    id="blocker-before-last",
                    predecessor_id=blocker.id,
                    successor_id=rotary_last.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                ),
            ],
            resources=[
                Resource(id="rotary_drill_1", name="Rotary 1", type="rotary_drill"),
                Resource(id="other_team_1", name="Other 1", type="other_team"),
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive", enable_balance_objective=False),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    rotary = next(
        item
        for item in result.stats["resource_organization_analysis"]["resources"]
        if item["resource_id"] == "rotary_drill_1"
    )
    assert rotary["idle_days"] >= 20
    assert rotary["max_idle_gap_days"] >= 20
    assert result.objective_breakdown["resource_idle_penalty"] >= 20


def test_control_priority_resource_path_continuity_counts_same_side_gap_and_side_switch() -> None:
    pytest.importorskip("ortools")

    def path_task(task_id: str, side: str, pier_no: int) -> Task:
        return Task(
            id=task_id,
            name=f"{side}{pier_no} pile",
            bridge_id="B1",
            work_section_id=f"WS-{side}",
            sequence_order=pier_no,
            structure_id=f"B1-{side}-P{pier_no:02d}",
            structure_name=f"{pier_no}# pier",
            structure_type="pier",
            component_type="pile",
            process_name="pile",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1",
            duration_days=1,
            compatible_resource_types=["path_team"],
        )

    first = path_task("B1-L-P01-PILE", "L", 1)
    second = path_task("B1-L-P04-PILE", "L", 4)
    third = path_task("B1-R-P04-PILE", "R", 4)

    result = solve_schedule(
        ScheduleInput(
            project_name="resource-path-transition-penalty",
            start_date=date(2026, 1, 1),
            tasks=[first, second, third],
            precedence_links=[
                PrecedenceLink(
                    id="left-1-before-left-4",
                    predecessor_id=first.id,
                    successor_id=second.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                ),
                PrecedenceLink(
                    id="left-4-before-right-4",
                    predecessor_id=second.id,
                    successor_id=third.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                ),
            ],
            resources=[Resource(id="path_team_1", name="Path Team 1", type="path_team")],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                objective_terms=_objective_terms_with_only("resource_path_continuity", 3_000),
            ),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_breakdown["resource_path_continuity_penalty"] == 4


def test_control_priority_resource_path_continuity_penalizes_back_and_forth_adjacent_piers() -> None:
    pytest.importorskip("ortools")

    def path_task(task_id: str, pier_no: int) -> Task:
        return Task(
            id=task_id,
            name=f"L{pier_no} pile",
            bridge_id="B1",
            work_section_id="WS-L",
            sequence_order=pier_no,
            structure_id=f"B1-L-P{pier_no:02d}",
            structure_name=f"{pier_no}# pier",
            structure_type="pier",
            component_type="pile",
            process_name="pile",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1",
            duration_days=1,
            compatible_resource_types=["path_team"],
        )

    first = path_task("B1-L-P04-PILE-A", 4)
    second = path_task("B1-L-P03-PILE", 3)
    third = path_task("B1-L-P04-PILE-B", 4)

    result = solve_schedule(
        ScheduleInput(
            project_name="resource-path-adjacent-back-and-forth-penalty",
            start_date=date(2026, 1, 1),
            tasks=[first, second, third],
            precedence_links=[
                PrecedenceLink(
                    id="left-4-before-left-3",
                    predecessor_id=first.id,
                    successor_id=second.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                ),
                PrecedenceLink(
                    id="left-3-before-left-4",
                    predecessor_id=second.id,
                    successor_id=third.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                ),
            ],
            resources=[Resource(id="path_team_1", name="Path Team 1", type="path_team")],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                objective_terms=_objective_terms_with_only("resource_path_continuity", 3_000),
            ),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_breakdown["resource_path_continuity_penalty"] == 2


def test_configured_resource_normal_work_uses_resource_continuity_not_unconfigured_balance() -> None:
    pytest.importorskip("ortools")

    def normal_path_task(task_id: str, side: str, pier_no: int) -> Task:
        return Task(
            id=task_id,
            name=f"{side}{pier_no}#墩桩基",
            bridge_id="B1",
            work_section_id=f"WS-{side}",
            sequence_order=pier_no,
            structure_id=f"B1-{side}-P{pier_no:02d}",
            structure_name=f"{pier_no}#墩",
            structure_type="pier",
            component_type="pile",
            process_name="桩基",
            productivity_rule_id="pile",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["rotary_drill"],
            control_level="normal",
        )

    result = solve_schedule(
        ScheduleInput(
            project_name="configured-normal-resource-continuity",
            start_date=date(2026, 1, 1),
            tasks=[
                normal_path_task("B1-L-P01-PILE", "L", 1),
                normal_path_task("B1-L-P04-PILE", "L", 4),
                normal_path_task("B1-R-P04-PILE", "R", 4),
            ],
            precedence_links=[],
            resources=[Resource(id="rotary_drill_1", name="旋挖钻1", type="rotary_drill")],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                objective_terms=_objective_terms_with_only("resource_path_continuity", 3_000),
                normal_balance_bucket="week",
            ),
            time_limit_seconds=5,
        )
    )

    metrics = result.stats["normal_balance_metrics"]

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert metrics["normal_task_count"] == 3
    assert metrics["configured_resource_normal_task_count"] == 3
    assert metrics["unconfigured_resource_normal_task_count"] == 0
    assert result.objective_breakdown["unconfigured_normal_balance_penalty"] == 0
    assert result.objective_breakdown["normal_balance_penalty"] == 0
    assert result.objective_breakdown["resource_path_continuity_penalty"] >= 1


def test_unconfigured_resource_normal_work_balances_weekly_workload_without_extending_critical_path() -> None:
    pytest.importorskip("ortools")

    control = _solver_task("Z-control", "控制墩盖梁", 30, "critical_team").model_copy(
        update={
            "bridge_id": "B1",
            "work_section_id": "WS-C",
            "structure_id": "B1-C-P99",
            "control_level": "control",
        }
    )
    normal_tasks = [
        _solver_task(f"N{index}", f"普通附属工作{index}", 2, "unconfigured_team").model_copy(
            update={
                "bridge_id": "B1",
                "work_section_id": "WS-N",
                "structure_id": f"B1-N-P{index:02d}",
                "control_level": "normal",
            }
        )
        for index in range(1, 7)
    ]

    result = solve_schedule(
        ScheduleInput(
            project_name="unconfigured-normal-weekly-balance",
            start_date=date(2026, 1, 1),
            tasks=[control, *normal_tasks],
            precedence_links=[],
            resources=[Resource(id="critical_team_1", name="控制班组1", type="critical_team")],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                normal_balance_bucket="week",
                normal_latest_finish_offset=21,
                max_parallel_normal_per_work_section=10,
            ),
            time_limit_seconds=5,
        )
    )

    metrics = result.stats["normal_balance_metrics"]
    bucket_workloads = [bucket["duration_days"] for bucket in metrics["bucket_loads"]]

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_days == 30
    assert metrics["normal_task_count"] == 6
    assert metrics["configured_resource_normal_task_count"] == 0
    assert metrics["unconfigured_resource_normal_task_count"] == 6
    assert bucket_workloads == [4, 4, 4]
    assert result.objective_breakdown["unconfigured_normal_balance_penalty"] == 0
    assert result.objective_breakdown["unconfigured_normal_balance_weight"] == 10


def test_control_chain_normal_predecessor_is_excluded_from_unconfigured_balance() -> None:
    pytest.importorskip("ortools")

    predecessor = _solver_task("N-control-predecessor", "控制链普通前置", 5, "unconfigured_team").model_copy(
        update={
            "bridge_id": "B1",
            "work_section_id": "WS-C",
            "structure_id": "B1-C-P01",
            "control_level": "normal",
        }
    )
    control = _solver_task("Z-control", "控制墩盖梁", 3, "critical_team").model_copy(
        update={
            "bridge_id": "B1",
            "work_section_id": "WS-C",
            "structure_id": "B1-C-P02",
            "control_level": "control",
        }
    )
    ordinary = [
        _solver_task(f"N-fill-{index}", f"普通补充工作{index}", 2, "unconfigured_team").model_copy(
            update={
                "bridge_id": "B1",
                "work_section_id": "WS-N",
                "structure_id": f"B1-N-P{index:02d}",
                "control_level": "normal",
            }
        )
        for index in range(1, 3)
    ]

    result = solve_schedule(
        ScheduleInput(
            project_name="control-chain-normal-excluded",
            start_date=date(2026, 1, 1),
            tasks=[predecessor, control, *ordinary],
            precedence_links=[
                PrecedenceLink(
                    id="pre-before-control",
                    predecessor_id=predecessor.id,
                    successor_id=control.id,
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="test",
                )
            ],
            resources=[Resource(id="critical_team_1", name="控制班组1", type="critical_team")],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                normal_earliest_start_offset=7,
                normal_balance_bucket="week",
                normal_latest_finish_offset=21,
                max_parallel_normal_per_work_section=10,
            ),
            time_limit_seconds=5,
        )
    )

    tasks_by_id = {task.id: task for task in result.tasks}
    metrics = result.stats["normal_balance_metrics"]
    bucket_task_ids = {
        task_id
        for bucket in metrics["bucket_loads"]
        for task_id in bucket["task_ids"]
    }

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert tasks_by_id[predecessor.id].start_offset == 0
    assert tasks_by_id[control.id].start_offset == predecessor.duration_days
    assert metrics["normal_task_count"] == 2
    assert metrics["unconfigured_resource_normal_task_count"] == 2
    assert predecessor.id not in bucket_task_ids


def test_control_priority_reports_configured_objective_terms_used() -> None:
    pytest.importorskip("ortools")
    first = _solver_task("A-first", "first", 2, "team")
    second = _solver_task("B-second", "second", 2, "team")

    result = solve_schedule(
        ScheduleInput(
            project_name="objective-term-config",
            start_date=date(2026, 1, 1),
            tasks=[first, second],
            precedence_links=[],
            resources=[Resource(id="team_1", name="Team 1", type="team")],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                objective_terms={
                    "resource_idle": {"enabled": False, "weight": 1234},
                    "makespan_and_soft_milestone": {"enabled": True, "weight": 333},
                    "normal_balance": {"enabled": False, "weight": 55},
                },
            ),
            time_limit_seconds=5,
        )
    )

    weights = result.objective_breakdown["objective_weights"]
    terms_used = result.objective_breakdown["objective_terms_used"]

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert weights["resource_idle"] == 0
    assert weights["makespan_and_soft_milestone"] == 333
    assert "normal_balance" not in weights
    assert "same_structure_craft_split" not in weights
    assert "same_structure_craft_split" not in terms_used
    assert "normal_balance" not in terms_used
    assert "same_structure_craft_split_penalty" not in result.objective_breakdown
    assert terms_used["resource_idle"] == {"enabled": False, "weight": 1234, "effective_weight": 0}
    assert result.objective_breakdown["normal_balance_penalty"] == 0


def test_control_priority_enforces_hard_milestone_without_explicit_flag() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    task = _solver_task("T-hard", "Hard constrained task", 5, "team")

    result = solve_schedule(
        ScheduleInput(
            project_name="hard-milestone-refinement",
            start_date=start,
            tasks=[task],
            precedence_links=[],
            resources=[Resource(id="team_1", name="Team 1", type="team")],
            milestones=[
                MilestoneConstraint(
                    id="M-hard",
                    name="Hard finish",
                    level="contract",
                    mode="hard",
                    scope_type="project",
                    target_event="finish",
                    target_date=start,
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive"),
            time_limit_seconds=5,
        )
    )

    assert result.status == "INFEASIBLE"
    assert not result.tasks
    assert result.stats["solve_mode"] == "control_priority"


def test_control_priority_hard_milestone_is_not_control_lateness_objective() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    task = _solver_task("T-hard-met", "Hard milestone task", 3, "team")

    result = solve_schedule(
        ScheduleInput(
            project_name="hard-milestone-not-soft-objective",
            start_date=start,
            tasks=[task],
            precedence_links=[],
            resources=[Resource(id="team_1", name="Team 1", type="team")],
            milestones=[
                MilestoneConstraint(
                    id="M-hard-met",
                    name="Hard finish",
                    level="contract",
                    mode="hard",
                    scope_type="project",
                    target_event="finish",
                    target_date=start + timedelta(days=4),
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive"),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.milestone_results[0].mode == "hard"
    assert result.milestone_results[0].lateness_days == 0
    assert result.objective_breakdown["control_lateness_days"] == 0
    assert result.objective_breakdown["soft_control_lateness_penalty"] == 0


def test_control_priority_soft_control_lateness_uses_highest_weight() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    task = _solver_task("T-soft-control", "Soft control task", 5, "team")

    result = solve_schedule(
        ScheduleInput(
            project_name="soft-control-lateness",
            start_date=start,
            tasks=[task],
            precedence_links=[],
            resources=[Resource(id="team_1", name="Team 1", type="team")],
            milestones=[
                MilestoneConstraint(
                    id="M-soft-control",
                    name="Soft control finish",
                    level="control",
                    mode="soft",
                    scope_type="project",
                    target_event="finish",
                    target_date=start + timedelta(days=2),
                    penalty_per_day=7,
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive"),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.milestone_results[0].lateness_days == 2
    assert result.objective_breakdown["control_lateness_days"] == 2
    assert result.objective_breakdown["soft_control_lateness_penalty"] == 2
    assert result.objective_breakdown["soft_milestone_penalty"] == 0
    assert result.objective_breakdown["weighted_objective"] >= 2_000_000_000


def test_control_priority_plain_soft_milestone_is_diagnostic_not_makespan_objective() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    task = _solver_task("T-soft-diagnostic", "Soft diagnostic task", 5, "team")

    result = solve_schedule(
        ScheduleInput(
            project_name="plain-soft-milestone-diagnostic",
            start_date=start,
            tasks=[task],
            precedence_links=[],
            resources=[Resource(id="team_1", name="Team 1", type="team")],
            milestones=[
                MilestoneConstraint(
                    id="M-soft-diagnostic",
                    name="Soft diagnostic finish",
                    level="internal",
                    mode="soft",
                    scope_type="project",
                    target_event="finish",
                    target_date=start,
                    penalty_per_day=10,
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="comprehensive",
                objective_terms=_objective_terms_with_only("makespan_and_soft_milestone", 10_000),
            ),
            time_limit_seconds=5,
        )
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.objective_breakdown["soft_milestone_penalty"] > 0
    assert result.objective_breakdown["control_lateness_days"] == 0
    assert result.objective_breakdown["weighted_objective"] == result.objective_days * 10_000


def test_control_priority_keeps_control_task_ahead_of_competing_normal_task() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    normal = _solver_task("A-normal", "Normal pier", 5, "template").model_copy(
        update={"structure_id": "S-normal", "control_level": "normal"}
    )
    control = _solver_task("Z-control", "Control pier", 5, "template").model_copy(
        update={"structure_id": "S-control", "control_level": "control"}
    )

    result = solve_schedule(
        ScheduleInput(
            project_name="control-priority",
            start_date=start,
            tasks=[normal, control],
            precedence_links=[],
            resources=[Resource(id="template-1", name="Template 1", type="template")],
            milestones=[
                MilestoneConstraint(
                    id="M-control",
                    name="Control finish",
                    level="control",
                    mode="hard",
                    scope_type="structure",
                    scope_id="S-control",
                    target_event="finish",
                    target_date=date(2026, 1, 5),
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive", resource_guarantee="priority"),
            time_limit_seconds=5,
        )
    )

    by_task = {task.id: task for task in result.tasks}
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert by_task["Z-control"].start_offset == 0
    assert by_task["A-normal"].start_offset >= by_task["Z-control"].end_offset
    assert result.objective_breakdown["solve_mode"] == "control_priority"
    assert result.stats["control_priority_analysis"]["bottleneck_resources"][0]["resource_type"] == "template"


def test_control_buffer_risk_is_zero_when_required_buffer_remains() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    normal = _solver_task("A-normal", "Normal pier", 5, "template").model_copy(
        update={"structure_id": "S-normal", "control_level": "normal"}
    )
    control = _solver_task("Z-control", "Control pier", 5, "template").model_copy(
        update={"structure_id": "S-control", "control_level": "control"}
    )

    result = solve_schedule(
        ScheduleInput(
            project_name="control-buffer-sufficient",
            start_date=start,
            tasks=[normal, control],
            precedence_links=[],
            resources=[
                Resource(id="template-1", name="Template 1", type="template"),
                Resource(id="template-2", name="Template 2", type="template"),
            ],
            milestones=[
                MilestoneConstraint(
                    id="M-control",
                    name="Control finish",
                    level="control",
                    mode="hard",
                    scope_type="structure",
                    scope_id="S-control",
                    target_event="finish",
                    target_date=date(2026, 1, 20),
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive", resource_guarantee="priority"),
            time_limit_seconds=5,
        )
    )

    risks = result.stats["control_priority_analysis"]["control_buffer_risks"]
    control_risk = next(item for item in risks if item["task_id"] == "Z-control")

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert control_risk["buffer_risk_days"] == 0
    assert control_risk["status"] == "normal"
    assert result.objective_breakdown["control_buffer_risk_penalty"] == 0


def test_control_buffer_risk_is_reported_when_required_buffer_is_missing() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    normal = _solver_task("A-normal", "Normal pier", 5, "template").model_copy(
        update={"structure_id": "S-normal", "control_level": "normal"}
    )
    control = _solver_task("Z-control", "Control pier", 5, "template").model_copy(
        update={"structure_id": "S-control", "control_level": "control"}
    )

    result = solve_schedule(
        ScheduleInput(
            project_name="control-buffer-insufficient",
            start_date=start,
            tasks=[normal, control],
            precedence_links=[],
            resources=[Resource(id="template-1", name="Template 1", type="template")],
            milestones=[
                MilestoneConstraint(
                    id="M-control",
                    name="Control finish",
                    level="control",
                    mode="hard",
                    scope_type="structure",
                    scope_id="S-control",
                    target_event="finish",
                    target_date=date(2026, 1, 8),
                )
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive", resource_guarantee="priority"),
            time_limit_seconds=5,
        )
    )

    risks = result.stats["control_priority_analysis"]["control_buffer_risks"]
    control_risk = next(item for item in risks if item["task_id"] == "Z-control")

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert control_risk["remaining_buffer_days"] == 3
    assert control_risk["buffer_risk_days"] == 4
    assert control_risk["status"] == "buffer_insufficient"
    assert result.stats["control_priority_analysis"]["control_buffer_status"] == "buffer_insufficient"
    assert result.objective_breakdown["control_buffer_risk_penalty"] >= 4


def test_control_priority_analysis_separates_objects_tasks_and_predecessors() -> None:
    pytest.importorskip("ortools")
    scenario = _scenario_with_continuous_beam(main_pier_count=2, standard_cycles=1)
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = [
        _abutment_structure(0),
        _pier_lower_structure(1),
        _pier_lower_structure(2),
        _pier_body_structure(3),
    ]
    for pool in scenario.resource_pools:
        if pool.type == "cast_in_place_continuous_beam_team":
            pool.quantity = 4
    scenario.time_limit_seconds = 5

    solved = solve_scenario(scenario)
    analysis = solved.result.stats["control_priority_analysis"]

    assert solved.result.status in {"OPTIMAL", "FEASIBLE"}
    assert any(item["object_type"] == "continuous_beam" for item in analysis["control_objects"])
    main_pier_objects = [
        item for item in analysis["control_objects"] if item["object_type"] == "main_pier_lower_structure"
    ]
    assert {item["structure_id"] for item in main_pier_objects} >= {"P01", "P02"}

    p01_object_tasks = [
        item for item in analysis["control_object_tasks"] if item["object_id"] == "lower:P01"
    ]
    assert {item["component_type"] for item in p01_object_tasks} >= {"pile", "cap", "pier_body"}
    assert {item["task_role"] for item in p01_object_tasks} == {"inherited_control_task"}

    predecessor = next(item for item in analysis["control_chain_predecessors"] if item["task_id"] == "P03-BODY")
    assert predecessor["source"] == "control_chain_predecessor"
    assert predecessor["impacted_control_objects"]
    assert all(item["id"].startswith("continuous:") for item in predecessor["impacted_control_objects"])
    assert "P03-BODY" not in {item["task_id"] for item in analysis["control_object_tasks"]}


def test_control_priority_analysis_labels_left_and_right_side_objects() -> None:
    pytest.importorskip("ortools")
    tasks = [
        Task(
            id="L10-PILE",
            name="10#墩-1#桩基",
            bridge_id="B1",
            work_section_id="WS-L",
            structure_id="B1-L-P10",
            structure_name="10#墩",
            structure_type="pier",
            control_level="control",
            component_type="pile",
            process_name="旋挖钻成孔",
            productivity_rule_id="pile_rotary_regular",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["rotary_drill"],
        ),
        Task(
            id="R10-PILE",
            name="10#墩-1#桩基",
            bridge_id="B1",
            work_section_id="WS-R",
            structure_id="B1-R-P10",
            structure_name="10#墩",
            structure_type="pier",
            control_level="control",
            component_type="pile",
            process_name="旋挖钻成孔",
            productivity_rule_id="pile_rotary_regular",
            quantity=1,
            quantity_label="1根",
            duration_days=1,
            compatible_resource_types=["rotary_drill"],
        ),
        Task(
            id="L-CB",
            name="左幅连续梁10#墩T构-0号块",
            bridge_id="B1",
            work_section_id="WS-L",
            structure_id="B1-L-CB-G01-T10",
            structure_name="左幅连续梁10#墩T构",
            structure_type="continuous_beam",
            control_level="control",
            component_type="cast_in_place_continuous_beam",
            process_name="0号块施工",
            productivity_rule_id="cast_in_place_continuous_beam",
            quantity=1,
            quantity_label="1段",
            duration_days=1,
            compatible_resource_types=["beam_team"],
        ),
        Task(
            id="R-CB",
            name="右幅连续梁10#墩T构-0号块",
            bridge_id="B1",
            work_section_id="WS-R",
            structure_id="B1-R-CB-G01-T10",
            structure_name="右幅连续梁10#墩T构",
            structure_type="continuous_beam",
            control_level="control",
            component_type="cast_in_place_continuous_beam",
            process_name="0号块施工",
            productivity_rule_id="cast_in_place_continuous_beam",
            quantity=1,
            quantity_label="1段",
            duration_days=1,
            compatible_resource_types=["beam_team"],
        ),
    ]
    result = solve_schedule(
        ScheduleInput(
            project_name="side-aware-control-diagnostics",
            start_date=date(2026, 1, 1),
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="L10-to-CB",
                    predecessor_id="L10-PILE",
                    successor_id="L-CB",
                    lag_days=0,
                    source_rule_id="continuous_beam_zero_block_after_main_pier_lower_structure",
                ),
                PrecedenceLink(
                    id="R10-to-CB",
                    predecessor_id="R10-PILE",
                    successor_id="R-CB",
                    lag_days=0,
                    source_rule_id="continuous_beam_zero_block_after_main_pier_lower_structure",
                ),
            ],
            resources=[
                Resource(id="rotary-1", name="旋挖钻1", type="rotary_drill"),
                Resource(id="beam-1", name="连续梁班组1", type="beam_team"),
            ],
            schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive", resource_guarantee="priority"),
            time_limit_seconds=5,
        )
    )

    analysis = result.stats["control_priority_analysis"]
    object_names = {
        item["name"] for item in analysis["control_objects"] if item["object_type"] == "main_pier_lower_structure"
    }
    task_names = {item["task_name"] for item in analysis["control_object_tasks"]}

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert {"左幅10#墩下部结构", "右幅10#墩下部结构"} <= object_names
    assert {"左幅10#墩-1#桩基", "右幅10#墩-1#桩基"} <= task_names


def test_control_priority_applies_normal_windows_and_workface_limit() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        _solver_task(f"N{index}", f"Normal {index}", 3, "crew").model_copy(
            update={
                "bridge_id": "B1",
                "work_section_id": "WS1",
                "structure_id": f"S{index}",
                "control_level": "normal",
            }
        )
        for index in range(1, 4)
    ]
    result = solve_schedule(
        ScheduleInput(
            project_name="normal-balance",
            start_date=start,
            tasks=tasks,
            precedence_links=[],
            resources=[
                Resource(id=f"crew-{index}", name=f"Crew {index}", type="crew")
                for index in range(1, 4)
            ],
            schedule_strategy=ScheduleStrategyConfig(
                strategy="balanced_normal",
                normal_earliest_start_offset=2,
                max_parallel_normal_per_work_section=1,
                normal_balance_bucket="week",
            ),
            time_limit_seconds=5,
        )
    )

    ordered = sorted(result.tasks, key=lambda task: task.start_offset)
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert all(task.start_offset >= 2 for task in ordered)
    for previous, current in zip(ordered, ordered[1:]):
        assert current.start_offset >= previous.end_offset
    assert result.stats["normal_balance_metrics"]["normal_task_count"] == 3
    assert "normal_balance" not in result.objective_breakdown["objective_weights"]
    assert result.objective_breakdown["normal_balance_penalty"] == 0
    assert result.objective_breakdown["normal_balance_score"] >= 0


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
    assert metrics["path_group_diagnostics"][0]["actual_sequence"] == ["左幅1#墩", "左幅3#墩", "左幅5#墩"]


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
    assert metrics["path_group_diagnostics"][0]["actual_sequence"] == ["左幅1#墩", "左幅3#墩", "左幅5#墩"]


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
    assert metrics["path_group_switch_count"] == 1
    assert {item["side"] for item in metrics["path_group_diagnostics"]} == {"L", "R"}


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
    assert result.stats["schedule_source"] == "control_priority_balanced_reoptimization"
    assert result.objective_breakdown["solve_mode"] == "min_resources_fixed_duration"
    assert "control_priority_analysis" in result.stats
    assert "normal_balance_metrics" in result.stats
    assert recommended["recommended_quantity"] == 2
    assert recommended["max_quantity"] == 2
    assert {allocation.resource_id for allocation in result.resource_allocations} <= {"team_1", "team_2"}


def test_min_resource_solver_reoptimizes_with_control_priority() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    normal = _solver_task("A-normal", "Normal pier", 5, "team").model_copy(
        update={"structure_id": "S-normal", "control_level": "normal"}
    )
    control = _solver_task("Z-control", "Control pier", 5, "team").model_copy(
        update={"structure_id": "S-control", "control_level": "control"}
    )
    schedule_input = ScheduleInput(
        project_name="min-resource-control-priority",
        start_date=start,
        tasks=[normal, control],
        precedence_links=[],
        resources=[Resource(id="team_1", name="Team 1", type="team", pool_id="pool-team", pool_label="Team")],
        milestones=[
            MilestoneConstraint(
                id="M-control",
                name="Control finish",
                level="control",
                mode="hard",
                scope_type="structure",
                scope_id="S-control",
                target_event="finish",
                target_date=date(2026, 1, 5),
            )
        ],
        schedule_strategy=ScheduleStrategyConfig(strategy="min_resource", resource_guarantee="off"),
        time_limit_seconds=5,
    )

    result = solve_min_resources_schedule(schedule_input)

    by_task = {task.id: task for task in result.tasks}
    recommended = result.stats["recommended_resource_counts"][0]
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.stats["schedule_source"] == "control_priority_balanced_reoptimization"
    assert result.objective_breakdown["resource_guarantee"] == "priority"
    assert result.stats["control_priority_analysis"]["control_task_count"] == 1
    assert recommended["recommended_quantity"] == 1
    assert by_task["Z-control"].start_offset == 0
    assert by_task["A-normal"].start_offset >= by_task["Z-control"].end_offset


def test_min_resource_reoptimization_candidates_copy_objective_configuration_without_legacy_balance_target() -> None:
    schedule_input = _min_resource_test_input(max_resources=2).model_copy(
        update={
            "schedule_strategy": ScheduleStrategyConfig(
                strategy="min_resource",
                resource_guarantee="off",
                objective_terms={
                    "resource_idle": {"enabled": False, "weight": 1234},
                    "makespan_and_soft_milestone": {"enabled": True, "weight": 333},
                },
            )
        }
    )

    candidates = solver_module._min_resource_reoptimization_candidates(schedule_input, {"team": 2})

    assert len(candidates) == 1
    primary_strategy = candidates[0]["schedule_input"].schedule_strategy
    assert primary_strategy.objective_terms["resource_idle"].enabled is False
    assert primary_strategy.objective_terms["resource_idle"].weight == 1234
    assert primary_strategy.objective_terms["makespan_and_soft_milestone"].weight == 333
    assert primary_strategy.enable_balance_objective is False
    assert "normal_balance" not in primary_strategy.objective_terms


def test_min_resource_solver_falls_back_to_binary_search_when_global_optimization_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")
    schedule_input = _min_resource_test_input(max_resources=2)
    calls: list[dict[str, object]] = []
    original_solve_capacity_model = solver_module._solve_capacity_model

    def fake_solve_capacity_model(*args: object, **kwargs: object) -> dict[str, object]:
        counts = kwargs.get("counts")
        minimize_resource_count = bool(kwargs.get("minimize_resource_count"))
        if minimize_resource_count:
            calls.append({"phase": "global", "counts": counts})
            return {
                "status": "UNKNOWN",
                "validation": [],
                "stats": {
                    "horizon_days": 1,
                    "wall_time_seconds": schedule_input.time_limit_seconds,
                    "conflicts": 0,
                    "branches": 0,
                },
                "group_counts": {},
            }
        calls.append({"phase": "fixed", "counts": dict(counts or {})})
        return original_solve_capacity_model(*args, **kwargs)

    monkeypatch.setattr(solver_module, "_solve_capacity_model", fake_solve_capacity_model)

    result = solve_min_resources_schedule(schedule_input, fallback_target_days=5)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.stats["global_capacity_model_status"] == "UNKNOWN"
    assert result.stats["capacity_model_stats"]["fallback_search_used"] is True
    assert result.stats["recommended_resource_counts"][0]["recommended_quantity"] == 2
    assert any(call["phase"] == "global" for call in calls)
    assert any(call["phase"] == "fixed" for call in calls)


def test_min_resource_solver_keeps_capacity_schedule_when_balanced_reoptimization_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")
    schedule_input = _min_resource_test_input(max_resources=2)
    calls: list[bool] = []

    def fake_control_priority(schedule_input: ScheduleInput, **_: object) -> ScheduleResult:
        calls.append(schedule_input.schedule_strategy.enable_balance_objective)
        return ScheduleResult(
            status="UNKNOWN",
            plan_start_date=schedule_input.start_date,
            milestone_results=[],
            stats={
                "wall_time_seconds": schedule_input.time_limit_seconds,
                "conflicts": 0,
                "branches": 0,
                "search_workers": solver_module._scheduler_search_workers(),
            },
        )

    monkeypatch.setattr(solver_module, "_solve_task_parallelism", lambda count: 1)
    monkeypatch.setattr(solver_module, "solve_control_priority_schedule", fake_control_priority)

    result = solve_min_resources_schedule(schedule_input, fallback_target_days=5)

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert result.stats["schedule_source"] == "capacity_model_verified_schedule"
    assert result.stats["recommended_schedule_source"] == "capacity_model_verified_schedule"
    assert result.stats["capacity_verification_status"] == "verified"
    assert result.stats["balanced_reoptimization_status"] == "UNKNOWN"
    assert result.stats["unbalanced_reoptimization_status"] == "not_attempted"
    assert result.stats["recommended_resource_counts"][0]["recommended_quantity"] == 2
    assert result.tasks
    assert result.resource_allocations
    assert calls == [False]
    assert any("capacity model" in message.message for message in result.validation)


def test_min_resource_reoptimization_uses_single_control_priority_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")
    schedule_input = _min_resource_test_input(max_resources=2)
    calls: list[bool] = []

    def fake_control_priority(
        schedule_input: ScheduleInput,
        *,
        max_makespan_days: int | None = None,
        **_: object,
    ) -> ScheduleResult:
        calls.append(schedule_input.schedule_strategy.enable_balance_objective)
        objective_days = max_makespan_days or 5
        return ScheduleResult(
            status="FEASIBLE",
            objective_days=objective_days,
            plan_start_date=schedule_input.start_date,
            plan_finish_date=schedule_input.start_date + timedelta(days=objective_days - 1),
            milestone_results=[],
            stats={"wall_time_seconds": schedule_input.time_limit_seconds},
        )

    monkeypatch.setattr(solver_module, "_solve_task_parallelism", lambda count: count)
    monkeypatch.setattr(solver_module, "solve_control_priority_schedule", fake_control_priority)

    result = solve_min_resources_schedule(schedule_input, fallback_target_days=5)

    assert result.status == "FEASIBLE"
    assert result.stats["schedule_source"] == "control_priority_balanced_reoptimization"
    assert result.stats["balanced_reoptimization_status"] == "FEASIBLE"
    assert result.stats["unbalanced_reoptimization_status"] == "not_attempted"
    assert result.stats["parallel_reoptimization_used"] is False
    assert calls == [False]


def test_min_resource_solver_returns_infeasible_when_reoptimization_cannot_meet_target() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        _solver_task(f"N{index}", f"Normal {index}", 5, "team").model_copy(
            update={
                "bridge_id": "B1",
                "work_section_id": "WS1",
                "structure_id": f"S{index}",
                "control_level": "normal",
            }
        )
        for index in range(1, 3)
    ]
    schedule_input = ScheduleInput(
        project_name="min-resource-reoptimization-infeasible",
        start_date=start,
        tasks=tasks,
        precedence_links=[],
        resources=[
            Resource(id=f"team_{index}", name=f"Team {index}", type="team", pool_id="pool-team", pool_label="Team")
            for index in range(1, 3)
        ],
        schedule_strategy=ScheduleStrategyConfig(
            strategy="min_resource",
            normal_earliest_start_offset=1,
        ),
        time_limit_seconds=5,
    )

    result = solve_min_resources_schedule(schedule_input, fallback_target_days=5)

    assert result.status == "INFEASIBLE"
    assert result.stats["reason"] == "resource_upper_bound_or_deadline_infeasible"
    assert result.stats["fixed_duration_precheck_failed"] is True
    assert result.stats["resource_upper_bound_counts"][0]["upper_bound_quantity"] == 2


def test_min_resource_solver_requires_target_duration() -> None:
    pytest.importorskip("ortools")
    result = solve_min_resources_schedule(_min_resource_test_input(max_resources=2))

    assert result.status == "MODEL_INVALID"
    assert any(message.level == "error" and "固定工期" in message.message for message in result.validation)


def test_min_resource_solver_reports_infeasible_when_max_resources_cannot_meet_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("ortools")
    capacity_model_calls = 0

    def fake_solve_capacity_model(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal capacity_model_calls
        capacity_model_calls += 1
        return {"status": "UNKNOWN", "validation": [], "stats": {}, "group_counts": {}}

    monkeypatch.setattr(solver_module, "_solve_capacity_model", fake_solve_capacity_model)
    result = solve_min_resources_schedule(_min_resource_test_input(max_resources=1), fallback_target_days=5)

    assert result.status == "INFEASIBLE"
    assert result.stats["reason"] == "resource_upper_bound_or_deadline_infeasible"
    assert result.stats["fixed_duration_precheck_failed"] is True
    assert result.stats["capacity_precheck_status"] == "exclusive_lower_bound_infeasible"
    assert result.stats["lower_bound_prune_used"] is True
    assert capacity_model_calls == 0
    assert result.stats["resource_upper_bound_counts"][0]["upper_bound_quantity"] == 1
    lower_bound = result.stats["resource_capacity_lower_bounds"][0]
    assert lower_bound["required_minimum"] == 2
    assert lower_bound["exceeds_upper_bound"] is True
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


def test_resource_cost_solver_keeps_current_when_current_meets_fixed_duration() -> None:
    pytest.importorskip("ortools")
    result = solve_resource_cost_schedule(
        _resource_cost_parallel_input(task_count=2, max_resources=2),
        {"pool-team": _linear_cost("pool-team", "钻机", current=1, max_quantity=2, unit_cost=1000)},
        fallback_target_days=10,
    )

    selected = _selected_resource_cost(result, "pool-team")
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert selected["selected_quantity"] == 1
    assert selected["added_quantity"] == 0
    assert result.objective_breakdown["resource_incremental_cost"] == 0
    assert result.objective_days == 10


def test_resource_cost_solver_recommends_zero_for_unused_resource_pool() -> None:
    pytest.importorskip("ortools")
    schedule_input = _resource_cost_parallel_input(task_count=1, max_resources=1)
    schedule_input.resources.extend(_resource_instances("pool-unused", "unused_team", "闲置资源", 3))

    result = solve_resource_cost_schedule(
        schedule_input,
        {
            "pool-team": _linear_cost("pool-team", "钻机", current=1, max_quantity=1, unit_cost=1000),
            "pool-unused": _linear_cost("pool-unused", "闲置资源", current=1, max_quantity=3, unit_cost=1000),
        },
        fallback_target_days=5,
    )

    selected = _selected_resource_cost(result, "pool-unused")
    recommended = {
        item["resource_pool_id"]: item
        for item in result.objective_breakdown["recommended_resource_counts"]
    }
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert selected["current_quantity"] == 0
    assert selected["selected_quantity"] == 0
    assert selected["added_quantity"] == 0
    assert selected["incremental_cost"] == 0
    assert recommended["pool-unused"]["recommended_quantity"] == 0


def test_resource_cost_solver_adds_cheapest_resource_to_meet_fixed_duration() -> None:
    pytest.importorskip("ortools")
    result = solve_resource_cost_schedule(
        _resource_cost_parallel_input(task_count=2, max_resources=2),
        {"pool-team": _linear_cost("pool-team", "钻机", current=1, max_quantity=2, unit_cost=1000)},
        fallback_target_days=5,
    )

    selected = _selected_resource_cost(result, "pool-team")
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert selected["selected_quantity"] == 2
    assert selected["added_quantity"] == 1
    assert result.objective_breakdown["resource_incremental_cost"] == 1000
    assert result.objective_days == 5


def test_resource_cost_solver_reports_infeasible_when_max_resources_cannot_meet_fixed_duration() -> None:
    pytest.importorskip("ortools")
    result = solve_resource_cost_schedule(
        _resource_cost_parallel_input(task_count=2, max_resources=1),
        {"pool-team": _linear_cost("pool-team", "钻机", current=1, max_quantity=1, unit_cost=1000)},
        fallback_target_days=5,
    )

    assert result.status == "INFEASIBLE"
    assert result.stats["reason"] == "resource_cost_upper_bound_or_deadline_infeasible"
    assert result.stats["fixed_duration_precheck_failed"] is True


def test_resource_cost_solver_uses_monthly_rental_active_window() -> None:
    pytest.importorskip("ortools")
    result = solve_resource_cost_schedule(
        _resource_cost_parallel_input(task_count=2, max_resources=2),
        {
            "pool-team": _linear_cost(
                "pool-team",
                "钻机",
                current=1,
                max_quantity=2,
                cost_type="monthly_rental",
                unit_cost=3000,
                billing_period_days=30,
            )
        },
        fallback_target_days=5,
    )

    selected = _selected_resource_cost(result, "pool-team")
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert selected["selected_quantity"] == 2
    assert selected["active_days"] == 5
    assert selected["daily_unit_cost"] == 100
    assert result.objective_breakdown["resource_incremental_cost"] == 500


def test_resource_cost_solver_uses_one_time_linear_template_cost() -> None:
    pytest.importorskip("ortools")
    result = solve_resource_cost_schedule(
        _resource_cost_parallel_input(task_count=3, max_resources=3, resource_type="template", label="模板"),
        {"pool-team": _linear_cost("pool-team", "模板", current=1, max_quantity=3, unit_cost=80000)},
        fallback_target_days=5,
    )

    selected = _selected_resource_cost(result, "pool-team")
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert selected["selected_quantity"] == 3
    assert selected["added_quantity"] == 2
    assert result.objective_breakdown["resource_incremental_cost"] == 160000


def test_resource_cost_solver_does_not_add_non_bottleneck_resource() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [_cost_task("T1", "任务1", 5, "team"), _cost_task("T2", "任务2", 5, "team")]
    result = solve_resource_cost_schedule(
        ScheduleInput(
            project_name="非瓶颈资源测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(
                    id="L1",
                    predecessor_id="T1",
                    successor_id="T2",
                    relationship="FS",
                    lag_days=0,
                    source_rule_id="manual",
                )
            ],
            resources=_resource_instances("pool-team", "team", "钻机", 2),
            time_limit_seconds=5,
        ),
        {"pool-team": _linear_cost("pool-team", "钻机", current=1, max_quantity=2, unit_cost=1000)},
        fallback_target_days=10,
    )

    selected = _selected_resource_cost(result, "pool-team")
    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert selected["selected_quantity"] == 1
    assert result.objective_breakdown["resource_incremental_cost"] == 0


def test_resource_cost_solver_can_choose_combined_resources() -> None:
    pytest.importorskip("ortools")
    start = date(2026, 1, 1)
    tasks = [
        _cost_task("P1", "1#桩基", 5, "drill"),
        _cost_task("P2", "2#桩基", 5, "drill"),
        _cost_task("C1", "1#盖梁", 5, "cap_beam_team", component_type="cap_beam"),
        _cost_task("C2", "2#盖梁", 5, "cap_beam_team", component_type="cap_beam"),
    ]
    result = solve_resource_cost_schedule(
        ScheduleInput(
            project_name="组合资源测试",
            start_date=start,
            tasks=tasks,
            precedence_links=[
                PrecedenceLink(id="P1-C1", predecessor_id="P1", successor_id="C1", lag_days=0, source_rule_id="manual"),
                PrecedenceLink(id="P2-C2", predecessor_id="P2", successor_id="C2", lag_days=0, source_rule_id="manual"),
            ],
            resources=[
                *_resource_instances("pool-drill", "drill", "钻机", 2),
                *_resource_instances("pool-cap-beam", "cap_beam_team", "盖梁模板", 2),
            ],
            time_limit_seconds=5,
        ),
        {
            "pool-drill": _linear_cost("pool-drill", "钻机", current=1, max_quantity=2, unit_cost=100),
            "pool-cap-beam": _linear_cost("pool-cap-beam", "盖梁模板", current=1, max_quantity=2, unit_cost=100),
        },
        fallback_target_days=10,
    )

    assert result.status in {"OPTIMAL", "FEASIBLE"}
    assert _selected_resource_cost(result, "pool-drill")["selected_quantity"] == 2
    assert _selected_resource_cost(result, "pool-cap-beam")["selected_quantity"] == 2
    assert result.objective_breakdown["resource_incremental_cost"] == 200
    assert result.objective_days == 10


def test_compare_scenarios_returns_best_result() -> None:
    pytest.importorskip("ortools")
    solved = solve_scenario(default_scenario())
    response = compare_scenarios(ScenarioCompareRequest(results=[solved]))

    assert response.best_scenario_id == solved.scenario_id
    assert response.summaries[0]["total_days"] == solved.result.objective_days


def _scenario_with_continuous_beam(
    *,
    main_pier_count: int,
    standard_cycles: int,
    middle_closure_order: str = "side_to_center",
):
    scenario = default_scenario()
    bridge = scenario.project.bridges[0]
    section = bridge.work_sections[0]
    section.id = "WS-L"
    section.name = "左幅结构参数"
    section.side = "left"
    section.structures = []
    span_count = main_pier_count + 1
    expression = "+".join("40" for _ in range(span_count))
    section.upper_structures = [
        UpperStructureComponent(
            id=f"B1-L-SPAN-{span_index:02d}",
            name=f"第{span_index}跨-现浇连续梁",
            structure_type="现浇连续梁",
            side="left",
            span_index=span_index,
            support_range=f"{span_index - 1}#墩~{span_index}#墩" if span_index > 1 else f"0#台~{span_index}#墩",
            span_length_m=40,
            span_group_expression=expression,
            properties={
                "structure_code": "castInPlaceContinuousBoxGirder",
                "group_index": 1,
                "continuous_beam": {
                    "standard_segment_cycles": standard_cycles,
                    "middle_closure_order": middle_closure_order,
                },
            },
        )
        for span_index in range(1, span_count + 1)
    ]
    scenario.milestones = []
    return scenario


def _scenario_with_single_upper_span(
    *,
    structure_type: str,
    structure_code: str,
    support_range: str,
):
    scenario = default_scenario()
    bridge = scenario.project.bridges[0]
    section = bridge.work_sections[0]
    section.id = "WS-L"
    section.name = "左幅结构参数"
    section.side = "left"
    section.structures = [_pier_body_structure(1), _pier_body_structure(2)]
    section.upper_structures = [
        UpperStructureComponent(
            id="B1-L-SPAN-02",
            name=f"{support_range}-{structure_type}",
            structure_type=structure_type,
            side="left",
            span_index=2,
            support_range=support_range,
            span_length_m=40,
            beam_count_per_span=5 if structure_code == "precastTGirder" else None,
            span_group_expression="40",
            properties={"structure_code": structure_code, "group_index": 1},
        )
    ]
    scenario.milestones = []
    return scenario


def _scenario_with_mixed_upper_structures():
    scenario = default_scenario()
    bridge = scenario.project.bridges[0]
    section = bridge.work_sections[0]
    section.id = "WS-L"
    section.name = "左幅结构参数"
    section.side = "left"
    section.structures = [
        _abutment_structure(0),
        _pier_body_structure(1),
        _pier_body_structure(2),
        _pier_body_structure(3),
        _pier_body_structure(4),
    ]
    section.upper_structures = [
        UpperStructureComponent(
            id="B1-L-SPAN-01",
            name="0#台~1#墩-简支T梁",
            structure_type="简支T梁",
            side="left",
            span_index=1,
            support_range="0#台~1#墩",
            span_length_m=40,
            beam_count_per_span=5,
            span_group_expression="40",
            properties={"structure_code": "precastTGirder", "group_index": 1},
        ),
        UpperStructureComponent(
            id="B1-L-SPAN-02",
            name="1#墩~2#墩-现浇箱梁",
            structure_type="现浇箱梁",
            side="left",
            span_index=2,
            support_range="1#墩~2#墩",
            span_length_m=40,
            span_group_expression="40",
            properties={"structure_code": "castInPlaceBoxGirder", "group_index": 2},
        ),
        UpperStructureComponent(
            id="B1-L-SPAN-03",
            name="2#墩~3#墩-现浇连续梁",
            structure_type="现浇连续梁",
            side="left",
            span_index=3,
            support_range="2#墩~3#墩",
            span_length_m=40,
            span_group_expression="40+40",
            properties={
                "structure_code": "castInPlaceContinuousBoxGirder",
                "group_index": 3,
                "continuous_beam": {"standard_segment_cycles": 0},
            },
        ),
        UpperStructureComponent(
            id="B1-L-SPAN-04",
            name="3#墩~4#墩-现浇连续梁",
            structure_type="现浇连续梁",
            side="left",
            span_index=4,
            support_range="3#墩~4#墩",
            span_length_m=40,
            span_group_expression="40+40",
            properties={
                "structure_code": "castInPlaceContinuousBoxGirder",
                "group_index": 3,
                "continuous_beam": {"standard_segment_cycles": 0},
            },
        ),
    ]
    return scenario


def _pier_body_structure(pier_no: int) -> StructureModel:
    return StructureModel(
        id=f"P{pier_no:02d}",
        name=f"{pier_no}#墩",
        structure_type="pier",
        order=pier_no,
        support_no=f"{pier_no}#墩",
        support_index=pier_no,
        components=[
            ComponentModel(
                id=f"P{pier_no:02d}-BODY",
                name=f"{pier_no}#墩-墩柱",
                component_type="pier_body",
                quantity=1,
                quantity_label="1个",
            )
        ],
    )

def _pier_lower_structure(pier_no: int) -> StructureModel:
    return StructureModel(
        id=f"P{pier_no:02d}",
        name=f"Pier {pier_no}",
        structure_type="pier",
        order=pier_no,
        support_no=f"{pier_no}#pier",
        support_index=pier_no,
        components=[
            ComponentModel(
                id=f"P{pier_no:02d}-PILE-01",
                name=f"Pier {pier_no} pile",
                component_type="pile",
                quantity=1,
                quantity_label="1",
                method_id="rotary_drill",
            ),
            ComponentModel(
                id=f"P{pier_no:02d}-CAP",
                name=f"Pier {pier_no} cap",
                component_type="cap",
                quantity=1,
                quantity_label="1",
            ),
            ComponentModel(
                id=f"P{pier_no:02d}-BODY",
                name=f"Pier {pier_no} body",
                component_type="pier_body",
                quantity=1,
                quantity_label="1",
            ),
        ],
    )


def _abutment_structure(abutment_no: int) -> StructureModel:
    return StructureModel(
        id=f"A{abutment_no:02d}",
        name=f"{abutment_no}#台",
        structure_type="abutment",
        order=abutment_no,
        support_no=f"{abutment_no}#台",
        support_index=abutment_no,
        components=[
            ComponentModel(
                id=f"A{abutment_no:02d}-BODY",
                name=f"{abutment_no}#台-桥台",
                component_type="abutment_body",
                quantity=1,
                quantity_label="1个",
            )
        ],
    )


def _solver_task(task_id: str, name: str, duration_days: int, resource_type: str) -> Task:
    return Task(
        id=task_id,
        name=name,
        structure_id=f"S-{task_id}",
        structure_name=name,
        structure_type="pier",
        component_type="pile",
        process_name="施工",
        productivity_rule_id="rule",
        quantity=1,
        quantity_label="1个",
        duration_days=duration_days,
        compatible_resource_types=[resource_type],
    )


def _same_pier_pile_tasks(resource_type: str, count: int = 2) -> list[Task]:
    return [
        _solver_task(f"P10-PILE-{index}", f"10#墩-{index}#桩基", 5, resource_type).model_copy(
            update={
                "bridge_id": "B1",
                "work_section_id": "WS-L",
                "sequence_order": index,
                "structure_id": "B1-L-P10",
                "structure_name": "10#墩",
                "structure_type": "pier",
                "component_type": "pile",
                "process_name": "桩基",
                "quantity_label": "1根",
            }
        )
        for index in range(1, count + 1)
    ]


def _task_named(tasks: list[Task], name_part: str) -> Task:
    return next(task for task in tasks if name_part in task.name)


def _small_resource_scenario():
    scenario = default_scenario()
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = section.structures[:5]
    section.upper_structures = []
    scenario.milestones = []
    scenario.time_limit_seconds = 5
    return scenario


def _abutment_resource_scenario():
    scenario = default_scenario()
    section = scenario.project.bridges[0].work_sections[0]
    section.structures = [structure for structure in section.structures if structure.structure_type == "abutment"]
    section.upper_structures = []
    scenario.resource_pools = [pool for pool in scenario.resource_pools if pool.type != "abutment_team"]
    _set_all_resource_modes(scenario, "UNLIMITED")
    scenario.milestones = []
    scenario.time_limit_seconds = 5
    return scenario


def _set_all_resource_modes(scenario, mode: str) -> None:
    for pool in scenario.resource_pools:
        pool.resource_mode = mode


def _resource_pool(scenario, resource_type: str) -> ResourcePool:
    return next(pool for pool in scenario.resource_pools if pool.type == resource_type)


def _max_parallel_allocations(allocations) -> int:
    events: list[tuple[int, int]] = []
    for allocation in allocations:
        events.append((allocation.start_offset, 1))
        events.append((allocation.end_offset, -1))

    current = 0
    maximum = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        current += delta
        maximum = max(maximum, current)
    return maximum


def _has_link(
    links: list[PrecedenceLink],
    predecessor_id: str,
    successor_id: str,
    source_rule_id: str,
) -> bool:
    return any(
        link.predecessor_id == predecessor_id
        and link.successor_id == successor_id
        and link.source_rule_id == source_rule_id
        for link in links
    )


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


def _parallel_fixed_resource_scenario(
    *,
    target_days: int,
    current_resources: int,
    max_resources: int,
) -> ScenarioInput:
    start = date(2026, 1, 1)
    structures = [
        StructureModel(
            id=f"S{index}",
            name=f"{index}#墩",
            structure_type="pier",
            order=index,
            components=[
                ComponentModel(
                    id=f"S{index}-CAP",
                    name=f"{index}#墩-承台",
                    component_type="cap",
                    quantity=1,
                    quantity_label="1个",
                )
            ],
        )
        for index in range(1, 3)
    ]
    return ScenarioInput(
        scenario_id="parallel-fixed-resource",
        scenario_name="固定资源增量建议测试",
        project=ProjectModel(
            project_id="P-test",
            project_name="固定资源增量建议测试",
            start_date=start,
            bridges=[
                ProjectBridge(
                    id="B1",
                    name="测试桥",
                    order=1,
                    work_sections=[
                        WorkSection(
                            id="WS1",
                            name="测试工区",
                            order=1,
                            structures=structures,
                        )
                    ],
                )
            ],
        ),
        process_library=[
            ProcessTemplate(
                id="cap-test",
                component_type="cap",
                process_name="承台施工",
                duration_method="fixed_days",
                quantity_source="count",
                productivity_value=5,
                productivity_unit="天/个",
                resource_type="cap_team",
                is_default=True,
            )
        ],
        logic_rules=[],
        resource_pools=[
            ResourcePool(
                id="pool-cap",
                type="cap_team",
                label="承台模板",
                quantity=current_resources,
                max_quantity=max_resources,
            )
        ],
        milestones=[
            MilestoneConstraint(
                id="M-hard",
                name="强制完工目标",
                mode="hard",
                scope_type="project",
                target_event="finish",
                target_date=start + timedelta(days=target_days - 1),
            )
        ],
        schedule_strategy=ScheduleStrategyConfig(strategy="comprehensive"),
        time_limit_seconds=5,
    )


def _resource_cost_parallel_input(
    *,
    task_count: int,
    max_resources: int,
    resource_type: str = "team",
    label: str = "钻机",
) -> ScheduleInput:
    start = date(2026, 1, 1)
    return ScheduleInput(
        project_name="资源成本测试",
        start_date=start,
        tasks=[
            _cost_task(f"T{index}", f"任务{index}", 5, resource_type)
            for index in range(1, task_count + 1)
        ],
        precedence_links=[],
        resources=_resource_instances("pool-team", resource_type, label, max_resources),
        time_limit_seconds=5,
    )


def _cost_task(
    task_id: str,
    name: str,
    duration_days: int,
    resource_type: str,
    *,
    component_type: str = "pile",
) -> Task:
    return Task(
        id=task_id,
        name=name,
        structure_id=f"S-{task_id}",
        structure_name=name,
        structure_type="pier",
        component_type=component_type,
        process_name="施工",
        productivity_rule_id="rule",
        quantity=1,
        quantity_label="1个",
        duration_days=duration_days,
        compatible_resource_types=[resource_type],
    )


def _resource_instances(pool_id: str, resource_type: str, label: str, count: int) -> list[Resource]:
    return [
        Resource(
            id=f"{resource_type}_{index}",
            name=f"{label}{index}",
            type=resource_type,
            pool_id=pool_id,
            pool_label=label,
        )
        for index in range(1, count + 1)
    ]


def _soft_finish_milestone(start: date, *, target_offset: int, penalty_per_day: int) -> MilestoneConstraint:
    return MilestoneConstraint(
        id="M-soft",
        name="关键节点",
        mode="soft",
        scope_type="project",
        target_event="finish",
        target_date=start + timedelta(days=target_offset - 1),
        penalty_per_day=penalty_per_day,
    )


def _linear_cost(
    pool_id: str,
    label: str,
    *,
    current: int,
    max_quantity: int,
    unit_cost: int,
    cost_type: str = "one_time_purchase",
    billing_period_days: int = 30,
) -> dict[str, object]:
    return {
        "resource_pool_id": pool_id,
        "label": label,
        "resource_type": "team",
        "current_quantity": current,
        "max_quantity": max_quantity,
        "cost_type": cost_type,
        "incremental_unit_cost": unit_cost,
        "billing_period_days": billing_period_days,
    }


def _selected_resource_cost(result, pool_id: str) -> dict[str, object]:
    resources = result.objective_breakdown["selected_resource_costs"]
    return next(resource for resource in resources if resource["resource_pool_id"] == pool_id)
