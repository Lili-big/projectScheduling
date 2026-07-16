from __future__ import annotations

import json
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from app.main import app  # noqa: E402
from capture_architecture_baseline import _route_manifest  # noqa: E402


FIXTURE = BACKEND_ROOT / "tests" / "fixtures" / "architecture" / "backend-baseline.json"


def test_all_api_routes_match_the_frozen_openapi_contract() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))["api"]
    current = _route_manifest(app)

    # 042 freezes the original 45 operations; later feature routers may add
    # operations but must not mutate those compatibility contracts.
    current_by_operation = {(item["method"], item["path"]): item for item in current}
    expected_by_operation = {(item["method"], item["path"]): item for item in expected["routes"]}
    assert len(current) >= 45
    assert {key: current_by_operation[key] for key in expected_by_operation} == expected_by_operation


def test_compatibility_routes_remain_available() -> None:
    routes = {(item["method"], item["path"]) for item in _route_manifest(app)}
    assert {("GET", "/api/demo"), ("POST", "/api/generate-wbs"), ("POST", "/api/solve")} <= routes
