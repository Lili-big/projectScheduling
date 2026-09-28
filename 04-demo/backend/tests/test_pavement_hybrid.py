"""Independent numeric validation and hybrid selection acceptance for 068."""
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from time import perf_counter

import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from test_pavement_generation import sample_scenario, shared_fleet_scenario, handover_scenario
from app.contracts import MilestoneConstraint, PavementAncillaryStep, PavementFixedSequence
from app.scheduling.generation.pavement import generate_pavement_input
from app.scheduling.solver.strategies import pavement as hybrid
from app.scheduling.solver.strategies.pavement_heuristic import (
    Candidate, STRATEGIES, construct_candidate, generate_initial_candidates, validate_candidate,
)


def prepared(scenario=None):
    schedule = generate_pavement_input(scenario or shared_fleet_scenario()).schedule_input
    errors, resources = hybrid.validate_pavement_schedule(schedule)
    assert not errors, errors
    return schedule, resources


def build(schedule, resources, strategy="earliest_start"):
    candidate = construct_candidate(schedule, resources, strategy, perf_counter() + 5)
    assert candidate is not None
    assert not validate_candidate(schedule, resources, candidate)
    return candidate


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("quantity,transfer", [(1, 0), (1, 2), (2, 1)])
def test_deterministic_shared_candidates(strategy, quantity, transfer):
    s, r = prepared(shared_fleet_scenario(quantity, transfer))
    assert build(s, r, strategy) == build(s, r, strategy)


def test_100_tasks_all_strategies_and_budget():
    scenario = sample_scenario((1790,) * 25, ("granular_base",) + ("cement_stabilized_base",) * 3)
    scenario.resource_pools = shared_fleet_scenario(1, 1).resource_pools
    s, r = prepared(scenario)
    candidates = generate_initial_candidates(s, r, perf_counter() + 1)
    assert len(candidates) == 3 and all(len(c.starts) == 100 for c in candidates)
    assert all(not validate_candidate(s, r, c) for c in candidates)
    assert generate_initial_candidates(s, r, perf_counter() - 1) == []


@pytest.mark.parametrize("all_pending", [False, True])
def test_handover_preparation_fixed_order_and_dedicated_fleets(all_pending):
    scenario = handover_scenario()
    if all_pending:
        for section in scenario.project.bridges[0].work_sections:
            for component in section.structures[0].components:
                component.properties.update(roadbed_handover_status="pending", roadbed_available_date=None)
    scenario.pavement_settings.ancillary_steps = [PavementAncillaryStep(id="prep", structure_id="C",
        before_component_id="C-1", kind="other_preparation", name="准备", duration_days=2,
        wait_after_days=1, order=1, basis_note="测试")]
    scenario.pavement_settings.fixed_sequences = [PavementFixedSequence(process_type="granular_base", component_ids=["B-1", "D-1"])]
    s, r = prepared(scenario)
    c = build(s, r)
    preparation = next(t for t in s.tasks if t.pavement_context.task_kind == "preparation")
    assert preparation.id not in c.assignments
    if not all_pending:
        for route in c.routes.values():
            pending_indices = [i for i, tid in enumerate(route) if next(t for t in s.tasks if t.id == tid).structure_id == "C"]
            if pending_indices:
                assert pending_indices == list(range(min(pending_indices), len(route)))
    else:
        assert min(c.starts.values()) == 0


@pytest.mark.parametrize("relationship,expected", [("FS", 12), ("SS", 8), ("FF", 9), ("SF", 5)])
def test_four_relationships_do_not_impose_global_dispatch_time(relationship, expected):
    s, r = prepared(sample_scenario((100,), ("granular_base", "cement_stabilized_base")))
    a, b = s.tasks
    a.duration_days, b.duration_days = 4, 3
    a.properties.update(wait_days=0, accepted_available_offset=0)
    link = s.precedence_links[0]
    link.relationship, link.lag_days = relationship, 1
    from app.contracts import TaskExecutionConstraint
    s.execution_constraints = [TaskExecutionConstraint(task_id=a.id, fixed_start_offset=7, fixed_resource_id=r[a.id][0].id)]
    c = build(s, r)
    assert c.starts[b.id] == expected


