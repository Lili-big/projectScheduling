from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import AiParameterApplyRequest  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAiPayload  # noqa: E402
from app.services.ai_parameter_assistant import AiParameterAssistantError, apply_ai_parameter_suggestions, parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_suggestion_store_expiry_blocks_apply_and_does_not_store_original_file() -> None:
    scenario = default_scenario()
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "旋挖钻 2 台"},
        {},
        client=FakeAiClient(),
        store=store,
    )
    entry = store.get(response.run_id)
    assert not hasattr(entry.material_summaries[0], "content")
    entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(AiParameterAssistantError) as exc:
        apply_ai_parameter_suggestions(
            AiParameterApplyRequest(
                scenario=scenario,
                run_id=response.run_id,
                selected_suggestion_ids=[response.suggestions[0].suggestion_id],
            ),
            store=store,
        )
    assert exc.value.status_code == 410
    assert scenario.resource_pools[0].quantity == 1


class FakeAiClient(AiParameterAiClient):
    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        return AiParameterAiPayload(
            suggestions=[
                {
                    "category": "resource_pool",
                    "target_ref": {"resource_type": scenario.resource_pools[0].type},
                    "parameter_key": "resource.quantity",
                    "proposed_value": 2,
                    "unit": "台",
                    "confidence_score": 88,
                    "source_refs": [{"material_id": "mat_text_001", "excerpt": "旋挖钻 2 台"}],
                }
            ]
        )
