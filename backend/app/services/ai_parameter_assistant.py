from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import date
from typing import Any

from pydantic import ValidationError

from ..process_nl import ensure_process_for_assignment, extract_process_method_suggestions
from ..contracts import (
    AiParameterApplyRequest,
    AiParameterApplyResponse,
    AiParameterAppliedItem,
    AiParameterApplicationSummary,
    AiParameterCandidateAddition,
    AiParameterConflictGroup,
    AiParameterManualValue,
    AiParameterParseResponse,
    AiParameterSourceEvidence,
    AiParameterSuggestion,
    AiParameterUploadedMaterialSummary,
    MilestoneConstraint,
    ProcessTemplate,
    ProductivityOption,
    ResourcePool,
    ScenarioInput,
    ValidationMessage,
)
from .ai_parameter_ai_client import AiParameterAiClient, AiParameterAssistantConfigError, get_ai_parameter_client
from .ai_parameter_materials import AiParameterMaterialError, collect_ai_parameter_materials
from .ai_parameter_store import AiParameterStore, AiParameterStoreExpiredError, default_ai_parameter_store


class AiParameterAssistantError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_ai_parameter_assistant(
    fields: dict[str, str],
    files: dict[str, dict[str, bytes | str]],
    *,
    client: AiParameterAiClient | None = None,
    store: AiParameterStore = default_ai_parameter_store,
) -> AiParameterParseResponse:
    scenario = _scenario_from_fields(fields)
    materials, material_warnings = collect_ai_parameter_materials(fields, files)
    parsed_materials = [material for material in materials if material.parse_status != "failed"]
    if not parsed_materials:
        raise AiParameterAssistantError("所有资料都解析失败，请检查文件格式或重新上传。", status_code=422)

    if fields.get("assistant_mode", "parameter") == "process_method":
        material_by_id = {material.material_id: material for material in materials}
        prompt = "\n".join(
            (material.content_text or material.source_summary).strip()
            for material in parsed_materials
            if (material.content_text or material.source_summary).strip()
        )
        raw_suggestions, payload_warnings = extract_process_method_suggestions(
            scenario,
            prompt,
            material_id=parsed_materials[0].material_id,
        )
        suggestions = _standardize_suggestions(raw_suggestions, scenario, material_by_id)
        suggestions, conflict_groups = _apply_conflicts_and_status(suggestions)
        summaries = [material.summary() for material in materials]
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        entry = store.put(
            run_id=run_id,
            scenario_id=scenario.scenario_id,
            suggestions=suggestions,
            conflict_groups=conflict_groups,
            candidate_additions=[],
            material_summaries=summaries,
        )
        warnings = [*material_warnings, *[ValidationMessage(level="warning", message=warning) for warning in payload_warnings]]
        return AiParameterParseResponse(
            run_id=run_id,
            status="partially_failed" if any(summary.parse_status == "failed" for summary in summaries) else "completed",
            material_count=len(materials),
            total_size_bytes=sum(material.size_bytes for material in materials),
            suggestion_count=len(suggestions),
            material_summaries=summaries,
            errors=[],
            warnings=warnings,
            expires_at=entry.expires_at,
            suggestions=suggestions,
            conflict_groups=conflict_groups,
            candidate_additions=[],
            manual_completion_count=sum(1 for item in suggestions if item.status == "needs_manual_input"),
        )

    try:
        payload = (client or get_ai_parameter_client()).understand(scenario=scenario, materials=parsed_materials)
    except AiParameterAssistantConfigError:
        raise
    except Exception as exc:
        raise AiParameterAssistantConfigError(f"AI 参数助手解析失败：{exc}") from exc

    material_by_id = {material.material_id: material for material in materials}
    suggestions = _standardize_suggestions(payload.suggestions, scenario, material_by_id)
    candidates = _standardize_candidates(payload.candidate_additions, material_by_id)
    suggestions, conflict_groups = _apply_conflicts_and_status(suggestions)
    if len(suggestions) > 100:
        suggestions = suggestions[:100]
        material_warnings.append(ValidationMessage(level="warning", message="建议数量超过 100 条，已截取前 100 条展示。"))
    summaries = [material.summary() for material in materials]
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    entry = store.put(
        run_id=run_id,
        scenario_id=scenario.scenario_id,
        suggestions=suggestions,
        conflict_groups=conflict_groups,
        candidate_additions=candidates,
        material_summaries=summaries,
    )
    warnings = [*material_warnings, *[ValidationMessage(level="warning", message=warning) for warning in payload.warnings]]
    status = "completed"
    if any(summary.parse_status == "failed" for summary in summaries):
        status = "partially_failed"
    return AiParameterParseResponse(
        run_id=run_id,
        status=status,
        material_count=len(materials),
        total_size_bytes=sum(material.size_bytes for material in materials),
        suggestion_count=len(suggestions),
        material_summaries=summaries,
        errors=[],
        warnings=warnings,
        expires_at=entry.expires_at,
        suggestions=suggestions,
        conflict_groups=conflict_groups,
        candidate_additions=candidates,
        manual_completion_count=sum(1 for item in suggestions if item.status == "needs_manual_input"),
    )


