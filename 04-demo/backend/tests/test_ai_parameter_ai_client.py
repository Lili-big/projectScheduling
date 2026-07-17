from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import ai_parameter_ai_client  # noqa: E402
from app.services.ai_parameter_ai_client import (  # noqa: E402
    AiParameterAssistantConfigError,
    LocalHeuristicAiParameterClient,
    get_ai_parameter_client,
)
from app.services.ai_parameter_materials import AiParameterMaterial  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402


def test_local_heuristic_adapter_extracts_chinese_schedule_parameters() -> None:
    scenario = default_scenario()
    material = AiParameterMaterial(
        material_id="mat_text_001",
        file_name="文本",
        kind="text",
        size_bytes=120,
        content_text="旋挖钻 2 台。旋挖钻工效调整为 4 根/天。下部及现浇结构施工完成 2027-12-31。",
        source_summary="旋挖钻 2 台。旋挖钻工效调整为 4 根/天。",
        parse_status="parsed",
    )

    payload = LocalHeuristicAiParameterClient().understand(scenario=scenario, materials=[material])

    categories = {item["category"] for item in payload.suggestions}
    assert {"process_productivity", "resource_pool", "milestone"} <= categories
    assert any(item["proposed_value"] == 4 for item in payload.suggestions)
    assert any(item["proposed_value"] == 2 for item in payload.suggestions)
    assert any(item["proposed_value"] == "2027-12-31" for item in payload.suggestions)


def test_ai_parameter_http_adapter_requires_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PARAMETER_ASSISTANT_PROVIDER", "http")
    monkeypatch.delenv("AI_PARAMETER_ASSISTANT_ENDPOINT", raising=False)

    with pytest.raises(AiParameterAssistantConfigError):
        get_ai_parameter_client()


def test_ai_parameter_openai_adapter_validates_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_PARAMETER_ASSISTANT_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AI_PARAMETER_ASSISTANT_ENDPOINT", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("AI_PARAMETER_ASSISTANT_MODEL", "test-model")
    monkeypatch.setenv("AI_PARAMETER_ASSISTANT_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int = 0):  # type: ignore[no-untyped-def]
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = request.data.decode("utf-8")
        return FakeJsonResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "suggestions": [
                                        {
                                            "category": "resource_pool",
                                            "target_ref": {"resource_type": "rotary_drill"},
                                            "parameter_key": "resource.quantity",
                                            "proposed_value": 2,
                                            "unit": "台",
                                            "confidence_score": 88,
                                            "source_refs": [{"material_id": "mat_text_001", "excerpt": "旋挖钻 2 台"}],
                                        }
                                    ],
                                    "candidate_additions": [],
                                    "warnings": [],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr(ai_parameter_ai_client.urllib.request, "urlopen", fake_urlopen)

    client = get_ai_parameter_client()
    payload = client.understand(
        scenario=default_scenario(),
        materials=[
            AiParameterMaterial(
                material_id="mat_text_001",
                file_name="文本",
                kind="text",
                size_bytes=10,
                content_text="旋挖钻 2 台",
                source_summary="旋挖钻 2 台",
                parse_status="parsed",
            )
        ],
    )

    assert "chat/completions" in captured["url"]
    assert "Bearer test-key" in captured["headers"].values()
    assert '"messages"' in captured["payload"]
    assert payload.suggestions[0]["parameter_key"] == "resource.quantity"


class FakeJsonResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self) -> "FakeJsonResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:  # type: ignore[no-untyped-def]
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")
