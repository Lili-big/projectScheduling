from __future__ import annotations

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.bootstrap import create_app  # noqa: E402
from app.contracts import ScenarioInput  # noqa: E402
from app.contracts.project_master import (  # noqa: E402
    ProjectMasterRoutePlacement,
    ProjectMasterSnapshot,
    TaskViewDisplayMapRequest,
    TaskViewDisplayMapResponse,
)
from app.project_master.definitions import COMPONENT_TYPES  # noqa: E402
from app.project_master.validation import validate_snapshot  # noqa: E402
from project_master_fixture_helpers import abutment_projection_snapshot  # noqa: E402


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
        "/api/project-master/versions/{version_id}/task-view-display-map",
        "/api/project-master/versions/{version_id}/export",
    }
    assert expected <= set(paths)
    scenario = ScenarioInput.model_json_schema()
    assert "project_data_version_id" in scenario["properties"]
    assert "project_master_version_id" not in scenario["properties"]
    assert "project_master_fingerprint" not in scenario["properties"]
    snapshot_schema = ProjectMasterSnapshot.model_json_schema()
    assert snapshot_schema["title"] == "ProjectMasterSnapshot"
    assert "route_placements" in snapshot_schema["properties"]
    assert set(ProjectMasterRoutePlacement.model_json_schema()["properties"]) >= {
        "placement_id",
        "workpoint_id",
        "side",
        "mileage_prefix",
        "spatial_group_id",
        "display_order",
    }
    request_schema = TaskViewDisplayMapRequest.model_json_schema()
    assert request_schema["properties"]["workpoint_ids"]["maxItems"] == 500
    response_schema = TaskViewDisplayMapResponse.model_json_schema()
    assert set(response_schema["properties"]) == {"project_data_version_id", "workpoints"}
    operation = paths["/api/project-master/versions/{version_id}/task-view-display-map"]["post"]
    assert operation["requestBody"]["required"] is True
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/TaskViewDisplayMapResponse"
    )


def test_legacy_import_endpoints_are_visible_but_deprecated() -> None:
    paths = create_app().openapi()["paths"]
    assert paths["/api/girder-planning/import-workpoints"]["post"]["deprecated"] is True
    assert paths["/api/import-bridge-params"]["post"]["deprecated"] is True
    assert paths["/api/project-structure-params"]["get"]["deprecated"] is True


def test_project_master_contract_supports_abutment_body_and_cap_beam_without_identity_rules() -> None:
    snapshot = abutment_projection_snapshot()
    component_types = {
        component.component_type
        for workpoint in snapshot.workpoints
        for structure in workpoint.structures
        for component in structure.components
    }

    assert {"abutment_body", "cap_beam"} <= component_types
    assert {"abutment_body", "cap_beam"} <= COMPONENT_TYPES.keys()
    assert not [issue for issue in validate_snapshot(snapshot) if issue.issue_code == "COMPONENT_TYPE_INVALID"]
