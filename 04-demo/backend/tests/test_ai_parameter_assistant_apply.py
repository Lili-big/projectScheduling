from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import AiParameterApplyRequest, ResourcePool  # noqa: E402
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


def test_apply_resource_suggestion_rejects_ambiguous_resource_type_without_pool_id() -> None:
    scenario = default_scenario()
    source = scenario.resource_pools[0]
    scenario.resource_pools.append(
        ResourcePool(
            id=f"{source.id}-second",
            type=source.type,
            label=f"{source.label}二号池",
            quantity=3,
            max_quantity=5,
        )
    )
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "建议"},
        {},
        client=FakeAiClient(
            [
                {
                    "category": "resource_pool",
                    "target_ref": {"resource_type": source.type},
                    "parameter_key": "resource.quantity",
                    "proposed_value": 2,
                    "unit": "台",
                    "confidence_score": 88,
                    "source_refs": [{"material_id": "mat_text_001", "excerpt": "建议 2 台"}],
                }
            ]
        ),
        store=store,
    )

    result = apply_ai_parameter_suggestions(
        AiParameterApplyRequest(
            scenario=scenario,
            run_id=response.run_id,
            selected_suggestion_ids=[response.suggestions[0].suggestion_id],
        ),
        store=store,
    )

    assert result.stale_results is False
    assert result.application_summary.applied_count == 0
    assert result.application_summary.failed_count == 1
    assert "多个资源池" in result.application_summary.failed_items[0].message
    assert [pool.quantity for pool in result.scenario.resource_pools if pool.type == source.type] == [
        source.quantity,
        3,
    ]


class FakeAiClient(AiParameterAiClient):
    def __init__(self, suggestions: list[dict]) -> None:
        self.suggestions = suggestions

    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(suggestions=self.suggestions)
