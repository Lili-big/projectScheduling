from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Iterable

from pydantic import BaseModel, Field, ValidationError

from .models import ComponentModel, ProcessNlChange, ProcessNlResponse, ProcessTemplate, ResourcePool, ScenarioInput


class ProcessNlIntent(BaseModel):
    component_type: str | None = None
    process_method_id: str | None = None
    process_name: str | None = None
    sides: list[str] = Field(default_factory=list)
    support_nos: list[str] = Field(default_factory=list)
    component_names: list[str] = Field(default_factory=list)
    pile_nos: list[str] = Field(default_factory=list)
    target_role: str | None = None
    action: str = "自然语言工艺设置"


class ProcessNlIntentPayload(BaseModel):
    intents: list[ProcessNlIntent] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def apply_process_natural_language(scenario: ScenarioInput, prompt: str) -> ProcessNlResponse:
    next_scenario = scenario.model_copy(deep=True)
    changes: list[ProcessNlChange] = []
    warnings: list[str] = []

    intent_payload = _understand_process_prompt(next_scenario, prompt)
    warnings.extend(intent_payload.warnings)
    for intent in intent_payload.intents:
        process = _resolve_process(next_scenario, intent)
        if not process:
            warnings.append(f"未能匹配工艺库：{intent.process_name or intent.process_method_id or '未指定工艺'}。")
            continue
        targets = _match_intent_components(next_scenario, intent)
        if targets:
            changes.append(_apply_process_to_components(next_scenario, process=process, components=targets, action=intent.action))
        else:
            warnings.append(f"未找到可应用构件：{_intent_target_label(intent)}。")

    if not changes and not warnings:
        warnings.append("暂未识别到可应用的工艺设置，请描述构件范围和工艺名称。")

    return ProcessNlResponse(scenario=next_scenario, changes=changes, warnings=warnings)


def _understand_process_prompt(scenario: ScenarioInput, prompt: str) -> ProcessNlIntentPayload:
    llm_payload = _understand_process_prompt_with_llm(scenario, prompt)
    if llm_payload and llm_payload.intents:
        return llm_payload
    fallback_payload = _understand_process_prompt_locally(prompt)
    if llm_payload and llm_payload.warnings:
        fallback_payload.warnings = [*llm_payload.warnings, *fallback_payload.warnings]
    return fallback_payload


