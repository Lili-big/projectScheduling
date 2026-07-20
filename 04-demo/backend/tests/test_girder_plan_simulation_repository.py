from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.contracts.girder_plan_simulation import ConfirmSimulationRunRequest, GirderPlanSimulationRun
from app.girder_plan_simulation.repository import GirderPlanConflictError, GirderPlanRepository
from girder_plan_simulation_fixture_helpers import line_graph, scenario_request


def test_repository_versions_fingerprints_and_stale_history(tmp_path) -> None:
    repository = GirderPlanRepository(tmp_path / "state" / "girder-plan.json")
    first = repository.create_scenario_version(scenario_request(scenario_id="S1"))
    request = scenario_request(scenario_id="S1")
    request.expected_latest_version_no = 1
    request.beam_yards[0].capacities[0].daily_capacity_pieces = 8
    second = repository.create_scenario_version(request)
    assert first.version_no == 1 and second.version_no == 2
    assert first.input_fingerprint != second.input_fingerprint
    assert repository.get_scenario_version(first.scenario_version_id).status == "stale"
    with pytest.raises(GirderPlanConflictError):
        stale = scenario_request(scenario_id="S1")
        stale.expected_latest_version_no = 1
        repository.create_scenario_version(stale)


def test_run_snapshot_is_immutable_reusable_and_confirmable(tmp_path) -> None:
    repository = GirderPlanRepository(tmp_path / "girder-plan.json")
    scenario = repository.create_scenario_version(scenario_request())
    now = datetime.now(timezone.utc)
    run = GirderPlanSimulationRun(
        run_id="RUN1",
        scenario_version_id=scenario.scenario_version_id,
        project_master_version_id="PMV1",
        status="calculated",
        started_at=now,
        finished_at=now,
        input_fingerprint=scenario.input_fingerprint,
        result_fingerprint="sha256:test",
    )
    repository.save_run(run)
    assert repository.find_reusable_run(scenario.scenario_version_id, scenario.input_fingerprint).run_id == "RUN1"
    with pytest.raises(GirderPlanConflictError):
        repository.save_run(run)
    confirmed = repository.confirm_run(
        "RUN1",
        ConfirmSimulationRunRequest(
            expected_input_fingerprint=scenario.input_fingerprint,
            confirmed_by="总工",
            confirmation_reason="独立策划复核通过",
        ),
    )
    assert confirmed.status == "confirmed"
    assert repository.get_scenario_version(scenario.scenario_version_id).status == "confirmed"
