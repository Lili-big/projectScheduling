from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json"
CURRENT_STAGES = (
    "00-governance",
    "01-customer-validation",
    "02-solution-analysis",
    "03-requirements",
    "04-demo",
    "06-delivery",
)
HISTORICAL_REPLACED_ROOTS = {"01-discovery", "05-validation"}
import sys
sys.path.insert(0, str(ROOT / "00-governance/repository-tools"))

from validate_docs import check_links, doc_files  # noqa: E402


def test_historical_document_targets_are_preserved_or_explicitly_replaced() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    document_entries = [
        entry
        for entry in entries
        if entry["action"] == "git-move"
        and Path(entry["target"]).suffix.lower() in {".md", ".docx"}
    ]
    assert document_entries
    for entry in document_entries:
        assert not (ROOT / entry["source"]).exists() or entry["source"] == entry["target"]
        target_root = entry["target"].split("/", 1)[0]
        if target_root in HISTORICAL_REPLACED_ROOTS:
            assert not (ROOT / entry["target"]).exists()
        else:
            assert (ROOT / entry["target"]).exists()


def test_document_and_spec_indexes_declare_status_semantics() -> None:
    lifecycle_index = "\n".join(
        (ROOT / stage / "README.md").read_text(encoding="utf-8")
        for stage in CURRENT_STAGES
    )
    specs_root = ROOT / "03-requirements/specs"
    specs_index = (specs_root / "README.md").read_text(encoding="utf-8")
    for status in ("current", "draft", "superseded", "historical"):
        assert status in lifecycle_index or status in specs_index
    spec_directories = {path.name for path in specs_root.iterdir() if path.is_dir()}
    assert all(name in specs_index for name in spec_directories)


def test_entry_and_architecture_markdown_links_resolve_after_lifecycle_migration() -> None:
    errors: list[str] = []
    for path in doc_files():
        check_links(path, errors)
    assert errors == []
