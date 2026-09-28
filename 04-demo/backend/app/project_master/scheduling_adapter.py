from __future__ import annotations

from datetime import date
from typing import Any

from ..contracts import (
    ComponentModel,
    ProjectBridge,
    ProjectModel,
    StructureModel,
    UpperStructureComponent,
    ValidationMessage,
    WorkSection,
)
from ..contracts.project_master import ProjectMasterSnapshot, ProjectMasterVersionSummary
from .definitions import COMPONENT_TYPES as PROJECT_MASTER_COMPONENT_TYPES


SCHEDULING_PROJECTION_VERSION = "project-master-scheduling/v2"


_COMPONENT_TYPES = {
    "pile": "pile",
    "cap": "cap",
    "tie_beam": "ground_tie_beam",
    "pier_body": "pier_body",
    "cap_beam": "cap_beam",
    "precast_beam": "precast_beam",
    "cast_in_place_box_beam": "cast_in_place_box_beam",
    "cast_in_place_continuous_beam": "cast_in_place_continuous_beam",
}
_LOWER_TYPES = {"bridge_pier": "pier", "bridge_abutment": "abutment"}
_UPPER_TYPES = {
    "simple_span": "simple_span",
    "cast_in_place_unit": "cast_in_place_box_beam",
    "continuous_unit": "continuous_beam",
}


def project_model_from_master(
    *,
    version: ProjectMasterVersionSummary,
    snapshot: ProjectMasterSnapshot,
    project_name: str,
    start_date: date,
    engineering_domain: str = "bridge",
) -> tuple[ProjectModel, list[ValidationMessage]]:
    """Create the existing scheduling projection without persisting another snapshot."""

    if version.status != "confirmed":
        raise ValueError("桥梁排程只能使用已确认的项目主数据版本。")
    if engineering_domain == "pavement":
        return _pavement_project(version, snapshot, project_name, start_date)
    diagnostics: list[ValidationMessage] = []
    bridges: list[ProjectBridge] = []
    for workpoint in sorted(snapshot.workpoints, key=lambda item: (item.sort_order, item.workpoint_id)):
        if workpoint.workpoint_type != "bridge":
            diagnostics.append(
                ValidationMessage(
                    level="info",
                    code="PROJECT_MASTER_WORKPOINT_NOT_SCHEDULED",
                    subject_id=workpoint.workpoint_id,
                    entity_refs=[workpoint.workpoint_id],
                    message=f"工点“{workpoint.workpoint_name}”当前不参与桥梁排程。",
                )
            )
            continue
        sections: dict[tuple[str, str], WorkSection] = {}
        for structure in sorted(workpoint.structures, key=lambda item: (item.sort_order, item.structure_id)):
            if not structure.section_code:
                diagnostics.append(
                    _message(
                        "error",
                        "PROJECT_MASTER_SECTION_REQUIRED",
                        f"桥梁结构物“{structure.structure_name}”缺少工区编码。",
                        structure.structure_id,
                    )
                )
                continue
            side = structure.side if structure.side in {"left", "right"} else "none"
            key = (structure.section_code, side)
            section = sections.get(key)
            if section is None:
                section = WorkSection(
                    id=f"{structure.section_code}:{side}",
                    name=structure.section_name or structure.section_code,
                    order=structure.sort_order,
                    side=side,
                )
                sections[key] = section
            if structure.structure_type in _LOWER_TYPES:
                section.structures.append(_lower_structure(structure, diagnostics))
            elif structure.structure_type in _UPPER_TYPES:
                upper = _upper_structure(structure, diagnostics)
                if upper is not None:
                    section.upper_structures.append(upper)
            else:
                diagnostics.append(
                    _message(
                        "warning",
                        "PROJECT_MASTER_STRUCTURE_NOT_SCHEDULED",
                        f"结构物“{structure.structure_name}”类型 {structure.structure_type} 暂不参与桥梁排程。",
                        structure.structure_id,
                    )
                )
        bridges.append(
            ProjectBridge(
                id=workpoint.workpoint_id,
                name=workpoint.workpoint_name,
                order=workpoint.sort_order,
                import_source={
                    "project_data_version_id": version.version_id,
                    "content_fingerprint": version.content_fingerprint,
                    "source_batch_id": version.source_batch_id,
                    "scheduling_projection_version": SCHEDULING_PROJECTION_VERSION,
                },
                work_sections=sorted(sections.values(), key=lambda item: (item.order, item.id)),
            )
        )
    return (
        ProjectModel(
            project_id=version.project_id,
            project_name=project_name,
            start_date=start_date,
            bridges=bridges,
        ),
        diagnostics,
    )