@pytest.mark.parametrize("mutation", ["missing", "duration", "negative", "fraction", "resource", "route", "overlap", "transfer", "makespan"])
def test_numeric_validator_rejects_corrupted_candidates(mutation):
    s, r = prepared(shared_fleet_scenario(1, 2))
    c = deepcopy(build(s, r)); a, b = sorted(c.starts, key=c.starts.get)
    if mutation == "missing": c.starts.pop(a)
    elif mutation == "duration": c.ends[a] += 1
    elif mutation == "negative": c.starts[a] = -1
    elif mutation == "fraction": c.starts[a] = .5
    elif mutation == "resource": c.assignments[a] = "unknown"
    elif mutation == "route": next(iter(c.routes.values())).pop()
    elif mutation in {"overlap", "transfer"}:
        c.starts[b] = c.ends[a] - (1 if mutation == "overlap" else 0)
        c.ends[b] = c.starts[b] + 1; c.makespan = max(c.ends.values())
    elif mutation == "makespan": c.makespan += 1
    assert validate_candidate(s, r, c)


def test_numeric_validator_checks_dates_fixed_constraints_links_and_milestones():
    from app.contracts import TaskExecutionConstraint
    s, r = prepared(sample_scenario((100,), ("granular_base", "cement_stabilized_base")))
    c = build(s, r); a, b = s.tasks
    s.execution_constraints = [TaskExecutionConstraint(task_id=a.id, earliest_start_offset=3)]
    assert validate_candidate(s, r, c)
    s.execution_constraints = [TaskExecutionConstraint(task_id=a.id, fixed_start_offset=2)]
    assert validate_candidate(s, r, c)
    s.execution_constraints = [TaskExecutionConstraint(task_id=a.id, fixed_resource_id="other")]
    assert validate_candidate(s, r, c)
    s.execution_constraints = []
    s.precedence_links[0].lag_days += 10
    assert validate_candidate(s, r, c)
    s.precedence_links[0].lag_days -= 10
    a.properties["accepted_available_offset"] = 10
    assert validate_candidate(s, r, c)
    a.properties["accepted_available_offset"] = 0
    a.properties["roadbed_available_date"] = "2026-02-01"
    assert validate_candidate(s, r, c)
    a.properties["roadbed_available_date"] = "2026-01-01"
    s.milestones = [MilestoneConstraint(id="m", name="finish", mode="hard", target_date=date(2025, 12, 31))]
    assert validate_candidate(s, r, c)
    assert construct_candidate(s, r, "earliest_start", perf_counter() + 1) is None


def seed_case():
    scenario = sample_scenario((2100, 1400), ("cement_stabilized_base", "cement_stabilized_base"))
    scenario.project.bridges[0].work_sections[1].structures[0].components.pop()
    s, r = prepared(scenario)
    a, a2, b = s.tasks
    assert [t.duration_days for t in s.tasks] == [3, 3, 2]
    rid = r[a.id][0].id
    seed = Candidate(starts={b.id: 0, a.id: 3, a2.id: 13}, ends={b.id: 2, a.id: 6, a2.id: 16},
        assignments={t.id: rid for t in s.tasks}, routes={rid: [b.id, a.id, a2.id]}, makespan=16, strategy="earliest_start")
    assert not validate_candidate(s, r, seed)
    return s, r, seed


def test_shared_result_conversion_has_complete_summary():
    s, r = prepared(handover_scenario())
    c = build(s, r)
    stats = {"pavement_handover": hybrid._result_handover_scope(s).model_dump(mode="json")}
    result = hybrid.result_from_candidate(s, r, c, "FEASIBLE", stats)
    assert len(result.tasks) == len(s.tasks) == len(result.resource_allocations)
    assert result.objective_days == max(t.end_offset for t in result.tasks)
    assert result.pavement_summary.ready_offset == result.objective_days
    assert not result.pavement_summary.readiness
    pending = [t for t in result.tasks if t.structure_id == "C"]
    dates = result.pavement_summary.pending_section_dates[0]
    assert dates.required_handover_date == min(t.start_date for t in pending)
    assert dates.estimated_finish_date == max(t.finish_date for t in pending)
    assert result.plan_finish_date == max(t.finish_date for t in result.tasks)


