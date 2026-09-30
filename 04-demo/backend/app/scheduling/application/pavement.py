from ...contracts import ScenarioSolveResult, ScheduleResult
from ..generation.pavement import generate_pavement_input
from ..solver.strategies.pavement import solve_pavement_schedule


def solve_pavement_scenario(scenario, *, workpoint_id=None, generated=None, on_solution=None, control=None):
    generated = generated if generated is not None else generate_pavement_input(scenario, workpoint_id=workpoint_id)
    def wrap(result):
        return ScenarioSolveResult(scenario_id=scenario.scenario_id,scenario_name=scenario.scenario_name,
            generated=generated,result=result,milestone_results=result.milestone_results,
            diagnostics=[*generated.validation, *result.validation],
            metrics={"engineering_domain":"pavement","ready_days":result.objective_days})
    if any(item.level == "error" for item in generated.validation):
        result = ScheduleResult(status="MODEL_INVALID",plan_start_date=scenario.project.start_date,validation=generated.validation,
            stats={"pavement_handover": generated.source_summary["pavement_handover"]})
        return wrap(result).model_copy(update={"diagnostics": generated.validation})
    else:
        result = solve_pavement_schedule(generated.schedule_input,
            on_solution=(lambda result: on_solution(wrap(result))) if on_solution else None, control=control)
    return wrap(result)


def prepare_pavement_idle(scenario, generated, baseline):
    from ..solver.strategies.pavement import IdleBaselineError, validate_idle_baseline
    errors=[d for d in generated.validation if d.level=="error"]
    if errors:
        raise IdleBaselineError(errors[0].message, errors[0].code)
    if baseline.generated.schedule_input.pavement_handover_scope and baseline.generated.schedule_input.pavement_handover_scope.pending_policy=="strict_last":
        raise IdleBaselineError("历史整体后置方案须先按当前规则重新求解。", "PAVEMENT_INPUT_OUTDATED")
    if (baseline.scenario_id != scenario.scenario_id or baseline.generated.solve_scope != generated.solve_scope
            or baseline.generated.schedule_input.model_dump(mode="json") != generated.schedule_input.model_dump(mode="json")):
        raise IdleBaselineError("当前输入、范围或主数据版本已变化，请重新求解后优化窝工。", "PAVEMENT_BASELINE_OUTDATED")
    return validate_idle_baseline(generated.schedule_input, baseline.result)


def solve_pavement_idle_scenario(scenario, generated, baseline, prepared, began, *, on_solution=None, control=None,
                               time_budget_seconds=None):
    from ..solver.strategies.pavement import solve_pavement_idle
    def wrap(result):
        return ScenarioSolveResult(scenario_id=scenario.scenario_id,scenario_name=scenario.scenario_name,
            generated=generated,result=result,milestone_results=result.milestone_results,
            diagnostics=[*generated.validation,*result.validation],
            metrics={"engineering_domain":"pavement","ready_days":result.objective_days,
                "idle_days":result.pavement_idle_optimization.final_idle_days})
    result=solve_pavement_idle(generated.schedule_input,baseline.result,prepared=prepared,began=began,
        on_solution=(lambda result:on_solution(wrap(result))) if on_solution else None,control=control,
        time_budget_seconds=time_budget_seconds)
    return wrap(result)