def apply_ai_parameter_suggestions(
    request: AiParameterApplyRequest,
    *,
    store: AiParameterStore = default_ai_parameter_store,
) -> AiParameterApplyResponse:
    try:
        entry = store.get(request.run_id)
    except AiParameterStoreExpiredError as exc:
        raise AiParameterAssistantError("本次解析建议已过期或不存在，请重新解析资料。", status_code=410) from exc
    if not request.selected_suggestion_ids and not request.conflict_resolutions:
        raise AiParameterAssistantError("请至少选择一条建议或解决一个冲突后再应用。", status_code=400)

    scenario = request.scenario.model_copy(deep=True)
    summary = AiParameterApplicationSummary(stale_result_reason="AI 参数助手已更新当前方案参数，任务视图和求解结果需要重新生成。")
    selected_ids = set(request.selected_suggestion_ids)
    suggestions_by_id = {suggestion.suggestion_id: suggestion for suggestion in entry.suggestions}
    resolved_suggestions = _resolved_conflict_suggestions(entry.conflict_groups, request.conflict_resolutions, suggestions_by_id, request.manual_values)
    for suggestion in resolved_suggestions:
        selected_ids.add(suggestion.suggestion_id)
        suggestions_by_id[suggestion.suggestion_id] = suggestion

    unresolved_conflicts = _unresolved_selected_conflicts(entry.conflict_groups, selected_ids, request.conflict_resolutions)
    if unresolved_conflicts:
        raise AiParameterAssistantError("存在未解决的冲突建议，请先选择来源值、保留当前值或手动填写。", status_code=400)

    for selected_id in request.selected_suggestion_ids:
        if selected_id in suggestions_by_id:
            continue
        candidate = next((item for item in entry.candidate_additions if item.candidate_id == selected_id), None)
        if candidate is None:
            summary.failed_items.append(ValidationMessage(level="error", message=f"建议 {selected_id} 不存在。", subject_id=selected_id))
            continue
        _apply_candidate(scenario, candidate, summary)

    for suggestion_id in selected_ids:
        suggestion = suggestions_by_id.get(suggestion_id)
        if suggestion is None:
            continue
        if suggestion.status == "needs_manual_input" and suggestion_id not in {value.suggestion_id for value in request.manual_values}:
            summary.manual_pending_count += 1
            summary.skipped_count += 1
            continue
        try:
            _apply_suggestion(scenario, suggestion, summary)
        except Exception as exc:
            summary.failed_items.append(ValidationMessage(level="error", message=str(exc), subject_id=suggestion.suggestion_id))

    summary.applied_count = len(summary.applied_items)
    summary.failed_count = len(summary.failed_items)
    if summary.applied_count == 0 and summary.failed_count > 0:
        stale_results = False
    else:
        stale_results = summary.applied_count > 0
    store.mark_applied(request.run_id, partial=summary.failed_count > 0 or summary.skipped_count > 0)
    return AiParameterApplyResponse(scenario=scenario, application_summary=summary, stale_results=stale_results)


def _scenario_from_fields(fields: dict[str, str]) -> ScenarioInput:
    raw = fields.get("scenario")
    if not raw:
        raise AiParameterAssistantError("缺少 scenario 参数。", status_code=400)
    try:
        return ScenarioInput.model_validate_json(raw)
    except ValidationError as exc:
        raise AiParameterAssistantError(f"scenario 格式不正确：{exc}", status_code=400) from exc


