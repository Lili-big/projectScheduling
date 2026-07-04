from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_ai_client import AiParameterAiClient, AiParameterAssistantConfigError  # noqa: E402
from app.services.ai_parameter_assistant import AiParameterAssistantError, parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_materials import AiParameterMaterialError  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_ai_parameter_parse_rejects_missing_materials() -> None:
    with pytest.raises(AiParameterMaterialError):
        parse_ai_parameter_assistant({"scenario": default_scenario().model_dump_json()}, {}, store=AiParameterStore())


def test_ai_parameter_parse_rejects_too_many_files() -> None:
    files = {f"file_{index}": {"filename": f"{index}.txt", "content": b"x"} for index in range(11)}
    with pytest.raises(AiParameterMaterialError):
        parse_ai_parameter_assistant({"scenario": default_scenario().model_dump_json()}, files, store=AiParameterStore())


def test_ai_parameter_parse_rejects_missing_scenario() -> None:
    with pytest.raises(AiParameterAssistantError):
        parse_ai_parameter_assistant({"text_inputs[]": "旋挖钻 2 台"}, {}, store=AiParameterStore())


def test_ai_parameter_parse_surfaces_ai_service_failure() -> None:
    with pytest.raises(AiParameterAssistantConfigError):
        parse_ai_parameter_assistant(
            {"scenario": default_scenario().model_dump_json(), "text_inputs[]": "旋挖钻 2 台"},
            {},
            client=FailingAiClient(),
            store=AiParameterStore(),
        )


class FailingAiClient(AiParameterAiClient):
    def understand(self, *, scenario, materials):  # type: ignore[no-untyped-def]
        raise AiParameterAssistantConfigError("AI unavailable")
