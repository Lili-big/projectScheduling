from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app.girder_planning.fingerprints import stable_fingerprint  # noqa: E402
from app.scenario import generate_schedule_input_from_scenario  # noqa: E402
from app.scenario_data import default_scenario  # noqa: E402
from capture_architecture_baseline import _scenario_manifest  # noqa: E402


FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "architecture" / "backend-baseline.json"
API_MIRROR = BACKEND_ROOT.parent / "tools" / "demo-api-mirror" / "api.mts"


def test_default_scenario_and_task_generation_are_behaviorally_stable() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["fixed_scenario"]
    assert _scenario_manifest() == expected
    assert expected["task_count"] > 0


def test_generated_schedule_keeps_task_identity_and_resource_candidates_stable() -> None:
    generated = generate_schedule_input_from_scenario(default_scenario())
    tasks = generated.schedule_input.tasks
    assert tasks
    assert len({task.id for task in tasks}) == len(tasks)
    assert all(task.duration_days >= 1 for task in tasks)
    resource_types = {resource.type for resource in generated.schedule_input.resources}
    assert any(task.compatible_resource_types for task in tasks)
    assert all(set(task.compatible_resource_types) <= resource_types for task in tasks)


def test_stable_fingerprint_ignores_mapping_order_but_not_business_values() -> None:
    assert stable_fingerprint({"a": 1, "b": [2, 3]}) == stable_fingerprint({"b": [2, 3], "a": 1})
    assert stable_fingerprint({"a": 1}) != stable_fingerprint({"a": 2})


def test_demo_api_mirror_preserves_pool_identity_and_explicit_workpoint_scope() -> None:
    source = API_MIRROR.read_text(encoding="utf-8")

    assert 'workpoint_id?: string | null' in source
    assert 'scope_mode?: "PROJECT_SHARED" | "WORKPOINT_EXCLUSIVE"' in source
    assert 'id: `${poolModel.id}_${index + 1}`' in source
    assert 'resource.exclusive_workpoint_id === task.bridge_id' in source
    assert 'resource.eligible_workpoint_ids.includes(task.bridge_id)' in source
    assert "manual_transfer_order" not in source
    assert "transfer_time_days" not in source
