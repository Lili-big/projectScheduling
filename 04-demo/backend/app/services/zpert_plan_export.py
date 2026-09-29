"""Assemble the zebra plan JSON that export builds before GetStandardInfo."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from ..contracts import GeneratedScheduleInput, PrecedenceLink, ProjectModel, ScheduleResult, ScheduledTask

DEFAULT_PLAN_NAME = "斑马进度计划"
EXPORTABLE_STATUSES = {"OPTIMAL", "FEASIBLE"}
_WORK_DAY_SECONDS = 28800
_CST = timezone(timedelta(hours=8))
_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|\r\n]+')


class ZpertPlanExportError(ValueError):
    """The displayed solve result cannot be written as a zebra plan."""


class ZpertPlanExportRequest(BaseModel):
    project: ProjectModel
    generated: GeneratedScheduleInput
    result: ScheduleResult
    plan_name: str | None = None


def export_zpert_plan(
    project: ProjectModel,
    generated: GeneratedScheduleInput,
    result: ScheduleResult,
    plan_name: str | None = None,
) -> tuple[dict[str, Any], str]:
    if result.status not in EXPORTABLE_STATUSES or not result.tasks:
        raise ZpertPlanExportError("当前结果没有可导出的施工计划。")
    name = _plan_name(project, plan_name)
    tasks = _task_documents(project, generated, result.tasks, name)
    return {"tasks": tasks}, _download_name(name)


def product_date_to_zpert_time(value: date) -> int:
    """Match JNAUtil.productTime2ZpertTime on a UTC+8 JVM.

    Local midnight plus 28800 seconds is the UTC midnight of the same calendar day.
    """
    local_midnight = datetime(value.year, value.month, value.day, tzinfo=_CST)
    return int(local_midnight.timestamp()) + _WORK_DAY_SECONDS


def _plan_name(project: ProjectModel, plan_name: str | None) -> str:
    chosen = (plan_name or "").strip() or (project.project_name or "").strip()
    return chosen or DEFAULT_PLAN_NAME


def _download_name(plan_name: str) -> str:
    cleaned = _INVALID_FILENAME.sub("_", plan_name).strip(" .") or DEFAULT_PLAN_NAME
    return f"{cleaned}.json"


def _task_documents(
    project: ProjectModel,
    generated: GeneratedScheduleInput,
    tasks: list[ScheduledTask],
    plan_name: str,
) -> list[dict[str, Any]]:
    catalog = _ProjectCatalog(project)
    roots = _collapse_same_name_summaries(_summary_nodes(tasks, catalog))
    _assign_ids(roots)
    zebra_by_task_id = {
        node.task.id: node.zebra_id
        for node in _walk(roots)
        if node.task is not None and node.zebra_id is not None
    }
    depends_by_task_id = _depends_by_successor(generated.schedule_input.precedence_links, zebra_by_task_id)
    earliest = min(task.start_date for task in tasks)
    documents = [_root_document(plan_name, earliest)]
    for node in _walk(roots):
        documents.append(_node_document(node, depends_by_task_id))
    return documents


class _Node:
    def __init__(self, name: str, *, task: ScheduledTask | None = None, children: list[_Node] | None = None):
        self.name = name
        self.task = task
        self.children = children or []
        self.zebra_id: int | None = None
        self.parent_id: int | None = None
        self.level = 1
        self.start_date = task.start_date if task is not None else _earliest(self.children)

    @property
    def is_task(self) -> bool:
        return self.task is not None


def _earliest(nodes: list[_Node]) -> date | None:
    dates = [node.start_date for node in nodes if node.start_date is not None]
    return min(dates) if dates else None


class _ProjectCatalog:
    def __init__(self, project: ProjectModel):
        self.bridge_names: dict[str, str] = {}
        self.bridge_order: dict[str, tuple[int, int]] = {}
        self.section_names: dict[str, str] = {}
        self.section_order: dict[str, tuple[int, int]] = {}
        self.structure_names: dict[str, str] = {}
        self.structure_order: dict[str, tuple[int, int]] = {}
        self.component_names: dict[str, str] = {}
        for bridge_index, bridge in enumerate(project.bridges):
            self.bridge_names[bridge.id] = bridge.name or bridge.id
            self.bridge_order[bridge.id] = (bridge.order, bridge_index)
            for section_index, section in enumerate(bridge.work_sections):
                self.section_names.setdefault(section.id, section.name or section.id)
                self.section_order.setdefault(section.id, (section.order, section_index))
                for structure_index, structure in enumerate(section.structures):
                    self.structure_names.setdefault(structure.id, structure.name or structure.id)
                    self.structure_order.setdefault(structure.id, (structure.order, structure_index))
                    for component in structure.components:
                        self.component_names.setdefault(component.id, component.name or component.id)
                for upper_index, upper in enumerate(section.upper_structures):
                    self.structure_names.setdefault(upper.id, upper.name or upper.id)
                    self.structure_order.setdefault(upper.id, (upper.span_index, upper_index))


def _summary_nodes(tasks: list[ScheduledTask], catalog: _ProjectCatalog) -> list[_Node]:
    return _group(
        tasks,
        key_fn=lambda task: _blank(task.bridge_id),
        name_fn=lambda key, _grouped: catalog.bridge_names.get(key, key),
        sort_fn=lambda key: (*catalog.bridge_order.get(key, (10**9, 10**8)), key),
        child_fn=lambda grouped: _group(
            grouped,
            key_fn=lambda task: _blank(task.work_section_id),
            name_fn=lambda key, _section_tasks: catalog.section_names.get(key, key),
            sort_fn=lambda key: (*catalog.section_order.get(key, (10**9, 10**8)), key),
            child_fn=lambda section_tasks: _group(
                section_tasks,
                key_fn=lambda task: task.structure_id,
                name_fn=lambda key, structure_tasks: catalog.structure_names.get(key, _structure_label(structure_tasks)),
                sort_fn=lambda key: (*catalog.structure_order.get(key, (10**9, 10**8)), key),
                child_fn=lambda structure_tasks: _task_nodes(structure_tasks, catalog),
            ),
        ),
    )


def _group(tasks, *, key_fn, name_fn, sort_fn, child_fn) -> list[_Node]:
    grouped: dict[str | None, list[ScheduledTask]] = defaultdict(list)
    for task in tasks:
        grouped[key_fn(task)].append(task)
    nodes: list[_Node] = []
    for key in sorted(grouped, key=lambda item: ((1, "") if item is None else (0, sort_fn(item)))):
        children = child_fn(grouped[key])
        if key is None:
            nodes.extend(children)
            continue
        nodes.append(_Node(name_fn(key, grouped[key]), children=children))
    return nodes


def _collapse_same_name_summaries(nodes: list[_Node], parent_name: str | None = None) -> list[_Node]:
    collapsed: list[_Node] = []
    for node in nodes:
        if node.task is None:
            node.children = _collapse_same_name_summaries(node.children, node.name)
        if node.task is None and parent_name is not None and node.name == parent_name:
            collapsed.extend(node.children)
        else:
            collapsed.append(node)
    return collapsed


def _task_nodes(tasks: list[ScheduledTask], catalog: _ProjectCatalog) -> list[_Node]:
    ordered = sorted(tasks, key=lambda task: (task.sequence_order, task.id))
    return [_Node(_leaf_name(task, catalog), task=task) for task in ordered]


def _leaf_name(task: ScheduledTask, catalog: _ProjectCatalog) -> str:
    if task.structure_type != "pavement_section":
        return task.name
    if task.pavement_context is not None and task.pavement_context.task_kind == "preparation" and task.process_name:
        return task.process_name
    component_name = catalog.component_names.get(task.component_id or "")
    if component_name:
        return component_name
    prefix = f"{task.structure_name} · "
    if task.structure_name and task.name.startswith(prefix):
        return task.name[len(prefix):]
    return task.name


def _structure_label(tasks: list[ScheduledTask]) -> str:
    ordered = sorted(tasks, key=lambda task: (task.sequence_order, task.id))
    return ordered[0].structure_name or ordered[0].structure_id


def _assign_ids(nodes: list[_Node], parent_id: int = 0, level: int = 1, counter: list[int] | None = None) -> None:
    if counter is None:
        counter = [1]
    for node in nodes:
        node.zebra_id = counter[0]
        counter[0] += 1
        node.parent_id = parent_id
        node.level = level
        node.start_date = node.task.start_date if node.task is not None else _earliest(node.children)
        _assign_ids(node.children, node.zebra_id, level + 1, counter)


def _walk(nodes: list[_Node]) -> list[_Node]:
    ordered: list[_Node] = []
    for node in nodes:
        ordered.append(node)
        ordered.extend(_walk(node.children))
    return ordered


def _depends_by_successor(links: list[PrecedenceLink], zebra_by_task_id: dict[str, int]) -> dict[str, str]:
    segments: dict[str, list[str]] = defaultdict(list)
    for link in links:
        predecessor_id = zebra_by_task_id.get(link.predecessor_id)
        if predecessor_id is None or link.successor_id not in zebra_by_task_id:
            continue
        relationship = link.relationship or "FS"
        lag = link.lag_days or 0
        sign = "+" if lag >= 0 else ""
        segments[link.successor_id].append(f"{predecessor_id}{relationship}{sign}{lag}")
    return {task_id: ",".join(parts) for task_id, parts in segments.items() if parts}


def _root_document(plan_name: str, earliest: date) -> dict[str, Any]:
    return {
        "id": 0,
        "name": plan_name,
        "level": 0,
        "ask_start_time": product_date_to_zpert_time(earliest),
    }


def _node_document(node: _Node, depends_by_task_id: dict[str, str]) -> dict[str, Any]:
    document: dict[str, Any] = {
        "id": node.zebra_id,
        "name": node.name,
        "level": node.level,
        "parent_id": node.parent_id,
    }
    if node.task is not None:
        document["duration"] = node.task.duration_days * _WORK_DAY_SECONDS
    if node.start_date is not None:
        zebra_time = product_date_to_zpert_time(node.start_date)
        document["plan_start_time"] = zebra_time
        document["ask_start_time"] = zebra_time
    if node.task is not None:
        depends = depends_by_task_id.get(node.task.id)
        if depends:
            document["depends"] = depends
    return document


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None
