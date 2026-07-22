from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError

from ..contracts import (
    AiWorkpointResourceInitializationResponse,
    AiWorkpointResourceInitializationSummary,
    AiWorkpointResourceRecommendation,
    ResourcePool,
    ScenarioInput,
    ValidationMessage,
)
from ..scenario_data import derive_resource_catalog, derive_workpoint_possible_resource_types
from .ai_resource_explainer import (
    generate_workpoint_resource_initialization_payload,
    strict_workpoint_resource_llm_config_status,
)


_PARAMETER_KEYS = {
    "beam_count_per_span",
    "diameter_m",
    "height_m",
    "length_m",
    "pile_count",
    "span_length_m",
    "standard_section_height_m",
    "width_m",
}


def initialize_workpoint_resources(scenario: ScenarioInput) -> AiWorkpointResourceInitializationResponse:
    version_id = (scenario.project_data_version_id or "").strip()
    if not version_id:
        raise ValueError("AI resource initialization requires project_data_version_id.")
    bridges = sorted(scenario.project.bridges, key=lambda item: (item.order, item.id))
    if not bridges:
        raise ValueError("The current project data version has no schedulable bridge workpoints.")

    original_resources = _resource_snapshot(scenario.resource_pools)
    catalog = {str(item["resource_type"]): item for item in derive_resource_catalog(scenario)}
    shared_types = {
        pool.type
        for pool in scenario.resource_pools
        if pool.scope_mode == "PROJECT_SHARED"
    }
    existing_local_keys = {
        (pool.workpoint_id, pool.type)
        for pool in scenario.resource_pools
        if pool.scope_mode == "WORKPOINT_EXCLUSIVE" and pool.workpoint_id
    }

    workpoint_contexts: list[dict[str, Any]] = []
    diagnostics: list[ValidationMessage] = []
    candidate_lookup: dict[str, dict[str, dict[str, Any]]] = {}
    unchanged_ids: set[str] = set()
    for bridge in bridges:
        structures = _structure_summaries(bridge, scenario)
        possible_types = derive_workpoint_possible_resource_types(scenario, bridge.id)
        candidates = [
            dict(catalog[resource_type])
            for resource_type in possible_types
            if resource_type in catalog
            and resource_type not in shared_types
            and (bridge.id, resource_type) not in existing_local_keys
        ]
        candidates.sort(key=lambda item: str(item["resource_type"]))
        if not structures:
            diagnostics.append(
                ValidationMessage(
                    level="warning",
                    code="AI_RESOURCE_INITIALIZER_STRUCTURE_EMPTY",
                    subject_id=bridge.id,
                    entity_refs=[bridge.id],
                    message=f"Workpoint {bridge.name or bridge.id} has no usable structure summary and was not sent to the model.",
                )
            )
            unchanged_ids.add(bridge.id)
            continue
        if not candidates:
            diagnostics.append(
                ValidationMessage(
                    level="info",
                    code="AI_RESOURCE_INITIALIZER_NO_MISSING_CANDIDATE",
                    subject_id=bridge.id,
                    entity_refs=[bridge.id],
                    message=f"Workpoint {bridge.name or bridge.id} has no missing local resource candidate.",
                )
            )
            unchanged_ids.add(bridge.id)
            continue
        candidate_lookup[bridge.id] = {
            str(candidate["resource_type"]): candidate for candidate in candidates
        }
        workpoint_contexts.append(
            {
                "workpoint_id": bridge.id,
                "workpoint_name": bridge.name,
                "structures": structures,
                "candidates": candidates,
            }
        )

    context = {
        "project_data_version_id": version_id,
        "project_name": scenario.project.project_name,
        "workpoints": workpoint_contexts,
    }
    input_fingerprint = _input_fingerprint(scenario, context)
    if workpoint_contexts:
        raw_recommendations, llm_status = generate_workpoint_resource_initialization_payload(context)
        recommendations, validation_errors = _validate_recommendations(raw_recommendations, candidate_lookup)
        _assert_resource_snapshot_unchanged(scenario.resource_pools, original_resources)
        if validation_errors:
            raw_recommendations, llm_status = generate_workpoint_resource_initialization_payload(
                context,
                validation_errors=validation_errors,
            )
            recommendations, validation_errors = _validate_recommendations(raw_recommendations, candidate_lookup)
            _assert_resource_snapshot_unchanged(scenario.resource_pools, original_resources)
        if validation_errors:
            codes = ", ".join(str(item["code"]) for item in validation_errors)
            raise ValueError(f"AI resource initialization output remained invalid after one correction: {codes}.")
    else:
        llm_status = strict_workpoint_resource_llm_config_status()
        recommendations = []

    additions: list[ResourcePool] = []
    recommended_ids: set[str] = set()
    for recommendation in recommendations:
        for resource in recommendation.resources:
            candidate = candidate_lookup[recommendation.workpoint_id][resource.resource_type]
            additions.append(
                ResourcePool(
                    id=_local_pool_id(recommendation.workpoint_id, resource.resource_type),
                    type=resource.resource_type,
                    label=str(candidate["label"]),
                    resource_mode="LIMITED",
                    scope_mode="WORKPOINT_EXCLUSIVE",
                    workpoint_id=recommendation.workpoint_id,
                    quantity=resource.quantity,
                    max_quantity=resource.max_quantity,
                    authorized_workpoint_ids=None,
                    workpoint_overrides=[],
                    calendar_id=str(candidate["default_calendar_id"]),
                    enabled=True,
                    compatible_process_ids=list(candidate["applicable_process_ids"]),
                )
            )
            recommended_ids.add(recommendation.workpoint_id)
        if not recommendation.resources:
            unchanged_ids.add(recommendation.workpoint_id)

    additions.sort(key=lambda pool: (pool.workpoint_id or "", pool.type, pool.id))
    _assert_additions_do_not_conflict(additions, scenario.resource_pools)
    _assert_resource_snapshot_unchanged(scenario.resource_pools, original_resources)
    unchanged_ids.update(bridge.id for bridge in bridges if bridge.id not in recommended_ids)
    return AiWorkpointResourceInitializationResponse(
        project_data_version_id=version_id,
        input_fingerprint=input_fingerprint,
        resource_pools_to_add=additions,
        summary=AiWorkpointResourceInitializationSummary(
            workpoint_count=len(bridges),
            recommended_workpoint_count=len(recommended_ids),
            unchanged_workpoint_ids=sorted(unchanged_ids),
            added_resource_count=len(additions),
        ),
        llm_config_status=llm_status,
        diagnostics=diagnostics,
    )


