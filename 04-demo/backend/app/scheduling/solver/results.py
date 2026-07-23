"""Schedule result construction and shared target classification."""

from __future__ import annotations

from typing import Any

from ...contracts import ScheduleInput, ScheduleResult


def apply_unified_target_achievement(
    result: ScheduleResult,
    schedule_input: ScheduleInput,
    *,
    evaluated_at_source: str,
    fixed_duration_target: int | None = None,
) -> dict[str, Any]:
    """Apply the four-state business result without discarding a usable schedule."""
    hard_lateness = [
        max(0, int(milestone.lateness_days or 0))
        for milestone in result.milestone_results
        if milestone.mode == "hard" and milestone.status != "not_evaluated"
    ]
    hard_milestone_late_days = sum(hard_lateness)
    fixed_duration_overrun_days = _fixed_duration_overrun_days(
        result,
        fixed_duration_target=fixed_duration_target,
    )
    max_target_delay_days = max([fixed_duration_overrun_days, *hard_lateness], default=0)
    target_present = fixed_duration_target is not None or any(
        milestone.mode == "hard" for milestone in schedule_input.milestones
    )
    solver_status = str(result.stats.get("primary_solver_status") or result.status)
    has_schedule = bool(result.tasks)
    optimality_proven = solver_status == "OPTIMAL"

    if solver_status in {"INFEASIBLE", "MODEL_INVALID"}:
        target_status = "infeasible"
    elif solver_status == "UNKNOWN":
        target_status = "unconfirmed"
    elif solver_status not in {"OPTIMAL", "FEASIBLE"}:
        target_status = "infeasible"
    elif not target_present:
        target_status = "unconfirmed"
    elif max_target_delay_days == 0:
        target_status = "met"
    elif optimality_proven:
        target_status = "not_met"
    else:
        target_status = "unconfirmed"

    failure_reasons: list[str] = []
    if hard_milestone_late_days:
        failure_reasons.append("hard_milestone_late")
    if fixed_duration_overrun_days:
        failure_reasons.append("fixed_duration_overrun")
    if not target_present and solver_status in {"OPTIMAL", "FEASIBLE"}:
        failure_reasons.append("target_missing")
    if target_status == "unconfirmed" and solver_status == "FEASIBLE" and max_target_delay_days:
        failure_reasons.append("optimality_unproven")
    if solver_status == "UNKNOWN":
        failure_reasons.extend(["unconfirmed", "time_budget_exhausted"])
    if target_status == "infeasible":
        failure_reasons.append(str(result.stats.get("reason") or "physical_infeasible"))

    payload = {
        "business_success": target_status == "met",
        "target_status": target_status,
        "solver_status": solver_status,
        "selected_schedule_solver_status": result.status,
        "target_present": target_present,
        "has_schedule": has_schedule,
        "optimality_proven": optimality_proven,
        "hard_milestone_late_days": hard_milestone_late_days,
        "fixed_duration_overrun_days": fixed_duration_overrun_days,
        "max_target_delay_days": max_target_delay_days,
        "failure_reasons": list(dict.fromkeys(failure_reasons)),
        "time_budget_seconds": schedule_input.time_limit_seconds,
        "time_budget_exhausted": solver_status in {"FEASIBLE", "UNKNOWN"},
        "evaluated_at_source": evaluated_at_source,
    }
    result.stats.update(
        {
            "target_achievement": payload,
            "hard_milestone_late_days": hard_milestone_late_days,
            "fixed_duration_overrun_days": fixed_duration_overrun_days,
            "max_target_delay_days": max_target_delay_days,
        }
    )
    result.objective_breakdown.update(
        {
            "target_achievement": payload,
            "hard_milestone_late_days": hard_milestone_late_days,
            "fixed_duration_overrun_days": fixed_duration_overrun_days,
            "max_target_delay_days": max_target_delay_days,
        }
    )
    return payload


def _fixed_duration_overrun_days(
    result: ScheduleResult,
    *,
    fixed_duration_target: int | None,
) -> int:
    direct = _int_or_none(result.objective_breakdown.get("fixed_duration_overrun_days"))
    if direct is not None:
        return max(0, direct)
    relaxed = result.stats.get("relaxed_target_constraints")
    if isinstance(relaxed, dict):
        relaxed_value = _int_or_none(relaxed.get("fixed_duration_overrun_days"))
        if relaxed_value is not None:
            return max(0, relaxed_value)
    if fixed_duration_target is None or result.objective_days is None:
        return 0
    return max(0, int(result.objective_days) - fixed_duration_target)


def _int_or_none(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None


# Lazy compatibility wrappers avoid a circular dependency while preserving the
# older private discovery surface for historical tests and callers.
def _engine_helper(name: str, *args: Any, **kwargs: Any) -> Any:
    from . import engine

    return getattr(engine, name)(*args, **kwargs)


def _capacity_model_result(*args: Any, **kwargs: Any) -> Any:
    return _engine_helper("_capacity_model_result", *args, **kwargs)


def _continuous_span_allocations(*args: Any, **kwargs: Any) -> Any:
    return _engine_helper("_continuous_span_allocations", *args, **kwargs)


def _continuous_span_result_payload(*args: Any, **kwargs: Any) -> Any:
    return _engine_helper("_continuous_span_result_payload", *args, **kwargs)


def _fixed_duration_infeasible_result(*args: Any, **kwargs: Any) -> Any:
    return _engine_helper("_fixed_duration_infeasible_result", *args, **kwargs)


def _objective_contributions_for_result(*args: Any, **kwargs: Any) -> Any:
    return _engine_helper("_objective_contributions_for_result", *args, **kwargs)


def _resource_model_result(*args: Any, **kwargs: Any) -> Any:
    return _engine_helper("_resource_model_result", *args, **kwargs)


__all__ = ["apply_unified_target_achievement"]
