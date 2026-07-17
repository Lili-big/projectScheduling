"""Freeze the pre-045 repository baseline without copying or moving assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/repository-baseline.json"
LOCAL_DETAIL_ROOTS = {
    ".local-data",
    "artifacts",
    "local-json-task-review",
    "logs",
    "output",
    "outputs/lugu-validation-20260715",
    "outputs/lugu-validation-20260716",
}
AGGREGATE_ONLY_ROOTS = {
    ".codex-tmp",
    ".git-tmp-projectScheduling",
    ".netlify",
    ".netlify-cli-runtime",
    ".netlify-deploy-staging",
    ".npm-cache",
    ".npm-cache-netlify-deploy",
    ".pip-cache",
    ".playwright-cli",
    ".pytest_cache",
    ".skill-build",
    ".venv",
    "ai-ppt-system",
    "frontend/node_modules",
    "node_modules",
}


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(relative: str, state: str, status: str = "") -> dict[str, Any]:
    normalized = relative.replace("\\", "/").rstrip("/")
    path = ROOT / normalized
    return {
        "path": normalized,
        "state": state,
        "git_status": status,
        "kind": "file",
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def directory_summary(relative: str) -> dict[str, Any]:
    normalized = relative.replace("\\", "/").rstrip("/")
    root = ROOT / normalized
    aggregate_without_walk = (
        any(normalized == item or normalized.startswith(f"{item}/") for item in AGGREGATE_ONLY_ROOTS)
        or "node_modules" in Path(normalized).parts
        or "__pycache__" in Path(normalized).parts
        or ".pytest_cache" in Path(normalized).parts
    )
    file_count = 0
    total_bytes = 0
    if root.exists() and not aggregate_without_walk:
        for current, dirs, files in os.walk(root):
            dirs[:] = [name for name in dirs if not Path(current, name).is_symlink()]
            for name in files:
                path = Path(current, name)
                try:
                    if path.is_file() and not path.is_symlink():
                        file_count += 1
                        total_bytes += path.stat().st_size
                except OSError:
                    continue
    return {
        "path": normalized,
        "state": "ignored",
        "git_status": "!!",
        "kind": "directory-summary",
        "summary_mode": "path-only" if aggregate_without_walk else "recursive-count",
        "file_count": None if aggregate_without_walk else file_count,
        "size_bytes": None if aggregate_without_walk else total_bytes,
        "sha256": None,
    }


def ignored_status_paths() -> list[str]:
    lines = git("status", "--short", "--ignored", check=False).splitlines()
    return sorted(
        line[3:].strip().replace("\\", "/")
        for line in lines
        if line.startswith("!! ")
    )


def detailed_local_files(tracked: set[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for local_root in sorted(LOCAL_DETAIL_ROOTS):
        root = ROOT / local_root
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if (
                not path.is_file()
                or path.is_symlink()
                or "__pycache__" in path.parts
                or "node_modules" in path.parts
            ):
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in tracked:
                continue
            records.append(file_record(relative, "ignored-local-detail", "!!"))
    for path in sorted(ROOT.glob("*.log")):
        if path.is_file():
            records.append(file_record(path.name, "ignored-local-detail", "!!"))
    for path in sorted((ROOT / "frontend").glob("*.log")):
        if path.is_file():
            records.append(file_record(path.relative_to(ROOT).as_posix(), "ignored-local-detail", "!!"))
    return records


def build() -> dict[str, Any]:
    tracked = sorted(git("ls-files").splitlines())
    tracked_records = [file_record(path, "tracked") for path in tracked if (ROOT / path).is_file()]
    ignored_paths = ignored_status_paths()
    ignored_summaries = [directory_summary(path) if (ROOT / path.rstrip("/")).is_dir() else file_record(path, "ignored", "!!") for path in ignored_paths]
    detail = detailed_local_files(set(tracked))
    aggregate_only = sorted(
        item["path"]
        for item in ignored_summaries
        if item["kind"] == "directory-summary"
        and item["summary_mode"] == "path-only"
    )
    return {
        "format_version": 1,
        "feature": "045-lifecycle-workspace-governance",
        "captured_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "repository_root": str(ROOT),
        "branch": git("branch", "--show-current").strip(),
        "head": git("rev-parse", "HEAD").strip(),
        "initial_untracked_count": 0,
        "detail_policy": {
            "tracked": "逐文件记录大小和 SHA-256",
            "untracked": "T001 初始快照为 0；045 实施生成文件不回写为初始未跟踪资产",
            "ignored": "业务/用户/日志/结果类本地产物逐文件记录；依赖、虚拟环境和工具缓存按忽略入口聚合",
            "secret_files": "只记录路径、大小和 SHA-256，不读取或输出内容",
        },
        "summary": {
            "tracked_files": len(tracked_records),
            "untracked_files": 0,
            "ignored_status_entries": len(ignored_summaries),
            "ignored_local_detail_files": len(detail),
            "aggregate_only_entries": len(aggregate_only),
        },
        "tracked_files": tracked_records,
        "untracked_files": [],
        "ignored_entries": ignored_summaries,
        "ignored_local_files": detail,
        "aggregate_only_paths": aggregate_only,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    payload = build()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), **payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
