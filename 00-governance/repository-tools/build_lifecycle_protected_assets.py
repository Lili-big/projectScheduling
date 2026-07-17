"""Build the 045 protected-asset register from the frozen baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/repository-baseline.json"
DEFAULT_OUTPUT = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/protected-assets.json"
BINARY_SUFFIXES = {".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".ppt", ".pptx", ".pdf", ".zip"}


def scope_digest(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["path"]):
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update((record.get("sha256") or "").encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def protected_record(record: dict[str, Any], kind: str, reason: str) -> dict[str, Any]:
    return {
        "path": record["path"],
        "kind": kind,
        "tracking_policy": "tracked" if record["state"] == "tracked" else "local-only",
        "size_bytes": record.get("size_bytes"),
        "sha256": record.get("sha256"),
        "protected": True,
        "reason": reason,
        "allowed_action": "keep-unless-separately-approved",
    }


def build() -> dict[str, Any]:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    tracked = baseline["tracked_files"]
    local = baseline["ignored_local_files"]
    untracked = baseline["untracked_files"]
    all_records = tracked + local + untracked

    scopes = []
    for prefix, reason in (
        ("specs/042-repo-architecture-modernization/", "042 已完成架构迁移证据，内容和编号必须保持"),
        ("specs/043-unified-workpoint-structure/", "043 在 045 中需要单独确认后才能随规格树移动"),
    ):
        records = [item for item in tracked if item["path"].startswith(prefix)]
        scopes.append(
            {
                "path": prefix.rstrip("/"),
                "kind": "feature-scope",
                "file_count": len(records),
                "sha256": scope_digest(records),
                "protected": True,
                "reason": reason,
            }
        )

    assets: dict[str, dict[str, Any]] = {}
    for record in all_records:
        path = record["path"]
        suffix = Path(path).suffix.lower()
        if suffix in BINARY_SUFFIXES and record.get("sha256"):
            assets[path] = protected_record(record, "formal-or-source-binary", "二进制只能按清单和哈希迁移，不得自动清理")
        if path.startswith("local-json-task-review/input/") or path.startswith("local-json-task-review/engineering-result/input/"):
            assets[path] = protected_record(record, "user-json-input", "独立 JSON 工作区输入，迁移前不得覆盖或删除")
        if path in {".local-data/scheduler-config.json", ".local-data/plan-control-store.json"}:
            assets[path] = protected_record(record, "persistent-json-state", "Demo 本地持久状态")
        if suffix in {".db", ".sqlite", ".sqlite3"}:
            assets[path] = protected_record(record, "persistent-database", "数据库或验收快照，禁止自动删除")
        if path == "泸古1标架梁工点导入模板.xlsx":
            assets[path] = protected_record(record, "root-customer-template", "根目录客户模板需单独确认目标工作包")

    env_entry = next((item for item in baseline["ignored_entries"] if item["path"] == ".local.env"), None)
    if env_entry:
        assets[".local.env"] = protected_record(env_entry, "secret-local-config", "可能含凭据，只保留路径、大小和哈希，不迁移内容")

    untracked_docx = [item for item in untracked if Path(item["path"]).suffix.lower() == ".docx"]
    return {
        "format_version": 1,
        "feature": "045-lifecycle-workspace-governance",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "default_action": "protect",
        "deletion_authorized": False,
        "protected_scopes": scopes,
        "untracked_docx_count": len(untracked_docx),
        "assets": [assets[key] for key in sorted(assets)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    payload = build()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": output.relative_to(ROOT).as_posix(), "protected_scopes": len(payload["protected_scopes"]), "protected_assets": len(payload["assets"]), "untracked_docx": payload["untracked_docx_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
