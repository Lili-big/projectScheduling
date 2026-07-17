from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "00-governance/asset-policy/cleanup-policy.json"
EXPECTED_CLASSES = {"persistent-state", "user-input", "formal-output", "diagnostic-log", "rebuildable", "cache", "temporary"}
PROTECTED_CLASSES = {"persistent-state", "user-input", "formal-output"}


def test_cleanup_policy_covers_all_seven_retention_classes_and_defaults_to_dry_run() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["default_mode"] == "dry-run"
    assert {rule["retention_class"] for rule in policy["rules"]} == EXPECTED_CLASSES


def test_protected_classes_can_never_be_automatic_deletion_candidates() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    for rule in policy["rules"]:
        if rule["retention_class"] in PROTECTED_CLASSES:
            assert rule["protected"] is True
        if rule["retention_class"] == "diagnostic-log":
            assert rule["requires_process_check"] is True

