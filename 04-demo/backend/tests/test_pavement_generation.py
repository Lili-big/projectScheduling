import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.contracts import ComponentModel, ProjectBridge, StructureModel, WorkSection, PavementLayerCondition, TaskOverride
from app.scenario_data import pavement_scenario
from app.scheduling.generation.pavement import generate_pavement_input


def sample_scenario(lengths=(760, 410, 680), layers=("cement_stabilized_base",)):
    scenario = pavement_scenario("pavement-test")
    scenario.project.start_date = __import__("datetime").date(2026, 1, 1)
    scenario.pavement_settings.input_kind = "demo"
    sections = []
    for index, length in enumerate(lengths):
        sid = chr(65+index)
        components = []
        for order, kind in enumerate(layers, 1):
            cid = f"{sid}-{order}"
            components.append(ComponentModel(id=cid, name=cid, component_type=kind, quantity=length, properties={
                "unit": "m", "quantity_basis": "entered", "quantity_basis_confirmed": True,
                "quantity_basis_note": "合成验收样例，非客户数据", "construction_length_m": length,
                "width_m": 10, "thickness_m": 0.2, "layer_order": order,
                "roadbed_available_date": "2026-01-01", "start_chainage": f"K{index}+000", "end_chainage": f"K{index}+{length}"}))
            scenario.pavement_settings.layer_conditions.append(PavementLayerCondition(component_id=cid, wait_days=7 if kind == "cement_stabilized_base" else 0, basis_note="样例条件"))
        sections.append(WorkSection(id=sid, name=sid, side="left", structures=[StructureModel(id=sid, name=sid, structure_type="pavement_section", components=components)]))
    scenario.project.bridges = [ProjectBridge(id="road", name="样例路面", workpoint_type="pavement", work_sections=sections)]
    for pool in scenario.resource_pools:
        pool.quantity = 1
        pool.transfer_days = 1
    return scenario


def handover_scenario():
    from datetime import date
    s = sample_scenario((100, 100, 100, 100), ("granular_base", "cement_stabilized_base"))
    s.project.start_date = date(2026, 9, 23)
    for section, status, available in zip(s.project.bridges[0].work_sections,
            ["dated", "handed_over", "pending", "dated"], ["2026-10-25", None, None, "2026-09-10"]):
        for c in section.structures[0].components:
            c.properties.update(roadbed_handover_status=status, roadbed_available_date=available, roadbed_handover_note="征地未解决" if status == "pending" else "")
    return s


def test_handover_scope_includes_pending_sections_and_preserves_fixed_order():
    from app.contracts.pavement import PavementFixedSequence, PavementAncillaryStep
    s = handover_scenario()
    s.pavement_settings.fixed_sequences = [PavementFixedSequence(process_type="granular_base", component_ids=["B-1", "C-1", "D-1"])]
    s.pavement_settings.ancillary_steps = [PavementAncillaryStep(id="blocked-prep", structure_id="C", before_component_id="C-1", kind="other_preparation", name="清扫", duration_days=1, wait_after_days=0, order=1, basis_note="测试")]
    result = generate_pavement_input(s)
    assert not [x for x in result.validation if x.level == "error"], result.validation
    scope = result.schedule_input.pavement_handover_scope
    assert (scope.total_section_count, scope.included_section_count, scope.included_layer_count) == (4, 4, 8)
    assert scope.pending_policy == "per_fleet_last" and not scope.blocked_sections
    notice = next(v.message for v in result.validation if v.code == "PAVEMENT_ROADBED_PENDING")
    assert "机组完成自身正常段任务后" in notice and "全部完成之后" not in notice
    assert scope.pending_sections[0].reason == "征地未解决"
    assert scope.pending_sections[0].component_ids == ["C-1", "C-2"]
    assert {t.structure_id for t in result.schedule_input.tasks} == {"A", "B", "C", "D"}
    assert len(result.schedule_input.tasks) == 9
    assert any(l.predecessor_id == "pavement:B-1" and l.successor_id == "pavement:C-1" for l in result.schedule_input.precedence_links)
    assert any(l.predecessor_id == "pavement:C-1" and l.successor_id == "pavement:D-1" for l in result.schedule_input.precedence_links)
    s.project.bridges[0].work_sections[2].structures[0].components[0].properties.pop("construction_length_m")
    assert any(v.level == "error" and v.subject_id == "C-1" for v in generate_pavement_input(s).validation)
    s.project.bridges[0].work_sections[1].structures[0].components[1].properties["roadbed_handover_status"] = "pending"
    assert "PAVEMENT_ROADBED_INVALID" in {v.code for v in generate_pavement_input(s).validation}


