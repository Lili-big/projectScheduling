"""076 shift-regime contracts, duration function and solver integration."""
import sys
from datetime import date
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from test_pavement_generation import sample_scenario, shared_fleet_scenario
from app.contracts.pavement import PavementShiftRegime
from app.scheduling.domain.shift_regime import (
    shift_config_errors, shift_runs, shifts_for_day, split_shift_days, task_duration_for_start,
)
from app.scheduling.generation.pavement import generate_pavement_input
from app.scheduling.solver.strategies import pavement as hybrid
from app.scheduling.solver.strategies.pavement_heuristic import (
    construct_candidate, generate_initial_candidates, validate_candidate,
)


START = date(2026, 7, 1)


def work_task(quantity=8000, productivity=1000.0, duration_days=8):
    return SimpleNamespace(quantity=quantity, duration_days=duration_days,
                           properties={"productivity_value": productivity})


def sc001_regimes():
    return [PavementShiftRegime(start_date=date(2026, 7, 1), end_date=date(2026, 9, 30), shifts=1),
            PavementShiftRegime(start_date=date(2026, 10, 1), end_date=None, shifts=2)]


def shift_scenario(sections=("A", "B"), quantity=8000):
    """Two single-layer sections on one shared fleet crossing the 10-01 boundary."""
    scenario = sample_scenario((quantity, quantity), ("cement_stabilized_base",))
    scenario.project.start_date = date(2026, 9, 25)
    scenario.pavement_settings.shift_regimes = [
        PavementShiftRegime(start_date=date(2026, 10, 1), end_date=None, shifts=2)]
    generated = generate_pavement_input(scenario)
    schedule = generated.schedule_input
    for task in schedule.tasks:
        task.quantity = quantity
        task.properties["productivity_value"] = 1000.0
        task.duration_days = 8
    return scenario, generated, schedule


# ---- Contracts (T001/T002) ----

def test_shift_regime_contract_bounds_and_order():
    assert PavementShiftRegime(start_date=START, end_date=None, shifts=2).end_date is None
    assert PavementShiftRegime(start_date=START, end_date=START, shifts=1).shifts == 1
    for kwargs in [dict(start_date=START, end_date=date(2026, 6, 30), shifts=1),
                   dict(start_date=START, end_date=None, shifts=0),
                   dict(start_date=START, end_date=None, shifts=3),
                   dict(start_date=START, end_date=None, shifts=1.5)]:
        with pytest.raises(ValidationError):
            PavementShiftRegime(**kwargs)


def test_empty_shift_regimes_are_excluded_from_schedule_input_dump():
    from app.contracts import ScheduleInput
    payload = dict(project_name="p", start_date=START, tasks=[], precedence_links=[], resources=[])
    assert "shift_regimes" not in ScheduleInput(**payload).model_dump(mode="json")
    with_regime = ScheduleInput(**payload, shift_regimes=sc001_regimes())
    assert len(with_regime.model_dump(mode="json")["shift_regimes"]) == 2


# ---- Domain duration function (T004/T005, SC-001) ----

def test_duration_matches_baseline_without_regimes():
    task = work_task()
    assert task_duration_for_start(task, 0, [], START) == 8
    assert task_duration_for_start(task, 95, [], START) == 8


def test_sc001_double_shift_start_finishes_in_four_days():
    task = work_task()
    assert task_duration_for_start(task, 96, sc001_regimes(), START) == 4  # 10-05


def test_sc001_crossing_task_speeds_up_mid_task_and_splits_days():
    task = work_task()
    assert task_duration_for_start(task, 86, sc001_regimes(), START) == 7  # 9-25
    assert split_shift_days(86, 93, sc001_regimes(), START) == {1: 6, 2: 1}


def test_sc001_single_shift_start_is_unaffected_by_later_double_shift():
    task = work_task()
    assert task_duration_for_start(task, 62, sc001_regimes(), START) == 8
    assert split_shift_days(62, 70, sc001_regimes(), START) == {1: 8}


def test_duration_minimum_one_day_and_fractional_productivity():
    regimes = sc001_regimes()
    assert task_duration_for_start(work_task(quantity=500), 0, regimes, START) == 1
    task = work_task(quantity=8000, productivity=300.0, duration_days=27)
    assert task_duration_for_start(task, 0, [], START) == 27
    assert task_duration_for_start(task, 95, regimes, START) == 14  # 8000/600 -> 13.34 -> 14