def test_real_cp_sat_improves_seed_without_fixing_route(monkeypatch):
    s, r, seed = seed_case()
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [seed])
    result = hybrid.solve_pavement_schedule(s)
    assert result.status == "OPTIMAL" and result.objective_days == 13
    assert result.pavement_optimization.initial_days == 16
    assert result.pavement_optimization.improvement_days == 3
    assert result.pavement_optimization.outcome == "improved"
    assert result.tasks[0].component_id == "A-1"


@pytest.mark.parametrize("cpus,workers", [(1, 1), (4, 4), (28, 8), (None, 1)])
def test_parallel_parameters(monkeypatch, cpus, workers):
    monkeypatch.setattr(hybrid.os, "cpu_count", lambda: cpus)
    s, r, seed = seed_case()
    model, *_ = hybrid._build_model(s, r, seed, perf_counter() + 5)
    solver, _, _ = hybrid._optimize(model, 1)
    assert solver.parameters.num_search_workers == workers
    assert solver.parameters.use_lns and not solver.parameters.use_lns_only
    assert solver.parameters.random_seed == 0


def test_live_initial_then_improvements_and_immutable_snapshot(monkeypatch):
    s, _, seed = seed_case()
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [seed])
    events = []
    result = hybrid.solve_pavement_schedule(s, on_solution=lambda result: events.append(result))
    days = [r.objective_days for r in events]
    assert days[0] == 16 and days[-1] == result.objective_days == 13
    assert all(a > b for a, b in zip(days, days[1:]))
    assert all(r.status == "FEASIBLE" and r.pavement_optimization.optimizer_status is None for r in events)
    assert events[0].pavement_optimization.final_days == 16
    assert result.status == "OPTIMAL" and result.pavement_optimization.improvement_count == len(events) - 1


@pytest.mark.parametrize("limit", [float("inf"), float("nan"), 0, -1])
def test_invalid_budget_never_enters_optimizer(monkeypatch, limit):
    s, _ = prepared(); s = s.model_copy(update={"time_limit_seconds": limit})
    monkeypatch.setattr(hybrid, "_optimize", lambda *args: pytest.fail("must not solve"))
    with pytest.raises(ValueError, match="有限"):
        hybrid.solve_pavement_schedule(s)


@pytest.mark.parametrize("optimizer_status", ["UNKNOWN", "INFEASIBLE", "MODEL_INVALID"])
def test_controlled_optimizer_fallback_or_inconsistency(monkeypatch, optimizer_status):
    s, r, seed = seed_case()
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [seed])
    monkeypatch.setattr(hybrid, "_optimize", lambda *args: (None, optimizer_status, 0.0))
    result = hybrid.solve_pavement_schedule(s)
    meta = result.pavement_optimization
    assert meta.optimizer_status == optimizer_status
    if optimizer_status == "UNKNOWN":
        assert result.status == "FEASIBLE" and result.objective_days == 16
        assert meta.selected_source == "greedy" and meta.outcome == "initial_retained"
        assert len(result.tasks) == 3 and len(result.resource_allocations) == 3
        assert result.pavement_summary.transfers and result.pavement_summary.wait_intervals
        assert not result.validation
    else:
        assert result.status == "MODEL_INVALID" and not result.tasks
        assert meta.outcome == "inconsistent" and meta.final_days is None
        assert result.validation[0].code == "PAVEMENT_OPTIMIZER_INCONSISTENT"


@pytest.mark.parametrize("status", ["UNKNOWN", "INFEASIBLE", "MODEL_INVALID"])
def test_no_seed_preserves_optimizer_failure(monkeypatch, status):
    s, _ = prepared()
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [])
    monkeypatch.setattr(hybrid, "_optimize", lambda *args: (None, status, 0.0))
    result = hybrid.solve_pavement_schedule(s)
    assert result.status == status and not result.tasks
    assert result.pavement_optimization.initial_days is None
    assert result.pavement_optimization.outcome == "no_plan"


