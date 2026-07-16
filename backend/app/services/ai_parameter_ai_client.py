from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ..contracts import ScenarioInput
from .ai_parameter_materials import AiParameterMaterial


class AiParameterAssistantConfigError(RuntimeError):
    pass


class AiParameterAiPayload(BaseModel):
    suggestions: list[dict[str, Any]] = Field(default_factory=list)
    candidate_additions: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AiParameterAiClient(ABC):
    @abstractmethod
    def understand(self, *, scenario: ScenarioInput, materials: list[AiParameterMaterial]) -> AiParameterAiPayload:
        """Return normalized AI parameter suggestions."""


class LocalHeuristicAiParameterClient(AiParameterAiClient):
    def understand(self, *, scenario: ScenarioInput, materials: list[AiParameterMaterial]) -> AiParameterAiPayload:
        suggestions: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        warnings: list[str] = []
        for material in materials:
            text = material.content_text or material.source_summary
            if not text:
                warnings.append(f"{material.file_name} 没有可解析文本，需人工核验。")
                continue
            suggestions.extend(_process_suggestions(scenario, material, text))
            resource_suggestions, resource_candidates = _resource_suggestions(scenario, material, text)
            suggestions.extend(resource_suggestions)
            candidates.extend(resource_candidates)
            milestone_suggestions, milestone_candidates = _milestone_suggestions(scenario, material, text)
            suggestions.extend(milestone_suggestions)
            candidates.extend(milestone_candidates)
            if _looks_like_structure_replacement(text):
                warnings.append(f"{material.file_name} 中的结构参数替换内容已排除，仅可作为定位依据。")
        return AiParameterAiPayload(suggestions=suggestions, candidate_additions=candidates, warnings=warnings)


class HttpAiParameterClient(AiParameterAiClient):
    def __init__(self, endpoint: str, model: str | None, api_key: str | None, *, openai_compatible: bool) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.openai_compatible = openai_compatible

    def understand(self, *, scenario: ScenarioInput, materials: list[AiParameterMaterial]) -> AiParameterAiPayload:
        payload = _openai_payload(scenario, materials, self.model) if self.openai_compatible else _generic_payload(scenario, materials, self.model)
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.endpoint, data=request_body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=_timeout_seconds()) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AiParameterAssistantConfigError(f"AI 参数助手服务调用失败：{exc}") from exc
        try:
            return AiParameterAiPayload.model_validate(_extract_ai_payload(raw))
        except ValidationError as exc:
            raise AiParameterAssistantConfigError(f"AI 参数助手返回格式不符合要求：{exc}") from exc


def get_ai_parameter_client() -> AiParameterAiClient:
    provider = os.getenv("AI_PARAMETER_ASSISTANT_PROVIDER", "local").strip().lower()
    if provider in {"", "local", "heuristic"}:
        return LocalHeuristicAiParameterClient()
    if provider in {"http", "generic_http", "openai", "openai_compatible", "openai-compatible", "chat_completions", "deepseek", "qwen"}:
        endpoint = os.getenv("AI_PARAMETER_ASSISTANT_ENDPOINT")
        if not endpoint:
            raise AiParameterAssistantConfigError("AI_PARAMETER_ASSISTANT_ENDPOINT 未配置，无法调用 AI 参数助手。")
        return HttpAiParameterClient(
            endpoint=endpoint,
            model=os.getenv("AI_PARAMETER_ASSISTANT_MODEL"),
            api_key=os.getenv("AI_PARAMETER_ASSISTANT_API_KEY"),
            openai_compatible=provider in {"openai", "openai_compatible", "openai-compatible", "chat_completions", "deepseek", "qwen"},
        )
    raise AiParameterAssistantConfigError(f"不支持的 AI 参数助手 provider：{provider}")


def _generic_payload(scenario: ScenarioInput, materials: list[AiParameterMaterial], model: str | None) -> dict[str, Any]:
    return {
        "model": model,
        "instruction": _instruction(),
        "scenario_context": _scenario_context(scenario),
        "materials": [material.ai_payload() for material in materials],
        "output_schema": _output_schema(),
    }