def test_crossing_fractional_remaining_ceil():
    task = work_task(quantity=7000, duration_days=7)
    assert task_duration_for_start(task, 86, sc001_regimes(), START) == 7  # 6 single + 0.5 -> 1 double day


def test_task_without_productivity_basis_keeps_fixed_duration():
    prep = SimpleNamespace(quantity=1, duration_days=2, properties={})
    assert task_duration_for_start(prep, 95, sc001_regimes(), START) == 2


def test_shift_config_errors_and_overlap_guard():
    good = sc001_regimes()
    assert shift_config_errors(good) == []
    assert shifts_for_day(good, date(2026, 6, 30)) == 1
    assert shifts_for_day(good, date(2026, 10, 1)) == 2
    overlapping = good + [PavementShiftRegime(start_date=date(2026, 8, 1), end_date=None, shifts=2)]
    assert shift_config_errors(overlapping) == ["shift_overlap"]
    with pytest.raises(ValueError):
        shift_runs(overlapping, START)
    duplicated = good + [PavementShiftRegime(start_date=date(2026, 10, 1), end_date=None, shifts=1)]
    assert shift_config_errors(duplicated) == ["shift_overlap"]  # same start always shares dates
    # Inverted ranges are rejected by the contract validator; the domain check
    # stays as defence for non-contract callers.
    inverted = [SimpleNamespace(start_date=date(2026, 10, 1), end_date=date(2026, 9, 1), shifts=2)]
    assert shift_config_errors(inverted) == ["shift_range:2026-10-01"]


# ---- Generation snapshot and validation (T006/T008) ----

def test_generation_snapshots_shift_regimes_into_schedule_input():
    scenario, generated, schedule = shift_scenario()
    assert schedule.shift_regimes == scenario.pavement_settings.shift_regimes
    assert not [v for v in generated.validation if v.level == "error"]


@pytest.mark.parametrize("extra", ["overlap", "duplicate"])
def test_generation_rejects_invalid_shift_regimes(extra):
    scenario, _, _ = shift_scenario()
    regimes = scenario.pavement_settings.shift_regimes
    if extra == "overlap":
        regimes = regimes + [PavementShiftRegime(start_date=date(2026, 11, 1), end_date=None, shifts=1)]
    else:
        regimes = regimes + [PavementShiftRegime(start_date=date(2026, 10, 1), end_date=None, shifts=1)]
    scenario.pavement_settings.shift_regimes = regimes
    generated = generate_pavement_input(scenario)
    assert any(v.code == "PAVEMENT_SHIFT_INVALID" for v in generated.validation)


# ---- Solver integration (T007/T010/T011) ----

def prepared_shift_schedule():
    scenario, generated, schedule = shift_scenario()
    schedule.shift_regimes = scenario.pavement_settings.shift_regimes
    return schedule


def test_validate_candidate_uses_function_durations():
    schedule = prepared_shift_schedule()
    errors, candidates = hybrid.validate_pavement_schedule(schedule)
    assert not errors, errors
    candidate = construct_candidate(schedule, candidates, "earliest_start", perf_counter() + 5)
    assert candidate is not None
    assert not validate_candidate(schedule, candidates, candidate)
    first, second = sorted(schedule.tasks, key=lambda t: t.id)
    assert candidate.starts[first.id] == 0 and candidate.ends[first.id] == 7   # 9-25 -> crosses
    assert candidate.starts[second.id] == 8 and candidate.ends[second.id] == 12  # transfer + double shift
    assert candidate.makespan == 12


def test_all_strategies_respect_shift_durations():
    schedule = prepared_shift_schedule()
    errors, candidates = hybrid.validate_pavement_schedule(schedule)
    valid = generate_initial_candidates(schedule, candidates, perf_counter() + 5)
    assert valid and all(c.makespan == 12 for c in valid)
    assert all(not validate_candidate(schedule, candidates, c) for c in valid)


def test_solve_pavement_schedule_with_double_shift_shortens_makespan():
    schedule = prepared_shift_schedule()
    schedule.time_limit_seconds = 5.0
    result = hybrid.solve_pavement_schedule(schedule)
    assert result.status in {"FEASIBLE", "OPTIMAL"}, result.validation
    assert result.objective_days == 12
    for task in result.tasks:
        expected = task_duration_for_start(
            SimpleNamespace(quantity=8000, duration_days=8, properties={"productivity_value": 1000.0}),
            task.start_offset, schedule.shift_regimes, schedule.start_date)
        assert task.end_offset - task.start_offset == expected


# ---- US2: crossing waits and idle coexistence ----