def test_real_cp_sat_cold_start_and_equal_optimum(monkeypatch):
    s, _ = prepared()
    equal = hybrid.solve_pavement_schedule(s)
    assert equal.status == "OPTIMAL" and equal.pavement_optimization.selected_source == "greedy"
    assert equal.pavement_optimization.improvement_days == 0
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [])
    result = hybrid.solve_pavement_schedule(s)
    assert result.status == "OPTIMAL" and result.pavement_optimization.outcome == "cp_sat_only"
    assert result.pavement_optimization.improvement_days is None


@pytest.mark.parametrize("with_seed", [True, False])
def test_budget_exhausted_during_model_never_calls_unlimited_solver(monkeypatch, with_seed):
    from app.scheduling.solver.strategies.pavement_heuristic import BudgetExpired
    s, _, seed = seed_case()
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [seed] if with_seed else [])
    def expired(*args): raise BudgetExpired
    monkeypatch.setattr(hybrid, "_build_model", expired)
    monkeypatch.setattr(hybrid, "_optimize", lambda *args: pytest.fail("must not solve"))
    result = hybrid.solve_pavement_schedule(s)
    assert result.status == ("FEASIBLE" if with_seed else "UNKNOWN")
    assert result.pavement_optimization.optimizer_status is None
    assert result.pavement_optimization.optimizer_not_run_reason == "budget_exhausted"


def test_bad_optimizer_numbers_are_not_hidden_by_fallback(monkeypatch):
    s, _, seed = seed_case()
    monkeypatch.setattr(hybrid, "generate_initial_candidates", lambda *args: [seed])
    original = hybrid._candidate_from_solver
    def bad(*args):
        candidate = original(*args)
        candidate.starts[next(iter(candidate.starts))] = -1
        return candidate
    monkeypatch.setattr(hybrid, "_candidate_from_solver", bad)
    result = hybrid.solve_pavement_schedule(s)
    assert result.status == "MODEL_INVALID"
    assert result.pavement_optimization.outcome == "inconsistent"


@pytest.mark.parametrize("relationship", ["FS", "SS", "FF", "SF"])
def test_only_proven_fs_reverse_edges_are_pruned(relationship):
    from app.scheduling.solver.constraints.pavement import forbidden_fleet_edges
    s, r, seed = seed_case()
    link = s.precedence_links[0]; link.relationship = relationship
    edges = forbidden_fleet_edges(s.tasks, s.precedence_links)
    assert ((link.successor_id, link.predecessor_id) in edges) == (relationship == "FS")
    h, _ = prepared(handover_scenario())
    edges = forbidden_fleet_edges(h.tasks, h.precedence_links)
    assert all((p.id, n.id) in edges for p in h.tasks if p.structure_id == "C" for n in h.tasks if n.structure_id != "C")


def test_build_deadline_checked_inside_arc_loop_and_hints_cover_model():
    from ortools.sat.python import cp_model
    from app.scheduling.solver.constraints.pavement import add_pavement_fleet_paths
    from app.scheduling.solver.strategies.pavement_heuristic import BudgetExpired
    s, r, seed = seed_case()
    model, *_ = hybrid._build_model(s, r, seed, perf_counter() + 5)
    assert not model.Validate()
    assert len(set(model.Proto().solution_hint.vars)) == len(model.Proto().variables)
    # Budget can expire within a fleet's quadratic arc loop, not only between phases.
    calls = 0
    def checkpoint():
        nonlocal calls
        calls += 1
        if calls == 12: raise BudgetExpired
    with pytest.raises(BudgetExpired):
        add_pavement_fleet_paths(cp_model.CpModel(), s.tasks, s.resources, r,
            {t.id: 0 for t in s.tasks}, {t.id: t.duration_days for t in s.tasks}, 100, s.precedence_links, checkpoint)
    assert calls == 12


