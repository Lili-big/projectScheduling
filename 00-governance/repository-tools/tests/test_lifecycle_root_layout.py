from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGES = [
    "00-governance",
    "01-discovery",
    "02-solution-analysis",
    "03-requirements",
    "04-demo",
    "05-validation",
    "06-delivery",
]
LEGACY_BUSINESS_ROOTS = {"backend", "deliverables", "docs", "examples", "frontend", "output", "outputs", "specs", "tools"}


def test_all_lifecycle_stages_exist_in_stable_order() -> None:
    policy_path = ROOT / "00-governance/asset-policy/lifecycle-stages.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    assert [stage["id"] for stage in policy["stages"]] == STAGES
    assert all((ROOT / stage).is_dir() for stage in STAGES)


def test_legacy_generic_business_roots_are_absent_after_migration() -> None:
    contract_path = ROOT / "00-governance/asset-policy/root-compatibility.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    retained = {entry["path"] for entry in contract["entries"] if entry["status"] == "retained-local-cache"}
    remaining = sorted(path for path in LEGACY_BUSINESS_ROOTS if (ROOT / path).exists() and path not in retained)
    assert remaining == []


def test_every_non_stage_root_entry_is_an_explicit_compatibility_entry() -> None:
    contract_path = ROOT / "00-governance/asset-policy/root-compatibility.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    declared = {entry["path"] for entry in contract["entries"]}
    actual = {
        path.name
        for path in ROOT.iterdir()
        if path.name not in STAGES and path.name != ".git" and not path.name.startswith(".git-")
    }
    assert actual <= declared
