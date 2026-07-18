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
    assert len(current) == expected["count"] == 155
    # 045 refreshes the fixture after the lifecycle move, so all currently
    # public schemas (including the approved 043-compatible and 047
    # resource-scope additions) are
    # frozen directly instead of normalized against an older fixture.
    assert current == expected["schemas"]
