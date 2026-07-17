from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_root_platform_entries_use_lifecycle_demo_paths() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["workspaces"] == ["04-demo/frontend"]
    docker = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY 04-demo/backend ./backend" in docker
    netlify = (ROOT / "netlify.toml").read_text(encoding="utf-8")
    assert 'publish = "04-demo/frontend/dist"' in netlify


def test_spec_kit_uses_only_the_canonical_lifecycle_spec_root() -> None:
    common = (ROOT / ".specify/scripts/powershell/common.ps1").read_text(encoding="utf-8")
    assert "Resolve-LifecycleFeatureDirectory" in common
    assert "03-requirements/specs" in common.replace("\\", "/")
    assert "$legacyPrefix" not in common
    pointer = json.loads((ROOT / ".specify/feature.json").read_text(encoding="utf-8"))
    assert pointer["feature_directory"].startswith("03-requirements/specs/")


def test_speckit_skills_document_the_canonical_path_policy() -> None:
    skills = sorted((ROOT / ".agents/skills").glob("speckit-*/SKILL.md"))
    assert skills
    for skill in skills:
        content = skill.read_text(encoding="utf-8").replace("\\", "/")
        assert "03-requirements/specs" in content, f"missing transition path policy: {skill}"
