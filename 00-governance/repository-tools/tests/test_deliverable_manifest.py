from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_042 = ROOT / "03-requirements/specs/042-repo-architecture-modernization/asset-migration-manifest.json"
MANIFEST_045 = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json"


def current_target(source: str) -> str:
    entries = json.loads(MANIFEST_045.read_text(encoding="utf-8"))["entries"]
    migrated = {entry["source"]: entry["target"] for entry in entries}
    return migrated.get(source, source)


def test_manifest_hashes_match_every_post_migration_binary_target() -> None:
    entries = json.loads(MANIFEST_042.read_text(encoding="utf-8"))["entries"]
    for entry in entries:
        path = ROOT / current_target(entry["target"])
        assert path.is_file(), entry["target"]
        if entry["binary"]:
            assert path.stat().st_size == entry["size_bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_formal_deliverables_remain_tracked_and_binary_assets_have_hashes() -> None:
    entries = json.loads(MANIFEST_042.read_text(encoding="utf-8"))["entries"]
    formal = [entry for entry in entries if entry["category"] == "formal_deliverable"]
    assert formal
    assert all(current_target(entry["target"]).startswith("06-delivery/deliverables/") for entry in formal)
    assert all(entry["tracking_action"] == "git_mv_keep_tracked" and entry["tracked_after"] for entry in formal)
    assert all(len(entry["sha256"]) == 64 for entry in entries if entry["binary"])
