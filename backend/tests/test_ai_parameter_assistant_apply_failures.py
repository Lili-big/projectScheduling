from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import AiParameterApplyRequest  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAiPayload  # noqa: E402
from app.services.ai_parameter_assistant import apply_ai_parameter_suggestions, parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_apply_keeps_valid_items_when_unrelated_suggestion_fails() -> None:
    scenario = default_scenario()
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "建议"},
        {},
        client=FakeAiClient(
            [
                {
                    "category": "resource_pool",
                    "target_ref": {"resource_type": scenario.resource_pools[0].type},
                    "parameter_key": "resource.quantity",
                    "proposed_value": 2,
                    "unit": "台",
                    "confidence_score": 88,
                    "source_refs": [{"material_id": "mat_text_001", "excerpt": "旋挖钻 2 台"}],
                },
                {
                    "category": "resource_pool",
                    "target_ref": {"resource_type": "missing_resource"},
                    "parameter_key": "resource.quantity",
                    "proposed_value": 9,
                    "unit": "台",
                    "confidence_score": 88,
                    "source_refs": [{"material_id": "mat_text_001", "excerpt": "不存在资源 9 台"}],
                },
            ]
        ),
        store=store,
    )
    result = apply_ai_parameter_suggestions(
        AiParameterApplyRequest(
            scenario=scenario,
            run_id=response.run_id,
            selected_suggestion_ids=[item.suggestion_id for item in response.suggestions],
        ),
        store=store,
    )

    assert result.scenario.resource_pools[0].quantity == 2
    assert result.application_summary.applied_count == 1
    assert result.application_summary.failed_count == 1


class FakeAiClient(AiParameterAiClient):
    def __init__(self, suggestions: list[dict]) -> None:
        self.suggestions = suggestions

    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(suggestions=self.suggestions)