def _pavement_project(version, snapshot, project_name, start_date):
    from .validation import validate_snapshot, PAVEMENT_COMPONENT_TYPES

    diagnostics = []
    for issue in validate_snapshot(snapshot):
        if issue.severity == "error" or issue.issue_code.startswith("PAVEMENT_"):
            diagnostics.append(_message("error", issue.issue_code, issue.message, issue.object_id))
    workpoints = []
    for workpoint in snapshot.workpoints:
        if workpoint.workpoint_type != "pavement":
            diagnostics.append(_message("error", "PAVEMENT_SCOPE_NOT_SUPPORTED", f"工点 {workpoint.workpoint_name} 不属于路面范围。", workpoint.workpoint_id))
            continue
        sections = []
        for structure in sorted(workpoint.structures, key=lambda x: (x.sort_order, x.structure_id)):
            components = []
            handover = {key: _parameters(structure.parameters).get(key) for key in (
                "roadbed_handover_status", "roadbed_available_date", "roadbed_handover_note")}
            for layer in sorted(structure.components, key=lambda x: (x.sort_order, x.component_id)):
                if layer.component_type not in PAVEMENT_COMPONENT_TYPES: continue
                properties = {**_parameters(structure.parameters), **_parameters(layer.parameters), **handover, "unit": layer.unit,
                              "layer_order": layer.sort_order, "source": layer.source.model_dump(mode="json") if layer.source else None}
                components.append(ComponentModel(id=layer.component_id, name=layer.component_name,
                    component_type=layer.component_type, quantity=layer.quantity, quantity_label=f"{layer.quantity:g}{layer.unit}",
                    enabled=layer.enabled, properties=properties))
            sections.append(WorkSection(id=structure.structure_id, name=structure.structure_name,
                side=structure.side if structure.side in {"left", "right"} else "none", order=structure.sort_order,
                structures=[StructureModel(id=structure.structure_id, name=structure.structure_name,
                    structure_type="pavement_section", order=structure.sort_order, properties=handover, components=components)]))
        workpoints.append(ProjectBridge(id=workpoint.workpoint_id, name=workpoint.workpoint_name,
            order=workpoint.sort_order, workpoint_type="pavement", work_sections=sections,
            import_source={"project_data_version_id": version.version_id, "content_fingerprint": version.content_fingerprint}))
    return ProjectModel(project_id=version.project_id, project_name=project_name, start_date=start_date, bridges=workpoints), diagnostics


def _lower_structure(structure, diagnostics: list[ValidationMessage]) -> StructureModel:
    parameters = _parameters(structure.parameters)
    components: list[ComponentModel] = []
    for component in sorted(structure.components, key=lambda item: (item.sort_order, item.component_id)):
        component_type = _projected_lower_component_type(
            structure_type=structure.structure_type,
            component_type=component.component_type,
        )
        if component_type is None:
            diagnostics.append(
                _message(
                    "warning",
                    "PROJECT_MASTER_COMPONENT_NOT_SCHEDULED",
                    f"构件“{component.component_name}”类型 {component.component_type} 暂不参与排程。",
                    component.component_id,
                )
            )
            continue
        properties = _parameters(component.parameters)
        properties.update(
            {
                "unit": component.unit,
                "project_master_structure_id": structure.structure_id,
                "project_master_component_id": component.component_id,
            }
        )
        components.append(
            ComponentModel(
                id=component.component_id,
                name=component.component_name,
                component_type=component_type,
                quantity=component.quantity,
                quantity_label=f"{component.quantity:g}{component.unit}",
                structure_parameter_label=_structure_parameter_label(parameters, properties),
                enabled=component.enabled,
                properties=properties,
            )
        )
    control_level = structure.control_level if structure.control_level in {"control", "key", "normal", "rough"} else None
    return StructureModel(
        id=structure.structure_id,
        name=structure.structure_name,
        structure_type=_LOWER_TYPES[structure.structure_type],
        order=structure.sort_order,
        support_no=str(parameters.get("support_no") or structure.structure_id),
        support_index=_optional_int(parameters.get("support_index")),
        control_level=control_level,
        components=components,
    )


