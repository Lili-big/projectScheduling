"""Generate tasks from confirmed pavement layers, retaining quantity evidence."""
from datetime import date
from collections import defaultdict
from graphlib import TopologicalSorter, CycleError

from ...contracts import (GeneratedScheduleInput, ScheduleInput, Task, ProductivityRule, ValidationMessage, SolveScope, PrecedenceLink, TaskExecutionConstraint)
from ...contracts.pavement import PavementTaskContext, PavementHandoverScope, PavementPendingSection
from ...process_library_defaults import PAVEMENT_PROCESSES
from ...project_master.validation import pavement_quantity_errors, resolve_roadbed_handover, roadbed_start_offset
from ...wbs import calculate_duration


def message(code, text, subject=None):
    return ValidationMessage(level="error", code=code, message=text, subject_id=subject,
                             entity_refs=[subject] if subject else [])


def generate_pavement_input(scenario, *, workpoint_id=None):
    validation, tasks = [], []
    scope = PavementHandoverScope(pending_policy="per_fleet_last", pending_sections=[])
    section_ids, component_ids = set(), set()
    selected = [w for w in scenario.project.bridges if workpoint_id is None or w.id == workpoint_id]
    if workpoint_id and not selected: raise ValueError("所选路面工点不属于当前项目。")
    settings = scenario.pavement_settings
    if settings is None:
        validation.append(message("PAVEMENT_DATA_INCOMPLETE", "请配置路面工序条件。"))
    for workpoint in selected:
        if workpoint.workpoint_type != "pavement":
            validation.append(message("PAVEMENT_SCOPE_NOT_SUPPORTED", "选中工点不属于路面。", workpoint.id))
            continue
        for section in workpoint.work_sections:
            for structure in section.structures:
                if structure.structure_type != "pavement_section":
                    validation.append(message("PAVEMENT_SCOPE_NOT_SUPPORTED", "路面施工段类型不合法。", structure.id))
                    continue
                enabled = [c for c in structure.components if c.enabled]
                if structure.id in section_ids or any(c.id in component_ids for c in structure.components) or len({c.id for c in structure.components}) != len(structure.components):
                    validation.append(message("PAVEMENT_REFERENCE_INVALID", "施工段或结构层ID重复。", structure.id))
                section_ids.add(structure.id)
                component_ids.update(c.id for c in structure.components)
                # Retain disabled layers in master data, outside the execution/handover scope.
                if not enabled:
                    continue
                scope.total_section_count += 1
                try:
                    source = structure.properties or (structure.components[0].properties if structure.components else {})
                    status, available_date, note = resolve_roadbed_handover(source)
                    if any(resolve_roadbed_handover(c.properties)[:2] != (status, available_date) for c in structure.components):
                        raise ValueError("同一施工段的路床移交条件不一致。")
                except ValueError as exc:
                    scope.included_section_count += 1
                    scope.included_layer_count += len(enabled)
                    validation.append(message("PAVEMENT_ROADBED_INVALID", str(exc), structure.id))
                    continue
                if status == "pending":
                    scope.pending_sections.append(PavementPendingSection(structure_id=structure.id, section_name=section.name,
                        reason=note, component_ids=[c.id for c in enabled]))
                    validation.append(ValidationMessage(level="info", code="PAVEMENT_ROADBED_PENDING", subject_id=structure.id,
                        message=f"{section.name}待移交，各机组完成自身正常段任务后再施工；以届时移交为前提：{note}"))
                scope.included_section_count += 1
                scope.included_layer_count += len(enabled)
                for component in structure.components:
                    if not component.enabled: continue
                    if component.component_type not in PAVEMENT_PROCESSES:
                        validation.append(message("PAVEMENT_REFERENCE_INVALID", "未知路面结构层类型。", component.id)); continue
                    props = component.properties
                    errors = pavement_quantity_errors(props, component.quantity, props.get("unit"))
                    validation.extend(message(code, text, component.id) for code, text in errors)
                    override = scenario.task_overrides.get(component.id)
                    method = override.method_id if override and override.method_id else component.method_id
                    matches = [p for p in scenario.process_library if p.component_type == component.component_type and (not method or p.method_id == method)]
                    process = next((p for p in matches if p.is_default), matches[0] if matches else None)
                    if not process:
                        validation.append(message("PAVEMENT_REFERENCE_INVALID", "没有适用工艺。", component.id)); continue
                    option_id = override.productivity_option_id if override and override.productivity_option_id else component.productivity_option_id
                    option = next((o for o in process.productivity_options if o.id == option_id), None) if option_id else next((o for o in process.productivity_options if o.is_default), process.productivity_options[0])
                    if option is None:
                        validation.append(message("PAVEMENT_REFERENCE_INVALID", "选用工效方案不存在。", component.id)); continue
                    if option.duration_method != "units_per_day" or option.quantity_source != "quantity" or option.productivity_unit != f"{props.get('unit')}/天":
                        validation.append(message("PAVEMENT_UNIT_MISMATCH", "工效必须使用与工程量一致的单位/天，按每套机组计算。", component.id)); continue
                    if errors: continue
                    rule = ProductivityRule(id=option.id, component_type=component.component_type,
                        process_name=process.process_name, group_name="路面", resource_type=process.resource_type,
                        **option.model_dump(exclude={"id", "name"}))
                    tasks.append(Task(id=f"pavement:{component.id}", name=f"{section.name} · {component.name}",
                        bridge_id=workpoint.id, work_section_id=section.id, component_id=component.id,
                        structure_id=structure.id, structure_name=structure.name, structure_type="pavement_section",
                        sequence_order=int(props.get("layer_order", 0)), component_type=component.component_type,
                        process_name=process.process_name, productivity_rule_id=option.id,
                        quantity=component.quantity, quantity_label=f"{component.quantity:g}{props['unit']}",
                        duration_days=calculate_duration(component.quantity, rule),
                        compatible_resource_types=[PAVEMENT_PROCESSES[component.component_type][1]],
                        properties={**props, "productivity_value": option.productivity_value, "productivity_unit": option.productivity_unit},
                        pavement_context=PavementTaskContext(process_id=process.id, source_component_id=component.id,
                            position_id=f"{structure.id}:{section.side}", task_kind="construction",
                            process_type=component.component_type, quantity_basis=str(props.get("quantity_basis")),
                            input_kind=settings.input_kind if settings else "customer")))
    if not tasks:
        validation.append(message("PAVEMENT_DATA_INCOMPLETE", "尚无可生成的路面结构层，请导入并完善主数据。"))
    schedule_input = ScheduleInput(engineering_domain="pavement", project_name=scenario.project.project_name,
        start_date=scenario.project.start_date, tasks=tasks, precedence_links=[], resources=[], pavement_handover_scope=scope,
        project_data_version_id=scenario.project_data_version_id, milestones=scenario.milestones,
        time_limit_seconds=scenario.time_limit_seconds, schedule_strategy=scenario.schedule_strategy)
    _expand_resources(scenario, schedule_input, validation)
    if settings is not None:
        _build_layer_graph(scenario, schedule_input, validation)
    return GeneratedScheduleInput(schedule_input=schedule_input, validation=validation,
        solve_scope=SolveScope(mode="WORKPOINT", workpoint_id=selected[0].id, workpoint_name=selected[0].name) if workpoint_id else SolveScope(),
        source_summary={"engineering_domain": "pavement", "input_kind": settings.input_kind if settings else "customer",
            "project_data_version_id": scenario.project_data_version_id, "section_count": sum(len(w.work_sections) for w in selected),
            "pavement_handover": scope.model_dump(mode="json")})


