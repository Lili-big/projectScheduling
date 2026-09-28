import sys
import pytest
from datetime import date
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from test_pavement_generation import sample_scenario, relation_rule, shared_fleet_scenario
from app.contracts import PavementFixedSequence, MilestoneConstraint
from app.scheduling.application.pavement import solve_pavement_scenario
from app.scheduling.generation.pavement import generate_pavement_input
from app.scheduling.solver.strategies.pavement import solve_pavement_schedule


def solve(scenario):
    response = solve_pavement_scenario(scenario)
    assert response.result.status in {"OPTIMAL", "FEASIBLE"}, response.diagnostics
    return response.result


@pytest.mark.parametrize("quantity,transfer,expected", [(1,0,2),(2,0,1),(1,1,3)])
def test_shared_fleet_cross_process_capacity_and_transfer(quantity, transfer, expected):
    result = solve(shared_fleet_scenario(quantity, transfer))
    assert result.objective_days == expected
    assert [t.duration_days for t in result.tasks] == [1,1]
    ids = {t.assigned_resource_id for t in result.tasks}
    assert len(ids) == quantity
    if quantity == 1:
        first, second = sorted(result.tasks, key=lambda t: t.start_offset)
        assert second.start_offset >= first.end_offset + transfer
    assert len(result.pavement_summary.transfers) == (1 if transfer else 0)


def test_shared_same_position_switch_has_no_transfer():
    s = sample_scenario((100,), ("granular_base", "cement_stabilized_base"))
    s.resource_pools = shared_fleet_scenario(1, 3).resource_pools
    for condition in s.pavement_settings.layer_conditions: condition.wait_days = 0
    r = solve(s)
    assert r.objective_days == 2
    assert len({t.assigned_resource_id for t in r.tasks}) == 1
    assert not r.pavement_summary.transfers


def test_shared_fleet_can_do_gravel_during_water_cure():
    s = shared_fleet_scenario()
    water = s.project.bridges[0].work_sections[1].structures[0].components[0]
    gravel = s.project.bridges[0].work_sections[0].structures[0].components[0]
    s.pavement_settings.layer_conditions[1].wait_days = 7
    second = water.model_copy(deep=True, update={"id": "B-2", "name": "上层水稳"})
    second.properties["layer_order"] = 2
    s.project.bridges[0].work_sections[1].structures[0].components.append(second)
    gravel.properties["roadbed_available_date"] = "2026-01-02"
    r = solve(s)
    w = next(t for t in r.tasks if t.component_id == water.id)
    g = next(t for t in r.tasks if t.component_id == gravel.id)
    assert w.end_offset <= g.start_offset < w.end_offset + 7
    assert r.objective_days == 9


def test_dedicated_and_shared_fleets_coexist_and_direct_legacy_stays_dedicated():
    s = shared_fleet_scenario()
    s.resource_pools[0].quantity = 1
    s.resource_pools[0].transfer_days = 0
    r = solve(s)
    assert r.objective_days == 1
    assert len({t.assigned_resource_id for t in r.tasks}) == 2
    old = generate_pavement_input(sample_scenario((100,))).schedule_input
    for resource in old.resources: resource.compatible_process_ids = None
    for task in old.tasks: task.pavement_context.process_id = None
    assert solve_pavement_schedule(old).status in {"OPTIMAL", "FEASIBLE"}
    s = shared_fleet_scenario()
    s.resource_pools[1].compatible_process_ids = ["pavement-cement_stabilized_base"]
    assert solve_pavement_scenario(s).result.status == "MODEL_INVALID"