def _understand_process_prompt_with_llm(scenario: ScenarioInput, prompt: str) -> ProcessNlIntentPayload | None:
    provider = os.getenv("PROCESS_NL_LLM_PROVIDER", "local").strip().lower()
    if provider in {"", "local", "heuristic", "none"}:
        return None
    if provider not in {
        "http",
        "generic_http",
        "openai",
        "openai_compatible",
        "openai-compatible",
        "chat_completions",
        "deepseek",
        "qwen",
        "siliconflow",
    }:
        return ProcessNlIntentPayload(warnings=[f"不支持的工艺自然语言 LLM 适配器：{provider}，已改用本地解析。"])

    endpoint = os.getenv("PROCESS_NL_LLM_ENDPOINT")
    if not endpoint:
        return ProcessNlIntentPayload(warnings=["PROCESS_NL_LLM_ENDPOINT 未配置，已改用本地解析。"])

    request_payload = (
        _openai_compatible_request_payload(scenario, prompt)
        if provider in {"openai", "openai_compatible", "openai-compatible", "chat_completions", "deepseek", "qwen", "siliconflow"}
        else _generic_http_request_payload(scenario, prompt)
    )
    payload = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("PROCESS_NL_LLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return ProcessNlIntentPayload(warnings=[f"工艺自然语言 LLM 调用失败，已改用本地解析：{exc}"])
    try:
        return ProcessNlIntentPayload.model_validate(_extract_intent_payload(raw))
    except ValidationError as exc:
        return ProcessNlIntentPayload(warnings=[f"工艺自然语言 LLM 返回格式不符合要求，已改用本地解析：{exc}"])


def _generic_http_request_payload(scenario: ScenarioInput, prompt: str) -> dict[str, Any]:
    return {
        "model": os.getenv("PROCESS_NL_LLM_MODEL"),
        "prompt": prompt,
        "instruction": _process_intent_instruction(),
        "process_library": _process_library_catalog(scenario),
        "component_catalog": _component_catalog(scenario),
        "output_schema": _process_intent_output_schema(),
    }


def _openai_compatible_request_payload(scenario: ScenarioInput, prompt: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": os.getenv("PROCESS_NL_LLM_MODEL"),
        "messages": [
            {"role": "system", "content": _process_intent_instruction()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_prompt": prompt,
                        "process_library": _process_library_catalog(scenario),
                        "component_catalog": _component_catalog(scenario),
                        "output_schema": _process_intent_output_schema(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": _llm_temperature(),
    }
    if os.getenv("PROCESS_NL_LLM_RESPONSE_FORMAT", "json_object").strip().lower() not in {"", "none", "false", "off"}:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _process_intent_instruction() -> str:
    return (
        "你是桥梁施工排程系统的工艺设置语义解析器。"
        "请把用户自然语言解析为 JSON，不要输出 Markdown，不要解释。"
        "只允许返回 {\"intents\": [...], \"warnings\": [...]}。"
        "intent 字段包括 component_type、process_method_id、process_name、sides、support_nos、"
        "component_names、pile_nos、target_role、action。"
        "component_type 只能从构件清单和工艺库中选择，例如 pile、pier_body、cap、cap_beam、"
        "ground_tie_beam、middle_tie_beam。"
        "sides 使用 left 或 right；support_nos 使用 3#墩、0#台 这种中文编号；"
        "process_method_id 优先使用工艺库 method_id。"
        "如果用户说连续梁主墩，可设置 target_role 为 continuous_girder_main_pier。"
        "不要臆造不存在的构件或工艺，无法确认时放入 warnings。"
    )


def _process_library_catalog(scenario: ScenarioInput) -> list[dict[str, str]]:
    return [
        {
            "component_type": process.component_type,
            "method_id": process.method_id or process.id,
            "process_name": process.process_name,
        }
        for process in scenario.process_library
    ]


def _process_intent_output_schema() -> dict[str, Any]:
    return {
        "intents": [
            {
                "component_type": "pile",
                "process_method_id": "manual_pile",
                "process_name": "人工挖孔",
                "sides": ["left"],
                "support_nos": ["3#墩", "4#墩"],
                "component_names": [],
                "pile_nos": [],
                "target_role": None,
                "action": "指定墩桩基工艺",
            }
        ],
        "warnings": [],
    }


def _llm_temperature() -> float:
    raw = os.getenv("PROCESS_NL_LLM_TEMPERATURE", "0")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _understand_process_prompt_locally(prompt: str) -> ProcessNlIntentPayload:
    text = _normalize_text(prompt)
    intents: list[ProcessNlIntent] = []

    if "桩基" in text and ("旋挖" in text or "旋挖钻" in text):
        intents.append(
            ProcessNlIntent(
                component_type="pile",
                process_method_id="rotary_drill",
                process_name="旋挖钻成孔",
                action="桩基默认工艺",
            )
        )

    if "桩基" in text:
        pile_process = _pile_process_from_text(text)
        if pile_process:
            process_method_id, process_name = pile_process
            pile_refs = _extract_pile_refs(text)
            if pile_refs:
                intents.append(
                    ProcessNlIntent(
                        component_type="pile",
                        process_method_id=process_method_id,
                        process_name=process_name,
                        component_names=[_pile_ref_label(ref) for ref in pile_refs],
                        action="指定桩基工艺",
                    )
                )
            else:
                support_nos = _extract_support_nos(text)
                sides = _extract_sides(text)
                if support_nos or sides:
                    intents.append(
                        ProcessNlIntent(
                            component_type="pile",
                            process_method_id=process_method_id,
                            process_name=process_name,
                            sides=sides,
                            support_nos=support_nos,
                            action="指定墩桩基工艺",
                        )
                    )

    if "爬模" in text:
        intents.append(
            ProcessNlIntent(
                component_type="pier_body",
                process_method_id="climbing_form",
                process_name="爬模施工",
                target_role="continuous_girder_main_pier",
                action="连续梁主墩工艺",
            )
        )

    return ProcessNlIntentPayload(intents=intents)


def _resolve_process(scenario: ScenarioInput, intent: ProcessNlIntent) -> ProcessTemplate | None:
    component_type = intent.component_type
    method_id = intent.process_method_id
    process_name = intent.process_name or ""
    if component_type == "pile":
        if not method_id:
            method_id = _pile_process_method_from_name(process_name)
        if method_id == "rotary_drill":
            return _ensure_process(scenario, "pile", "rotary_drill", "旋挖钻成孔")
        if method_id == "impact_drill":
            return _ensure_process(scenario, "pile", "impact_drill", "冲击钻成孔")
        if method_id == "manual_pile":
            return _ensure_process(scenario, "pile", "manual_pile", "人工挖孔")
    if component_type == "pier_body" and (method_id == "climbing_form" or "爬模" in process_name):
        return _ensure_process(scenario, "pier_body", "climbing_form", "爬模施工")
    for process in scenario.process_library:
        if component_type and process.component_type != component_type:
            continue
        if method_id and (process.method_id == method_id or process.id == method_id):
            return process
        if process_name and (process_name in process.process_name or process.process_name in process_name):
            return process
    return None


def _match_intent_components(scenario: ScenarioInput, intent: ProcessNlIntent) -> list[ComponentModel]:
    if intent.target_role == "continuous_girder_main_pier":
        return _continuous_girder_main_pier_components(scenario)

    side_set = {_normalize_side(side) for side in intent.sides}
    side_set.discard("")
    support_set = {_normalize_support_no(item) for item in intent.support_nos}
    support_set.discard("")
    pile_no_set = {re.sub(r"\D", "", item) for item in intent.pile_nos}
    pile_no_set.discard("")
    component_name_set = {_normalize_text(name).replace("桩基", "#桩基") for name in intent.component_names}
    component_name_set.update({_normalize_text(name) for name in intent.component_names})

    targets: list[ComponentModel] = []
    for component, section_side, structure_support_no in _iter_component_context(scenario):
        if intent.component_type and component.component_type != intent.component_type:
            continue
        if side_set and section_side not in side_set:
            continue
        if support_set and _normalize_support_no(structure_support_no or "") not in support_set:
            continue
        if component_name_set and _normalize_text(component.name) not in component_name_set:
            continue
        if pile_no_set and _component_pile_no(component) not in pile_no_set:
            continue
        targets.append(component)
    return targets


def _extract_intent_payload(raw: Any) -> Any:
    if isinstance(raw, dict) and "intents" in raw:
        return raw
    if isinstance(raw, dict) and "choices" in raw and raw["choices"]:
        message = raw["choices"][0].get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if content:
            return json.loads(_strip_json_fence(content))
    if isinstance(raw, dict) and "output_text" in raw:
        return json.loads(_strip_json_fence(str(raw["output_text"])))
    if isinstance(raw, dict) and "content" in raw:
        return json.loads(_strip_json_fence(str(raw["content"])))
    return raw


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def _component_catalog(scenario: ScenarioInput) -> list[dict[str, str | None]]:
    catalog: list[dict[str, str | None]] = []
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for structure in section.structures:
                for component in structure.components:
                    catalog.append(
                        {
                            "bridge": bridge.name,
                            "section": section.name,
                            "side": section.side,
                            "support_no": structure.support_no or structure.name,
                            "component_type": component.component_type,
                            "component_name": component.name,
                            "current_method_id": component.method_id,
                        }
                    )
    return catalog


def _pile_process_from_text(text: str) -> tuple[str, str] | None:
    if "人工挖孔" in text or "挖孔桩" in text:
        return ("manual_pile", "人工挖孔")
    if "冲击钻" in text:
        return ("impact_drill", "冲击钻成孔")
    if "旋挖" in text or "旋挖钻" in text:
        return ("rotary_drill", "旋挖钻成孔")
    return None


def _pile_process_method_from_name(process_name: str) -> str | None:
    text = _normalize_text(process_name)
    if "人工挖孔" in text or "挖孔桩" in text:
        return "manual_pile"
    if "冲击钻" in text:
        return "impact_drill"
    if "旋挖" in text:
        return "rotary_drill"
    return None


def _extract_sides(text: str) -> list[str]:
    sides: list[str] = []
    if "左幅" in text or "左线" in text:
        sides.append("left")
    if "右幅" in text or "右线" in text:
        sides.append("right")
    return sides


def _extract_support_nos(text: str) -> list[str]:
    support_nos: list[str] = []
    for value in re.findall(r"(\d+)#墩", text):
        support_no = f"{int(value)}#墩"
        if support_no not in support_nos:
            support_nos.append(support_no)
    for first, second in re.findall(r"(\d+)#(?:墩)?[、,，和](\d+)#墩", text):
        for value in (first, second):
            support_no = f"{int(value)}#墩"
            if support_no not in support_nos:
                support_nos.append(support_no)
    return support_nos


def _normalize_side(side: str) -> str:
    text = _normalize_text(side).lower()
    if text in {"left", "l"} or "左" in text:
        return "left"
    if text in {"right", "r"} or "右" in text:
        return "right"
    return text


def _normalize_support_no(support_no: str) -> str:
    text = _normalize_text(support_no)
    match = re.search(r"(\d+)#?(墩|台)", text)
    if match:
        return f"{int(match.group(1))}#{match.group(2)}"
    return text


def _component_pile_no(component: ComponentModel) -> str:
    match = re.search(r"-(\d+)#桩基$", _normalize_text(component.name))
    return match.group(1) if match else ""


def _iter_component_context(scenario: ScenarioInput) -> Iterable[tuple[ComponentModel, str, str | None]]:
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for structure in section.structures:
                for component in structure.components:
                    yield component, section.side, structure.support_no or structure.name


def _intent_target_label(intent: ProcessNlIntent) -> str:
    parts = []
    if intent.sides:
        parts.append("/".join(intent.sides))
    if intent.support_nos:
        parts.append("、".join(intent.support_nos))
    if intent.component_names:
        parts.append("、".join(intent.component_names[:5]))
    if intent.component_type:
        parts.append(intent.component_type)
    return " ".join(parts) or "未指定范围"


def _apply_process_to_components(
    scenario: ScenarioInput,
    *,
    process: ProcessTemplate,
    components: list[ComponentModel],
    action: str,
) -> ProcessNlChange:
    for component in components:
        component.method_id = process.method_id or process.id
    return ProcessNlChange(
        action=action,
        process_id=process.method_id or process.id,
        process_name=process.process_name,
        matched_count=len(components),
        targets=[component.name for component in components[:20]],
        message=f"{action}：已将 {len(components)} 个构件设置为“{process.process_name}”。",
    )


def _ensure_process(
    scenario: ScenarioInput,
    component_type: str,
    method_id: str,
    process_name: str,
) -> ProcessTemplate:
    for process in scenario.process_library:
        if process.component_type == component_type and (process.method_id == method_id or process.id == method_id):
            return process

    resource_by_method = {
        "climbing_form": ("climbing_form_team", "m/天", "units_per_day", 1.0),
    }
    resource_type, unit, duration_method, productivity = resource_by_method.get(
        method_id,
        ("general_team", "天/个", "fixed_days", 1.0),
    )
    process = ProcessTemplate(
        id=f"{component_type}_{method_id}",
        component_type=component_type,  # type: ignore[arg-type]
        process_name=process_name,
        method_id=method_id,
        duration_method=duration_method,  # type: ignore[arg-type]
        quantity_source="pier_height_m" if component_type == "pier_body" else "count",
        productivity_value=productivity,
        productivity_unit=unit,
        resource_type=resource_type,
        is_default=False,
    )
    scenario.process_library.append(process)
    _ensure_resource_pool(scenario, resource_type, process_name)
    return process


def _ensure_resource_pool(scenario: ScenarioInput, resource_type: str, process_name: str) -> None:
    if any(pool.type == resource_type for pool in scenario.resource_pools):
        return
    scenario.resource_pools.append(
        ResourcePool(
            id=f"pool-{resource_type.replace('_', '-')}",
            type=resource_type,
            label=process_name,
            quantity=1,
        )
    )


def _continuous_girder_main_pier_components(scenario: ScenarioInput) -> list[ComponentModel]:
    main_supports: set[str] = set()
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            spans_by_group: dict[int, list[int]] = {}
            for upper in section.upper_structures:
                if "连续" not in upper.structure_type:
                    continue
                group_index = int(upper.properties.get("group_index") or upper.span_index)
                spans_by_group.setdefault(group_index, []).append(upper.span_index)
            for span_indices in spans_by_group.values():
                if len(span_indices) < 2:
                    continue
                for support_index in range(min(span_indices), max(span_indices)):
                    main_supports.add(f"{support_index}#墩")
    return [
        component
        for bridge in scenario.project.bridges
        for section in bridge.work_sections
        for structure in section.structures
        if (structure.support_no or structure.name) in main_supports
        for component in structure.components
        if component.component_type == "pier_body"
    ]


def _extract_pile_refs(text: str) -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    pattern = re.compile(r"(\d+#墩)[-—~]?\s*(\d+)#?桩基")
    for pier, pile_no in pattern.findall(text):
        refs.append((pier, pile_no))
    return refs


def _component_matches_any_pile_ref(component: ComponentModel, refs: Iterable[tuple[str, str]]) -> bool:
    match = re.fullmatch(r"(.+?#墩)-(\d+)#桩基", _normalize_text(component.name))
    if not match:
        return False
    component_pier, component_pile_no = match.groups()
    return any(component_pier == pier and component_pile_no == pile_no for pier, pile_no in refs)


def _pile_ref_label(ref: tuple[str, str]) -> str:
    return f"{ref[0]}-{ref[1]}#桩基"


def _iter_components(scenario: ScenarioInput) -> Iterable[ComponentModel]:
    for bridge in scenario.project.bridges:
        for section in bridge.work_sections:
            for structure in section.structures:
                yield from structure.components


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("－", "-").replace("—", "-").replace("～", "~"))
