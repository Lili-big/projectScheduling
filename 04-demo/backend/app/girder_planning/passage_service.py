from __future__ import annotations

from datetime import date, timedelta

from ..contracts import (
    ErectionOwnership,
    GeneratedScheduleInput,
    GirderSpanPlan,
    PassageActual,
    PassageReleaseResult,
    ProjectDataVersion,
    ScheduleResult,
    ValidationMessage,
)


def calculate_passage_releases(
    project_version: ProjectDataVersion,
    ownerships: list[ErectionOwnership],
    span_plans: list[GirderSpanPlan],
    *,
    post_erection_buffer_days: int,
    generated: GeneratedScheduleInput | None = None,
    schedule_result: ScheduleResult | None = None,
    actuals: list[PassageActual] | None = None,
) -> tuple[list[PassageReleaseResult], list[ValidationMessage]]:
    owner_by_key = {(item.bridge_id, item.side): item for item in ownerships}
    finish_by_key: dict[tuple[str, str], date] = {}
    for plan in span_plans:
        finish = plan.planned_finish_date or plan.earliest_start_date
        key = (plan.bridge_id, _side_for_section(project_version, plan.work_section_id))
        finish_by_key[key] = max(finish_by_key.get(key, finish), finish)
    actual_by_workpoint = {item.workpoint_id: item for item in actuals or []}
    results: list[PassageReleaseResult] = []
    diagnostics: list[ValidationMessage] = []

    for workpoint in project_version.workpoints:
        linked_dates, unresolved = resolve_passage_condition_refs(workpoint, generated, schedule_result)
        key = (workpoint.bridge_id, workpoint.side)
        owner = owner_by_key.get(key) if workpoint.bridge_id else None
        erection_finish = finish_by_key.get(key)
        erection_buffer_date = erection_finish + timedelta(days=post_erection_buffer_days) if owner and erection_finish else None
        candidates: list[tuple[str, date]] = []
        if erection_buffer_date:
            candidates.append(("erection_buffer", erection_buffer_date))
        if workpoint.explicit_readiness_date:
            candidates.append(("explicit_readiness", workpoint.explicit_readiness_date))
        candidates.extend(("linked_condition", value) for value in linked_dates.values())
        actual = actual_by_workpoint.get(workpoint.workpoint_id)
        if actual and actual.status == "open" and actual.actual_open_date:
            candidates.append(("actual_fact", actual.actual_open_date))
        if unresolved:
            diagnostics.append(_message("error", "GIRDER_PASSAGE_REF_UNRESOLVED", f"工点 {workpoint.name} 的通行条件无法解析：{', '.join(unresolved)}。", workpoint.workpoint_id))
            results.append(
                PassageReleaseResult(
                    workpoint_id=workpoint.workpoint_id,
                    erection_buffer_date=erection_buffer_date,
                    explicit_readiness_date=workpoint.explicit_readiness_date,
                    linked_condition_finish_dates=linked_dates,
                    controlling_source="none",
                    status="blocked",
                )
            )
            continue
        controlling_source, passable_date = max(candidates, key=lambda item: item[1]) if candidates else ("none", None)
        results.append(
            PassageReleaseResult(
                workpoint_id=workpoint.workpoint_id,
                passable_date=passable_date,
                erection_buffer_date=erection_buffer_date,
                explicit_readiness_date=workpoint.explicit_readiness_date,
                linked_condition_finish_dates=linked_dates,
                controlling_source=controlling_source,
                status="ready" if passable_date else "waiting",
            )
        )
    return results, diagnostics


def resolve_passage_condition_refs(workpoint, generated, schedule_result) -> tuple[dict[str, date], list[str]]:
    if not workpoint.linked_condition_refs:
        return {}, []
    task_by_structure: dict[str, list[str]] = {}
    task_by_upper: dict[str, list[str]] = {}
    if generated:
        for task in generated.schedule_input.tasks:
            task_by_structure.setdefault(task.structure_id, []).append(task.id)
            upper_id = task.properties.get("upper_structure_id")
            if upper_id:
                task_by_upper.setdefault(str(upper_id), []).append(task.id)
    finish_by_task = {item.id: item.finish_date for item in schedule_result.tasks} if schedule_result else {}
    milestone_dates = {item.id: item.actual_date for item in schedule_result.milestone_results if item.actual_date} if schedule_result else {}
    resolved: dict[str, date] = {}
    unresolved: list[str] = []
    for ref in workpoint.linked_condition_refs:
        key = f"{ref.ref_type}:{ref.entity_id}"
        if ref.ref_type == "milestone":
            value = milestone_dates.get(ref.entity_id)
            if value:
                resolved[key] = value
            else:
                unresolved.append(key)
            continue
        task_ids = task_by_structure.get(ref.entity_id, []) if ref.ref_type == "structure" else task_by_upper.get(ref.entity_id, [])
        dates = [finish_by_task[task_id] for task_id in task_ids if task_id in finish_by_task]
        if dates:
            resolved[key] = max(dates)
        else:
            unresolved.append(key)
    return resolved, unresolved


def _side_for_section(project_version: ProjectDataVersion, work_section_id: str) -> str:
    for bridge in project_version.project.bridges:
        for section in bridge.work_sections:
            if section.id == work_section_id:
                return section.side if section.side in {"left", "right"} else "unknown"
    return "unknown"


def _message(level: str, code: str, message: str, *refs: str) -> ValidationMessage:
    return ValidationMessage(level=level, code=code, message=message, subject_id=refs[0] if refs else None, entity_refs=list(refs))