def test_remaining_budget_and_greedy_interruption(monkeypatch):
    s, r, seed = seed_case()
    times = iter([0, 0, 0, 0, 0, 0, 2])
    from app.scheduling.solver.strategies.pavement_heuristic import construct_candidate
    assert construct_candidate(s, r, "earliest_start", 1, lambda: next(times, 2)) is None
    original = hybrid._optimize
    def measured(model, remaining, *args):
        assert 0 < remaining < s.time_limit_seconds
        return original(model, remaining, *args)
    monkeypatch.setattr(hybrid, "_optimize", measured)
    assert hybrid.solve_pavement_schedule(s).status == "OPTIMAL"


def test_pending_boundary_and_no_eligible_fleet_rejected():
    from test_pavement_solver import pending_last_scenario
    s, r = prepared(pending_last_scenario()); c = build(s, r)
    a, p = s.tasks
    rid = c.assignments[p.id]
    c.routes[rid] = [p.id, a.id]
    c.starts[p.id], c.ends[p.id] = 0, p.duration_days
    c.starts[a.id], c.ends[a.id] = p.duration_days + 1, p.duration_days + 1 + a.duration_days
    assert any(e.startswith("pending:") for e in validate_candidate(s, r, c))
    s, r = prepared(); r[s.tasks[0].id] = []
    assert generate_initial_candidates(s, r, perf_counter() + 1) == []


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_initial_pending_uses_actual_fleet_boundary(strategy):
    from test_pavement_solver import fleet_pending_scenario
    s, resources = prepared(fleet_pending_scenario())
    c = build(s, resources, strategy)
    tasks = {t.component_id: t for t in s.tasks}
    assert c.starts[tasks["B-1"].id] == 2
    assert c.starts[tasks["A-2"].id] == 8
    assert c.makespan == 9


def test_initial_can_dispatch_pending_to_an_idle_instance():
    from app.contracts import TaskExecutionConstraint
    from test_pavement_solver import pending_last_scenario
    scenario = pending_last_scenario()
    for pool in scenario.resource_pools: pool.quantity = 2
    s, resources = prepared(scenario)
    normal, pending = s.tasks
    s.execution_constraints = [TaskExecutionConstraint(task_id=normal.id, fixed_start_offset=5, fixed_resource_id=resources[normal.id][0].id),
                              TaskExecutionConstraint(task_id=pending.id, fixed_start_offset=0, fixed_resource_id=resources[pending.id][1].id)]
    c = build(s, resources)
    assert c.starts[pending.id] == 0 and c.starts[normal.id] == 5


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_cross_fleet_real_dependency_can_precede_a_normal_task(strategy):
    from app.contracts import PrecedenceLink
    s, resources = prepared(shared_fleet_scenario())
    normal, pending = s.tasks
    pending.properties.update(roadbed_handover_status="pending", roadbed_available_date=None)
    # Give each process its own actual resource; an explicit cross-fleet link is legal.
    original = resources[normal.id][0]
    other = original.model_copy(update={"id":"other", "name":"other"})
    s.resources.append(other)
    resources[pending.id] = [other]
    s.precedence_links.append(PrecedenceLink(id="cross", predecessor_id=pending.id, successor_id=normal.id, relationship="FS", lag_days=0, source_rule_id="test"))
    c = build(s, resources, strategy)
    assert c.starts[normal.id] >= c.ends[pending.id]
    assert c.assignments[normal.id] != c.assignments[pending.id]
    s.pavement_handover_scope = None
    from app.contracts import TaskExecutionConstraint
    s.execution_constraints = [TaskExecutionConstraint(task_id=normal.id, fixed_resource_id=original.id),
                              TaskExecutionConstraint(task_id=pending.id, fixed_resource_id=other.id)]
    solved = hybrid.solve_pavement_schedule(s)
    assert solved.status in {"OPTIMAL", "FEASIBLE"}, solved.validation
    by_id = {t.id:t for t in solved.tasks}
    assert by_id[normal.id].start_offset >= by_id[pending.id].end_offset