def _build_layer_graph(scenario, schedule, validation):
    settings = scenario.pavement_settings
    all_layers = {c.id: (s.id, c.component_type) for w in scenario.project.bridges for sec in w.work_sections for s in sec.structures for c in s.components}
    by_component = {t.component_id: t for t in schedule.tasks}
    conditions = {c.component_id: c for c in settings.layer_conditions}
    node_keys, step_keys, structure_keys = {}, {}, {}
    terminal_components, predecessor_components = set(), {}
    for workpoint in scenario.project.bridges:
        for section in workpoint.work_sections:
            for structure in section.structures:
                enabled = sorted((c for c in structure.components if c.enabled), key=lambda c: (int(c.properties.get("layer_order", 0)), c.id))
                if enabled: terminal_components.add(enabled[-1].id)
                predecessor_components.update({b.id: a.id for a, b in zip(enabled, enabled[1:])})
                counts = defaultdict(int)
                keys = structure_keys[structure.id] = set()
                for component in sorted(structure.components, key=lambda c: (int(c.properties.get("layer_order", 0)), c.id)):
                    counts[component.component_type] += 1
                    key = f"layer:{component.component_type}:{counts[component.component_type]}"
                    node_keys[component.id] = key
                    keys.add(key)
                    prep_counts = defaultdict(int)
                    for step in sorted((s for s in settings.ancillary_steps if s.before_component_id == component.id), key=lambda s: (s.order, s.id)):
                        prep_counts[step.kind] += 1
                        step_keys[step.id] = f"{key}/prep:{step.kind}:{prep_counts[step.kind]}"
                        keys.add(step_keys[step.id])
    rules, matched_rules = {}, set()
    for rule in settings.dependency_rules:
        key = (rule.structure_id, rule.predecessor_key, rule.successor_key)
        if key in rules:
            validation.append(message("PAVEMENT_REFERENCE_INVALID", "同一范围的工序关系重复。", rule.structure_id))
        candidates = [structure_keys.get(rule.structure_id, set())] if rule.structure_id else structure_keys.values()
        if rule.predecessor_key == rule.successor_key or not any({rule.predecessor_key, rule.successor_key} <= keys for keys in candidates):
            validation.append(message("PAVEMENT_REFERENCE_INVALID", "工序关系引用的施工段或工序已不存在。", rule.structure_id))
        rules[key] = rule
    for task in schedule.tasks:
        task.properties["pavement_node_key"] = node_keys[task.component_id]
    for values in ([c.component_id for c in settings.layer_conditions], [s.id for s in settings.ancillary_steps]):
        if len(values) != len(set(values)):
            validation.append(message("PAVEMENT_REFERENCE_INVALID", "条件或配套步骤ID重复。"))
    for cid in set(conditions) | set(scenario.task_overrides):
        if cid not in all_layers: validation.append(message("PAVEMENT_REFERENCE_INVALID", "配置引用的结构层不存在于当前主数据。", cid))
    for step in settings.ancillary_steps:
        if step.before_component_id not in all_layers or all_layers[step.before_component_id][0] != step.structure_id:
            validation.append(message("PAVEMENT_REFERENCE_INVALID", "配套步骤引用的施工段/结构层无效。", step.id))

    def offset(value, subject, required=False):
        if not value:
            if required: validation.append(message("PAVEMENT_DATA_INCOMPLETE", "请填写路床最早可用日期。", subject))
            return 0
        try:
            parsed = value if isinstance(value, date) else date.fromisoformat(str(value))
            return max(0, (parsed - schedule.start_date).days)
        except (ValueError, TypeError):
            validation.append(message("PAVEMENT_DATA_INCOMPLETE", "日期必须为 YYYY-MM-DD。", subject)); return 0

    def link(previous, successor, lag, source):
        if previous:
            relationship = "FS"
            if source == "pavement_layer_condition":
                pair = (previous.properties["pavement_node_key"], successor.properties["pavement_node_key"])
                global_key, local_key = (None, *pair), (successor.structure_id, *pair)
                matched_rules.update(k for k in (global_key, local_key) if k in rules)
                rule = rules.get(local_key, rules.get(global_key))
                if rule:
                    relationship = rule.relationship
                    if rule.lag_days is None:
                        previous.properties.pop("wait_basis", None)
                        validation.append(message("PAVEMENT_DATA_INCOMPLETE", "请填写工序关系的技术间歇，0天也需确认。", successor.component_id))
                    else:
                        lag = rule.lag_days
                        previous.properties.update(wait_days=lag if relationship == "FS" else 0,
                            wait_basis="分段工序关系" if rule.structure_id else "统一工序关系")
            schedule.precedence_links.append(PrecedenceLink(id=f"pavement-link-{len(schedule.precedence_links)}",
                predecessor_id=previous.id, successor_id=successor.id, relationship=relationship, lag_days=lag, source_rule_id=source))

    def earliest(task, available):
        schedule.execution_constraints.append(TaskExecutionConstraint(task_id=task.id,
            earliest_start_offset=max(available, roadbed_start_offset(task.properties, schedule.start_date, allow_pending=True)), source="pavement_conditions"))

    groups = defaultdict(list)
    for task in schedule.tasks: groups[task.pavement_context.position_id].append(task)
    for group in groups.values():
        group.sort(key=lambda t: (t.sequence_order, t.id))
        if any(t.sequence_order <= 0 for t in group) or len({t.sequence_order for t in group}) != len(group):
            validation.append(message("PAVEMENT_DATA_INCOMPLETE", "结构层顺序须为不重复的正整数。", group[0].structure_id))
        previous, pending_wait, available = None, 0, 0
        for task in group:
            if predecessor_components.get(task.component_id) not in by_component:
                previous, pending_wait, available = None, 0, 0
            available = max(available, roadbed_start_offset(task.properties, schedule.start_date, allow_pending=True))
            steps = sorted([s for s in settings.ancillary_steps if s.before_component_id == task.component_id], key=lambda s: (s.order, s.id))
            if len({s.order for s in steps}) != len(steps): validation.append(message("PAVEMENT_REFERENCE_INVALID", "同一层前的配套步骤顺序重复。", task.component_id))
            for step in steps:
                available = max(available, offset(step.available_date, step.id))
                if step.duration_days == 0:
                    pending_wait += step.wait_after_days
                    available += step.wait_after_days
                    continue
                prep = task.model_copy(deep=True, update={"id": f"pavement-prep:{step.id}", "name": f"{task.structure_name} · {step.name}",
                    "component_type": "pavement_preparation", "process_name": step.name, "productivity_rule_id": step.id,
                    "quantity": 1, "quantity_label": "固定工期", "duration_days": step.duration_days, "compatible_resource_types": [],
                    "properties": {**{key: task.properties.get(key) for key in ("roadbed_handover_status", "roadbed_available_date", "roadbed_handover_note")},
                        "wait_days": step.wait_after_days, "accepted_available_offset": 0, "ancillary_resources": "assumed_sufficient", "pavement_node_key": step_keys[step.id]},
                    "pavement_context": task.pavement_context.model_copy(update={"task_kind": "preparation"})})
                schedule.tasks.append(prep)
                link(previous, prep, pending_wait, "pavement_layer_condition")
                earliest(prep, available)
                previous, pending_wait, available = prep, step.wait_after_days, 0
            link(previous, task, pending_wait, "pavement_layer_condition")
            earliest(task, available)
            if task.component_id in terminal_components:
                task.properties.update(wait_days=0, accepted_available_offset=0)
                task.properties.pop("wait_basis", None)
                previous, pending_wait, available = task, 0, 0
                continue
            condition = conditions.get(task.component_id)
            if condition is None:
                task.properties["accepted_available_offset"] = 0
                previous, pending_wait, available = task, 0, 0
                continue
            pending_wait = condition.wait_days
            available = offset(condition.accepted_available_date, task.id)
            task.properties.update(wait_days=pending_wait, accepted_available_offset=available, wait_basis=condition.basis_note)
            previous = task
    for task in schedule.tasks:
        if task.pavement_context.task_kind == "construction" and task.component_id not in terminal_components and not task.properties.get("wait_basis"):
            validation.append(message("PAVEMENT_DATA_INCOMPLETE", "请确认工序关系的技术间歇，0天也需确认。", task.component_id))
    selected_structures = {task.structure_id for task in schedule.tasks}
    for key, rule in rules.items():
        if key not in matched_rules and (rule.structure_id is None or rule.structure_id in selected_structures):
            validation.append(ValidationMessage(level="warning", code="PAVEMENT_RELATION_UNUSED",
                message="配置的前置关系未匹配当前启用工序，请检查停用层或层序变化。", subject_id=rule.structure_id))
    for sequence in settings.fixed_sequences:
        if len(sequence.component_ids) != len(set(sequence.component_ids)):
            validation.append(message("PAVEMENT_LOGIC_CYCLE", "固定施工顺序含重复层。"))
        if any(cid not in all_layers or all_layers[cid][1] != sequence.process_type for cid in sequence.component_ids):
            validation.append(message("PAVEMENT_REFERENCE_INVALID", "固定顺序含不存在或工艺不匹配的层。")); continue
        selected = [by_component[cid] for cid in sequence.component_ids if cid in by_component]
        for first, second in zip(selected, selected[1:]): link(first, second, 0, "pavement_fixed_sequence")
    graph = {t.id: set() for t in schedule.tasks}
    for edge in schedule.precedence_links: graph[edge.successor_id].add(edge.predecessor_id)
    try: list(TopologicalSorter(graph).static_order())
    except CycleError: validation.append(message("PAVEMENT_LOGIC_CYCLE", "工序链存在循环，请检查固定顺序。"))


