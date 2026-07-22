from __future__ import annotations

from typing import get_args

from ...contracts import ComponentType, MilestoneConstraint, Task


def is_lower_or_cast_in_place_beam_task(task: Task) -> bool:
    return task.structure_type in {"pier", "abutment"} or task.component_type in {
        "cast_in_place_continuous_beam",
        "cast_in_place_box_beam",
    }


def task_ids_for_milestone(milestone: MilestoneConstraint, tasks: list[Task]) -> list[str]:
    related_ids = {
        task.id
        for task in tasks
        if task.structure_id in set(milestone.related_structure_ids)
    }
    if milestone.scope_type == "project":
        return sorted(related_ids | {task.id for task in tasks if is_lower_or_cast_in_place_beam_task(task)})
    if milestone.scope_type == "bridge":
        return sorted(related_ids | {
            task.id
            for task in tasks
            if task.bridge_id == milestone.scope_id and is_lower_or_cast_in_place_beam_task(task)
        })
    if milestone.scope_type == "work_section":
        return sorted(related_ids | {
            task.id
            for task in tasks
            if task.work_section_id == milestone.scope_id and is_lower_or_cast_in_place_beam_task(task)
        })
    if milestone.scope_type == "structure":
        return sorted(related_ids | {task.id for task in tasks if task.structure_id == milestone.scope_id})
    if milestone.scope_type == "component":
        if milestone.scope_id in get_args(ComponentType):
            return sorted(related_ids | {task.id for task in tasks if task.component_type == milestone.scope_id})
        return sorted(related_ids | {
            task.id
            for task in tasks
            if task.component_id == milestone.scope_id or task.id == milestone.scope_id
        })
    return sorted(related_ids)
