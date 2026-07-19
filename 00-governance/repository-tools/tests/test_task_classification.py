from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "00-governance/asset-policy/placement-rules.json"
CASES = {
    "agent-thread-governance": "00-governance",
    "customer-research": "01-customer-validation",
    "solution-proposal": "02-solution-analysis",
    "product-requirement": "03-requirements",
    "demo-implementation": "04-demo",
    "customer-validation": "01-customer-validation",
    "formal-delivery": "06-delivery",
}


def policy() -> dict:
    return json.loads(POLICY.read_text(encoding="utf-8"))


def test_representative_tasks_resolve_to_one_primary_stage() -> None:
    routes = {route["id"]: route for route in policy()["task_routes"]}
    assert set(routes) == set(CASES)
    for route_id, stage in CASES.items():
        route = routes[route_id]
        assert route["stage"] == stage
        assert route["primary_owner"].startswith(stage)
        assert route["asset_type"]
        assert route["tracking_policy"] in {"tracked", "ignored", "local-only"}
        assert route["retention_class"]


def test_cross_stage_dependencies_are_references_not_duplicate_ownership() -> None:
    data = policy()
    assert data["cross_stage_policy"] == "reference-only-primary-owner-unchanged"
    assert data["allow_multiple_primary_owners"] is False


def test_unknown_workpackage_stops_instead_of_falling_back_to_generic_folder() -> None:
    data = policy()
    assert data["on_unknown_workpackage"] == "stop-and-create-workpackage-contract"
    assert data["unknown_asset_action"] == "fail-validation-and-request-classification"


def test_root_level_scripts_logs_and_outputs_are_rejected() -> None:
    data = policy()
    assert {"docs", "tools", "outputs", "output", "logs"} <= set(data["forbidden_business_roots"])
    assert {".py", ".js", ".mjs", ".log"} <= set(data["forbidden_root_file_suffixes"])