def test_all_pending_is_conditional_and_empty_master_stays_distinct():
    from app.scheduling.application import pavement
    s = handover_scenario()
    for sec in s.project.bridges[0].work_sections:
        for c in sec.structures[0].components: c.properties.update(roadbed_handover_status="pending", roadbed_available_date=None)
    result = pavement.solve_pavement_scenario(s)
    assert result.result.status in {"OPTIMAL", "FEASIBLE"}
    assert min(t.start_offset for t in result.result.tasks) == 0
    assert len(result.result.tasks) == 8
    assert result.result.stats["pavement_handover"]["included_section_count"] == 4
    for sec in s.project.bridges[0].work_sections:
        for c in sec.structures[0].components: c.enabled = False
    disabled_codes = {v.code for v in generate_pavement_input(s).validation}
    assert "PAVEMENT_DATA_INCOMPLETE" in disabled_codes and "PAVEMENT_NO_SCHEDULABLE_SECTION" not in disabled_codes
    s.project.bridges = []
    codes = {v.code for v in generate_pavement_input(s).validation}
    assert "PAVEMENT_NO_SCHEDULABLE_SECTION" not in codes and "PAVEMENT_DATA_INCOMPLETE" in codes


def shared_fleet_scenario(quantity=1, transfer_days=0):
    scenario = sample_scenario((100, 100), ("granular_base",))
    scenario.project.bridges[0].work_sections[1].structures[0].components[0].component_type = "cement_stabilized_base"
    for pool in scenario.resource_pools:
        pool.quantity = pool.max_quantity = 0
        pool.transfer_days = None
    pool = scenario.resource_pools[1]
    pool.quantity = pool.max_quantity = quantity
    pool.transfer_days = transfer_days
    pool.label = "碎石/水稳共享机组"
    pool.compatible_process_ids = ["pavement-granular_base", "pavement-cement_stabilized_base"]
    return scenario


def test_shared_pool_expands_once_and_transmits_actual_process_ids():
    result = generate_pavement_input(shared_fleet_scenario())
    assert not [v for v in result.validation if v.level == "error"], result.validation
    assert len(result.schedule_input.resources) == 1
    resource = result.schedule_input.resources[0]
    assert resource.compatible_process_ids == ["pavement-granular_base", "pavement-cement_stabilized_base"]
    assert [t.pavement_context.process_id for t in result.schedule_input.tasks] == resource.compatible_process_ids
    assert [t.duration_days for t in result.schedule_input.tasks] == [1, 1]


def test_shared_pool_coverage_still_requires_actual_scope_and_valid_process():
    s = shared_fleet_scenario()
    s.resource_pools[1].authorized_workpoint_ids = []
    result = generate_pavement_input(s)
    assert not result.schedule_input.resources
    assert "PAVEMENT_RESOURCE_MISSING" in {v.code for v in result.validation}
    s.resource_pools[1].authorized_workpoint_ids = None
    s.resource_pools[1].compatible_process_ids = ["unknown"]
    assert "PAVEMENT_REFERENCE_INVALID" in {v.code for v in generate_pavement_input(s).validation}


def test_confirmed_lengths_ceil_per_fleet():
    result = generate_pavement_input(sample_scenario())
    assert [t.duration_days for t in result.schedule_input.tasks] == [2, 1, 1]
    assert not [v for v in result.validation if v.level == "error"]


@pytest.mark.parametrize("unit,quantity", [("m", 760), ("m2", 7600), ("m3", 1520), ("t", 3000)])
def test_matching_units_and_layer_option(unit, quantity):
    scenario = sample_scenario((760,))
    component = scenario.project.bridges[0].work_sections[0].structures[0].components[0]
    component.properties["unit"] = unit
    component.quantity = quantity
    process = next(p for p in scenario.process_library if p.component_type == component.component_type)
    option = process.productivity_options[0].model_copy(update={"id": "chosen", "productivity_value": quantity/2, "productivity_unit": f"{unit}/天"})
    process.productivity_options.append(option)
    scenario.task_overrides[component.id] = TaskOverride(productivity_option_id="chosen")
    generated = generate_pavement_input(scenario)
    assert generated.schedule_input.tasks[0].duration_days == 2
    assert not [x for x in generated.validation if x.level == "error"]


