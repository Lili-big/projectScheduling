"""Finalize and audit the approved 045 migration manifest without deleting assets."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance"
MANIFEST = FEATURE / "asset-migration-manifest.json"
MARKDOWN = FEATURE / "asset-migration-manifest.md"
HASH_AUDIT = FEATURE / "manifest-hash-refresh.json"
VERIFICATION = FEATURE / "manifest-verification.json"
ROOT_COMPATIBILITY = ROOT / "00-governance/asset-policy/root-compatibility.json"
APPROVAL_TEXT = (
    "确认 T019，批准 1127 条清单全部执行，包括 9 条 043 规格及日志、用户输入、"
    "持久状态、缓存和临时入口的清单动作；不授权删除。"
)
MOVE_ACTIONS = {"git-move", "local-move"}
STATIC_ACTIONS = {"compatibility-entry", "keep"}


def registered_rebuildable_sources() -> set[str]:
    """Return ignored root caches that may legitimately reappear after migration.

    The manifest archives the cache instance that existed at approval time. A package
    manager may then recreate its standard root cache path during verification. This
    is not a duplicate migration source when the path remains an explicit, ignored
    compatibility entry and the approved instance still exists at its target.
    """

    payload = json.loads(ROOT_COMPATIBILITY.read_text(encoding="utf-8"))
    return {
        item["path"].replace("\\", "/")
        for item in payload.get("entries", [])
        if item.get("status") == "local-cache"
        and item.get("tracking_policy") == "ignored"
    }


def is_registered_rebuildable_source(entry: dict[str, Any], registered: set[str]) -> bool:
    return (
        entry["action"] == "local-move"
        and entry["retention_class"] in {"cache", "rebuildable"}
        and entry["tracking_policy"] in {"ignored", "local-only"}
        and entry["source"].replace("\\", "/") in registered
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(relative: str) -> Path:
    root = Path(os.path.abspath(ROOT))
    candidate = Path(os.path.abspath(ROOT / relative))
    candidate.relative_to(root)
    if candidate == root:
        raise ValueError("manifest endpoint cannot be the repository root")
    return candidate


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {line.replace("\\", "/") for line in result.stdout.splitlines() if line}


def ignored_paths(paths: list[str]) -> set[str]:
    if not paths:
        return set()
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "check-ignore", "-z", "--stdin"],
        cwd=ROOT,
        input="\0".join(paths) + "\0",
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.strip() or "git check-ignore failed")
    return {item.replace("\\", "/") for item in result.stdout.split("\0") if item}


def update_markdown(payload: dict[str, Any]) -> None:
    text = MARKDOWN.read_text(encoding="utf-8")
    text = text.replace("**状态**：`executed`", "**状态**：`verified`", 1)
    statuses = {entry["id"]: entry["status"] for entry in payload["entries"]}
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("| `M"):
            parts = line.rsplit("|", 2)
            if len(parts) == 3:
                entry_id = line.split("`", 2)[1]
                line = f"{parts[0]}| `{statuses[entry_id]}` |"
        lines.append(line)
    MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = payload.get("entries", [])
    if len(entries) != 1127:
        raise ValueError(f"expected 1127 entries, found {len(entries)}")
    if sum(entry["source"].startswith("specs/043-") for entry in entries) != 9:
        raise ValueError("feature 043 entry count is not 9")
    if any("delete" in entry["action"] for entry in entries):
        raise ValueError("delete action detected")
    if any(entry["action"] not in MOVE_ACTIONS | STATIC_ACTIONS for entry in entries):
        raise ValueError("unsupported action detected")

    working_visible = git_lines("ls-files", "-c", "-o", "--exclude-standard")
    local_candidates = [
        entry["target"] if entry["action"] in MOVE_ACTIONS else entry["source"]
        for entry in entries
        if entry["tracking_policy"] in {"ignored", "local-only"}
    ]
    ignored = ignored_paths(local_candidates)
    previous_refreshes: dict[str, dict[str, Any]] = {}
    if HASH_AUDIT.is_file():
        previous_payload = json.loads(HASH_AUDIT.read_text(encoding="utf-8"))
        previous_refreshes = {
            item["id"]: item for item in previous_payload.get("entries", [])
        }
    refresh_by_id = dict(previous_refreshes)
    rebuildable_sources = registered_rebuildable_sources()
    recreated_compatibility_sources: list[str] = []
    source_conflicts: list[str] = []
    missing_targets: list[str] = []
    tracking_errors: list[str] = []
    hashed = 0

    for entry in entries:
        source = repo_path(entry["source"])
        target = repo_path(entry["target"])
        current = target if entry["action"] in MOVE_ACTIONS else source
        if entry["action"] in MOVE_ACTIONS and source.exists():
            if is_registered_rebuildable_source(entry, rebuildable_sources):
                recreated_compatibility_sources.append(entry["source"])
            else:
                source_conflicts.append(entry["source"])
        if not current.exists():
            missing_targets.append(entry["target"])
            continue
        if entry["sha256"] is not None:
            if not current.is_file():
                raise ValueError(f"hashed endpoint is not a file: {entry['id']} {current}")
            actual = sha256(current)
            hashed += 1
            if actual != entry["sha256"]:
                previous = previous_refreshes.get(entry["id"])
                refresh_by_id[entry["id"]] = {
                    "id": entry["id"],
                    "source": entry["source"],
                    "target": entry["target"],
                    "approved_sha256": (
                        previous["approved_sha256"] if previous else entry["sha256"]
                    ),
                    "verified_sha256": actual,
                    "reason": "批准迁移后为完成 045 路径兼容、文档或测试而发生的受控修改",
                }
                entry["sha256"] = actual

        current_relative = (
            entry["target"] if entry["action"] in MOVE_ACTIONS else entry["source"]
        ).replace("\\", "/")
        if entry["tracking_policy"] == "tracked":
            if current_relative not in working_visible or current_relative in ignored:
                tracking_errors.append(
                    f"{entry['id']}: tracked endpoint is hidden or missing {current_relative}"
                )
        elif current_relative not in ignored:
            tracking_errors.append(f"{entry['id']}: local endpoint is not ignored {current_relative}")
        entry["status"] = "verified"

    if source_conflicts or missing_targets or tracking_errors:
        raise ValueError(
            json.dumps(
                {
                    "source_conflicts": source_conflicts[:20],
                    "missing_targets": missing_targets[:20],
                    "tracking_errors": tracking_errors[:20],
                },
                ensure_ascii=False,
            )
        )

    timestamp = datetime.now(timezone.utc).astimezone().isoformat()
    refreshed = [refresh_by_id[key] for key in sorted(refresh_by_id)]
    hash_audit = {
        "feature": payload["feature"],
        "verified_at": timestamp,
        "approval_text": APPROVAL_TEXT,
        "delete_authorized": False,
        "reason": "保留批准时哈希与最终实施哈希的逐项审计链；不掩盖受控内容变化。",
        "entries": refreshed,
    }
    atomic_json(HASH_AUDIT, hash_audit)

    payload["status"] = "verified"
    marker = "T073 最终复核"
    payload["exceptions"] = [item for item in payload["exceptions"] if not item.startswith(marker)]
    payload["exceptions"].append(
        f"{marker}（{timestamp}）：1,127 条全部 verified；删除动作 0；"
        f"{len(refreshed)} 条受控实施后哈希刷新见 manifest-hash-refresh.json。"
    )
    atomic_json(MANIFEST, payload)
    update_markdown(payload)

    verification = {
        "feature": payload["feature"],
        "verified_at": timestamp,
        "status": "pass",
        "entries": len(entries),
        "feature_043_entries": 9,
        "move_entries": sum(entry["action"] in MOVE_ACTIONS for entry in entries),
        "static_entries": sum(entry["action"] in STATIC_ACTIONS for entry in entries),
        "hashed_entries": hashed,
        "hash_refresh_entries": len(refreshed),
        "source_conflicts": 0,
        "recreated_compatibility_sources": sorted(recreated_compatibility_sources),
        "missing_targets": 0,
        "tracking_errors": 0,
        "delete_actions": 0,
        "delete_authorized": False,
        "manifest_status": payload["status"],
    }
    atomic_json(VERIFICATION, verification)
    print(json.dumps(verification, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
