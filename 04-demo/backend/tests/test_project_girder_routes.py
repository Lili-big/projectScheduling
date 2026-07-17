from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routers.project_girder import router  # noqa: E402


def test_project_girder_router_owns_versions_imports_and_integrated_schedule() -> None:
    operations = {(method, route.path, route.status_code) for route in router.routes for method in route.methods}
    assert ("POST", "/api/project-data-versions", 201) in operations
    assert ("POST", "/api/planning-scenario-versions", 201) in operations
    assert any(path == "/api/girder-planning/import-workpoints" for _, path, _ in operations)
    assert any(path == "/api/girder-planning/validate" for _, path, _ in operations)
    assert any(path == "/api/integrated-schedules" for _, path, _ in operations)


def test_project_girder_router_keeps_bridge_import_compatibility() -> None:
    paths = {route.path for route in router.routes}
    assert {"/api/import-bridge-params", "/api/import-local-bridge-params"} <= paths
