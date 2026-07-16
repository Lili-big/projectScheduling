from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "specs/042-repo-architecture-modernization/asset-migration-manifest.json"
sys.path.insert(0, str(ROOT / "tools/repo-governance"))

from validate_docs import check_links, doc_files  # noqa: E402


def test_document_mappings_have_supported_status_categories_and_resolve_after_migration() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    document_entries = [entry for entry in entries if entry["target"].startswith("docs/")]
    assert document_entries
    assert all(entry["category"] in {"product_document", "engineering_document", "validation_document", "research_document", "historical_document"} for entry in document_entries)
    assert all(not (ROOT / entry["source"]).exists() for entry in document_entries if entry["source"] != entry["target"])
    assert all((ROOT / entry["target"]).exists() for entry in document_entries)


def test_document_and_spec_indexes_declare_status_semantics() -> None:
    docs_index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
    specs_index = (ROOT / "specs/README.md").read_text(encoding="utf-8")
    for status in ("current", "draft", "superseded", "historical"):
        assert status in docs_index or status in specs_index
    spec_directories = {path.name for path in (ROOT / "specs").iterdir() if path.is_dir()}
    assert all(name in specs_index for name in spec_directories)


def test_entry_and_architecture_markdown_links_resolve_before_migration() -> None:
    errors: list[str] = []
    for path in doc_files():
        check_links(path, errors)
    assert errors == []
