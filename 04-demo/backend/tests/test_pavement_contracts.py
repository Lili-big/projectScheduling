import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.contracts import ScheduleInput, Resource, PavementLayerCondition, PavementSettings


def test_live_event_contract_and_optional_diagnostics():
    from pydantic import TypeAdapter
    from app.contracts import PavementSolveEvent, PavementOptimization
    adapter = TypeAdapter(PavementSolveEvent)
    started = adapter.validate_python(dict(type="started", sequence=1, elapsed_seconds=0, time_budget_seconds=15))
    assert adapter.validate_json(started.model_dump_json()) == started
    for raw in [dict(type="solution", sequence=2, elapsed_seconds=1),
                dict(type="started", sequence=0, elapsed_seconds=0, time_budget_seconds=15),
                dict(type="started", sequence=1, elapsed_seconds=0, time_budget_seconds=float("inf"))]:
        with pytest.raises(ValidationError): adapter.validate_python(raw)
    old = PavementOptimization(outcome="no_plan")
    assert old.search_workers is None and old.improvement_count is None
    with pytest.raises(ValidationError): PavementOptimization(outcome="no_plan", search_workers=0)


def test_hybrid_result_roundtrip_and_legacy_omission():
    from app.contracts import PavementOptimization, ScheduleResult
    base = ScheduleResult(status="UNKNOWN", plan_start_date=date(2026, 1, 1))
    assert "pavement_optimization" not in base.model_dump()
    for outcome, source, optimizer in [("initial_retained", "greedy", "UNKNOWN"),
            ("improved", "cp_sat", "OPTIMAL"), ("cp_sat_only", "cp_sat", "FEASIBLE"),
            ("no_plan", None, None), ("inconsistent", None, "INFEASIBLE")]:
        meta = PavementOptimization(method="greedy_cpsat", outcome=outcome,
            selected_source=source, optimizer_status=optimizer)
        result = base.model_copy(update={"pavement_optimization": meta})
        assert ScheduleResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        PavementOptimization(outcome="no_plan", initial_days=0)
    with pytest.raises(ValidationError):
        PavementOptimization(outcome="no_plan", total_seconds=-1)


def test_legacy_dump_has_no_pavement_defaults():
    old = dict(project_name="bridge", start_date="2026-01-01", tasks=[], precedence_links=[], resources=[])
    model = ScheduleInput.model_validate(old)
    assert model.engineering_domain == "bridge"
    assert "engineering_domain" not in model.model_dump()
    assert "readiness_conditions" not in model.model_dump()
    assert "pavement_handover_scope" not in model.model_dump()
    from app.contracts import StructureModel
    assert "properties" not in StructureModel(id="b", name="b", structure_type="pier").model_dump()
    assert "transfer_days" not in Resource(id="r", name="r", type="drill").model_dump()
    assert "compatible_process_ids" not in Resource(id="r", name="r", type="drill").model_dump()
    assert ScheduleInput.model_validate(model.model_dump()).model_dump() == model.model_dump()


def test_handover_scope_roundtrip_and_old_pavement_payload():
    from app.contracts import PavementHandoverScope, PavementBlockedSection
    raw = dict(project_name="pavement", start_date="2026-09-23", tasks=[], precedence_links=[], resources=[], engineering_domain="pavement")
    assert ScheduleInput.model_validate(raw).pavement_handover_scope is None
    scope = PavementHandoverScope(total_section_count=1, blocked_sections=[PavementBlockedSection(structure_id="C",section_name="段C",reason="征地",component_ids=["c"])])
    model = ScheduleInput.model_validate({**raw, "pavement_handover_scope":scope})
    assert ScheduleInput.model_validate_json(model.model_dump_json()).pavement_handover_scope == scope


def test_shared_fleet_and_actual_process_roundtrip():
    from app.contracts.pavement import PavementTaskContext
    resource = Resource(id="shared", name="共享", type="pavement_paving_crew",
                        compatible_process_ids=["gravel-method", "water-method"])
    assert Resource.model_validate_json(resource.model_dump_json()).compatible_process_ids == ["gravel-method", "water-method"]
    context = PavementTaskContext(source_component_id="a", position_id="a:left", task_kind="construction",
        process_type="granular_base", process_id="gravel-method", quantity_basis="entered", input_kind="demo")
    assert PavementTaskContext.model_validate_json(context.model_dump_json()).process_id == "gravel-method"