def _expand_resources(scenario, schedule, validation):
    from ..domain.resource_scope import resolve_effective_resource_pools, normalize_pavement_resource_pools, pavement_resource_matches
    from ..application._scenario import expand_effective_resource_pools
    pools, errors = normalize_pavement_resource_pools(scenario.resource_pools, scenario.process_library, legacy=True, require_transfer=False)
    validation.extend(errors)
    for calendar in scenario.resource_calendars:
        if set(calendar.working_weekdays) != set(range(7)) or calendar.blackout_dates:
            validation.append(message("PAVEMENT_FEATURE_NOT_SUPPORTED", "首版路面使用连续日历天，暂不支持天气/停工日历。", calendar.id))
    resolution = resolve_effective_resource_pools(project_data_version_id=scenario.project_data_version_id,
        bridges=scenario.project.bridges, resource_pools=pools, engineering_domain="pavement")
    resources, messages = expand_effective_resource_pools(resolution.pools)
    validation.extend(resolution.diagnostics)
    validation.extend(messages)
    selected_ids = {t.bridge_id for t in schedule.tasks}
    schedule.resources = [r for r in resources if selected_ids.intersection(r.eligible_workpoint_ids)]
    source_pools = {p.id: p for p in pools}
    effective_pools = {p.effective_pool_id: p for p in resolution.pools}
    for resource in schedule.resources:
        source = source_pools[effective_pools[resource.pool_id].source_pool_id]
        resource.compatible_process_ids = list(source.compatible_process_ids)
        if resource.transfer_days is None:
            validation.append(message("PAVEMENT_TRANSFER_UNCONFIRMED", "请确认可用机组跨段转场天数，零天也需填写。", source.id))
    for task in schedule.tasks:
        if not any(pavement_resource_matches(task, r) for r in schedule.resources):
            validation.append(message("PAVEMENT_RESOURCE_MISSING", f"{task.process_name}没有可用机组，请检查适用工艺、数量和工点范围。", task.component_id))
