"""Inventory repository assets, tracked state, references and binary hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
BINARY_SUFFIXES = {".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".zip"}
GENERATED_PARTS = {"dist", "build", "node_modules", "artifacts", "__pycache__", ".pytest_cache"}


def _git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=REPO_ROOT, check=check, capture_output=True, text=True, encoding="utf-8")
    return result.stdout


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _category(path: Path) -> str:
    parts = set(path.parts)
    if parts & GENERATED_PARTS:
        return "generated"
    if path.suffix.lower() in BINARY_SUFFIXES:
        if path.parts and path.parts[0] == "deliverables":
            return "deliverable"
        return "binary_asset"
    if path.parts and path.parts[0] == "docs":
        return "documentation"
    if path.parts and path.parts[0] == "specs":
        return "specification"
    if path.parts and path.parts[0] in {"backend", "frontend", "netlify", "tools"}:
        return "source_or_tool"
    if len(path.parts) == 1:
        return "root_entry"
    return "other"


def _references(relative_path: str) -> list[str]:
    result = subprocess.run(
        ["git", "grep", "-l", "-F", relative_path, "--", "*.md", "*.py", "*.ts", "*.tsx", "*.mts", "*.json", "*.toml", "*.yml", "*.yaml"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sorted(line for line in result.stdout.splitlines() if line != relative_path)


def inventory() -> dict[str, Any]:
    tracked = set(_git("ls-files").splitlines())
    status_lines = _git("status", "--short", "--untracked-files=all").splitlines()
    status = {line[3:].replace("\\", "/"): line[:2] for line in status_lines if len(line) >= 4}
    candidates = set(tracked) | set(status)
    entries: list[dict[str, Any]] = []
    for relative_path in sorted(candidates):
        path = REPO_ROOT / relative_path
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        category = _category(Path(relative_path))
        relevant = category in {"binary_asset", "deliverable", "generated", "root_entry"} or relative_path.startswith("00-governance/repository-tools/")
        if not relevant:
            continue
        entries.append(
            {
                "path": relative_path.replace("\\", "/"),
                "category": category,
                "tracked": relative_path in tracked,
                "status": status.get(relative_path, ""),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path) if suffix in BINARY_SUFFIXES else None,
                "references": _references(relative_path.replace("\\", "/")),
            }
        )
    return {"format_version": 1, "entry_count": len(entries), "entries": entries}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "03-requirements/specs/042-repo-architecture-modernization/repository-inventory.json")
    args = parser.parse_args()
    result = inventory()
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output.relative_to(REPO_ROOT)} ({result['entry_count']} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
