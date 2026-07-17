"""Approve, preflight, and execute the feature 045 asset migration manifest.

The executor is deliberately move-only.  It has no delete operation, checks
that every source and target stays under the repository root, and stops on the
first source drift or target conflict.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OLD_FEATURE = ROOT / "specs/045-lifecycle-workspace-governance"
NEW_FEATURE = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance"
MANIFEST_NAME = "asset-migration-manifest.json"
MARKDOWN_NAME = "asset-migration-manifest.md"
APPROVAL_TEXT = (
    "确认 T019，批准 1127 条清单全部执行，包括 9 条 043 规格及日志、用户输入、"
    "持久状态、缓存和临时入口的清单动作；不授权删除。"
)
APPROVAL_MUTABLE_SOURCES = {
    "specs/045-lifecycle-workspace-governance/implementation-log.md",
    "specs/045-lifecycle-workspace-governance/tasks.md",
}
MOVE_ACTIONS = {"git-move", "local-move"}
STATIC_ACTIONS = {"compatibility-entry", "keep"}
ENTRY_STATUSES = {
    "draft",
    "prechecked",
    "approved",
    "moved",
    "verified",
    "rollback-required",
    "rolled-back",
}
ROW_PATTERN = re.compile(r"^\| `(?P<id>M[0-9]{4})` \|")
STATUS_CELL_PATTERN = re.compile(
    r"`(?:draft|prechecked|approved|moved|verified|rollback-required|rolled-back)` \|$"
)


def feature_dir() -> Path:
    for candidate in (NEW_FEATURE, OLD_FEATURE):
        if (candidate / MANIFEST_NAME).is_file():
            return candidate
    raise FileNotFoundError("cannot locate the feature 045 migration manifest")


def manifest_path() -> Path:
    return feature_dir() / MANIFEST_NAME


def markdown_path() -> Path:
    return feature_dir() / MARKDOWN_NAME


def load_manifest() -> dict[str, Any]:
    return json.loads(manifest_path().read_text(encoding="utf-8"))


def atomic_write_text(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.migration-tmp")
    if temporary.exists():
        raise FileExistsError(f"stale migration temporary file: {temporary}")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def save_manifest(payload: dict[str, Any], path: Path | None = None) -> None:
    destination = path or manifest_path()
    atomic_write_text(
        destination, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repository_path(relative: str) -> Path:
    # Keep the leaf lexical so a repository-owned junction can be moved as an
    # entry without following it into the external cache it references.
    candidate = Path(os.path.abspath(ROOT / relative))
    root = Path(os.path.abspath(ROOT))
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository root: {relative}") from exc
    if candidate == root:
        raise ValueError("repository root itself cannot be a migration endpoint")
    return candidate


def ensure_target_parent_inside_repository(target: Path) -> None:
    resolved_parent = target.parent.resolve(strict=False)
    root = ROOT.resolve()
    try:
        resolved_parent.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"target parent escapes repository root: {target}") from exc


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def tracked_files() -> set[str]:
    return set(git("ls-files").stdout.splitlines())


def update_markdown(payload: dict[str, Any], *, approval: bool = False) -> None:
    path = markdown_path()
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"\*\*状态\*\*：`(?:awaiting-approval|approved|executed|verified)`",
        f"**状态**：`{payload['status']}`",
        text,
        count=1,
    )
    if approval:
        text = text.replace(
            "> 本清单只描述拟执行动作。当前未移动、复制、取消跟踪或删除任何既有资产。缓存和日志也不会因确认目录结构而自动删除。",
            "> T019 已获明确批准。仅执行清单内移动、兼容与保留动作；删除授权仍为 false。",
        )
        text = text.replace(
            "- T019 未完成：所有条目均等待第二次明确确认。",
            f"- T019 批准原文：{APPROVAL_TEXT}",
        )
    statuses = {entry["id"]: entry["status"] for entry in payload["entries"]}
    lines: list[str] = []
    for line in text.splitlines():
        match = ROW_PATTERN.match(line)
        if match:
            line = STATUS_CELL_PATTERN.sub(f"`{statuses[match.group('id')]}` |", line)
        lines.append(line)
    atomic_write_text(path, "\n".join(lines) + "\n")


def validate_shape(payload: dict[str, Any]) -> None:
    entries = payload.get("entries", [])
    if len(entries) != 1127:
        raise ValueError(f"expected 1127 manifest entries, found {len(entries)}")
    if sum(entry["source"].startswith("specs/043-") for entry in entries) != 9:
        raise ValueError("the manifest does not contain exactly 9 feature 043 entries")
    if any("delete" in entry["action"] for entry in entries):
        raise ValueError("delete action detected; execution refused")
    if len({entry["id"] for entry in entries}) != len(entries):
        raise ValueError("duplicate manifest ids")
    if len({entry["source"] for entry in entries}) != len(entries):
        raise ValueError("duplicate manifest sources")
    moving_targets = [
        entry["target"] for entry in entries if entry["action"] in MOVE_ACTIONS
    ]
    if len(set(moving_targets)) != len(moving_targets):
        raise ValueError("duplicate physical migration targets")
    for entry in entries:
        repository_path(entry["source"])
        repository_path(entry["target"])
        if entry["status"] not in ENTRY_STATUSES:
            raise ValueError(f"invalid entry status: {entry['id']}")


def append_approval_log(timestamp: str, old_hashes: dict[str, str]) -> None:
    path = OLD_FEATURE / "implementation-log.md"
    marker = "## T019：迁移清单批准"
    existing = path.read_text(encoding="utf-8")
    if marker in existing:
        return
    details = "\n".join(
        f"- 批准前哈希 `{source}`：`{value}`" for source, value in sorted(old_hashes.items())
    )
    block = (
        f"\n## T019：迁移清单批准（{timestamp}）\n\n"
        f"- 用户批准原文：{APPROVAL_TEXT}\n"
        "- 批准范围：1,127 条全部动作，明确包含 9 条 043 规格，以及日志、用户输入、"
        "持久状态、缓存和临时入口。\n"
        "- 删除授权：`false`。执行器不提供删除分支；任一哈希漂移、路径越界或目标冲突都会停止对应批次。\n"
        f"{details}\n"
        "- 勾选 T019 和追加本批准记录后，仅刷新上述两项源哈希；其余条目保持批准时哈希不变。\n"
    )
    path.write_text(existing.rstrip() + "\n" + block, encoding="utf-8")


def mark_t019_complete() -> None:
    path = OLD_FEATURE / "tasks.md"
    text = path.read_text(encoding="utf-8")
    pending = "- [ ] T019 "
    complete = "- [X] T019 "
    if pending in text:
        text = text.replace(pending, complete, 1)
        path.write_text(text, encoding="utf-8")
    elif complete not in text:
        raise ValueError("cannot locate T019 in tasks.md")


def approve() -> dict[str, Any]:
    if feature_dir() != OLD_FEATURE:
        raise ValueError("approval must be recorded before the 045 spec directory is moved")
    payload = load_manifest()
    validate_shape(payload)
    if payload["status"] not in {"awaiting-approval", "approved"}:
        raise ValueError(f"manifest cannot be approved from status {payload['status']}")

    entries_by_source = {entry["source"]: entry for entry in payload["entries"]}
    old_hashes = {
        source: entries_by_source[source]["sha256"] for source in APPROVAL_MUTABLE_SOURCES
    }
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S +08:00")
    mark_t019_complete()
    append_approval_log(timestamp, old_hashes)

    for entry in payload["entries"]:
        entry["status"] = "approved"
    payload["status"] = "approved"
    payload["exceptions"] = [
        item
        for item in payload["exceptions"]
        if not item.startswith("T019 未完成：")
        and not item.startswith("`specs/043-unified-workpoint-structure/` 必须在确认中")
    ]
    payload["exceptions"].insert(0, f"T019 批准原文（{timestamp}）：{APPROVAL_TEXT}")
    payload["exceptions"].insert(
        1,
        "批准登记仅改动 tasks.md 与 implementation-log.md；两项哈希已在登记后刷新，批准前哈希保存在实施记录。",
    )
    for source in APPROVAL_MUTABLE_SOURCES:
        path = repository_path(source)
        entries_by_source[source]["sha256"] = sha256(path)
    save_manifest(payload)
    update_markdown(payload, approval=True)
    return {
        "status": payload["status"],
        "entries": len(payload["entries"]),
        "feature_043_entries": sum(
            entry["source"].startswith("specs/043-") for entry in payload["entries"]
        ),
        "delete_actions": 0,
        "approval": APPROVAL_TEXT,
    }


def select_entries(
    payload: dict[str, Any],
    actions: set[str] | None,
    stages: set[str] | None,
    workpackages: set[str] | None,
    retention_classes: set[str] | None,
) -> list[dict[str, Any]]:
    return [
        entry
        for entry in payload["entries"]
        if (not actions or entry["action"] in actions)
        and (not stages or entry["stage"] in stages)
        and (not workpackages or entry["workpackage"] in workpackages)
        and (not retention_classes or entry["retention_class"] in retention_classes)
    ]


def verify_at(path: Path, entry: dict[str, Any]) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing path for {entry['id']}: {path}")
    expected = entry.get("sha256")
    if expected is not None:
        if not path.is_file():
            raise ValueError(f"hashed entry is not a file: {entry['id']} {path}")
        actual = sha256(path)
        if actual != expected:
            raise ValueError(
                f"sha256 drift for {entry['id']} {entry['source']}: expected {expected}, found {actual}"
            )


def preflight_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    checked = 0
    for entry in entries:
        source = repository_path(entry["source"])
        target = repository_path(entry["target"])
        if entry["status"] == "verified":
            verify_at(target if entry["action"] in MOVE_ACTIONS else source, entry)
            checked += 1
            continue
        if entry["status"] == "rollback-required":
            if source.exists() and not target.exists():
                # The previous attempt stopped before changing the filesystem.
                entry["status"] = "approved"
            else:
                raise ValueError(
                    f"rollback review required for {entry['id']}: source/target state changed"
                )
        if entry["status"] not in {"approved", "moved"}:
            raise ValueError(f"entry is not executable: {entry['id']} {entry['status']}")
        if entry["action"] in MOVE_ACTIONS:
            if not source.exists() and target.exists():
                verify_at(target, entry)
                entry["status"] = "verified"
                checked += 1
                continue
            verify_at(source, entry)
            if target.exists():
                raise FileExistsError(f"target conflict for {entry['id']}: {entry['target']}")
        else:
            if source != target:
                raise ValueError(f"static action changes path: {entry['id']}")
            verify_at(source, entry)
        checked += 1
    return {"checked": checked, "conflicts": 0, "hash_mismatches": 0, "delete_actions": 0}


def move_entry(entry: dict[str, Any]) -> None:
    source = repository_path(entry["source"])
    target = repository_path(entry["target"])
    ensure_target_parent_inside_repository(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Filesystem moves avoid mutating .git in restricted workspaces. Git still
    # reports tracked source/target pairs as renames during status/diff checks.
    shutil.move(str(source), str(target))
    entry["status"] = "moved"
    verify_at(target, entry)
    entry["status"] = "verified"


def relocate_manifest_outputs_if_ready(payload: dict[str, Any]) -> None:
    feature_entries = [
        entry
        for entry in payload["entries"]
        if entry["source"].startswith("specs/045-lifecycle-workspace-governance/")
        and entry["action"] in MOVE_ACTIONS
    ]
    if not feature_entries or not all(entry["status"] == "verified" for entry in feature_entries):
        return
    NEW_FEATURE.mkdir(parents=True, exist_ok=True)
    for name in (MARKDOWN_NAME, MANIFEST_NAME):
        source = OLD_FEATURE / name
        target = NEW_FEATURE / name
        if source.exists() and not target.exists():
            shutil.move(str(source), str(target))
        elif source.exists() and target.exists():
            raise FileExistsError(f"manifest output target conflict: {target}")


def execute(
    payload: dict[str, Any],
    actions: set[str] | None,
    stages: set[str] | None,
    workpackages: set[str] | None,
    retention_classes: set[str] | None,
) -> dict[str, Any]:
    if payload["status"] not in {"approved", "executed", "verified"}:
        raise ValueError(f"manifest is not approved: {payload['status']}")
    selected = select_entries(payload, actions, stages, workpackages, retention_classes)
    pending = [entry for entry in selected if entry["status"] != "verified"]
    already_verified = len(selected) - len(pending)
    preflight_entries(pending)
    recovered = sum(entry["status"] == "verified" for entry in pending)
    pending = [entry for entry in pending if entry["status"] != "verified"]
    moved = 0
    static_verified = 0
    current: dict[str, Any] | None = None
    try:
        for current in pending:
            if current["action"] in MOVE_ACTIONS:
                move_entry(current)
                moved += 1
            elif current["action"] in STATIC_ACTIONS:
                verify_at(repository_path(current["source"]), current)
                current["status"] = "verified"
                static_verified += 1
            else:
                raise ValueError(f"unsupported action: {current['action']}")
    except Exception:
        if current is not None:
            current["status"] = "rollback-required"
        payload["status"] = "executed"
        save_manifest(payload)
        update_markdown(payload)
        raise

    payload["status"] = (
        "verified"
        if all(entry["status"] == "verified" for entry in payload["entries"])
        else "executed"
    )
    save_manifest(payload)
    update_markdown(payload)
    relocate_manifest_outputs_if_ready(payload)
    save_manifest(payload)
    update_markdown(payload)
    return {
        "status": payload["status"],
        "selected": len(selected),
        "already_verified": already_verified,
        "recovered_verified": recovered,
        "moved": moved,
        "static_verified": static_verified,
        "delete_actions": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("approve", "preflight", "execute"))
    parser.add_argument("--action", action="append", choices=sorted(MOVE_ACTIONS | STATIC_ACTIONS))
    parser.add_argument(
        "--stage",
        action="append",
        choices=[
            "00-governance",
            "01-discovery",
            "02-solution-analysis",
            "03-requirements",
            "04-demo",
            "05-validation",
            "06-delivery",
        ],
    )
    parser.add_argument("--workpackage", action="append")
    parser.add_argument("--retention-class", action="append")
    args = parser.parse_args()
    if args.command == "approve":
        result = approve()
    else:
        payload = load_manifest()
        validate_shape(payload)
        actions = set(args.action) if args.action else None
        stages = set(args.stage) if args.stage else None
        workpackages = set(args.workpackage) if args.workpackage else None
        retention_classes = set(args.retention_class) if args.retention_class else None
        if args.command == "preflight":
            selected = select_entries(payload, actions, stages, workpackages, retention_classes)
            result = {
                "status": payload["status"],
                "selected": len(selected),
                **preflight_entries(selected),
            }
        else:
            result = execute(payload, actions, stages, workpackages, retention_classes)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