def shifted_two_layers():
    """Two cement layers in one section chained by FS+7 crossing the boundary."""
    scenario = sample_scenario((8000,), ("cement_stabilized_base", "cement_stabilized_base"))
    scenario.project.start_date = date(2026, 9, 25)
    scenario.pavement_settings.shift_regimes = [
        PavementShiftRegime(start_date=date(2026, 10, 1), end_date=None, shifts=2)]
    generated = generate_pavement_input(scenario)
    schedule = generated.schedule_input
    for task in schedule.tasks:
        task.quantity = 8000
        task.properties["productivity_value"] = 1000.0
        task.duration_days = 8
    return schedule


def test_layer_wait_days_stay_natural_days_across_shift_boundary():
    schedule = shifted_two_layers()
    errors, candidates = hybrid.validate_pavement_schedule(schedule)
    assert not errors, errors
    candidate = construct_candidate(schedule, candidates, "earliest_start", perf_counter() + 5)
    assert candidate is not None and not validate_candidate(schedule, candidates, candidate)
    first, second = sorted(schedule.tasks, key=lambda t: t.sequence_order)
    assert (candidate.starts[first.id], candidate.ends[first.id]) == (0, 7)    # 9-25 crossing
    assert candidate.starts[second.id] == 14   # ready = 7 + 7 natural wait days, inside double shift
    assert candidate.ends[second.id] == 18     # f(14) = 4 double-shift days


def test_idle_optimization_works_with_shift_regimes_and_rejects_stale_baseline():
    from app.scheduling.solver.strategies.pavement import IdleBaselineError
    schedule = shifted_two_layers()
    schedule.time_limit_seconds = 5.0
    baseline = hybrid.solve_pavement_schedule(schedule)
    assert baseline.status in {"FEASIBLE", "OPTIMAL"}
    result = hybrid.solve_pavement_idle(schedule, baseline)
    assert result.pavement_idle_optimization.final_idle_days >= 0
    assert result.objective_days == baseline.objective_days
    stale = schedule.model_copy(deep=True)
    stale.shift_regimes = [PavementShiftRegime(start_date=date(2026, 12, 1), end_date=None, shifts=2)]
    with pytest.raises(IdleBaselineError) as exc:
        hybrid.validate_idle_baseline(stale, baseline)
    assert exc.value.code == "PAVEMENT_BASELINE_OUTDATED"


# ---- US3: summary assumption and result visibility ----

def test_summary_reports_shift_assumption_only_when_configured():
    with_shift = hybrid.solve_pavement_schedule(prepared_shift_schedule())
    assert any("班制区间" in text for text in with_shift.pavement_summary.resource_assumptions)
    scenario = sample_scenario((8000, 8000), ("cement_stabilized_base",))
    scenario.project.start_date = date(2026, 9, 25)
    generated = generate_pavement_input(scenario)
    schedule = generated.schedule_input
    for task in schedule.tasks:
        task.quantity = 8000
        task.properties["productivity_value"] = 1000.0
        task.duration_days = 8
    assert not schedule.shift_regimes
    without_shift = hybrid.solve_pavement_schedule(schedule)
    assert not any("班制区间" in text for text in without_shift.pavement_summary.resource_assumptions)


# ---- US4: bit-for-bit equivalence without shift regimes ----

def test_no_shift_regimes_reproduce_pre_change_snapshot():
    """Snapshot captured from the pre-shift implementation at HEAD (FR-005/SC-002)."""
    import json
    snapshot = json.loads((Path(__file__).parent / "fixtures/pavement_shift_baseline.json").read_text(encoding="utf-8"))
    scenario = sample_scenario((1790, 940, 1790), ("granular_base", "cement_stabilized_base"))
    scenario.resource_pools = shared_fleet_scenario(1, 1).resource_pools
    generated = generate_pavement_input(scenario)
    schedule = generated.schedule_input
    assert not schedule.shift_regimes
    assert hybrid.schedule_fingerprint(schedule) == snapshot["fingerprint"]
    errors, candidates = hybrid.validate_pavement_schedule(schedule)
    assert not errors, errors
    for strategy, expected in snapshot["strategies"].items():
        candidate = construct_candidate(schedule, candidates, strategy, perf_counter() + 10)
        assert candidate is not None, strategy
        assert candidate.starts == expected["starts"], strategy
        assert candidate.ends == expected["ends"], strategy
        assert candidate.assignments == expected["assignments"], strategy
        assert candidate.makespan == expected["makespan"], strategy