def _standardize_suggestions(
    raw_suggestions: list[dict[str, Any]],
    scenario: ScenarioInput,
    material_by_id: dict[str, Any],
) -> list[AiParameterSuggestion]:
    suggestions: list[AiParameterSuggestion] = []
    for index, raw in enumerate(raw_suggestions, start=1):
        target_ref = dict(raw.get("target_ref") or {})
        category = raw.get("category")
        parameter_key = str(raw.get("parameter_key") or "")
        current_value = raw.get("current_value")
        if current_value is None:
            current_value = _current_value_for(scenario, category, target_ref, parameter_key)
        score = int(raw.get("confidence_score", 50))
        source_refs = [AiParameterSourceEvidence.model_validate(ref) for ref in raw.get("source_refs", [])]
        score = _score_with_source_material(score, source_refs, material_by_id)
        label = _confidence_label(score)
        status = "suggested" if label != "Low" else "needs_manual_input"
        messages = []
        if not source_refs:
            messages.append(ValidationMessage(level="warning", message="缺少来源证据，需人工核验。"))
            status = "needs_manual_input"
        suggestion = AiParameterSuggestion(
            suggestion_id=str(raw.get("suggestion_id") or f"sug_{index:03d}"),
            category=category,
            target_ref=target_ref,
            parameter_key=parameter_key,
            current_value=current_value,
            proposed_value=raw.get("proposed_value"),
            unit=raw.get("unit"),
            confidence_label=label,
            confidence_score=score,
            source_refs=source_refs,
            status=status,
            validation_messages=messages,
        )
        suggestions.append(suggestion)
    return suggestions


def _standardize_candidates(raw_candidates: list[dict[str, Any]], material_by_id: dict[str, Any]) -> list[AiParameterCandidateAddition]:
    candidates: list[AiParameterCandidateAddition] = []
    for index, raw in enumerate(raw_candidates, start=1):
        source_refs = [AiParameterSourceEvidence.model_validate(ref) for ref in raw.get("source_refs", [])]
        score = _score_with_source_material(int(raw.get("confidence_score", 50)), source_refs, material_by_id)
        candidates.append(
            AiParameterCandidateAddition(
                candidate_id=str(raw.get("candidate_id") or f"cand_{index:03d}"),
                category=raw.get("category"),
                display_name=str(raw.get("display_name") or f"候选项 {index}"),
                proposed_fields=dict(raw.get("proposed_fields") or {}),
                confidence_label=_confidence_label(score),
                confidence_score=score,
                source_refs=source_refs,
                validation_status="valid" if score >= 60 else "needs_manual_input",
            )
        )
    return candidates


def _score_with_source_material(score: int, source_refs: list[AiParameterSourceEvidence], material_by_id: dict[str, Any]) -> int:
    for source in source_refs:
        material = material_by_id.get(source.material_id)
        if getattr(material, "kind", None) == "image":
            return min(score, 45)
    return max(0, min(100, score))


