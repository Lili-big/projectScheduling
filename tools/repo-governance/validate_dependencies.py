"""Validate architecture dependency directions without third-party packages."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"


def python_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def check_python(errors: list[str]) -> None:
    contracts = BACKEND / "contracts"
    if contracts.exists():
        forbidden = ("app.api", "app.services", "app.scheduling", "app.girder_planning", "app.plan_control", "app.main")
        for path in contracts.rglob("*.py"):
            for imported in python_imports(path):
                if imported.startswith(forbidden):
                    errors.append(f"{path.relative_to(ROOT)}: contracts cannot import {imported}")

    scheduling = BACKEND / "scheduling"
    if scheduling.exists():
        for path in scheduling.rglob("*.py"):
            for imported in python_imports(path):
                if imported.startswith(("app.api", "app.main")):
                    errors.append(f"{path.relative_to(ROOT)}: scheduling cannot import HTTP layer {imported}")


IMPORT_PATTERN = re.compile(r"(?:from\s+|import\s*\()\s*[\"']([^\"']+)[\"']")


def check_frontend(errors: list[str]) -> None:
    features = FRONTEND / "features"
    if features.exists():
        for path in features.rglob("*.ts*"):
            current_feature = path.relative_to(features).parts[0]
            for imported in IMPORT_PATTERN.findall(path.read_text(encoding="utf-8")):
                normalized = imported.replace("\\", "/")
                match = re.search(r"features/([^/]+)(?:/(.*))?$", normalized)
                if match and match.group(1) != current_feature and match.group(2) not in {None, "", "index", "index.ts", "index.tsx"}:
                    errors.append(f"{path.relative_to(ROOT)}: cross-feature internal import {imported}")

    contracts = FRONTEND / "contracts"
    if contracts.exists():
        for path in contracts.rglob("*.ts"):
            content = path.read_text(encoding="utf-8")
            if re.search(r"from\s+[\"'](?:react|\.\./api|\.\./features)", content):
                errors.append(f"{path.relative_to(ROOT)}: contracts must not depend on React, API, or features")

    domain = FRONTEND / "domain"
    if domain.exists():
        for path in domain.rglob("*.ts"):
            content = path.read_text(encoding="utf-8")
            if re.search(r"from\s+[\"']react[\"']|fetch\s*\(", content):
                errors.append(f"{path.relative_to(ROOT)}: domain must remain pure")


def main() -> int:
    errors: list[str] = []
    check_python(errors)
    check_frontend(errors)
    if errors:
        print("\n".join(f"ERROR {item}" for item in errors), file=sys.stderr)
        return 1
    print("dependency directions: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
