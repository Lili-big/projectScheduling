from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "specs/042-repo-architecture-modernization/asset-migration-manifest.json"
STABLE_ROOT = {
    ".agents", ".codex", ".dockerignore", ".gitignore", ".local.env.example", ".netlifyignore", ".specify",
    "AGENTS.md", "agent.md", "README.md", "Dockerfile", "backend", "docs", "examples", "frontend", "netlify",
    "netlify.toml", "package-lock.json", "package.json", "requirements.txt", "specs", "tools",
}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.splitlines()


def test_root_exceptions_are_explicit_manifest_sources_before_approval() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sources = {entry["source"] for entry in payload["entries"]}
    tracked_roots = {path.split("/", 1)[0] for path in tracked_files()}
    target_roots = {entry["target"].split("/", 1)[0] for entry in payload["entries"] if entry["tracked_after"]}
    assert tracked_roots <= STABLE_ROOT | target_roots
    assert all(entry["approval_status"] == "approved_moved_verified" for entry in payload["entries"])


def test_manifest_targets_and_temporary_tracking_actions_are_unambiguous() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    assert len({entry["source"] for entry in entries}) == len(entries)
    assert len({entry["target"] for entry in entries}) == len(entries)
    for entry in entries:
        if entry["target"].startswith("artifacts/"):
            assert entry["tracking_action"] == "move_then_untrack"
            assert entry["tracked_after"] is False
        if Path(entry["source"]).name.startswith("~$"):
            assert entry["category"] == "temporary_lock"
            assert entry["tracking_action"] == "move_then_untrack"


def test_every_root_runtime_log_is_declared_for_local_only_migration() -> None:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))["entries"]
    declared = {
        entry["source"]: entry
        for entry in entries
        if entry["category"] == "runtime_log"
    }
    root_logs = {path.name for path in ROOT.glob("*.log") if path.is_file()}
    assert root_logs == set()
    assert len(declared) == 16
    for entry in declared.values():
        assert entry["target"].startswith(".local-data/logs/legacy/")
        assert entry["tracking_action"] == "move_local_only"
        assert entry["tracked_before"] is False
        assert entry["tracked_after"] is False
        assert not (ROOT / entry["source"]).exists()
        assert (ROOT / entry["target"]).is_file()


def test_logged_process_helper_never_targets_the_repository_root() -> None:
    helper = ROOT / "tools/local-runtime/start_logged_process.ps1"
    content = helper.read_text(encoding="utf-8")
    assert ".local-data\\logs" in content
    assert "RedirectStandardOutput" in content
    assert "RedirectStandardError" in content
    assert "WindowStyle Hidden" in content