# 074: a second objective inside the already obtained makespan.
def idle_case(fixed=False, lag=0, transfer=0):
    from app.contracts import TaskExecutionConstraint, PrecedenceLink
    scenario = sample_scenario((1400, 1400, 7000), ("granular_base",))
    scenario.resource_pools = shared_fleet_scenario(2, transfer).resource_pools
    s, r = prepared(scenario)
    a, b, c = s.tasks
    for t, duration in zip(s.tasks, (2, 2, 10)):
        t.duration_days = duration
    r1, r2 = [x.id for x in s.resources]
    s.execution_constraints = [TaskExecutionConstraint(task_id=t.id, fixed_resource_id=rid, fixed_start_offset=start)
        for t, rid, start in [(a,r1,0 if fixed else None),(b,r1,6),(c,r2,0)]]
    s.precedence_links = [PrecedenceLink(id="test-order", predecessor_id=a.id, successor_id=b.id,
        relationship="FS", lag_days=lag, source_rule_id="test")]
    seed = Candidate(starts={a.id:0,b.id:6,c.id:0},ends={a.id:2,b.id:8,c.id:10},
        assignments={a.id:r1,b.id:r1,c.id:r2},routes={r1:[a.id,b.id],r2:[c.id]},makespan=10)
    assert not validate_candidate(s,r,seed)
    baseline = hybrid.result_from_candidate(s,r,seed,"FEASIBLE",{"pavement_handover":hybrid._result_handover_scope(s).model_dump(mode="json")})
    return s,r,seed,baseline


@pytest.mark.parametrize("fixed,lag,transfer,expected", [(False,0,0,0),(True,0,0,4),(False,4,0,4),(True,0,1,3)])
def test_idle_optimization_respects_cap_dates_waits_and_actual_transfer(fixed,lag,transfer,expected):
    s,r,seed,baseline=idle_case(fixed,lag,transfer)
    before=baseline.model_dump_json(); events=[]
    result=hybrid.solve_pavement_idle(s,baseline,on_solution=events.append)
    meta=result.pavement_idle_optimization
    assert result.status=="OPTIMAL" and result.objective_days<=10
    assert meta.proved_optimal and meta.makespan_cap_days==10
    assert meta.baseline_idle_days==4-transfer and meta.final_idle_days==expected
    assert meta.final_transfer_days==transfer
    assert [e.pavement_idle_optimization.final_idle_days for e in events]==sorted(
        {e.pavement_idle_optimization.final_idle_days for e in events},reverse=True)
    assert all(e.status=="FEASIBLE" and not e.pavement_idle_optimization.proved_optimal for e in events)
    assert baseline.model_dump_json()==before
    hybrid.validate_idle_baseline(s,result)


def test_idle_zero_bound_and_budget_keep_valid_baseline(monkeypatch):
    s,r,seed,baseline=idle_case()
    result=hybrid.solve_pavement_idle(s,baseline)
    monkeypatch.setattr(hybrid,"_optimize",lambda *a,**kw: pytest.fail("No remaining search necessary"))
    zero=hybrid.solve_pavement_idle(s,result)
    assert zero.pavement_idle_optimization.optimizer_not_run_reason=="zero_idle"
    assert zero.pavement_idle_optimization.optimizer_status is None
    assert zero.pavement_idle_optimization.proved_optimal
    limited=hybrid.solve_pavement_idle(s,baseline,began=perf_counter()-s.time_limit_seconds-1)
    assert limited.pavement_idle_optimization.optimizer_not_run_reason=="budget_exhausted"
    assert limited.pavement_idle_optimization.final_idle_days==4
    assert limited.tasks==baseline.tasks


@pytest.mark.parametrize("mutation", ["task", "duplicate", "time", "duration", "resource", "date", "cap", "fingerprint"])
def test_idle_baseline_rejects_untrusted_result(mutation):
    s,r,seed,baseline=idle_case(); bad=baseline.model_copy(deep=True)
    if mutation=="task": bad.tasks.pop()
    elif mutation=="duplicate": bad.tasks.append(bad.tasks[0])
    elif mutation=="time": bad.tasks[0].end_offset+=1
    elif mutation=="duration": bad.tasks[0].duration_days+=1
    elif mutation=="resource": bad.tasks[0].assigned_resource_id="unknown"
    elif mutation=="date": bad.tasks[0].start_date=date(2030,1,1)
    elif mutation=="cap": bad.objective_days=11
    else: bad.pavement_summary.input_fingerprint="wrong"
    with pytest.raises(hybrid.IdleBaselineError): hybrid.validate_idle_baseline(s,bad)


