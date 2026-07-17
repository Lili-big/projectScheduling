"""Run lifecycle validation and cleanup dry-run with protected-asset checks."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

from validate_lifecycle_workspace import validate


ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance"
MANIFEST = FEATURE / "asset-migration-manifest.json"
OUTPUT = FEATURE / "cleanup-preview.json"
CLEANUP = ROOT / "00-governance/repository-tools/cleanup-workspace.ps1"
PROTECTED_CLASSES = {"persistent-state", "user-input", "formal-output"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def protected_hashes(manifest: dict) -> dict[str, str]:
    paths: set[Path] = set()
    for entry in manifest["entries"]:
        if entry["retention_class"] not in PROTECTED_CLASSES:
            continue
        relative = (
            entry["target"]
            if entry["action"] in {"git-move", "local-move"} and entry["status"] == "verified"
            else entry["source"]
        )
        path = ROOT / relative
        if path.is_file():
            paths.add(path)
    state_root = ROOT / ".local-data/state"
    if state_root.is_dir():
        paths.update(path for path in state_root.rglob("*") if path.is_file())
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(paths)}


def git_status() -> str:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain=v2", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def main() -> int:
    started = time.perf_counter()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    hashes_before = protected_hashes(manifest)
    status_before = git_status()
    governance = validate()
    cleanup_process = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(CLEANUP),
            "-Json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    cleanup = json.loads(cleanup_process.stdout)
    hashes_after = protected_hashes(manifest)
    status_after = git_status()
    elapsed = time.perf_counter() - started
    changed = sorted(
        path
        for path in set(hashes_before) | set(hashes_after)
        if hashes_before.get(path) != hashes_after.get(path)
    )
    report = {
        "mode": "dry-run",
        "elapsed_seconds": round(elapsed, 6),
        "threshold_seconds": 30,
        "within_threshold": elapsed <= 30,
        "governance": governance,
        "cleanup": cleanup,
        "protected_integrity": {
            "classes": sorted(PROTECTED_CLASSES),
            "files_before": len(hashes_before),
            "files_after": len(hashes_after),
            "changed": changed,
            "unchanged": not changed,
        },
        "git_status_unchanged_during_dry_run": status_before == status_after,
        "pass": (
            elapsed <= 30
            and governance["status"] == "pass"
            and cleanup["mode"] == "dry-run"
            and cleanup["deleted_count"] == 0
            and cleanup["protected_candidate_count"] == 0
            and not changed
            and status_before == status_after
        ),
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