def _confidence_label(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 60:
        return "Medium"
    return "Low"


def _apply_conflicts_and_status(suggestions: list[AiParameterSuggestion]) -> tuple[list[AiParameterSuggestion], list[AiParameterConflictGroup]]:
    by_key: dict[str, list[AiParameterSuggestion]] = {}
    for suggestion in suggestions:
        by_key.setdefault(_conflict_key(suggestion), []).append(suggestion)
    groups: list[AiParameterConflictGroup] = []
    for group_index, group in enumerate(by_key.values(), start=1):
        values = {_stable_value(item.proposed_value) for item in group}
        if len(group) <= 1 or len(values) <= 1:
            continue
        group_id = f"conflict_{group_index:03d}"
        for suggestion in group:
            suggestion.conflict_group_id = group_id
            suggestion.status = "conflict"
        first = group[0]
        groups.append(
            AiParameterConflictGroup(
                conflict_group_id=group_id,
                parameter_key=first.parameter_key,
                target_ref=first.target_ref,
                suggestion_ids=[item.suggestion_id for item in group],
                current_value=first.current_value,
            )
        )
    return suggestions, groups


def _current_value_for(scenario: ScenarioInput, category: str, target_ref: dict[str, Any], parameter_key: str) -> Any:
    if category == "process_productivity":
        process = _find_process(scenario, target_ref)
        if not process:
            return None
        return process.productivity_unit if parameter_key.endswith("unit") else process.productivity_value
    if category == "resource_pool":
        pool = _find_resource_pool(scenario, target_ref)
        if not pool:
            return None
        return pool.max_quantity if parameter_key.endswith("max_quantity") else pool.quantity
    if category == "milestone":
        milestone = _find_milestone(scenario, target_ref)
        if not milestone:
            return None
        return milestone.target_date.isoformat()
    if category == "process_method_assignment":
        component_ids = target_ref.get("component_ids")
        components = _find_components_by_ids(scenario, component_ids if isinstance(component_ids, list) else [])
        values = sorted({component.method_id or "" for component in components})
        if len(values) == 1:
            return values[0] or None
        if len(values) > 1:
            return "mixed"
    return None


def _conflict_key(suggestion: AiParameterSuggestion) -> str:
    return json.dumps(
        {
            "category": suggestion.category,
            "target_ref": suggestion.target_ref,
            "parameter_key": suggestion.parameter_key,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def _stable_value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _resolved_conflict_suggestions(
    conflict_groups: list[AiParameterConflictGroup],
    resolutions: list[AiParameterConflictGroup],
    suggestions_by_id: dict[str, AiParameterSuggestion],
    manual_values: list[AiParameterManualValue],
) -> list[AiParameterSuggestion]:
    manual_by_group = {value.conflict_group_id: value for value in manual_values if value.conflict_group_id}
    result: list[AiParameterSuggestion] = []
    for resolution in resolutions:
        group = next((item for item in conflict_groups if item.conflict_group_id == resolution.conflict_group_id), None)
        if group is None:
            continue
        if resolution.resolution_status == "keep_current":
            continue
        if resolution.resolution_status == "selected_suggestion" and resolution.selected_suggestion_id:
            suggestion = suggestions_by_id.get(resolution.selected_suggestion_id)
            if suggestion:
                result.append(suggestion.model_copy(update={"status": "selected"}))
        elif resolution.resolution_status == "manual_value":
            base = suggestions_by_id.get(group.suggestion_ids[0])
            manual = resolution.manual_value
            if manual is None and group.conflict_group_id in manual_by_group:
                manual = manual_by_group[group.conflict_group_id].value
            if base is not None:
                result.append(base.model_copy(update={"suggestion_id": f"{group.conflict_group_id}_manual", "proposed_value": manual, "status": "selected"}))
    return result


def _unresolved_selected_conflicts(
    conflict_groups: list[AiParameterConflictGroup],
    selected_ids: set[str],
    resolutions: list[AiParameterConflictGroup],
) -> list[AiParameterConflictGroup]:
    resolved_ids = {resolution.conflict_group_id for resolution in resolutions if resolution.resolution_status != "unresolved"}
    return [
        group
        for group in conflict_groups
        if group.conflict_group_id not in resolved_ids and any(suggestion_id in selected_ids for suggestion_id in group.suggestion_ids)
    ]


def _apply_suggestion(scenario: ScenarioInput, suggestion: AiParameterSuggestion, summary: AiParameterApplicationSummary) -> None:
    if suggestion.category == "process_productivity":
        _apply_process_suggestion(scenario, suggestion, summary)
    elif suggestion.category == "process_method_assignment":
        _apply_process_method_assignment_suggestion(scenario, suggestion, summary)
    elif suggestion.category == "resource_pool":
        _apply_resource_suggestion(scenario, suggestion, summary)
    elif suggestion.category == "milestone":
        _apply_milestone_suggestion(scenario, suggestion, summary)


def _apply_process_suggestion(scenario: ScenarioInput, suggestion: AiParameterSuggestion, summary: AiParameterApplicationSummary) -> None:
    process = _find_process(scenario, suggestion.target_ref)
    if process is None:
        raise ValueError("未找到目标工艺。")
    old = process.productivity_value
    value = float(suggestion.proposed_value)
    process.productivity_value = value
    if suggestion.unit:
        process.productivity_unit = str(suggestion.unit)
        process.duration_method = _duration_method_for_unit(process.productivity_unit)
    default_option = next((option for option in process.productivity_options if option.is_default), None)
    if default_option is not None:
        default_option.productivity_value = process.productivity_value
        default_option.productivity_unit = process.productivity_unit
        default_option.duration_method = process.duration_method
    summary.applied_items.append(_applied_item(suggestion, old, process.productivity_value))


def _apply_process_method_assignment_suggestion(scenario: ScenarioInput, suggestion: AiParameterSuggestion, summary: AiParameterApplicationSummary) -> None:
    target_ref = suggestion.target_ref
    process = ensure_process_for_assignment(
        scenario,
        component_type=str(target_ref.get("component_type") or "") or None,
        process_method_id=str(target_ref.get("process_method_id") or suggestion.proposed_value or "") or None,
        process_name=str(target_ref.get("process_name") or "") or None,
    )
    if process is None:
        raise ValueError("未找到目标工艺。")
    component_ids = target_ref.get("component_ids")
    if not isinstance(component_ids, list):
        raise ValueError("缺少目标构件。")
    components = _find_components_by_ids(scenario, component_ids)
    if not components:
        raise ValueError("未找到目标构件。")
    old_values = sorted({component.method_id or "" for component in components})
    old: Any = (old_values[0] or None) if len(old_values) == 1 else "mixed"
    method_id = process.method_id or process.id
    for component in components:
        component.method_id = method_id
    summary.applied_items.append(_applied_item(suggestion, old, {"method_id": method_id, "matched_count": len(components)}))


def _apply_resource_suggestion(scenario: ScenarioInput, suggestion: AiParameterSuggestion, summary: AiParameterApplicationSummary) -> None:
    pool = _find_resource_pool(scenario, suggestion.target_ref)
    if pool is None:
        raise ValueError("未找到目标资源。")
    value = int(suggestion.proposed_value)
    if suggestion.parameter_key.endswith("max_quantity"):
        old = pool.max_quantity
        pool.max_quantity = value
        if pool.quantity is not None and pool.max_quantity < pool.quantity:
            pool.quantity = pool.max_quantity
    else:
        old = pool.quantity
        pool.quantity = value
        if pool.max_quantity is None or pool.max_quantity < value:
            pool.max_quantity = value
    summary.applied_items.append(_applied_item(suggestion, old, value))


def _apply_milestone_suggestion(scenario: ScenarioInput, suggestion: AiParameterSuggestion, summary: AiParameterApplicationSummary) -> None:
    milestone = _find_milestone(scenario, suggestion.target_ref)
    fields = suggestion.target_ref.get("milestone_fields") if isinstance(suggestion.target_ref.get("milestone_fields"), dict) else {}
    target_date = _parse_date(suggestion.proposed_value)
    if milestone is None:
        milestone = MilestoneConstraint(
            id=f"M-ai-{uuid.uuid4().hex[:8]}",
            name=str(fields.get("name") or suggestion.target_ref.get("milestone_name") or "AI识别里程碑"),
            level=fields.get("level") or "internal",
            mode=fields.get("mode") or "soft",
            scope_type=fields.get("scope_type") or "project",
            scope_id=fields.get("scope_id"),
            target_event=fields.get("target_event") or "finish",
            target_date=target_date,
        )
        scenario.milestones.append(milestone)
        old = None
    else:
        old = milestone.target_date.isoformat()
        milestone.target_date = target_date
        if fields:
            milestone.level = fields.get("level") or milestone.level
            milestone.mode = fields.get("mode") or milestone.mode
    summary.applied_items.append(_applied_item(suggestion, old, milestone.target_date.isoformat()))


def _apply_candidate(scenario: ScenarioInput, candidate: AiParameterCandidateAddition, summary: AiParameterApplicationSummary) -> None:
    fields = deepcopy(candidate.proposed_fields)
    if candidate.category == "resource_pool":
        resource_type = str(fields.get("type") or f"ai_resource_{len(scenario.resource_pools) + 1}")
        pool = ResourcePool(
            id=str(fields.get("id") or f"pool-{resource_type.replace('_', '-')}"),
            type=resource_type,
            label=str(fields.get("label") or candidate.display_name),
            quantity=int(fields.get("quantity") or 1),
            max_quantity=int(fields.get("max_quantity") or fields.get("quantity") or 1),
        )
        scenario.resource_pools.append(pool)
        summary.applied_items.append(
            AiParameterAppliedItem(
                suggestion_id=candidate.candidate_id,
                category=candidate.category,
                target_ref={"resource_pool_id": pool.id, "resource_type": pool.type},
                parameter_key="resource_pool.candidate",
                old_value=None,
                new_value=pool.model_dump(),
            )
        )
    elif candidate.category == "milestone":
        milestone = MilestoneConstraint(
            id=str(fields.get("id") or f"M-ai-{uuid.uuid4().hex[:8]}"),
            name=str(fields.get("name") or candidate.display_name),
            level=fields.get("level") or "internal",
            mode=fields.get("mode") or "soft",
            scope_type=fields.get("scope_type") or "project",
            scope_id=fields.get("scope_id"),
            target_event=fields.get("target_event") or "finish",
            target_date=_parse_date(fields.get("target_date")),
        )
        scenario.milestones.append(milestone)
        summary.applied_items.append(
            AiParameterAppliedItem(
                suggestion_id=candidate.candidate_id,
                category=candidate.category,
                target_ref={"milestone_id": milestone.id},
                parameter_key="milestone.candidate",
                old_value=None,
                new_value=milestone.model_dump(),
            )
        )
    elif candidate.category == "process_productivity":
        process = ProcessTemplate(
            id=str(fields.get("id") or f"process-ai-{uuid.uuid4().hex[:8]}"),
            component_type=fields.get("component_type") or "pile",
            process_name=str(fields.get("process_name") or candidate.display_name),
            method_id=fields.get("method_id"),
            duration_method=fields.get("duration_method") or _duration_method_for_unit(str(fields.get("productivity_unit") or "天/个")),
            quantity_source=fields.get("quantity_source") or "count",
            productivity_value=float(fields.get("productivity_value") or 1),
            productivity_unit=str(fields.get("productivity_unit") or "天/个"),
            resource_type=str(fields.get("resource_type") or "general_team"),
        )
        scenario.process_library.append(process)
        summary.applied_items.append(
            AiParameterAppliedItem(
                suggestion_id=candidate.candidate_id,
                category=candidate.category,
                target_ref={"process_id": process.id},
                parameter_key="process.candidate",
                old_value=None,
                new_value=process.model_dump(),
            )
        )


def _find_process(scenario: ScenarioInput, target_ref: dict[str, Any]) -> ProcessTemplate | None:
    process_id = target_ref.get("process_id")
    process_name = target_ref.get("process_name")
    return next((item for item in scenario.process_library if item.id == process_id or item.process_name == process_name), None)


def _find_components_by_ids(scenario: ScenarioInput, component_ids: list[Any]) -> list[Any]:
    wanted = {str(component_id) for component_id in component_ids}
    components = []
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for structure in section.structures:
                for component in structure.components:
                    if component.id in wanted:
                        components.append(component)
    return components


def _find_resource_pool(scenario: ScenarioInput, target_ref: dict[str, Any]) -> ResourcePool | None:
    pool_id = target_ref.get("resource_pool_id")
    resource_type = target_ref.get("resource_type")
    return next((item for item in scenario.resource_pools if item.id == pool_id or item.type == resource_type), None)


def _find_milestone(scenario: ScenarioInput, target_ref: dict[str, Any]) -> MilestoneConstraint | None:
    milestone_id = target_ref.get("milestone_id")
    milestone_name = target_ref.get("milestone_name")
    return next((item for item in scenario.milestones if item.id == milestone_id or item.name == milestone_name), None)


def _duration_method_for_unit(unit: str) -> str:
    if unit in {"天/根", "天/个"}:
        return "fixed_days"
    if unit.startswith("天/"):
        return "days_per_unit"
    return "units_per_day"


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _applied_item(suggestion: AiParameterSuggestion, old: Any, new: Any) -> AiParameterAppliedItem:
    return AiParameterAppliedItem(
        suggestion_id=suggestion.suggestion_id,
        category=suggestion.category,
        target_ref=suggestion.target_ref,
        parameter_key=suggestion.parameter_key,
        old_value=old,
        new_value=new,
    )
