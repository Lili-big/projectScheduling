from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "00-governance/asset-policy/placement-rules.json"
REQUIRED_CLASSIFICATION = {"stage", "workpackage", "asset_type", "retention_class", "primary_owner"}


def test_placement_policy_requires_all_five_task_classifications() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert REQUIRED_CLASSIFICATION <= set(policy["required_classification"])


def test_placement_policy_rejects_generic_root_business_assets() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    forbidden = set(policy["forbidden_business_roots"])
    assert {"docs", "tools", "outputs", "output", "logs"} <= forbidden
    assert policy["on_unknown_workpackage"] == "stop-and-create-workpackage-contract"

