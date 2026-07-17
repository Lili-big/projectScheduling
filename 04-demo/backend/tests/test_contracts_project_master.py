from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.bootstrap import create_app  # noqa: E402
from app.contracts import ScenarioInput  # noqa: E402
from app.contracts.project_master import ProjectMasterSnapshot  # noqa: E402


def test_openapi_exposes_project_master_contract_and_keeps_shared_field_names() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    expected = {
        "/api/project-master/template",
        "/api/projects/{project_id}/project-master/imports",
        "/api/project-master/imports/{batch_id}",
        "/api/projects/{project_id}/project-master/versions",
        "/api/projects/{project_id}/project-master/versions/current",
        "/api/project-master/versions/{version_id}",
        "/api/project-master/versions/{version_id}/confirm",
        "/api/project-master/versions/{version_id}/workpoints",
        "/api/project-master/versions/{version_id}/workpoints/{workpoint_id}",
        "/api/project-master/versions/{version_id}/export",
    }
    assert expected <= set(paths)
    scenario = ScenarioInput.model_json_schema()
    assert "project_data_version_id" in scenario["properties"]
    assert "project_master_version_id" not in scenario["properties"]
    assert "project_master_fingerprint" not in scenario["properties"]
    assert ProjectMasterSnapshot.model_json_schema()["title"] == "ProjectMasterSnapshot"


def test_legacy_import_endpoints_are_visible_but_deprecated() -> None:
    paths = create_app().openapi()["paths"]
    assert paths["/api/girder-planning/import-workpoints"]["post"]["deprecated"] is True
    assert paths["/api/import-bridge-params"]["post"]["deprecated"] is True
    assert paths["/api/project-structure-params"]["get"]["deprecated"] is True
