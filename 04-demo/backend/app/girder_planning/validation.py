from __future__ import annotations

from collections import Counter, defaultdict

from ..contracts import (
    GirderPlanningReadiness,
    GirderPlanningReadinessCheck,
    PlanningScenarioVersion,
    ProjectDataVersion,
    ValidationMessage,
)


def validate_girder_planning(
    scenario_version: PlanningScenarioVersion,
    project_version: ProjectDataVersion,
) -> GirderPlanningReadiness:
    checks: list[GirderPlanningReadinessCheck] = []
    diagnostics: list[ValidationMessage] = []
    config = scenario_version.girder_planning
    if project_version.status != "confirmed":
        _add(checks, diagnostics, "PROJECT_VERSION_CONFIRMED", "blocking", "方案引用的项目主数据版本尚未确认。", project_version.project_data_version_id)
    else:
        _add(checks, diagnostics, "PROJECT_VERSION_CONFIRMED", "passed", "项目主数据版本已确认。")

    if not config.enabled:
        _add(checks, diagnostics, "GIRDER_SPECIALTY_ENABLED", "passed", "本方案未启用架梁专项，综合排程按原有范围运行。")
        return _result(checks, diagnostics)

    unresolved = [item for item in project_version.field_conflicts if item.severity == "blocking" and item.status == "unresolved"]
    _add(
        checks,
        diagnostics,
        "FIELD_CONFLICTS_RESOLVED",
        "blocking" if unresolved else "passed",
        f"存在 {len(unresolved)} 个未解决的阻断字段冲突。" if unresolved else "字段冲突已解决。",
        *(item.entity_ref for item in unresolved),
    )
    enabled_yards = {item.beam_yard_id: item for item in config.beam_yards if item.enabled}
    enabled_machines = {item.erection_machine_id: item for item in config.erection_machines if item.enabled}
    enabled_routes = [item for item in config.routes if item.enabled]
    _add(checks, diagnostics, "BEAM_YARDS_PRESENT", "passed" if enabled_yards else "blocking", "已配置启用梁场。" if enabled_yards else "启用架梁专项时至少需要一个梁场。")
    _add(checks, diagnostics, "ERECTION_MACHINES_PRESENT", "passed" if enabled_machines else "blocking", "已配置启用架桥机。" if enabled_machines else "启用架梁专项时至少需要一台架桥机。")
    _add(checks, diagnostics, "ROUTES_PRESENT", "passed" if enabled_routes else "blocking", "已配置启用路线。" if enabled_routes else "启用架梁专项时至少需要一条启用路线。")

    yard_route_counts = Counter(item.beam_yard_id for item in enabled_routes)
    multi_line_yards = [yard_id for yard_id, count in yard_route_counts.items() if count > 1]
    _add(
        checks,
        diagnostics,
        "ONE_ACTIVE_LINE_PER_YARD",
        "blocking" if multi_line_yards else "passed",
        "首期同一梁场只能启用一条逻辑架梁线。" if multi_line_yards else "每个梁场最多一条启用逻辑线。",
        *multi_line_yards,
    )

    broken_refs: list[str] = []
    unconfirmed_routes: list[str] = []
    workpoint_by_id = {item.workpoint_id: item for item in project_version.workpoints}
    occurrences: dict[tuple[str, str], list[str]] = defaultdict(list)
    for route in enabled_routes:
        if route.beam_yard_id not in enabled_yards or route.erection_machine_id not in enabled_machines:
            broken_refs.append(route.route_id)
        if not route.confirmed:
            unconfirmed_routes.append(route.route_id)
        machine = enabled_machines.get(route.erection_machine_id)
        if machine and machine.beam_yard_id != route.beam_yard_id:
            broken_refs.append(route.route_id)
        for node in route.nodes:
            workpoint = workpoint_by_id.get(node.workpoint_id)
            if workpoint is None:
                broken_refs.append(node.route_node_id)
            elif workpoint.requires_erection and workpoint.bridge_id:
                occurrences[(workpoint.bridge_id, workpoint.side)].append(route.route_id)
    _add(checks, diagnostics, "ROUTE_REFERENCES_VALID", "blocking" if broken_refs else "passed", "路线存在无效的梁场、设备或工点引用。" if broken_refs else "路线引用有效。", *broken_refs)
    _add(checks, diagnostics, "ROUTES_CONFIRMED", "blocking" if unconfirmed_routes else "passed", "启用路线必须先确认节点顺序。" if unconfirmed_routes else "启用路线节点顺序已确认。", *unconfirmed_routes)

    required_keys = {
        (item.bridge_id, item.side)
        for item in project_version.workpoints
        if item.requires_erection and item.bridge_id and item.side in {"left", "right"}
    }
    missing = sorted(f"{bridge_id}:{side}" for bridge_id, side in required_keys if not occurrences.get((bridge_id, side)))
    _add(checks, diagnostics, "BRIDGE_ROUTE_COVERAGE", "blocking" if missing else "passed", "存在待架桥梁幅别未分配到任何启用路线。" if missing else "待架桥梁幅别均已被启用路线覆盖。", *missing)

    rough = [item.workpoint_id for item in project_version.workpoints if item.requires_erection and (item.rough_granularity or item.side in {"both", "unknown"})]
    _add(
        checks,
        diagnostics,
        "SPAN_GRANULARITY",
        "warning" if rough and config.coarse_mode else ("blocking" if rough else "passed"),
        "存在仅可用于粗粒度预览的桥梁工点。" if rough else "桥梁工点已达到正式分跨联算粒度。",
        *rough,
    )
    _add(
        checks,
        diagnostics,
        "POST_ERECTION_BUFFER_CONFIRMED",
        "passed" if config.parameters.post_erection_buffer_confirmed else "blocking",
        "架后通行缓冲已确认。" if config.parameters.post_erection_buffer_confirmed else "必须确认架后通行缓冲后才能正式计算。",
    )
    return _result(checks, diagnostics)


def _add(
    checks: list[GirderPlanningReadinessCheck],
    diagnostics: list[ValidationMessage],
    code: str,
    status: str,
    message: str,
    *refs: str,
) -> None:
    unique_refs = list(dict.fromkeys(ref for ref in refs if ref))
    checks.append(GirderPlanningReadinessCheck(code=code, status=status, message=message, entity_refs=unique_refs))
    level = "error" if status == "blocking" else ("warning" if status == "warning" else "info")
    diagnostics.append(ValidationMessage(level=level, code=code, message=message, subject_id=unique_refs[0] if unique_refs else None, entity_refs=unique_refs))


def _result(checks: list[GirderPlanningReadinessCheck], diagnostics: list[ValidationMessage]) -> GirderPlanningReadiness:
    if any(item.status == "blocking" for item in checks):
        status = "blocking"
    elif any(item.status == "warning" for item in checks):
        status = "warning"
    else:
        status = "ready"
    return GirderPlanningReadiness(status=status, checks=checks, diagnostics=diagnostics)
