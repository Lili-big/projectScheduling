from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAiPayload  # noqa: E402
from app.services.ai_parameter_assistant import parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_ai_parameter_parse_returns_three_categories_and_store_entry() -> None:
    scenario = default_scenario()
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "资料"},
        {},
        client=FakeAiClient(
            [
                _suggestion("process_productivity", {"process_id": scenario.process_library[0].id}, "process.productivity_value", 4, "根/天"),
                _suggestion("resource_pool", {"resource_type": scenario.resource_pools[0].type}, "resource.quantity", 2, "台"),
                _suggestion("milestone", {"milestone_id": scenario.milestones[0].id}, "milestone.target_date", "2027-12-31", "date"),
            ]
        ),
        store=store,
    )

    assert response.status == "completed"
    assert {item.category for item in response.suggestions} == {"process_productivity", "resource_pool", "milestone"}
    assert all(item.source_refs for item in response.suggestions)
    assert store.get(response.run_id).suggestions[0].suggestion_id == "sug_001"
    assert scenario.resource_pools[0].quantity == 1


def _suggestion(category: str, target_ref: dict, parameter_key: str, value, unit: str) -> dict:
    return {
        "category": category,
        "target_ref": target_ref,
        "parameter_key": parameter_key,
        "proposed_value": value,
        "unit": unit,
        "confidence_score": 88,
        "source_refs": [{"material_id": "mat_text_001", "excerpt": str(value)}],
    }


class FakeAiClient(AiParameterAiClient):
    def __init__(self, suggestions: list[dict]) -> None:
        self.suggestions = suggestions

    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(suggestions=self.suggestions)