def test_bad_quantity_unit_option_and_missing_conditions_block():
    scenario = sample_scenario((760,))
    component = scenario.project.bridges[0].work_sections[0].structures[0].components[0]
    component.quantity = 0
    assert any(x.level == "error" for x in generate_pavement_input(scenario).validation)
    component.quantity = 760
    component.properties["unit"] = "m3"
    assert "PAVEMENT_UNIT_MISMATCH" in {x.code for x in generate_pavement_input(scenario).validation}
    scenario.task_overrides[component.id] = TaskOverride(productivity_option_id="missing")
    assert "PAVEMENT_REFERENCE_INVALID" in {x.code for x in generate_pavement_input(scenario).validation}


def test_zero_productivity_rejected():
    process = sample_scenario().process_library[0]
    with pytest.raises(ValidationError):
        type(process).model_validate({**process.model_dump(), "productivity_value": 0})


def test_layer_wait_without_terminal_readiness():
    scenario = sample_scenario((760,), ("cement_stabilized_base", "cement_stabilized_base"))
    generated = generate_pavement_input(scenario)
    assert generated.schedule_input.precedence_links[0].lag_days == 7
    assert generated.schedule_input.readiness_conditions == []
    assert len(generated.schedule_input.tasks) == 2


def test_zero_day_step_forwards_wait_and_positive_steps_chain():
    from app.contracts import PavementAncillaryStep
    scenario = sample_scenario((760,), ("cement_stabilized_base", "asphalt_course"))
    scenario.pavement_settings.ancillary_steps = [PavementAncillaryStep(id="prime", structure_id="A", before_component_id="A-2",
        kind="prime", name="透层", duration_days=0, wait_after_days=1, order=1, basis_note="样例"),
        PavementAncillaryStep(id="seal", structure_id="A", before_component_id="A-2", kind="seal", name="封层",
        duration_days=1, wait_after_days=2, order=2, basis_note="样例")]
    schedule = generate_pavement_input(scenario).schedule_input
    assert len(schedule.tasks) == 3
    assert [l.lag_days for l in schedule.precedence_links] == [8, 2]
    assert schedule.readiness_conditions == []
    assert schedule.tasks[-1].compatible_resource_types == []


def test_missing_date_conditions_and_cycle_block():
    from app.contracts import PavementFixedSequence
    scenario = sample_scenario((760,), ("cement_stabilized_base", "cement_stabilized_base"))
    scenario.pavement_settings.fixed_sequences = [PavementFixedSequence(process_type="cement_stabilized_base", component_ids=["A-2", "A-1"])]
    assert "PAVEMENT_LOGIC_CYCLE" in {x.code for x in generate_pavement_input(scenario).validation}
    scenario.pavement_settings.fixed_sequences = []
    scenario.pavement_settings.layer_conditions = []
    del scenario.project.bridges[0].work_sections[0].structures[0].components[0].properties["roadbed_available_date"]
    assert "PAVEMENT_DATA_INCOMPLETE" in {x.code for x in generate_pavement_input(scenario).validation}


def test_handover_and_acceptance_dates_are_offsets_without_extra_day():
    scenario = sample_scenario((760,), ("cement_stabilized_base", "asphalt_course"))
    for component in scenario.project.bridges[0].work_sections[0].structures[0].components:
        component.properties["roadbed_available_date"] = "2026-01-05"
    scenario.pavement_settings.layer_conditions[0].accepted_available_date = __import__("datetime").date(2026,1,28)
    schedule = generate_pavement_input(scenario).schedule_input
    assert [c.earliest_start_offset for c in schedule.execution_constraints] == [4,27]


def relation_rule(**patch):
    from app.contracts.pavement import PavementDependencyRule
    return PavementDependencyRule(predecessor_key="layer:cement_stabilized_base:1",
        successor_key="layer:asphalt_course:1", **patch)


