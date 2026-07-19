from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from pydantic import ValidationError

from ..contracts import (
    ResourceAssistantComparison,
    ResourceAssistantLlmConfigStatus,
    ResourceAssistantRecommendation,
)


class AiResourceAssistantLlmError(RuntimeError):
    pass


PROVIDER_ENV = "AI_RESOURCE_ASSISTANT_PROVIDER"
ENDPOINT_ENV = "AI_RESOURCE_ASSISTANT_ENDPOINT"
MODEL_ENV = "AI_RESOURCE_ASSISTANT_MODEL"
API_KEY_ENV = "AI_RESOURCE_ASSISTANT_API_KEY"
TIMEOUT_ENV = "AI_RESOURCE_ASSISTANT_TIMEOUT_SECONDS"
TEMPERATURE_ENV = "AI_RESOURCE_ASSISTANT_TEMPERATURE"
RESPONSE_FORMAT_ENV = "AI_RESOURCE_ASSISTANT_RESPONSE_FORMAT"

SHARED_PROVIDER_ENV = "PROCESS_NL_LLM_PROVIDER"
SHARED_ENDPOINT_ENV = "PROCESS_NL_LLM_ENDPOINT"
SHARED_MODEL_ENV = "PROCESS_NL_LLM_MODEL"
SHARED_API_KEY_ENV = "PROCESS_NL_LLM_API_KEY"
SHARED_TEMPERATURE_ENV = "PROCESS_NL_LLM_TEMPERATURE"
SHARED_RESPONSE_FORMAT_ENV = "PROCESS_NL_LLM_RESPONSE_FORMAT"


SUPPORTED_OPENAI_COMPATIBLE_PROVIDERS = {
    "openai",
    "openai_compatible",
    "openai-compatible",
    "chat_completions",
    "deepseek",
    "qwen",
    "siliconflow",
}
SUPPORTED_GENERIC_PROVIDERS = {"http", "generic_http"}
LOCAL_PROVIDERS = {"", "local", "heuristic", "none", "off"}


def llm_config_status(warning: str | None = None) -> ResourceAssistantLlmConfigStatus:
    provider = _provider()
    endpoint = _endpoint()
    api_key = _api_key()
    model = _model() or None
    status = "local_fallback" if provider in LOCAL_PROVIDERS else "configured"
    if warning:
        status = "failed" if provider not in LOCAL_PROVIDERS else "local_fallback"
    return ResourceAssistantLlmConfigStatus(
        provider=provider or "local",
        model=model,
        endpoint_configured=bool(endpoint),
        api_key_configured=bool(api_key),
        timeout_seconds=_timeout_seconds(),
        status=status,
        warning=warning,
    )


def generate_resource_plan_payload(
    context: dict[str, Any],
    validation_errors: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]] | None, ResourceAssistantLlmConfigStatus]:
    provider = _provider()
    if provider in LOCAL_PROVIDERS:
        return None, llm_config_status()
    try:
        raw = _call_llm_json(
            instruction=_plan_generation_instruction(),
            payload={
                "task": "resource_plan_generation_correction" if validation_errors else "resource_plan_generation",
                "context": context,
                "output_schema": _plan_generation_output_schema(),
                **({"validation_errors": validation_errors} if validation_errors else {}),
            },
            provider=provider,
        )
    except AiResourceAssistantLlmError as exc:
        return None, llm_config_status(str(exc))
    plans = _extract_plans(raw)
    if plans is None:
        return None, llm_config_status("AI 资源方案返回格式不符合要求，已改用本地回退。")
    return plans, llm_config_status()


