from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json"
import sys
sys.path.insert(0, str(ROOT / "00-governance/repository-tools"))

from validate_docs import check_links, doc_files  # noqa: E402


def test_document_mappings_have_supported_status_categories_and_resolve_after_migration() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    document_entries = [
        entry
        for entry in entries
        if entry["action"] == "git-move"
        and entry["target"].split("/", 1)[0] in {
            "00-governance", "01-discovery", "02-solution-analysis",
            "03-requirements", "05-validation", "06-delivery",
        }
        and Path(entry["target"]).suffix.lower() in {".md", ".docx"}
    ]
    assert document_entries
    assert all(not (ROOT / entry["source"]).exists() for entry in document_entries if entry["source"] != entry["target"])
    assert all((ROOT / entry["target"]).exists() for entry in document_entries)


def test_document_and_spec_indexes_declare_status_semantics() -> None:
    lifecycle_index = "\n".join(
        (ROOT / stage / "README.md").read_text(encoding="utf-8")
        for stage in (
            "00-governance", "01-discovery", "02-solution-analysis",
            "03-requirements", "04-demo", "05-validation", "06-delivery",
        )
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