def test_shared_relation_section_override_and_restore_inheritance():
    s = sample_scenario((760, 410), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.dependency_rules = [relation_rule(relationship="FS", lag_days=7),
        relation_rule(structure_id="B", relationship="SS", lag_days=2)]
    result = generate_pavement_input(s)
    assert not [v for v in result.validation if v.level == "error"]
    assert [(l.relationship, l.lag_days) for l in result.schedule_input.precedence_links] == [("FS", 7), ("SS", 2)]
    assert [t.properties["wait_days"] for t in result.schedule_input.tasks] == [7, 0, 0, 0]
    assert s.pavement_settings.layer_conditions[2].wait_days == 7
    s.pavement_settings.dependency_rules.pop()
    assert [(l.relationship, l.lag_days) for l in generate_pavement_input(s).schedule_input.precedence_links] == [("FS", 7), ("FS", 7)]


def test_explicit_gap_replaces_old_wait_without_terminal_condition():
    s = sample_scenario((760,), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.layer_conditions = s.pavement_settings.layer_conditions[1:]
    s.pavement_settings.dependency_rules = [relation_rule(lag_days=2)]
    result = generate_pavement_input(s)
    assert not [v for v in result.validation if v.level == "error"]
    assert result.schedule_input.precedence_links[0].lag_days == 2
    assert result.schedule_input.tasks[0].properties["wait_days"] == 2
    assert result.schedule_input.readiness_conditions == []
    s.pavement_settings.dependency_rules[0].lag_days = None
    assert "PAVEMENT_DATA_INCOMPLETE" in {v.code for v in generate_pavement_input(s).validation}


def test_dependency_reference_duplicate_and_inactive_rules_are_visible():
    s = sample_scenario((760,), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.dependency_rules = [relation_rule(lag_days=0), relation_rule(lag_days=1)]
    assert "PAVEMENT_REFERENCE_INVALID" in {v.code for v in generate_pavement_input(s).validation}
    s.pavement_settings.dependency_rules = [relation_rule(structure_id="missing", lag_days=0)]
    assert "PAVEMENT_REFERENCE_INVALID" in {v.code for v in generate_pavement_input(s).validation}
    s.pavement_settings.dependency_rules = [relation_rule(lag_days=0)]
    s.project.bridges[0].work_sections[0].structures[0].components[1].enabled = False
    result = generate_pavement_input(s)
    assert not [v for v in result.validation if v.level == "error"]
    assert "PAVEMENT_RELATION_UNUSED" in {v.code for v in result.validation}


def test_preparation_edges_can_be_overridden_and_zero_steps_do_not_shift_keys():
    from app.contracts import PavementAncillaryStep
    from app.contracts.pavement import PavementDependencyRule
    s = sample_scenario((760,), ("cement_stabilized_base", "asphalt_course"))
    s.pavement_settings.ancillary_steps = [PavementAncillaryStep(id="zero", structure_id="A", before_component_id="A-2",
        kind="seal", name="零天封层条件", duration_days=0, wait_after_days=1, order=1, basis_note="样例"),
        PavementAncillaryStep(id="seal", structure_id="A", before_component_id="A-2", kind="seal", name="封层",
        duration_days=1, wait_after_days=2, order=2, basis_note="样例")]
    s.pavement_settings.dependency_rules = [PavementDependencyRule(predecessor_key="layer:cement_stabilized_base:1",
        successor_key="layer:asphalt_course:1/prep:seal:2", relationship="FF", lag_days=3)]
    result = generate_pavement_input(s)
    assert not [v for v in result.validation if v.level == "error"]
    assert [(l.relationship, l.lag_days) for l in result.schedule_input.precedence_links] == [("FF", 3), ("FS", 2)]


def test_task_preview_25_sections_100_tasks_and_authoritative_productivity():
    s = sample_scenario((1790,) * 25, ("granular_base",) + ("cement_stabilized_base",) * 3)
    for p in s.process_library:
        for o in p.productivity_options: o.productivity_value = 800
    result = generate_pavement_input(s)
    assert len(result.schedule_input.tasks) == 100
    assert len(result.schedule_input.precedence_links) == 75
    assert [t.duration_days for t in result.schedule_input.tasks[:4]] == [3] * 4
    assert [l.lag_days for l in result.schedule_input.precedence_links[:3]] == [0, 7, 7]
    assert result.schedule_input.readiness_conditions == []
    p = s.process_library[0]
    p.productivity_options.append(p.productivity_options[0].model_copy(update={"id": "fast", "productivity_value": 1000}))
    s.task_overrides["A-1"] = TaskOverride(productivity_option_id="fast")
    for c in s.project.bridges[0].work_sections[0].structures[0].components:
        c.properties.update(roadbed_handover_status="handed_over", roadbed_available_date=None)
    result = generate_pavement_input(s)
    assert len(result.schedule_input.tasks) == 100
    assert result.schedule_input.tasks[0].duration_days == 2
    assert not any(v.level == "error" for v in result.validation)


def test_missing_intermediate_task_does_not_create_confirmed_shortcut():
    s = sample_scenario((100,), ("cement_stabilized_base",) * 3)
    s.task_overrides["A-2"] = TaskOverride(productivity_option_id="missing")
    result = generate_pavement_input(s)
    assert [t.component_id for t in result.schedule_input.tasks] == ["A-1", "A-3"]
    assert not result.schedule_input.precedence_links
    assert any(v.level == "error" for v in result.validation)