def _projected_lower_component_type(*, structure_type: str, component_type: str) -> str | None:
    if component_type not in PROJECT_MASTER_COMPONENT_TYPES:
        return None
    if structure_type == "bridge_abutment":
        return "pile" if component_type == "pile" else "abutment_body"
    return _COMPONENT_TYPES.get(component_type)


def _upper_structure(structure, diagnostics: list[ValidationMessage]) -> UpperStructureComponent | None:
    parameters = _parameters(structure.parameters)
    required = ["span_index", "span_length_m", "bearing_from", "bearing_to"]
    missing = [code for code in required if parameters.get(code) in {None, ""}]
    if missing:
        diagnostics.append(
            _message(
                "error",
                "PROJECT_MASTER_BRIDGE_PARAMETER_REQUIRED",
                f"结构物“{structure.structure_name}”缺少参数：{', '.join(missing)}。",
                structure.structure_id,
            )
        )
        return None
    span_index = int(parameters["span_index"])
    span_length = float(parameters["span_length_m"])
    from_support = str(parameters["bearing_from"])
    to_support = str(parameters["bearing_to"])
    beam_count = _optional_int(parameters.get("beam_count_per_span"))
    if beam_count is None:
        beam_count = int(
            sum(
                component.quantity
                for component in structure.components
                if component.enabled and component.component_type == "precast_beam"
            )
        ) or None
    control_level = structure.control_level if structure.control_level in {"control", "key", "normal", "rough"} else None
    properties: dict[str, Any] = {
        **parameters,
        "project_master_structure_id": structure.structure_id,
        "section_code": structure.section_code,
    }
    return UpperStructureComponent(
        id=structure.structure_id,
        name=structure.structure_name,
        structure_type=_UPPER_TYPES[structure.structure_type],
        side=structure.side if structure.side in {"left", "right"} else "none",
        span_index=span_index,
        support_range=f"{from_support}~{to_support}",
        span_length_m=span_length,
        beam_count_per_span=beam_count,
        span_group_expression=str(parameters.get("span_expression") or f"{span_length:g}m"),
        structure_parameter_label=str(parameters.get("span_expression") or f"{span_length:g}m"),
        control_level=control_level,
        properties=properties,
    )


def _parameters(items) -> dict[str, Any]:
    return {item.parameter_code: item.value for item in items}


def _structure_parameter_label(*values: dict[str, Any]) -> str | None:
    merged: dict[str, Any] = {}
    for value in values:
        merged.update(value)
    if merged.get("height_m") not in {None, ""}:
        return f"H={float(merged['height_m']):g}m"
    if merged.get("diameter_m") not in {None, ""}:
        return f"D={float(merged['diameter_m']):g}m"
    return None


def _optional_int(value: Any) -> int | None:
    return None if value in {None, ""} else int(value)


def _message(level: str, code: str, message: str, subject_id: str) -> ValidationMessage:
    return ValidationMessage(
        level=level,
        code=code,
        message=message,
        subject_id=subject_id,
        entity_refs=[subject_id],
    )


__all__ = ["SCHEDULING_PROJECTION_VERSION", "project_model_from_master"]