def test_idle_metrics_empty_single_and_unresourced_tasks():
    from app.scheduling.solver.strategies.pavement_heuristic import idle_metrics
    s,r,seed,_=idle_case(transfer=1)
    seed.routes["unused"]=[]
    assert idle_metrics(s,seed)==(3,1)


def test_idle_inconsistent_solver_cannot_claim_completion(monkeypatch):
    s,r,seed,baseline=idle_case(); events=[]
    monkeypatch.setattr(hybrid,"_optimize",lambda *a,**kw:(None,"INFEASIBLE",0))
    with pytest.raises(hybrid.HintInconsistent): hybrid.solve_pavement_idle(s,baseline,on_solution=events.append)
    assert len(events)==1 and events[0].tasks==baseline.tasks


def test_idle_incumbent_comparison_does_not_tighten_original_cap(monkeypatch):
    from types import SimpleNamespace
    s,r,seed,_=idle_case()
    a,b,c=s.tasks; c.duration_days=8
    s.execution_constraints[-1].fixed_start_offset=None
    seed.starts[c.id]=2
    baseline=hybrid.result_from_candidate(s,r,seed,"FEASIBLE",{"pavement_handover":hybrid._result_handover_scope(s).model_dump(mode="json")})
    intermediate=deepcopy(seed); intermediate.starts[a.id]=2;intermediate.ends[a.id]=4
    intermediate.starts[c.id]=0;intermediate.ends[c.id]=8;intermediate.makespan=8
    better=deepcopy(seed);better.starts[a.id]=4;better.ends[a.id]=6
    monkeypatch.setattr(hybrid,"_candidate_from_solver",lambda solver,*a:solver.candidate)
    def optimize(model,remaining,callback,control):
        for candidate,idle in [(intermediate,2),(better,0),(better,0)]:
            value=SimpleNamespace(candidate=candidate,WallTime=lambda:0.01,ObjectiveValue=lambda:idle)
            callback.accept(value)
        return value,"FEASIBLE",0.01
    monkeypatch.setattr(hybrid,"_optimize",optimize)
    events=[];result=hybrid.solve_pavement_idle(s,baseline,on_solution=events.append)
    assert [(e.objective_days,e.pavement_idle_optimization.final_idle_days) for e in events]==[(10,4),(8,2),(10,0)]
    assert result.objective_days==10 and result.pavement_idle_optimization.improvement_count==2
    assert not result.pavement_idle_optimization.proved_optimal


def test_idle_still_enforces_real_fleet_pending_order_and_supports_preparation():
    from test_pavement_solver import fleet_pending_scenario
    from app.scheduling.application.pavement import solve_pavement_scenario
    scenario=fleet_pending_scenario()
    baseline=solve_pavement_scenario(scenario)
    result=hybrid.solve_pavement_idle(baseline.generated.schedule_input,baseline.result)
    resources,candidate=hybrid.validate_idle_baseline(baseline.generated.schedule_input,result)
    assert not validate_candidate(baseline.generated.schedule_input,resources,candidate)
    assert result.objective_days<=baseline.result.objective_days
    scenario=handover_scenario()
    scenario.pavement_settings.ancillary_steps=[PavementAncillaryStep(id="prep",structure_id="C",before_component_id="C-1",kind="other_preparation",name="准备",duration_days=1,wait_after_days=0,order=1,basis_note="测试")]
    baseline=solve_pavement_scenario(scenario)
    result=hybrid.solve_pavement_idle(baseline.generated.schedule_input,baseline.result)
    assert any(t.assigned_resource_id is None for t in result.tasks)
    hybrid.validate_idle_baseline(baseline.generated.schedule_input,result)
