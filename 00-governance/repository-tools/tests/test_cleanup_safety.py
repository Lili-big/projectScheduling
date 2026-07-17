from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "00-governance/asset-policy/cleanup-policy.json"
SCRIPT = ROOT / "00-governance/repository-tools/cleanup-workspace.ps1"
PROTECTED = ["persistent-state", "user-input", "formal-output"]


def test_protection_priority_wins_when_patterns_overlap() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["classification_priority"][:3] == PROTECTED
    assert policy["on_classification_conflict"] == "select-highest-protection-and-report"
    example = next(item for item in policy["conflict_examples"] if item["path"].endswith("state/debug.log"))
    assert example["resolved_class"] == "persistent-state"


def test_cleanup_defaults_to_dry_run_and_never_selects_protected_assets() -> None:
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(SCRIPT),
            "-Json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    report = json.loads(result.stdout)
    assert report["mode"] == "dry-run"
    assert report["deleted_count"] == 0
    assert report["protected_candidate_count"] == 0
    assert set(report["protected_classes"]) == set(PROTECTED)


def test_apply_requires_explicit_non_protected_categories() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "[switch]$Apply" in source
    assert "ValidateSet('diagnostic-log', 'rebuildable', 'cache', 'temporary')" in source
    assert "persistent-state" in source and "user-input" in source and "formal-output" in source
