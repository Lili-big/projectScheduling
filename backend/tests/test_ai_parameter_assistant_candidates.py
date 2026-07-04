from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models import AiParameterApplyRequest  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import LocalHeuristicAiParameterClient  # noqa: E402
from app.services.ai_parameter_assistant import apply_ai_parameter_suggestions, parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_candidate_resource_is_not_added_until_selected() -> None:
    scenario = default_scenario()
    store = AiParameterStore()
    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "智能张拉班组 3 组"},
        {},
        client=LocalHeuristicAiParameterClient(),
        store=store,
    )

    assert response.candidate_additions
    assert not any(pool.label == "智能张拉班组" for pool in scenario.resource_pools)

    response = parse_ai_parameter_assistant(
        {"scenario": scenario.model_dump_json(), "text_inputs[]": "智能张拉班组 3 组"},
        {},
        client=LocalHeuristicAiParameterClient(),
        store=store,
    )
    applied = apply_ai_parameter_suggestions(
        AiParameterApplyRequest(
            scenario=scenario,
            run_id=response.run_id,
            selected_suggestion_ids=[response.candidate_additions[0].candidate_id],
        ),
        store=store,
    )
    assert any(pool.label == "智能张拉班组" for pool in applied.scenario.resource_pools)
