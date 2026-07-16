from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

import app.models as legacy  # noqa: E402
from app.contracts import girder, plan_control  # noqa: E402


def test_girder_and_plan_control_contracts_keep_identity() -> None:
    assert girder.ProjectDataVersion is legacy.ProjectDataVersion
    assert girder.IntegratedCalculationSnapshot is legacy.IntegratedCalculationSnapshot
    assert plan_control.PlanVersion is legacy.PlanVersion
    assert plan_control.ForecastSchedule is legacy.ForecastSchedule


def test_version_and_store_status_fields_remain_serializable() -> None:
    assert "status" in girder.ProjectDataVersion.model_json_schema()["properties"]
    assert "schema_version" in plan_control.PlanControlStore.model_json_schema()["properties"]
