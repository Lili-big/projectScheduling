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


def test_root_and_stage_navigation_expose_all_seven_lifecycle_stages() -> None:
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert all(stage in root_readme for stage in STAGES)
    for stage in STAGES:
        stage_readme = (ROOT / stage / "README.md").read_text(encoding="utf-8")
        assert "进入条件" in stage_readme
        assert "退出条件" in stage_readme
        assert "工作包索引" in stage_readme


def test_every_physical_asset_has_one_approved_primary_target() -> None:
    feature = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance"
    manifest = json.loads(
        (feature / "asset-migration-manifest.json").read_text(encoding="utf-8")
    )
    physical = [
        entry for entry in manifest["entries"] if entry["action"] in {"git-move", "local-move"}
    ]
    targets = [entry["target"] for entry in physical]
    assert len(targets) == len(set(targets))
    assert all(entry["stage"] in STAGES for entry in physical)
    assert all(entry["source"] != entry["target"] for entry in physical)


def test_business_assets_are_reachable_within_two_directory_hops() -> None:
    expected = {
        "01-discovery": "workpackages",
        "02-solution-analysis": "proposals",
        "03-requirements": "specs",
        "04-demo": "backend",
        "05-validation": "workpackages",
        "06-delivery": "deliverables",
    }
    for stage, child in expected.items():
        assert (ROOT / stage / child).exists(), f"missing {stage}/{child}"
