from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import process_nl  # noqa: E402
from app.models import AiParameterApplyRequest  # noqa: E402
from app.process_nl import ProcessNlIntent, ProcessNlIntentPayload  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from app.services.ai_parameter_assistant import apply_ai_parameter_suggestions, parse_ai_parameter_assistant  # noqa: E402
from app.services.ai_parameter_store import AiParameterStore  # noqa: E402


def test_process_method_mode_parse_returns_reviewable_suggestion_without_mutating_scenario(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    scenario = default_scenario()
    process = scenario.process_library[0]
    before_methods = _component_methods(scenario)
    store = AiParameterStore()

    monkeypatch.setattr(
        process_nl,
        "_understand_process_prompt",
        lambda scenario, prompt: ProcessNlIntentPayload(
            intents=[
                ProcessNlIntent(
                    component_type=process.component_type,
                    process_method_id=process.method_id or process.id,
                    process_name=process.process_name,
                    action="test process assignment",
                )
            ]
        ),
    )

    response = parse_ai_parameter_assistant(
        {
            "scenario": scenario.model_dump_json(),
            "assistant_mode": "process_method",
            "text_input": "set process",
        },
        {},
        store=store,
    )

    assert response.status == "completed"
    assert len(response.suggestions) == 1
    suggestion = response.suggestions[0]
    assert suggestion.category == "process_method_assignment"
    assert suggestion.parameter_key == "component.method_id"
    assert suggestion.target_ref["matched_count"] > 0
    assert suggestion.proposed_value == (process.method_id or process.id)
    assert _component_methods(scenario) == before_methods


def test_process_method_mode_apply_updates_only_after_selection(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    scenario = default_scenario()
    process = scenario.process_library[0]
    store = AiParameterStore()

    monkeypatch.setattr(
        process_nl,
        "_understand_process_prompt",
        lambda scenario, prompt: ProcessNlIntentPayload(
            intents=[
                ProcessNlIntent(
                    component_type=process.component_type,
                    process_method_id=process.method_id or process.id,
                    process_name=process.process_name,
                    action="test process assignment",
                )
            ]
        ),
    )

    response = parse_ai_parameter_assistant(
        {
            "scenario": scenario.model_dump_json(),
            "assistant_mode": "process_method",
            "text_input": "set process",
        },
        {},
        store=store,
    )
    suggestion = response.suggestions[0]
    target_ids = set(suggestion.target_ref["component_ids"])
    untouched_before = {
        component_id: method_id
        for component_id, method_id in _component_methods(scenario).items()
        if component_id not in target_ids
    }

    result = apply_ai_parameter_suggestions(
        AiParameterApplyRequest(
            scenario=scenario,
            run_id=response.run_id,
            selected_suggestion_ids=[suggestion.suggestion_id],
        ),
        store=store,
    )

    assert result.stale_results is True
    assert result.application_summary.applied_count == 1
    after_methods = _component_methods(result.scenario)
    assert all(after_methods[component_id] == suggestion.proposed_value for component_id in target_ids)
    assert {
        component_id: method_id
        for component_id, method_id in after_methods.items()
        if component_id not in target_ids
    } == untouched_before


def _component_methods(scenario) -> dict[str, str | None]:  # type: ignore[no-untyped-def]
    return {
        component.id: component.method_id
        for bridge in scenario.project.bridges
        for section in bridge.work_sections
        for structure in section.structures
        for component in structure.components
    }