def test_cure_can_overlap_next_section_and_return_transfer_uses_actual_path():
    s = sample_scenario((760,410), ("cement_stabilized_base","cement_stabilized_base"))
    s.pavement_settings.fixed_sequences=[PavementFixedSequence(process_type="cement_stabilized_base",component_ids=["A-1","B-1","A-2","B-2"])]
    result=solve(s); tasks={t.component_id:t for t in result.tasks}
    assert tasks["A-1"].start_offset == 0
    assert tasks["A-1"].end_offset == 2
    assert tasks["B-1"].start_offset == 3
    assert tasks["A-2"].start_offset >= 9
    assert tasks["B-2"].start_offset >= 11
    assert len(result.pavement_summary.transfers)==3
    assert tasks["B-1"].start_offset < tasks["A-1"].end_offset+7
    for transfer in result.pavement_summary.transfers:
        first=next(t for t in result.tasks if t.id==transfer.from_task_id)
        following=next(t for t in result.tasks if t.id==transfer.to_task_id)
        assert transfer.start_offset==first.end_offset
        assert transfer.end_offset <= following.start_offset
        assert transfer.resource_id==first.assigned_resource_id==following.assigned_resource_id


def test_three_sections_transfer_only_two_adjacent_arcs():
    s=sample_scenario((700,700,700))
    s.pavement_settings.fixed_sequences=[PavementFixedSequence(process_type="cement_stabilized_base",component_ids=["A-1","B-1","C-1"])]
    result=solve(s)
    assert result.objective_days==5  # 3 work + 2 transfers; no terminal cure
    assert len(result.pavement_summary.transfers)==2
    assert [(t.start_offset,t.end_offset) for t in result.tasks]==[(0,1),(2,3),(4,5)]


def test_same_position_has_no_transfer_and_two_crews_do_not_halve_task():
    s=sample_scenario((760,), ("cement_stabilized_base","cement_stabilized_base"))
    result=solve(s)
    assert result.pavement_summary.transfers==[]
    assert result.objective_days==11
    s=sample_scenario((760,760))
    pool=next(p for p in s.resource_pools if p.type=="water_stable_paving_crew")
    one=solve(s)
    pool.quantity=2
    two=solve(s)
    assert two.objective_days==2 < one.objective_days
    assert [t.duration_days for t in two.tasks]==[2,2]
    pool.quantity=0
    blocked=solve_pavement_scenario(s)
    assert blocked.result.status=="MODEL_INVALID"
    assert "PAVEMENT_RESOURCE_MISSING" in {d.code for d in blocked.diagnostics}


def test_far_handover_and_last_layer_acceptance_horizon():
    s=sample_scenario((700,))
    s.project.bridges[0].work_sections[0].structures[0].components[0].properties["roadbed_available_date"]="2028-01-05"
    s.pavement_settings.layer_conditions[0].accepted_available_date=date(2028,2,1)
    r=solve(s)
    assert r.tasks[0].start_date >= date(2028,1,5)
    assert r.plan_finish_date==date(2028,1,5)
    assert r.stats["horizon"]>r.objective_days


def test_final_cure_and_asphalt_zero_wait_date_boundary():
    s=sample_scenario((700,))
    s.project.bridges[0].work_sections[0].structures[0].components[0].properties["roadbed_available_date"]="2026-01-20"
    s.pavement_settings.layer_conditions[0].accepted_available_date=date(2026,1,28)
    r=solve(s)
    assert r.plan_finish_date==date(2026,1,20)
    s=sample_scenario((700,), ("asphalt_course",))
    r=solve(s)
    assert r.objective_days==1
    assert r.tasks[0].finish_date==date(2026,1,1)
    assert r.pavement_summary.ready_date==date(2026,1,2)
    assert r.pavement_summary.wait_intervals==[]


def test_hard_target_not_relaxed_and_timeout_not_infeasible():
    s=sample_scenario((700,))
    s.milestones=[MilestoneConstraint(id="target",name="施工完成",mode="hard",target_date=date(2025,12,31))]
    assert solve_pavement_scenario(s).result.status=="INFEASIBLE"
    s.milestones=[]
    schedule=generate_pavement_input(s).schedule_input
    schedule.time_limit_seconds=0.000001
    timed=solve_pavement_schedule(schedule)
    assert timed.status=="UNKNOWN"
    assert timed.stats["hard_constraints_relaxed"] is False


