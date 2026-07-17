from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "00-governance/repository-tools/finalize_lifecycle_manifest.py"
SPEC = importlib.util.spec_from_file_location("finalize_lifecycle_manifest", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_only_registered_ignored_rebuildable_source_can_reappear() -> None:
    registered = {"node_modules"}
    approved_cache = {
        "source": "node_modules",
        "action": "local-move",
        "tracking_policy": "ignored",
        "retention_class": "cache",
    }
    assert MODULE.is_registered_rebuildable_source(approved_cache, registered)

    for field, value in (
        ("source", "unexpected-cache"),
        ("action", "git-move"),
        ("tracking_policy", "tracked"),
        ("retention_class", "persistent-state"),
    ):
        candidate = dict(approved_cache)
        candidate[field] = value
        assert not MODULE.is_registered_rebuildable_source(candidate, registered)


def test_root_compatibility_registers_node_modules_as_local_cache() -> None:
    assert "node_modules" in MODULE.registered_rebuildable_sources()