@pytest.mark.parametrize("policy", ["strict_last", "per_fleet_last"])
def test_conditional_handover_contract_roundtrip_and_legacy_omission(policy):
    from app.contracts.pavement import PavementHandoverScope, PavementSummary
    raw = dict(total_section_count=2, included_section_count=2, included_layer_count=2,
        blocked_sections=[], pending_policy=policy, pending_sections=[dict(
            structure_id="B", section_name="段B", reason="征地", component_ids=["B-1"])])
    scope = PavementHandoverScope.model_validate(raw)
    assert scope.model_dump(mode="json") == raw
    assert PavementHandoverScope.model_validate_json(scope.model_dump_json()) == scope
    assert "pending_policy" not in PavementHandoverScope().model_dump()
    assert "pending_sections" not in PavementHandoverScope().model_dump()
    base = dict(input_kind="demo", input_fingerprint="sample", construction_finish_offset=5,
        construction_finish_date="2026-09-27", ready_offset=5, ready_date="2026-09-28")
    assert "pending_section_dates" not in PavementSummary(**base).model_dump()
    dates = [dict(structure_id="B", required_handover_date="2026-09-26", estimated_finish_date="2026-09-27")]
    summary = PavementSummary(**base, pending_section_dates=dates)
    assert summary.model_dump(mode="json")["pending_section_dates"] == dates
    assert PavementSummary.model_validate_json(summary.model_dump_json()) == summary


def test_explicit_pavement_conditions_roundtrip():
    settings = PavementSettings(layer_conditions=[dict(component_id="w", wait_days=7, basis_note="项目确认")])
    assert PavementSettings.model_validate_json(settings.model_dump_json()) == settings
    start = date(2026, 1, 1)
    assert start + timedelta(days=2-1) == date(2026, 1, 2)
    assert start + timedelta(days=2+7) == date(2026, 1, 10)


@pytest.mark.parametrize("payload", [dict(component_id="w", basis_note="确认"), dict(component_id="w", wait_days=-1, basis_note="确认")])
def test_unconfirmed_or_negative_wait_is_not_zero(payload):
    with pytest.raises(ValidationError):
        PavementLayerCondition(**payload)


def test_invalid_domain_and_transfer_rejected():
    with pytest.raises(ValidationError):
        ScheduleInput(project_name="x", start_date="2026-01-01", tasks=[], precedence_links=[], resources=[], engineering_domain="road")
    with pytest.raises(ValidationError):
        Resource(id="r", name="r", type="crew", transfer_days=-1)


def test_dependency_contract_rejects_invalid_gap_and_keeps_old_profiles_compatible():
    from app.contracts.pavement import PavementDependencyRule
    assert PavementSettings.model_validate({"layer_conditions": []}).dependency_rules == []
    base = dict(predecessor_key="water:1", successor_key="water:2")
    for patch in [dict(lag_days=-1), dict(lag_days=1.5), dict(lag_days=True), dict(lag_days="2"),
                  dict(relationship="invalid"), dict(predecessor_key=""), dict(structure_id="")]:
        with pytest.raises(ValidationError):
            PavementDependencyRule(**{**base, **patch})
    assert PavementDependencyRule(**base).lag_days is None
    rule = PavementDependencyRule(**base, relationship="SF", lag_days=0)
    assert PavementDependencyRule.model_validate_json(rule.model_dump_json()) == rule


def test_idle_metadata_is_optional_and_has_explicit_units_and_bounds():
    from app.contracts import ScheduleResult, PavementIdleOptimization, PavementIdleOptimizeRequest
    from pydantic import ValidationError
    from datetime import date
    import pytest
    old = ScheduleResult(status="UNKNOWN", plan_start_date=date(2026,1,1))
    assert "pavement_idle_optimization" not in old.model_dump(mode="json")
    data=dict(baseline_input_fingerprint="abc",makespan_cap_days=10,baseline_idle_days=4,
        final_idle_days=0,improvement_idle_days=4,baseline_transfer_days=1,final_transfer_days=1,time_budget_seconds=15)
    meta=PavementIdleOptimization(**data)
    assert meta.metric=="fleet_internal_idle_v1" and not meta.proved_optimal
    for key,value in [("makespan_cap_days",0),("final_idle_days",-1),("baseline_idle_days",1.5),("time_budget_seconds",float("inf"))]:
        with pytest.raises(ValidationError): PavementIdleOptimization(**{**data,key:value})


def test_idle_request_optional_runtime_budget_is_positive_and_finite():
    from app.contracts import PavementIdleOptimizeRequest
    from test_pavement_api import idle_api_payload
    from pydantic import ValidationError
    import pytest
    payload = idle_api_payload()
    assert PavementIdleOptimizeRequest(**payload).time_budget_seconds is None
    for value in [None, 15, 30, 60, .5]:
        assert PavementIdleOptimizeRequest(**payload, time_budget_seconds=value).time_budget_seconds == value
    for value in [0, -1, float("inf"), float("nan"), "invalid"]:
        with pytest.raises(ValidationError):
            PavementIdleOptimizeRequest(**payload, time_budget_seconds=value)
