from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import AiParameterApplyRequest  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAiPayload  # noqa: E402
from app.services.ai_parameter_assistant import AiParameterAssistantError, apply_ai_parameter_suggestions, parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_conflicting_suggestions_must_be_resolved_before_apply() -> None:
    scenario = default_scenario()
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "旋挖钻 2 台；旋挖钻 3 台"},
        {},
        client=FakeAiClient(
            [
                _resource_suggestion(scenario, 2),
                _resource_suggestion(scenario, 3),
            ]
        ),
        store=store,
    )

    assert len(response.conflict_groups) == 1
    assert all(item.status == "conflict" for item in response.suggestions)
    with pytest.raises(AiParameterAssistantError):
        apply_ai_parameter_suggestions(
            AiParameterApplyRequest(
                scenario=scenario,
                run_id=response.run_id,
                selected_suggestion_ids=[response.suggestions[0].suggestion_id],
            ),
            store=store,
        )


def _resource_suggestion(scenario, value: int) -> dict:  # type: ignore[no-untyped-def]
    return {
        "category": "resource_pool",
        "target_ref": {"resource_type": scenario.resource_pools[0].type},
        "parameter_key": "resource.quantity",
        "proposed_value": value,
        "unit": "台",
        "confidence_score": 88,
        "source_refs": [{"material_id": "mat_text_001", "excerpt": f"旋挖钻 {value} 台"}],
    }


class FakeAiClient(AiParameterAiClient):
    def __init__(self, suggestions: list[dict]) -> None:
        self.suggestions = suggestions

    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(suggestions=self.suggestions)
