from __future__ import annotations

from typing import Any
from uuid import uuid4

from ..contracts.project_master import ProjectMasterDiffEntry, ProjectMasterSnapshot


def diff_snapshots(
    base: ProjectMasterSnapshot | None,
    candidate: ProjectMasterSnapshot,
) -> list[ProjectMasterDiffEntry]:
    before = _flatten(base or ProjectMasterSnapshot())
    after = _flatten(candidate)
    entries: list[ProjectMasterDiffEntry] = []
    for key in sorted(before.keys() | after.keys()):
        object_kind, object_id = key
        previous = before.get(key)
        current = after.get(key)
        if previous is None:
            entries.append(_entry(object_kind, object_id, "added", None, None, current))
            continue
        if current is None:
            entries.append(_entry(object_kind, object_id, "deleted", None, previous, None))
            continue
        fields = sorted(previous.keys() | current.keys())
        for field in fields:
            if previous.get(field) != current.get(field):
                entries.append(_entry(object_kind, object_id, "modified", field, previous.get(field), current.get(field)))
    return entries


def _flatten(snapshot: ProjectMasterSnapshot) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for placement in snapshot.route_placements:
        result[("route_placement", placement.placement_id)] = placement.model_dump(
            exclude={"source"}, mode="json"
        )
    for workpoint in snapshot.workpoints:
        result[("workpoint", workpoint.workpoint_id)] = workpoint.model_dump(
            exclude={"source", "structures"}, mode="json"
        )
        for structure in workpoint.structures:
            result[("structure", structure.structure_id)] = structure.model_dump(
                exclude={"source", "parameters", "components"}, mode="json"
            )
            for parameter in structure.parameters:
                result[("parameter", f"structure:{structure.structure_id}:{parameter.parameter_code}")] = {
                    "owner_kind": "structure",
                    "owner_id": structure.structure_id,
                    "parameter_code": parameter.parameter_code,
                    "value_type": parameter.value_type,
                    "value": parameter.value,
                    "unit": parameter.unit,
                }
            for component in structure.components:
                result[("component", component.component_id)] = component.model_dump(
                    exclude={"source", "parameters"}, mode="json"
                )
                for parameter in component.parameters:
                    result[("parameter", f"component:{component.component_id}:{parameter.parameter_code}")] = {
                        "owner_kind": "component",
                        "owner_id": component.component_id,
                        "parameter_code": parameter.parameter_code,
                        "value_type": parameter.value_type,
                        "value": parameter.value,
                        "unit": parameter.unit,
                    }
    return result


def _entry(kind: str, object_id: str, change: str, field: str | None, before: Any, after: Any) -> ProjectMasterDiffEntry:
    return ProjectMasterDiffEntry(
        diff_id=f"pmd-{uuid4().hex}",
        object_kind=kind,
        object_id=object_id,
        change_type=change,
        field_name=field,
        before_value=before,
        after_value=after,
    )


__all__ = ["diff_snapshots"]