def explain_recommendation(
    recommendation: ResourceAssistantRecommendation,
    comparison: ResourceAssistantComparison,
) -> ResourceAssistantRecommendation:
    provider = _provider()
    if provider in LOCAL_PROVIDERS:
        return recommendation.model_copy(
            update={
                "ai_explanation": local_recommendation_explanation(recommendation),
                "explanation_source": "local",
                "llm_status": llm_config_status(),
            }
        )
    try:
        raw = _call_llm_json(
            instruction=_recommendation_instruction(),
            payload={
                "task": "recommendation_explanation",
                "recommendation": recommendation.model_dump(mode="json"),
                "comparison": comparison.model_dump(mode="json"),
                "output_schema": {"ai_explanation": "面向项目经理的中文解释，不超过 600 字。"},
            },
            provider=provider,
        )
        explanation = _extract_explanation(raw)
        if not explanation:
            raise AiResourceAssistantLlmError("AI 推荐解释返回中缺少 ai_explanation。")
        return recommendation.model_copy(
            update={
                "ai_explanation": explanation,
                "explanation_source": "llm",
                "llm_status": llm_config_status(),
            }
        )
    except AiResourceAssistantLlmError as exc:
        return recommendation.model_copy(
            update={
                "ai_explanation": local_recommendation_explanation(recommendation),
                "explanation_source": "local",
                "llm_status": llm_config_status(str(exc)),
            }
        )


def local_recommendation_explanation(recommendation: ResourceAssistantRecommendation) -> str:
    if recommendation.recommendation_status != "recommended" or not recommendation.recommended_scenario_id:
        reason = recommendation.rule_reason or "当前没有足够可比较的可行求解结果。"
        return f"暂无推荐方案。{reason}建议先调整资源配置、目标节点或项目数据后重新求解。"
    evidence = "；".join(recommendation.evidence[:4]) or "推荐来自三方案求解指标对比。"
    risks = "；".join(recommendation.risk_notes[:3]) or "需继续关注控制墩释放和关键资源利用。"
    marginal = "；".join(recommendation.marginal_benefit_notes[:3]) or "边际收益以工期、成本和等待指标综合判断。"
    return (
        f"推荐 {recommendation.recommended_scenario_id}。主要依据：{evidence}。"
        f"主要风险：{risks}。边际收益判断：{marginal}。"
        "该推荐来自 CP-SAT 求解结果和指标对比，AI 仅负责解释。"
    )


def _call_llm_json(*, instruction: str, payload: dict[str, Any], provider: str) -> Any:
    endpoint = _endpoint()
    if not endpoint:
        raise AiResourceAssistantLlmError(f"{ENDPOINT_ENV} 或 {SHARED_ENDPOINT_ENV} 未配置。")
    request_payload = (
        _openai_compatible_payload(instruction, payload)
        if provider in SUPPORTED_OPENAI_COMPATIBLE_PROVIDERS
        else _generic_payload(instruction, payload)
        if provider in SUPPORTED_GENERIC_PROVIDERS
        else None
    )
    if request_payload is None:
        raise AiResourceAssistantLlmError(f"不支持的 AI 资源助手 provider：{provider}。")

    request_body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = _api_key()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(endpoint, data=request_body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=_timeout_seconds()) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AiResourceAssistantLlmError(f"AI 资源助手服务调用失败：{exc}") from exc


def _openai_compatible_payload(instruction: str, payload: dict[str, Any]) -> dict[str, Any]:
    request_payload: dict[str, Any] = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": _temperature(),
    }
    if _response_format() not in {"", "none", "false", "off"}:
        request_payload["response_format"] = {"type": "json_object"}
    return request_payload


def _generic_payload(instruction: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": _model(),
        "instruction": instruction,
        **payload,
    }


