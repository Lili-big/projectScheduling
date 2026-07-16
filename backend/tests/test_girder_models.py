from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from app.girder_planning.fingerprints import canonical_json, stable_fingerprint
from app.models import (
    BeamYardConfig,
    GirderPlanningConfig,
    GirderRouteConfig,
    GirderRouteNode,
    PlanControlStore,
    ScenarioInput,
    ValidationMessage,
)
from app.services.process_library_service import default_scenario_with_process_library


def test_girder_dto_defaults_and_scenario_backward_compatibility() -> None:
    legacy_payload = default_scenario_with_process_library().model_dump(mode="json")
    legacy_payload.pop("girder_planning", None)

    restored = ScenarioInput.model_validate(legacy_payload)

    assert restored.girder_planning is None
    assert PlanControlStore().schema_version == "plan-control/v2"
    assert ValidationMessage(level="error", code="GIRDER_BLOCKED", message="阻断").code == "GIRDER_BLOCKED"


def test_girder_config_validates_inventory_and_route_order() -> None:
    yard = BeamYardConfig(
        beam_yard_id="yard-1",
        name="一号梁场",
        mileage_m=1000,
        side="left",
        corridor_id="main",
        production_start_date=date(2026, 1, 1),
        daily_production_capacity=4,
        initial_inventory_by_type={"T": 10},
    )
    config = GirderPlanningConfig(enabled=True, beam_yards=[yard])
    assert config.beam_yards[0].initial_inventory_by_type["T"] == 10

    with pytest.raises(ValidationError, match="顺序号不能重复"):
        GirderRouteConfig(
            route_id="route-1",
            name="路线一",
            beam_yard_id="yard-1",
            erection_machine_id="machine-1",
            nodes=[
                GirderRouteNode(route_node_id="n1", workpoint_id="w1", sequence_index=0),
                GirderRouteNode(route_node_id="n2", workpoint_id="w2", sequence_index=0),
            ],
        )


def test_fingerprint_is_stable_for_mapping_order_and_changes_with_input() -> None:
    left = {"b": [2, 1], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "b": [2, 1]}

    assert canonical_json(left) == canonical_json(right)
    assert stable_fingerprint(left) == stable_fingerprint(right)
    assert stable_fingerprint(left) != stable_fingerprint({**left, "c": 3})
