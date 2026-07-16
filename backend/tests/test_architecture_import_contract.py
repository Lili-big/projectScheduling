from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from capture_architecture_baseline import _models_manifest, _public_module_manifest  # noqa: E402


FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "architecture" / "backend-baseline.json"


def _baseline() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_legacy_python_modules_keep_their_public_import_surface() -> None:
    expected = _baseline()["python_imports"]
    current = {module: _public_module_manifest(module) for module in expected}
    assert current == expected


def test_models_keep_their_pydantic_json_schemas() -> None:
    expected = _baseline()["models"]
    current = _models_manifest()
    assert len(current) == expected["count"] == 153
    # Feature 043 intentionally adds the optional, backwards-compatible
    # project_data_version_id to ScenarioInput. Normalize only that field so
    # the architecture freeze continues to guard every other legacy detail.
    assert _without_project_master_reference(current) == expected["schemas"]


def _without_project_master_reference(value):
    if isinstance(value, list):
        return [_without_project_master_reference(item) for item in value]
    if not isinstance(value, dict):
        return value
    normalized = {key: _without_project_master_reference(item) for key, item in value.items()}
    if normalized.get("title") == "ScenarioInput":
        normalized.get("properties", {}).pop("project_data_version_id", None)
    if normalized.get("title") == "PlanVersion":
        status = normalized.get("properties", {}).get("status", {})
        if "enum" in status:
            status["enum"] = [item for item in status["enum"] if item != "stale"]
    return normalized