def _validate_recommendations(
    raw_recommendations: list[dict[str, Any]],
    candidate_lookup: dict[str, dict[str, dict[str, Any]]],
) -> tuple[list[AiWorkpointResourceRecommendation], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    recommendations: list[AiWorkpointResourceRecommendation] = []
    for index, raw in enumerate(raw_recommendations):
        try:
            recommendations.append(AiWorkpointResourceRecommendation.model_validate(raw))
        except ValidationError as exc:
            errors.append(
                {
                    "code": "AI_RESOURCE_RECOMMENDATION_SCHEMA_INVALID",
                    "record_index": index,
                    "details": exc.errors(include_url=False, include_input=False),
                }
            )
    if errors:
        return [], errors

    expected_ids = set(candidate_lookup)
    actual_ids = [item.workpoint_id for item in recommendations]
    if len(set(actual_ids)) != len(actual_ids):
        errors.append({"code": "AI_RESOURCE_RECOMMENDATION_WORKPOINT_DUPLICATE"})
    missing_ids = sorted(expected_ids - set(actual_ids))
    extra_ids = sorted(set(actual_ids) - expected_ids)
    if missing_ids:
        errors.append({"code": "AI_RESOURCE_RECOMMENDATION_WORKPOINT_MISSING", "workpoint_ids": missing_ids})
    if extra_ids:
        errors.append({"code": "AI_RESOURCE_RECOMMENDATION_WORKPOINT_UNKNOWN", "workpoint_ids": extra_ids})
    for recommendation in recommendations:
        candidates = candidate_lookup.get(recommendation.workpoint_id, {})
        unknown_types = sorted(
            resource.resource_type
            for resource in recommendation.resources
            if resource.resource_type not in candidates
        )
        if unknown_types:
            errors.append(
                {
                    "code": "AI_RESOURCE_RECOMMENDATION_TYPE_NOT_ALLOWED",
                    "workpoint_id": recommendation.workpoint_id,
                    "resource_types": unknown_types,
                }
            )
    return (recommendations if not errors else []), errors


def _structure_summaries(bridge: Any, scenario: ScenarioInput) -> list[dict[str, Any]]:
    aggregates: dict[tuple[str, str, str, str, str], float] = defaultdict(float)
    for section in sorted(bridge.work_sections, key=lambda item: (item.order, item.id)):
        for structure in sorted(section.structures, key=lambda item: (item.order, item.id)):
            for component in sorted(structure.components, key=lambda item: item.id):
                if not component.enabled or component.quantity <= 0:
                    continue
                process = _process_for_component(component, scenario)
                unit = str(component.properties.get("unit") or component.quantity_label or "item")
                parameters = _parameter_summary(component.properties)
                key = (
                    structure.structure_type,
                    component.component_type,
                    process.id if process else "",
                    unit,
                    json.dumps(parameters, ensure_ascii=False, sort_keys=True),
                )
                aggregates[key] += float(component.quantity)
        for upper in sorted(section.upper_structures, key=lambda item: (item.span_index, item.id)):
            parameters = _parameter_summary(
                {
                    **upper.properties,
                    "span_length_m": upper.span_length_m,
                    "beam_count_per_span": upper.beam_count_per_span,
                }
            )
            component_type = _upper_component_type(upper)
            process = _default_process(component_type, scenario) if component_type else None
            key = (
                upper.structure_type,
                component_type or "upper_structure",
                process.id if process else "",
                "span",
                json.dumps(parameters, ensure_ascii=False, sort_keys=True),
            )
            aggregates[key] += 1
    return [
        {
            "structure_type": key[0],
            "component_type": key[1],
            "process_id": key[2] or None,
            "quantity": quantity,
            "unit": key[3],
            "parameter_summary": json.loads(key[4]),
        }
        for key, quantity in sorted(aggregates.items(), key=lambda item: item[0])
    ]


def _process_for_component(component: Any, scenario: ScenarioInput) -> Any | None:
    candidates = [
        process for process in scenario.process_library if process.component_type == component.component_type
    ]
    if component.method_id:
        matched = next(
            (
                process
                for process in candidates
                if process.id == component.method_id or process.method_id == component.method_id
            ),
            None,
        )
        if matched is not None:
            return matched
    return next((process for process in candidates if process.is_default), candidates[0] if candidates else None)


def _default_process(component_type: str, scenario: ScenarioInput) -> Any | None:
    candidates = [
        process for process in scenario.process_library if process.component_type == component_type
    ]
    return next((process for process in candidates if process.is_default), candidates[0] if candidates else None)


def _upper_component_type(upper: Any) -> str | None:
    code = str(upper.properties.get("structure_code") or "")
    text = f"{code} {upper.structure_type}".lower()
    if "continuous" in text or "连续" in text:
        return "cast_in_place_continuous_beam"
    if "castinplace" in text.replace("_", "") or "现浇" in text:
        return "cast_in_place_box_beam"
    if upper.properties.get("resource_type"):
        return "precast_beam"
    return None


def _parameter_summary(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in sorted(properties.items())
        if key in _PARAMETER_KEYS and value is not None and isinstance(value, (str, int, float, bool))
    }


def _local_pool_id(workpoint_id: str, resource_type: str) -> str:
    safe = "-_.!~*'()"
    return f"workpoint-{quote(workpoint_id, safe=safe)}-{quote(resource_type, safe=safe)}"


def _assert_additions_do_not_conflict(additions: list[ResourcePool], existing: list[ResourcePool]) -> None:
    existing_ids = {pool.id for pool in existing}
    existing_keys = {(pool.workpoint_id, pool.type) for pool in existing if pool.workpoint_id}
    addition_ids = [pool.id for pool in additions]
    addition_keys = [(pool.workpoint_id, pool.type) for pool in additions]
    if len(set(addition_ids)) != len(addition_ids) or len(set(addition_keys)) != len(addition_keys):
        raise ValueError("AI resource initialization produced duplicate resource pools.")
    if existing_ids.intersection(addition_ids) or existing_keys.intersection(addition_keys):
        raise ValueError("AI resource initialization conflicts with an existing resource pool.")


def _resource_snapshot(pools: list[ResourcePool]) -> str:
    return json.dumps(
        [pool.model_dump(mode="json") for pool in pools],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _assert_resource_snapshot_unchanged(pools: list[ResourcePool], expected: str) -> None:
    if _resource_snapshot(pools) != expected:
        raise ValueError("Existing resource pools changed during AI resource initialization.")


def _input_fingerprint(scenario: ScenarioInput, context: dict[str, Any]) -> str:
    payload = {
        "context": context,
        "process_library": [item.model_dump(mode="json") for item in scenario.process_library],
        "resource_pools": [item.model_dump(mode="json") for item in scenario.resource_pools],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
