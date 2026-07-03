from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAiPayload  # noqa: E402
from app.services.ai_parameter_assistant import parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_confidence_review_rules_and_batch_count() -> None:
    scenario = default_scenario()
    suggestions = []
    for index in range(20):
        score = 90 if index == 0 else 70 if index == 1 else 45 if index == 2 else 82
        suggestions.append(
            {
                "category": "resource_pool",
                "target_ref": {"resource_type": scenario.resource_pools[index % len(scenario.resource_pools)].type},
                "parameter_key": f"resource.quantity.{index}",
                "proposed_value": 2,
                "unit": "台",
                "confidence_score": score,
                "source_refs": [{"material_id": "mat_text_001", "excerpt": f"建议 {index}"}],
            }
        )
    suggestions.append(
        {
            "category": "resource_pool",
            "target_ref": {"resource_type": scenario.resource_pools[0].type},
            "parameter_key": "resource.no_source",
            "proposed_value": 5,
            "unit": "台",
            "confidence_score": 90,
            "source_refs": [],
        }
    )
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "批量建议"},
        {},
        client=FakeAiClient(suggestions),
        store=AiParameterStore(),
    )

    assert len(response.suggestions) == 21
    assert response.suggestions[0].confidence_label == "High"
    assert response.suggestions[1].confidence_label == "Medium"
    assert response.suggestions[2].status == "needs_manual_input"
    assert response.suggestions[-1].status == "needs_manual_input"


class FakeAiClient(AiParameterAiClient):
    def __init__(self, suggestions: list[dict]) -> None:
        self.suggestions = suggestions

    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(suggestions=self.suggestions)