def test_direct_schedule_cannot_omit_resources_or_layer_logic():
    s=sample_scenario((700,), ("cement_stabilized_base","asphalt_course"))
    schedule=generate_pavement_input(s).schedule_input
    for field,value in [("resources",[]),("precedence_links",[])]:
        invalid=schedule.model_copy(deep=True,update={field:value})
        assert solve_pavement_schedule(invalid).status=="MODEL_INVALID"


@pytest.mark.parametrize("relationship,expected_ready", [("FS", 9), ("SS", 5), ("FF", 6), ("SF", 4)])
def test_four_relationships_have_real_effect_without_residual_fs_or_old_cure(relationship, expected_ready):
    s = sample_scenario((2800,), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.dependency_rules = [relation_rule(relationship=relationship, lag_days=2)]
    r = solve(s)
    first = next(t for t in r.tasks if t.component_id == "A-1")
    second = next(t for t in r.tasks if t.component_id == "A-2")
    assert first.duration_days == 4 and second.duration_days == 3
    lhs = second.start_offset if relationship[1] == "S" else second.end_offset
    rhs = first.start_offset if relationship[0] == "S" else first.end_offset
    assert lhs >= rhs + 2
    assert r.objective_days == expected_ready
    if relationship != "FS":
        assert second.start_offset < first.end_offset
        assert first.properties["wait_days"] == 0
    assert s.pavement_settings.layer_conditions[0].wait_days == 7


def test_custom_relation_keeps_calendar_boundaries_and_cycles_blocked():
    s = sample_scenario((2800,), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.dependency_rules = [relation_rule(relationship="SS", lag_days=0)]
    s.pavement_settings.layer_conditions[0].accepted_available_date = date(2026, 1, 10)
    r = solve(s)
    assert next(t for t in r.tasks if t.component_id == "A-2").start_offset >= 9
    schedule = generate_pavement_input(s).schedule_input
    edge = schedule.precedence_links[0]
    schedule.precedence_links.append(edge.model_copy(update={"id": "cycle", "predecessor_id": edge.successor_id, "successor_id": edge.predecessor_id}))
    assert solve_pavement_schedule(schedule).status == "MODEL_INVALID"


def test_chain_only_waits_ignore_terminal_history_and_do_not_double_count():
    s = sample_scenario((700,), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.dependency_rules = [relation_rule(lag_days=5)]
    s.pavement_settings.layer_conditions[-1].wait_days = 70
    s.pavement_settings.layer_conditions[-1].accepted_available_date = date(2030, 1, 1)
    before = s.model_dump()
    r = solve(s)
    assert r.objective_days == 7
    assert r.plan_finish_date == date(2026, 1, 7)
    assert not r.pavement_summary.readiness
    assert len(r.pavement_summary.wait_intervals) == 1
    assert r.pavement_summary.wait_intervals[0].end_offset - r.pavement_summary.wait_intervals[0].start_offset == 5
    assert s.model_dump() == before
    s.pavement_settings.layer_conditions = []
    assert solve(s).objective_days == 7


def test_single_layer_without_condition_and_terminal_finish_milestone():
    s = sample_scenario((700,))
    s.pavement_settings.layer_conditions = []
    s.milestones = [MilestoneConstraint(id="finish", name="施工完成", mode="hard", target_date=date(2026, 1, 1))]
    r = solve(s)
    assert r.plan_finish_date == r.tasks[0].finish_date == date(2026, 1, 1)
    assert r.milestone_results[0].actual_date == date(2026, 1, 1)


def test_direct_legacy_terminal_conditions_require_regeneration():
    from app.contracts.pavement import PavementReadinessCondition
    schedule = generate_pavement_input(sample_scenario((100,))).schedule_input
    task = schedule.tasks[0]
    schedule.readiness_conditions = [PavementReadinessCondition(id="old", terminal_task_id=task.id, source_component_id=task.component_id, wait_days=7)]
    r = solve_pavement_schedule(schedule)
    assert r.status == "MODEL_INVALID"
    assert any("重新生成" in d.message for d in r.validation)
    schedule.readiness_conditions = []
    task.properties["wait_days"] = 7
    assert solve_pavement_schedule(schedule).status == "MODEL_INVALID"
def test_handover_boundaries_apply_to_all_tasks_and_direct_solve():
    from datetime import date
    from test_pavement_generation import handover_scenario
    from app.contracts.pavement import PavementAncillaryStep, PavementDependencyRule
    from app.project_master.validation import roadbed_start_offset
    s = handover_scenario()
    s.pavement_settings.ancillary_steps = [PavementAncillaryStep(id="prep", structure_id="A", before_component_id="A-1", kind="other_preparation", name="清扫", duration_days=1, wait_after_days=0, order=1, basis_note="测试")]
    for relationship in ["SS", "SF"]:
        s.pavement_settings.dependency_rules = [PavementDependencyRule(predecessor_key="layer:granular_base:1", successor_key="layer:cement_stabilized_base:1", relationship=relationship, lag_days=0)]
        for start, lower in [(date(2026, 9, 23), 32), (date(2026, 10, 1), 24)]:
            s.project.start_date = start
            generated = generate_pavement_input(s)
            assert not [v for v in generated.validation if v.level == "error"]
            schedule = generated.schedule_input
            assert all(c.earliest_start_offset >= lower for c in schedule.execution_constraints if c.task_id in {t.id for t in schedule.tasks if t.structure_id == "A"})
            schedule.execution_constraints = []
            result = solve_pavement_schedule(schedule)
            assert result.status in {"OPTIMAL", "FEASIBLE"}, result.validation
            assert all(t.start_offset >= roadbed_start_offset(t.properties, start, allow_pending=True) for t in result.tasks)
            assert all(t.start_offset >= lower for t in result.tasks if t.structure_id == "A")
            assert_pending_last_per_fleet(result)
            assert result.stats["pavement_handover"]["included_section_count"] == 4
    task = schedule.tasks[0]
    task.properties.update(roadbed_handover_status="pending", roadbed_available_date=None)
    invalid = solve_pavement_schedule(schedule)
    assert "PAVEMENT_ROADBED_INVALID" in {v.code for v in invalid.validation}


def pending_last_scenario():
    s = sample_scenario((1400, 1400))
    s.project.start_date = date(2026, 9, 23)
    c = s.project.bridges[0].work_sections[1].structures[0].components[0]
    c.properties.update(roadbed_handover_status="pending", roadbed_available_date=None, roadbed_handover_note="征地待解决")
    return s


def fleet_pending_scenario():
    """R1 can enter pending B while R2 still has normal asphalt A to finish."""
    s = sample_scenario((100, 100), ("cement_stabilized_base", "asphalt_course"))
    s.project.start_date = date(2027, 4, 20)
    pending = s.project.bridges[0].work_sections[1].structures[0]
    pending.components = pending.components[:1]
    pending.components[0].component_type = "granular_base"
    pending.components[0].properties.update(roadbed_handover_status="pending", roadbed_available_date=None)
    s.pavement_settings.layer_conditions = [c for c in s.pavement_settings.layer_conditions if c.component_id != "B-2"]
    s.resource_pools[0].quantity = 0
    s.resource_pools[1].compatible_process_ids = ["pavement-granular_base", "pavement-cement_stabilized_base"]
    return s


def assert_pending_last_per_fleet(result):
    for rid in {t.assigned_resource_id for t in result.tasks if t.assigned_resource_id}:
        route = sorted((t for t in result.tasks if t.assigned_resource_id == rid), key=lambda t: t.start_offset)
        seen_pending = False
        for task in route:
            pending = task.properties.get("roadbed_handover_status") == "pending"
            assert not (seen_pending and not pending), rid
            seen_pending |= pending


def test_pending_fleet_does_not_wait_for_another_fleets_normal_asphalt():
    from app.contracts import TaskExecutionConstraint
    s = generate_pavement_input(fleet_pending_scenario()).schedule_input
    before = s.model_dump()
    pending = next(t for t in s.tasks if t.structure_id == "B")
    next(c for c in s.execution_constraints if c.task_id == pending.id).fixed_start_offset = 2
    r = solve_pavement_schedule(s)
    assert r.status == "OPTIMAL", r.validation
    tasks = {t.component_id: t for t in r.tasks}
    assert tasks["B-1"].start_date == date(2027, 4, 22)
    assert tasks["A-2"].start_date == date(2027, 4, 28)
    assert tasks["A-1"].assigned_resource_id == tasks["B-1"].assigned_resource_id
    assert tasks["A-2"].assigned_resource_id != tasks["B-1"].assigned_resource_id
    assert r.objective_days == 9
    assert_pending_last_per_fleet(r)
    assert s.model_dump(exclude={"execution_constraints"}) == {k:v for k,v in before.items() if k != "execution_constraints"}


def test_pending_order_is_per_instance_even_for_identical_fleets():
    from app.contracts import TaskExecutionConstraint
    scenario = pending_last_scenario()
    for pool in scenario.resource_pools: pool.quantity = 2
    s = generate_pavement_input(scenario).schedule_input
    normal, pending = s.tasks
    water = [r for r in s.resources if "pavement-cement_stabilized_base" in (r.compatible_process_ids or [])]
    s.execution_constraints = [TaskExecutionConstraint(task_id=normal.id, fixed_start_offset=5, fixed_resource_id=water[0].id),
                              TaskExecutionConstraint(task_id=pending.id, fixed_start_offset=0, fixed_resource_id=water[1].id)]
    r = solve_pavement_schedule(s)
    assert r.status in {"OPTIMAL", "FEASIBLE"}, r.validation
    assert_pending_last_per_fleet(r)
    s.execution_constraints[1].fixed_resource_id = water[0].id
    assert solve_pavement_schedule(s).status == "INFEASIBLE"


@pytest.mark.parametrize("fleets", [1, 2])
def test_pending_order_keeps_curing_and_unresourced_preparation(fleets):
    from app.contracts.pavement import PavementAncillaryStep
    s = sample_scenario((100, 100), ("cement_stabilized_base",) * 2)
    for c in s.project.bridges[0].work_sections[1].structures[0].components:
        c.properties.update(roadbed_handover_status="pending", roadbed_available_date=None)
    for pool in s.resource_pools: pool.quantity = fleets
    s.pavement_settings.ancillary_steps = [PavementAncillaryStep(id=sid, structure_id=sid,
        before_component_id=f"{sid}-1", kind="other_preparation", name="清扫", duration_days=2,
        wait_after_days=0, order=1, basis_note="测试") for sid in ("A", "B")]
    before = s.model_dump()
    result = solve(s)
    normal = [t for t in result.tasks if t.structure_id == "A"]
    pending = [t for t in result.tasks if t.structure_id == "B"]
    assert len(normal) == len(pending) == 3
    assert_pending_last_per_fleet(result)
    for group in (normal, pending):
        preparation = next(t for t in group if t.pavement_context.task_kind == "preparation")
        core = sorted((t for t in group if t.pavement_context.task_kind == "construction"), key=lambda t: t.sequence_order)
        assert preparation.assigned_resource_id is None
        assert core[0].start_offset >= preparation.end_offset
        assert core[1].start_offset >= core[0].end_offset + 7
    if fleets == 1:
        assert min(t.start_offset for t in pending if t.assigned_resource_id) >= max(t.end_offset for t in normal)
    assert s.model_dump() == before


def test_pending_direct_input_scope_and_fixed_sequence_conflicts():
    from app.contracts.pavement import PavementHandoverScope, PavementBlockedSection
    s = pending_last_scenario()
    schedule = generate_pavement_input(s).schedule_input
    schedule.pavement_handover_scope = None
    r = solve_pavement_schedule(schedule)
    assert r.status in {"OPTIMAL", "FEASIBLE"}
    assert {t.structure_id: t.start_offset for t in r.tasks}["B"] == 3
    assert r.stats["pavement_handover"]["pending_policy"] == "per_fleet_last"
    old = generate_pavement_input(s).schedule_input
    old.pavement_handover_scope.pending_policy = "strict_last"
    invalid = solve_pavement_schedule(old)
    assert invalid.status == "MODEL_INVALID"
    assert "PAVEMENT_INPUT_OUTDATED" in {v.code for v in invalid.validation}
    bad = generate_pavement_input(s).schedule_input
    bad.pavement_handover_scope.pending_sections = []
    assert solve_pavement_schedule(bad).status == "MODEL_INVALID"
    bad.pavement_handover_scope = PavementHandoverScope(total_section_count=2, included_section_count=1,
        included_layer_count=1, blocked_sections=[PavementBlockedSection(structure_id="B", section_name="B", reason="待定")])
    bad.tasks = [t for t in bad.tasks if t.structure_id == "A"]
    assert any(v.code == "PAVEMENT_INPUT_OUTDATED" for v in solve_pavement_schedule(bad).validation)
    s.pavement_settings.fixed_sequences = [PavementFixedSequence(process_type="cement_stabilized_base", component_ids=["B-1", "A-1"])]
    assert solve_pavement_scenario(s).result.status == "INFEASIBLE"


def test_pending_dates_use_first_task_and_inclusive_finish_without_mutating_facts():
    from app.contracts.pavement import PavementAncillaryStep
    from app.contracts import ScheduleResult
    s = pending_last_scenario()
    before = s.model_dump()
    r = solve(s)
    by_id = {t.structure_id: t for t in r.tasks}
    assert (by_id["A"].start_date, by_id["A"].finish_date) == (date(2026, 9, 23), date(2026, 9, 24))
    dates = r.pavement_summary.pending_section_dates
    assert dates[0].required_handover_date == date(2026, 9, 26)
    assert dates[0].estimated_finish_date == date(2026, 9, 27)
    assert ScheduleResult.model_validate_json(r.model_dump_json()).pavement_summary.pending_section_dates == dates
    assert s.model_dump() == before
    s.pavement_settings.ancillary_steps = [PavementAncillaryStep(id="prep", structure_id="B",
        before_component_id="B-1", kind="other_preparation", name="清扫", duration_days=2,
        wait_after_days=0, order=1, basis_note="测试")]
    r = solve(s)
    tasks = [t for t in r.tasks if t.structure_id == "B"]
    dates = r.pavement_summary.pending_section_dates[0]
    assert dates.required_handover_date == min(t.start_date for t in tasks)
    assert dates.estimated_finish_date == max(t.finish_date for t in tasks)
    assert next(t for t in tasks if t.pavement_context.task_kind == "construction").start_date > dates.required_handover_date
    schedule = generate_pavement_input(s).schedule_input
    schedule.time_limit_seconds = 0.000001
    failed = solve_pavement_schedule(schedule)
    assert failed.status == "UNKNOWN" and failed.pavement_summary is None
    assert len(failed.stats["pavement_handover"]["pending_sections"]) == 1
    schedule.resources = []
    failed = solve_pavement_schedule(schedule)
    assert failed.status == "MODEL_INVALID" and failed.pavement_summary is None
    s.pavement_settings.fixed_sequences = []
    s.milestones = [MilestoneConstraint(id="finish", name="完工", mode="hard", target_date=date(2026, 9, 25))]
    assert solve_pavement_scenario(s).result.status == "INFEASIBLE"