def _extract_plans(raw: Any) -> list[dict[str, Any]] | None:
    payload = _extract_json_payload(raw)
    if isinstance(payload, dict) and isinstance(payload.get("plans"), list):
        return [item for item in payload["plans"] if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def _extract_explanation(raw: Any) -> str:
    payload = _extract_json_payload(raw)
    if isinstance(payload, dict):
        value = payload.get("ai_explanation") or payload.get("explanation") or payload.get("content")
        return str(value).strip() if value else ""
    return str(payload).strip() if payload else ""


def _extract_json_payload(raw: Any) -> Any:
    if isinstance(raw, dict) and ("plans" in raw or "ai_explanation" in raw or "explanation" in raw):
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
    raw = os.getenv(TIMEOUT_ENV, "30")
    try:
        return max(1, int(raw))
    except ValueError:
        return 30


def _temperature() -> float:
    raw = _env_value(TEMPERATURE_ENV, SHARED_TEMPERATURE_ENV, "0.2")
    try:
        return max(0, min(2, float(raw)))
    except ValueError:
        return 0.2


def _provider() -> str:
    return _env_value(PROVIDER_ENV, SHARED_PROVIDER_ENV, "local").lower()


def _endpoint() -> str:
    return _env_value(ENDPOINT_ENV, SHARED_ENDPOINT_ENV, "")


def _model() -> str:
    return _env_value(MODEL_ENV, SHARED_MODEL_ENV, "")


def _api_key() -> str:
    return _env_value(API_KEY_ENV, SHARED_API_KEY_ENV, "")


def _response_format() -> str:
    return _env_value(RESPONSE_FORMAT_ENV, SHARED_RESPONSE_FORMAT_ENV, "json_object").lower()


def _env_value(primary_env: str, shared_env: str, default: str) -> str:
    primary = os.getenv(primary_env)
    if primary is not None and primary.strip():
        return primary.strip()
    return os.getenv(shared_env, default).strip()


def _plan_generation_instruction() -> str:
    return (
        "你是桥梁施工资源配置方案助手。只返回 JSON，不输出 Markdown。"
        "你需要在同一次响应中生成 economy、balanced、crash 三套资源配置初始方案。"
        "输入中的 reference_examples 是当前项目的确定性三方案基线；resource_types 是唯一允许输出的资源类型。"
        "新数量统一在 scoped_resource_quantities 中按 resource_pool_id 输出；PROJECT_SHARED 的 workpoint_id 为空，"
        "WORKPOINT_EXCLUSIVE 必须输出其 workpoint_id。旧 resource_quantities 只兼容可唯一定位的单个项目共享池。"
        "不得输出或修改 scope_mode、workpoint_id、authorized_workpoint_ids、workpoint_overrides，不得新增资源池或工点。"
        "实际工作量为零、未映射、禁用或数据异常的资源在三个方案中都必须输出 0，不得扩充。"
        "所有数量必须是非负整数，不得超过 current_resource_pools 中原始 max_quantity，"
        "同类有效资源必须满足 economy 不高于 balanced、balanced 不高于 crash。"
        "organization_strategy 必须是字符串；如果收到 validation_errors，必须逐项纠正后完整重发三个方案。"
        "不得生成最终施工计划，不得生成任务起止日期，不得判断哪个方案最优。"
        "每个方案必须包含 profile、positioning、resource_quantities、scoped_resource_quantities、organization_strategy、"
        "generation_rationale、applicable_scenarios、expected_risks。"
    )


def _plan_generation_output_schema() -> dict[str, Any]:
    return {
        "plans": [
            {
                "profile": "economy",
                "positioning": "经济方案",
                "resource_quantities": {"rotary_drill": 4, "pier_body_team": 6},
                "scoped_resource_quantities": [
                    {"resource_pool_id": "pool-exclusive", "workpoint_id": "WP-A", "quantity": 2}
                ],
                "organization_strategy": "优先保证控制墩，普通墩顺序推进。",
                "generation_rationale": "参考工程画像和经济方案样例。",
                "applicable_scenarios": "成本敏感、节点压力较低。",
                "expected_risks": "控制墩释放可能等待。",
            }
        ]
    }


def _recommendation_instruction() -> str:
    return (
        "你是桥梁施工排程结果解释助手。只返回 JSON，不输出 Markdown。"
        "推荐结论已经由系统根据 CP-SAT 求解结果确定，你不得改变 recommended_scenario_id。"
        "解释必须引用 recommendation.evidence 中的指标证据，并说明风险和边际收益。"
    )
