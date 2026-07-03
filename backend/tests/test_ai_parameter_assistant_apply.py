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


def test_apply_selected_process_resource_and_milestone_suggestions_only() -> None:
    scenario = default_scenario()
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "建议"},
        {},
        client=FakeAiClient(
            [
                {
                    "category": "process_productivity",
                    "target_ref": {"process_id": scenario.process_library[0].id},
                    "parameter_key": "process.productivity_value",
                    "proposed_value": 4,
                    "unit": "根/天",
                    "confidence_score": 88,
                    "source_refs": [{"material_id": "mat_text_001", "excerpt": "工效 4 根/天"}],
                },
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
                    "category": "milestone",
                    "target_ref": {"milestone_id": scenario.milestones[0].id},
                    "parameter_key": "milestone.target_date",
                    "proposed_value": "2027-12-31",
                    "unit": "date",
                    "confidence_score": 88,
                    "source_refs": [{"material_id": "mat_text_001", "excerpt": "2027-12-31"}],
                },
            ]
        ),
        store=store,
    )

    result = apply_ai_parameter_suggestions(
        AiParameterApplyRequest(
            scenario=scenario,
            run_id=response.run_id,
            selected_suggestion_ids=[item.suggestion_id for item in response.suggestions[:2]],
        ),
        store=store,
    )

    assert result.stale_results is True
    assert result.scenario.process_library[0].productivity_value == 4
    assert result.scenario.resource_pools[0].quantity == 2
    assert result.scenario.milestones[0].target_date == scenario.milestones[0].target_date
    assert result.application_summary.applied_count == 2


class FakeAiClient(AiParameterAiClient):
    def __init__(self, suggestions: list[dict]) -> None:
        self.suggestions = suggestions

    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(suggestions=self.suggestions)
