from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import app.models as legacy  # noqa: E402
from app.contracts import common, project, scheduling  # noqa: E402


def test_scheduling_contracts_are_the_legacy_objects_not_copies() -> None:
    assert common.ValidationMessage is legacy.ValidationMessage
    assert project.ScenarioInput is legacy.ScenarioInput
    assert scheduling.ScheduleInput is legacy.ScheduleInput
    assert scheduling.ScheduleResult is legacy.ScheduleResult


def test_scenario_defaults_and_schedule_json_stay_snake_case() -> None:
    schema = project.ScenarioInput.model_json_schema()
    assert "scenario_id" in schema["properties"]
    assert scheduling.ScheduleResult.model_json_schema()["properties"]["tasks"]
