"""Validate repository hygiene and frozen runtime dependencies."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "03-requirements/specs/042-repo-architecture-modernization"
FORBIDDEN_TRACKED = re.compile(r"(^|/)(\.local\.env|\.env|node_modules|dist|__pycache__|\.pytest_cache|logs)(/|$)|(^|/)~\$|\.log$|\.pyc$")
STANDARD_ROOT = {
    ".agents", ".codex", ".dockerignore", ".gitignore", ".local.env.example", ".netlifyignore", ".specify",
    ".local-data", "00-governance", "01-customer-validation", "02-solution-analysis", "03-requirements", "04-demo",
    "06-delivery", "AGENTS.md", "agent.md", "README.md", "Dockerfile", "netlify.toml",
    "package-lock.json", "package.json", "pytest.ini", "requirements.txt",
}
LEGACY_ROOT_PENDING_ASSET_APPROVAL = {".netlify-cli-runtime"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-c", "-o", "--exclude-standard"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    return [path for path in result.stdout.splitlines() if (ROOT / path).is_file()]


def main() -> int:
    errors: list[str] = []
    tracked = tracked_files()
    inventory_path = SPEC / "repository-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8")) if inventory_path.exists() else {"entries": []}
    baseline_tracked = {item["path"] for item in inventory["entries"] if item.get("tracked")}
    for path in tracked:
        normalized = path.replace("\\", "/")
        if FORBIDDEN_TRACKED.search(normalized) and normalized not in baseline_tracked:
            errors.append(f"new forbidden tracked local/generated file: {path}")
    grandfathered_root = {item["path"].split("/", 1)[0] for item in inventory["entries"] if item["path"]}
    allowed_root = STANDARD_ROOT | LEGACY_ROOT_PENDING_ASSET_APPROVAL | grandfathered_root
    for path in tracked:
        root_entry = path.replace("\\", "/").split("/", 1)[0]
        if root_entry not in allowed_root:
            errors.append(f"new root entry is not allowlisted: {root_entry}")

    backend_fixture = ROOT / "04-demo/backend/tests/fixtures/architecture/backend-baseline.json"
    if backend_fixture.exists():
        expected = json.loads(backend_fixture.read_text(encoding="utf-8"))["requirements"]["sha256"]
        if sha256(ROOT / "requirements.txt") != expected:
            errors.append("requirements.txt changed without architecture dependency approval")

    frontend_fixture = ROOT / "04-demo/frontend/tests/fixtures/architecture/frontend-baseline.json"
    if frontend_fixture.exists():
        for lock in json.loads(frontend_fixture.read_text(encoding="utf-8"))["npm_locks"]:
            path = ROOT / lock["path"]
            if not path.exists() or sha256(path) != lock["sha256"]:
                errors.append(f"npm dependency lock changed without approval: {lock['path']}")

    if errors:
        print("\n".join(f"ERROR {item}" for item in sorted(set(errors))), file=sys.stderr)
        return 1
    print("repository hygiene and dependency baselines: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
