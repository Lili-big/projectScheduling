from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import LocalHeuristicAiParameterClient  # noqa: E402
from app.services.ai_parameter_assistant import parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_structure_parameter_replacement_is_excluded_from_suggestions() -> None:
    fixture = json.loads(Path("backend/tests/fixtures/ai_parameter_assistant_cases.json").read_text(encoding="utf-8"))
    response = parse_ai_parameter_assistant(
        {"scenario": default_scenario().model_dump_json(), "text_inputs[]": fixture["structure_negative_case"]},
        {},
        client=LocalHeuristicAiParameterClient(),
        store=AiParameterStore(),
    )

    assert response.suggestions == []
    assert any("结构参数替换内容已排除" in warning.message for warning in response.warnings)