def _openai_payload(scenario: ScenarioInput, materials: list[AiParameterMaterial], model: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": _instruction()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "scenario_context": _scenario_context(scenario),
                        "materials": [material.ai_payload() for material in materials],
                        "output_schema": _output_schema(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0,
    }
    if os.getenv("AI_PARAMETER_ASSISTANT_RESPONSE_FORMAT", "json_object").strip().lower() not in {"", "none", "false", "off"}:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _instruction() -> str:
    return (
        "你是桥梁施工排程系统的 AI 参数输入助手。只返回 JSON，不输出 Markdown。"
        "只允许提取三类建议：process_productivity、resource_pool、milestone。"
        "不得生成替换桥梁结构参数的建议；结构信息只能用于定位目标。"
        "每条建议必须包含 category、target_ref、parameter_key、proposed_value、unit、confidence_score、source_refs。"
        "图片和扫描材料没有清晰证据时应低置信。"
    )


def _output_schema() -> dict[str, Any]:
    return {
        "suggestions": [
            {
                "category": "resource_pool",
                "target_ref": {"resource_type": "rotary_drill"},
                "parameter_key": "resource.quantity",
                "proposed_value": 2,
                "unit": "台",
                "confidence_score": 88,
                "source_refs": [{"material_id": "mat_file_001", "excerpt": "旋挖钻 2 台"}],
            }
        ],
        "candidate_additions": [],
        "warnings": [],
    }


def _scenario_context(scenario: ScenarioInput) -> dict[str, Any]:
    return {
        "scenario_id": scenario.scenario_id,
        "process_library": [
            {
                "id": process.id,
                "component_type": process.component_type,
                "process_name": process.process_name,
                "resource_type": process.resource_type,
                "productivity_value": process.productivity_value,
                "productivity_unit": process.productivity_unit,
            }
            for process in scenario.process_library
        ],
        "resource_pools": [
            {"id": pool.id, "type": pool.type, "label": pool.label, "quantity": pool.quantity, "max_quantity": pool.max_quantity}
            for pool in scenario.resource_pools
        ],
        "milestones": [
            {"id": milestone.id, "name": milestone.name, "target_date": milestone.target_date.isoformat()}
            for milestone in scenario.milestones
        ],
    }


def _extract_ai_payload(raw: Any) -> Any:
    if isinstance(raw, dict) and ("suggestions" in raw or "candidate_additions" in raw):
        return raw
    if isinstance(raw, dict) and raw.get("choices"):
        message = raw["choices"][0].get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if content:
            return json.loads(_strip_json_fence(str(content)))
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


def _timeout_seconds() -> int:
    raw = os.getenv("AI_PARAMETER_ASSISTANT_TIMEOUT_SECONDS", "60")
    try:
        return max(1, int(raw))
    except ValueError:
        return 60


def _process_suggestions(scenario: ScenarioInput, material: AiParameterMaterial, text: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for process in scenario.process_library:
        names = {process.process_name, process.id, process.method_id or ""}
        if not any(name and name in text for name in names):
            continue
        name_pattern = "|".join(re.escape(name) for name in names if name)
        pattern = re.compile(
            rf"({name_pattern})[^\n\u3002\uff1b;\uff0c,]{{0,30}}?(?:\u5de5\u6548|\u6548\u7387|\u4ea7\u80fd|\u8c03\u6574\u4e3a|\u4e3a|=|\uff1a|:)?\s*"
            rf"(\d+(?:\.\d+)?)\s*(m/\u5929|\u7c73/\u5929|\u6839/\u5929|\u5929/\u6839|\u5929/\u4e2a|\u8282/\u5929|\u4e2a/\u5929)"
        )
        for match in pattern.finditer(text):
            value = float(match.group(2))
            unit = match.group(3).replace("\u7c73/\u5929", "m/\u5929")
            suggestions.append(
                _suggestion_dict(
                    category="process_productivity",
                    target_ref={"process_id": process.id, "process_name": process.process_name},
                    parameter_key="process.productivity_value",
                    current_value=process.productivity_value,
                    proposed_value=value,
                    unit=unit,
                    confidence_score=_confidence_for_material(material, 86),
                    material=material,
                    excerpt=match.group(0),
                )
            )
    return suggestions


def _resource_suggestions(scenario: ScenarioInput, material: AiParameterMaterial, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    suggestions: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    matched_spans: list[tuple[int, int]] = []
    for pool in scenario.resource_pools:
        labels = {pool.label, pool.type, pool.id}
        for label in labels:
            if not label:
                continue
            pattern = re.compile(rf"{re.escape(label)}[^\d\n]{{0,18}}(\d+)\s*(\u53f0|\u5957|\u7ec4|\u4eba|\u4e2a)?")
            for match in pattern.finditer(text):
                if any(keyword in match.group(0) for keyword in ("\u5de5\u6548", "\u6548\u7387", "\u4ea7\u80fd")):
                    continue
                matched_spans.append(match.span())
                parameter_key = "resource.max_quantity" if "\u4e0a\u9650" in match.group(0) or "\u6700\u5927" in match.group(0) else "resource.quantity"
                current_value = pool.max_quantity if parameter_key.endswith("max_quantity") else pool.quantity
                suggestions.append(
                    _suggestion_dict(
                        category="resource_pool",
                        target_ref={"resource_pool_id": pool.id, "resource_type": pool.type},
                        parameter_key=parameter_key,
                        current_value=current_value,
                        proposed_value=int(match.group(1)),
                        unit=match.group(2) or "\u4e2a",
                        confidence_score=_confidence_for_material(material, 88),
                        material=material,
                        excerpt=match.group(0),
                    )
                )
    for match in re.finditer(r"([\u4e00-\u9fa5A-Za-z_]{2,20})[^\d\n]{0,8}(\d+)\s*(\u53f0|\u5957|\u7ec4|\u4eba)", text):
        if any(start <= match.start() <= end for start, end in matched_spans):
            continue
        name = match.group(1).strip("\uff0c,\u3002\uff1a:\uff1b;")
        if any(keyword in name for keyword in ("\u8d44\u6e90", "\u8ba1\u5212", "\u6570\u91cf", "\u6708\u4efd", "\u65e5\u671f", "\u5b8c\u6210", "\u5de5\u6548", "\u6548\u7387", "\u4ea7\u80fd")):
            continue
        candidates.append(
            _candidate_dict(
                category="resource_pool",
                display_name=name,
                proposed_fields={"type": _slug(name), "label": name, "quantity": int(match.group(2)), "max_quantity": int(match.group(2)), "unit": match.group(3)},
                confidence_score=_confidence_for_material(material, 72),
                material=material,
                excerpt=match.group(0),
            )
        )
    return suggestions, candidates


def _milestone_suggestions(scenario: ScenarioInput, material: AiParameterMaterial, text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    suggestions: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    date_pattern = re.compile(r"(\d{4})(?:-(\d{1,2})-(\d{1,2})|/(\d{1,2})/(\d{1,2})|\u5e74(\d{1,2})\u6708(\d{1,2})\u65e5?)")
    for segment in re.split(r"[\u3002\uff1b;\n]", text):
        segment = segment.strip()
        if not segment:
            continue
        for match in date_pattern.finditer(segment):
            raw_name = segment[: match.start()].strip()
            raw_name = re.sub(r".*[,\uff0c\uff1a:]", "", raw_name).strip()
            name = _clean_milestone_name(raw_name) or "AI\u8bc6\u522b\u91cc\u7a0b\u7891"
            month = next(value for value in match.group(2, 4, 6) if value)
            day = next(value for value in match.group(3, 5, 7) if value)
            target_date = f"{int(match.group(1)):04d}-{int(month):02d}-{int(day):02d}"
            level, mode = ("internal", "soft")
            if any(keyword in segment for keyword in ("\u5408\u540c", "\u63a7\u5236", "\u5f3a\u5236", "\u5fc5\u987b")):
                level, mode = ("control", "hard")
            existing = next((milestone for milestone in scenario.milestones if milestone.name == name or name in milestone.name or milestone.name in name), None)
            payload = {
                "name": name,
                "target_date": target_date,
                "level": level,
                "mode": mode,
                "scope_type": "project",
                "target_event": "finish",
            }
            if existing:
                suggestions.append(
                    _suggestion_dict(
                        category="milestone",
                        target_ref={"milestone_id": existing.id, "milestone_name": existing.name},
                        parameter_key="milestone.target_date",
                        current_value=existing.target_date.isoformat(),
                        proposed_value=target_date,
                        unit="date",
                        confidence_score=_confidence_for_material(material, 82),
                        material=material,
                        excerpt=segment[:120],
                        extra={"milestone_fields": payload},
                    )
                )
            else:
                candidates.append(
                    _candidate_dict(
                        category="milestone",
                        display_name=name,
                        proposed_fields=payload,
                        confidence_score=_confidence_for_material(material, 76),
                        material=material,
                        excerpt=segment[:120],
                    )
                )
    return suggestions, candidates


def _suggestion_dict(
    *,
    category: str,
    target_ref: dict[str, Any],
    parameter_key: str,
    current_value: Any,
    proposed_value: Any,
    unit: str | None,
    confidence_score: int,
    material: AiParameterMaterial,
    excerpt: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = dict(target_ref)
    if extra:
        target.update(extra)
    return {
        "category": category,
        "target_ref": target,
        "parameter_key": parameter_key,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "unit": unit,
        "confidence_score": confidence_score,
        "source_refs": [
            {
                "material_id": material.material_id,
                "excerpt": excerpt[:120],
                "page_or_sheet": material.file_name,
                "cell_or_region": "image-region" if material.kind == "image" else None,
                "note": "图片来源需人工核验" if material.kind == "image" else None,
            }
        ],
    }


def _candidate_dict(
    *,
    category: str,
    display_name: str,
    proposed_fields: dict[str, Any],
    confidence_score: int,
    material: AiParameterMaterial,
    excerpt: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "display_name": display_name,
        "proposed_fields": proposed_fields,
        "confidence_score": confidence_score,
        "source_refs": [
            {
                "material_id": material.material_id,
                "excerpt": excerpt[:120],
                "page_or_sheet": material.file_name,
                "cell_or_region": "image-region" if material.kind == "image" else None,
                "note": "图片来源需人工核验" if material.kind == "image" else None,
            }
        ],
    }


def _confidence_for_material(material: AiParameterMaterial, score: int) -> int:
    if material.kind == "image":
        return min(score, 45)
    if material.parse_status == "partially_parsed":
        return min(score, 62)
    return score


def _looks_like_structure_replacement(text: str) -> bool:
    return any(keyword in text for keyword in ("\u8de8\u5f84", "\u58a9\u53f0", "\u6869\u57fa\u6570\u91cf", "\u6869\u957f", "\u6865\u8de8", "\u6865\u58a9\u6570\u91cf")) and not any(
        keyword in text for keyword in ("\u5de5\u6548", "\u8d44\u6e90", "\u91cc\u7a0b\u7891", "\u8282\u70b9")
    )


def _clean_milestone_name(text: str) -> str:
    text = re.sub(r"^[,\uff0c\uff1a:\s]+", "", text)
    text = re.sub(r"(\u8ba1\u5212|\u8981\u6c42|\u8282\u70b9|\u76ee\u6807)$", "", text)
    return text[-18:].strip("\uff0c,\u3002\uff1b;")


def _slug(text: str) -> str:
    ascii_part = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    if ascii_part:
        return ascii_part
    return f"ai_resource_{abs(hash(text)) % 100000}"
