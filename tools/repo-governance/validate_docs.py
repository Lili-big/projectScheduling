"""Check entry-document links and facts against the current repository."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENTRY_DOCS = [ROOT / "README.md", ROOT / "agent.md", ROOT / "docs/README.md", ROOT / "specs/README.md"]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
API = re.compile(r"`(?:GET|POST|PUT|PATCH|DELETE)\s+(/api/[^`\s]+)`")


def doc_files() -> list[Path]:
    result = [path for path in ENTRY_DOCS if path.exists()]
    architecture = ROOT / "docs/architecture"
    if architecture.exists():
        result.extend(sorted(architecture.rglob("*.md")))
    return result


def check_links(path: Path, errors: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    for destination in LINK.findall(content):
        destination = destination.strip().strip("<>")
        if not destination or destination.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target_text = destination.split("#", 1)[0].replace("%20", " ")
        if not target_text:
            continue
        target = (path.parent / target_text).resolve()
        try:
            target.relative_to(ROOT)
        except ValueError:
            errors.append(f"{path.relative_to(ROOT)}: link escapes repository: {destination}")
            continue
        if not target.exists():
            errors.append(f"{path.relative_to(ROOT)}: missing link target: {destination}")


def check_api_facts(path: Path, routes: set[str], errors: list[str]) -> None:
    for api_path in API.findall(path.read_text(encoding="utf-8")):
        normalized = re.sub(r"\{[^}]+\}", "{parameter}", api_path.rstrip(".,;"))
        normalized_routes = {re.sub(r"\{[^}]+\}", "{parameter}", route) for route in routes}
        if normalized not in normalized_routes:
            errors.append(f"{path.relative_to(ROOT)}: undocumented API path is not implemented: {api_path}")


def main() -> int:
    errors: list[str] = []
    backend_fixture = ROOT / "backend/tests/fixtures/architecture/backend-baseline.json"
    routes = set()
    if backend_fixture.exists():
        routes = {item["path"] for item in json.loads(backend_fixture.read_text(encoding="utf-8"))["api"]["routes"]}
    for path in doc_files():
        check_links(path, errors)
        if routes:
            check_api_facts(path, routes, errors)
    if errors:
        print("\n".join(f"ERROR {item}" for item in errors), file=sys.stderr)
        return 1
    print(f"documentation links and API facts: OK ({len(doc_files())} documents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
