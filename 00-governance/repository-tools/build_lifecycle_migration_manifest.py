"""Build the complete pre-approval migration manifest for feature 045.

The command is read-only with respect to repository assets. It writes only the
machine manifest and its human-readable projection under the active 045 spec.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
FEATURE = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance"
BASELINE = FEATURE / "repository-baseline.json"
PROTECTED = FEATURE / "protected-assets.json"
DEFAULT_JSON = FEATURE / "asset-migration-manifest.json"
DEFAULT_MD = FEATURE / "asset-migration-manifest.md"
EXCLUDED_OUTPUTS = {
    "specs/045-lifecycle-workspace-governance/asset-migration-manifest.json",
    "specs/045-lifecycle-workspace-governance/asset-migration-manifest.md",
}
TEXT_SUFFIXES = {".cmd", ".html", ".js", ".json", ".md", ".mjs", ".mts", ".ps1", ".py", ".toml", ".ts", ".tsx", ".yaml", ".yml"}
SOLUTION_DOCS = {
    "LLM+CPSAT融合方案.md",
    "MVP方案_工程化落地版.md",
    "基建智能计划管控中枢整体产品方案_v1.0.md",
    "系统整体长期目标.md",
}
ROOT_COMPATIBILITY = {
    ".dockerignore": "04-demo",
    ".gitignore": "00-governance",
    ".local.env.example": "04-demo",
    ".netlifyignore": "04-demo",
    "AGENTS.md": "00-governance",
    "Dockerfile": "04-demo",
    "README.md": "00-governance",
    "agent.md": "00-governance",
    "netlify.toml": "04-demo",
    "package-lock.json": "04-demo",
    "package.json": "04-demo",
    "requirements.txt": "04-demo",
}
ALLOWED_ACTIONS = {"git-move", "local-move", "compatibility-entry", "keep"}
ALLOWED_TRACKING = {"tracked", "ignored", "local-only"}
ALLOWED_RETENTION = {"persistent-state", "user-input", "formal-output", "diagnostic-log", "rebuildable", "cache", "temporary"}
ENTRY_KEYS = {"id", "source", "target", "stage", "workpackage", "action", "tracking_policy", "retention_class", "sha256", "references", "rollback", "status"}


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


def current_repository_records() -> list[dict[str, Any]]:
    tracked = set(git("ls-files").splitlines())
    untracked = set(git("ls-files", "--others", "--exclude-standard").splitlines())
    records: list[dict[str, Any]] = []
    for source in sorted((tracked | untracked) - EXCLUDED_OUTPUTS):
        path = ROOT / source
        if not path.is_file():
            continue
        records.append(
            {
                "source": source,
                "state": "tracked" if source in tracked else "implementation-new",
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "kind": "file",
            }
        )
    return records


def local_records(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    detailed = {item["path"]: item for item in baseline["ignored_local_files"]}
    records = [
        {
            "source": item["path"],
            "state": "ignored-local-detail",
            "size_bytes": item.get("size_bytes"),
            "sha256": item.get("sha256"),
            "kind": "file",
        }
        for item in detailed.values()
        if (ROOT / item["path"]).is_file()
    ]
    detailed_paths = tuple(f"{path}/" for path in detailed)
    for item in baseline["ignored_entries"]:
        source = item["path"].rstrip("/")
        if source in detailed or any(path.startswith(f"{source}/") for path in detailed):
            continue
        if source in EXCLUDED_OUTPUTS or not (ROOT / source).exists():
            continue
        records.append(
            {
                "source": source,
                "state": "ignored-summary",
                "size_bytes": item.get("size_bytes"),
                "sha256": item.get("sha256"),
                "kind": item.get("kind", "directory-summary"),
            }
        )
    del detailed_paths
    return records


def target_for_tracked(source: str) -> tuple[str, str, str | None, str, str, str]:
    path = Path(source)
    name = path.name
    if source.startswith("00-governance/"):
        return source, "00-governance", "lifecycle-workspace-governance", "keep", "tracked", "formal-output"
    if source.startswith(".agents/"):
        return source, "00-governance", "lifecycle-workspace-governance", "compatibility-entry", "tracked", "formal-output"
    if source.startswith(".specify/"):
        return source, "03-requirements", "spec-kit", "compatibility-entry", "tracked", "formal-output"
    if source.startswith(".codex/"):
        return source, "00-governance", "lifecycle-workspace-governance", "compatibility-entry", "tracked", "formal-output"
    if source in ROOT_COMPATIBILITY:
        stage = ROOT_COMPATIBILITY[source]
        return source, stage, "bridge-scheduling-demo" if stage == "04-demo" else "lifecycle-workspace-governance", "compatibility-entry", "tracked", "formal-output"
    if source == "泸古1标架梁工点导入模板.xlsx":
        target = f"01-discovery/workpackages/lugu-source-data-analysis/inputs/{name}"
        return target, "01-discovery", "lugu-source-data-analysis", "git-move", "tracked", "user-input"
    if source.startswith("backend/"):
        return f"04-demo/backend/{source[8:]}", "04-demo", "bridge-scheduling-demo", "git-move", "tracked", "formal-output"
    if source.startswith("frontend/"):
        return f"04-demo/frontend/{source[9:]}", "04-demo", "bridge-scheduling-demo", "git-move", "tracked", "formal-output"
    if source.startswith("examples/"):
        rel = source[9:]
        workpackage = "schedule-result-viewer" if rel.startswith("result-viewer/") else "bridge-scheduling-demo"
        target = f"04-demo/standalone/schedule-result-viewer/{rel[14:]}" if rel.startswith("result-viewer/") else f"04-demo/examples/{rel}"
        return target, "04-demo", workpackage, "git-move", "tracked", "formal-output"
    if source.startswith("deliverables/"):
        return f"06-delivery/deliverables/{source[13:]}", "06-delivery", None, "git-move", "tracked", "formal-output"
    if source.startswith("specs/"):
        rel = source[6:]
        feature_name = rel.split("/", 1)[0]
        workpackage = "lifecycle-workspace-governance" if feature_name.startswith("045-") else feature_name
        return f"03-requirements/specs/{rel}", "03-requirements", workpackage, "git-move", "tracked", "formal-output"
    if source == "docs/README.md":
        return "00-governance/history/legacy-docs-index.md", "00-governance", "lifecycle-workspace-governance", "git-move", "tracked", "formal-output"
    if source.startswith("docs/architecture/"):
        return f"00-governance/architecture/{source[18:]}", "00-governance", "lifecycle-workspace-governance", "git-move", "tracked", "formal-output"
    if source == "docs/archive/path-migration.md":
        return "00-governance/history/path-migration.md", "00-governance", "lifecycle-workspace-governance", "git-move", "tracked", "formal-output"
    if source.startswith("docs/archive/application-case/"):
        return f"06-delivery/workpackages/ai-case-summary/history/{name}", "06-delivery", "ai-case-summary", "git-move", "tracked", "formal-output"
    if source.startswith("docs/research/"):
        bucket = "inputs" if "提纲" in name else "results"
        return f"01-discovery/workpackages/lugu-customer-research/{bucket}/{name}", "01-discovery", "lugu-customer-research", "git-move", "tracked", "user-input" if bucket == "inputs" else "formal-output"
    if source.startswith("docs/product/"):
        if name in SOLUTION_DOCS:
            return f"02-solution-analysis/proposals/{name}", "02-solution-analysis", None, "git-move", "tracked", "formal-output"
        return f"03-requirements/product/{name}", "03-requirements", None, "git-move", "tracked", "formal-output"
    if source.startswith("docs/engineering/"):
        return f"03-requirements/rules/{name}", "03-requirements", None, "git-move", "tracked", "formal-output"
    if source.startswith("docs/validation/"):
        if "泸古" in name:
            return f"05-validation/workpackages/lugu-validation-material/plans/{name}", "05-validation", "lugu-validation-material", "git-move", "tracked", "formal-output"
        return f"05-validation/reports/{name}", "05-validation", None, "git-move", "tracked", "formal-output"
    if source.startswith("docs/"):
        return f"05-validation/workpackages/lugu-plan-granularity/results/{name}", "05-validation", "lugu-plan-granularity", "git-move", "tracked", "formal-output"
    if source.startswith("tools/repo-governance/"):
        return f"00-governance/repository-tools/{source[22:]}", "00-governance", "lifecycle-workspace-governance", "git-move", "tracked", "formal-output"
    if source.startswith("tools/ai-ppt-system/"):
        return f"06-delivery/presentations/ai-ppt-system/{source[20:]}", "06-delivery", "ai-ppt-system", "git-move", "tracked", "formal-output"
    if source.startswith("tools/delivery-builders/lugu-report/"):
        return f"01-discovery/workpackages/lugu-customer-research/scripts/{source[36:]}", "01-discovery", "lugu-customer-research", "git-move", "tracked", "formal-output"
    if source.startswith("tools/delivery-builders/lugu-validation/"):
        return f"05-validation/workpackages/lugu-validation-material/scripts/{source[40:]}", "05-validation", "lugu-validation-material", "git-move", "tracked", "formal-output"
    if source.startswith("tools/demo-api-mirror/"):
        return f"04-demo/tools/demo-api-mirror/{source[22:]}", "04-demo", "bridge-scheduling-demo", "git-move", "tracked", "formal-output"
    if source.startswith("tools/local-runtime/"):
        return f"04-demo/runtime/{source[20:]}", "04-demo", "bridge-scheduling-demo", "git-move", "tracked", "formal-output"
    if source.startswith("tools/"):
        return f"04-demo/tools/{source[6:]}", "04-demo", "bridge-scheduling-demo", "git-move", "tracked", "formal-output"
    if source.startswith("outputs/019f69ae-"):
        bucket = "scripts" if path.suffix.lower() in {".js", ".mjs", ".py"} else "results"
        return f"05-validation/workpackages/lugu-validation-material/project-master/{bucket}/{name}", "05-validation", "lugu-validation-material", "git-move", "tracked", "formal-output"
    if source.startswith("outputs/lugu-report-20260715/"):
        bucket = "scripts" if path.suffix.lower() == ".py" else "results"
        return f"01-discovery/workpackages/lugu-source-data-analysis/{bucket}/{name}", "01-discovery", "lugu-source-data-analysis", "git-move", "tracked", "formal-output"
    if source.startswith("outputs/lugu-validation-20260716/"):
        bucket = "scripts" if path.suffix.lower() == ".py" else "results"
        return f"05-validation/workpackages/lugu-plan-granularity/{bucket}/{name}", "05-validation", "lugu-plan-granularity", "git-move", "tracked", "formal-output"
    raise ValueError(f"unclassified tracked or implementation asset: {source}")


def target_for_local(source: str) -> tuple[str, str, str | None, str, str, str]:
    path = Path(source)
    name = path.name
    parts = path.parts
    if source == ".local.env":
        return source, "04-demo", "bridge-scheduling-demo", "keep", "local-only", "user-input"
    if source.startswith(".local-data/logs/"):
        return source, "04-demo", "bridge-scheduling-demo", "keep", "ignored", "diagnostic-log"
    if source in {".local-data/plan-control-store.json", ".local-data/project-master.db", ".local-data/scheduler-config.json"}:
        return f".local-data/state/{name}", "04-demo", "bridge-scheduling-demo", "local-move", "local-only", "persistent-state"
    if source.startswith(".local-data/"):
        retention = "diagnostic-log" if name.endswith(".log") else "temporary" if "/tmp/" in source else "rebuildable"
        target = f".local-data/logs/legacy-unclassified/{name}" if name.endswith(".log") and "/logs/" not in source else source
        return target, "04-demo", "bridge-scheduling-demo", "local-move" if target != source else "keep", "ignored", retention
    if source.startswith("local-json-task-review/engineering-result/"):
        rel = source[len("local-json-task-review/engineering-result/"):]
        if rel.startswith("input/"):
            retention, tracking = "user-input", "local-only"
        elif rel.startswith("output/"):
            retention, tracking = "rebuildable", "ignored"
        else:
            retention, tracking = "formal-output", "tracked"
        return f"05-validation/workpackages/json-schedule-review/{rel}", "05-validation", "json-schedule-review", "local-move", tracking, retention
    if source.startswith("local-json-task-review/"):
        rel = source[len("local-json-task-review/"):]
        if rel.startswith("input/"):
            retention, tracking = "user-input", "local-only"
        elif rel.startswith("output/"):
            retention, tracking = "rebuildable", "ignored"
        else:
            retention, tracking = "formal-output", "tracked"
        return f"04-demo/standalone/json-task-viewer/{rel}", "04-demo", "json-task-viewer", "local-move", tracking, retention
    if source.startswith("logs/") or (len(parts) == 1 and name.endswith(".log")):
        rel = source[5:] if source.startswith("logs/") else source
        return f".local-data/logs/legacy-unclassified/{rel}", "04-demo", "bridge-scheduling-demo", "local-move", "ignored", "diagnostic-log"
    if source.startswith("frontend/") and name.endswith(".log"):
        return f".local-data/logs/legacy-unclassified/frontend/{name}", "04-demo", "bridge-scheduling-demo", "local-move", "ignored", "diagnostic-log"
    if source == "frontend/node_modules":
        return "04-demo/frontend/node_modules", "04-demo", "bridge-scheduling-demo", "local-move", "ignored", "cache"
    if source == "frontend/dist":
        return ".local-data/archive/rebuildable/frontend-dist", "04-demo", "bridge-scheduling-demo", "local-move", "ignored", "rebuildable"
    if source.startswith("output/"):
        return f".local-data/archive/rebuildable/{source[7:]}", "05-validation", None, "local-move", "ignored", "rebuildable"
    if source.startswith("artifacts/"):
        return f".local-data/archive/rebuildable/{source[10:]}", "06-delivery" if "ai-ppt-system" in source else "05-validation", "ai-ppt-system" if "ai-ppt-system" in source else None, "local-move", "ignored", "rebuildable"
    if source == "ai-ppt-system":
        return ".local-data/cache/legacy-ai-ppt-system-node_modules", "06-delivery", "ai-ppt-system", "local-move", "ignored", "cache"
    if "node_modules" in parts:
        safe = source.replace("/", "__")
        return f".local-data/cache/legacy-node-modules/{safe}", "05-validation", "lifecycle-workspace-governance", "local-move", "ignored", "cache"
    if "__pycache__" in parts or ".pytest_cache" in parts or name.endswith(".pyc"):
        safe = source.replace("/", "__")
        return f".local-data/tmp/python-cache/{safe}", "05-validation", "lifecycle-workspace-governance", "local-move", "ignored", "temporary"
    if source.startswith("outputs/lugu-validation-20260715"):
        return source, "05-validation", "lugu-validation-material", "keep", "ignored", "cache"
    cache_roots = (
        ".codex-tmp", ".edge-profile", ".git-tmp-projectScheduling", ".netlify", ".netlify-cli-runtime",
        ".netlify-deploy-staging", ".npm-cache", ".npm-cache-netlify-deploy", ".pip-cache", ".playwright-cli",
        ".pytest_cache", ".venv", "node_modules",
    )
    if source.startswith(cache_roots):
        return source, "00-governance", "lifecycle-workspace-governance", "keep", "ignored", "cache"
    raise ValueError(f"unclassified ignored/local asset: {source}")


def load_reference_documents(records: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    documents: list[tuple[str, str, str]] = []
    for record in records:
        source = record["source"]
        path = ROOT / source
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        if source in EXCLUDED_OUTPUTS or source.endswith(("repository-baseline.json", "protected-assets.json")):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        kind = "history" if source.startswith("specs/") or source.startswith("docs/archive/") else "current"
        documents.append((source, content, kind))
    return documents


def references_for(source: str, documents: list[tuple[str, str, str]]) -> list[str]:
    return sorted(f"{kind}:{path}" for path, content, kind in documents if path != source and source in content)


def rollback_for(source: str, target: str, action: str, tracking: str) -> str:
    if action in {"keep", "compatibility-entry"}:
        return f"保持 {source} 原位，不执行物理操作"
    suffix = "并恢复 Git 跟踪" if tracking == "tracked" else "且保持本地忽略/不跟踪状态"
    return f"将 {target} 移回 {source}，{suffix}"


def build_entries(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    documents = load_reference_documents([item for item in records if item["state"] in {"tracked", "implementation-new"}])
    entries: list[dict[str, Any]] = []
    sizes: dict[str, int | None] = {}
    for index, record in enumerate(sorted(records, key=lambda item: item["source"]), start=1):
        source = record["source"]
        if record["state"] in {"tracked", "implementation-new"}:
            target, stage, workpackage, action, tracking, retention = target_for_tracked(source)
        else:
            target, stage, workpackage, action, tracking, retention = target_for_local(source)
        entry_id = f"M{index:04d}"
        sizes[entry_id] = record.get("size_bytes")
        entries.append(
            {
                "id": entry_id,
                "source": source,
                "target": target,
                "stage": stage,
                "workpackage": workpackage,
                "action": action,
                "tracking_policy": tracking,
                "retention_class": retention,
                "sha256": record.get("sha256"),
                "references": references_for(source, documents),
                "rollback": rollback_for(source, target, action, tracking),
                "status": "prechecked",
            }
        )
    return entries, sizes


def validate(entries: list[dict[str, Any]]) -> None:
    if len({entry["id"] for entry in entries}) != len(entries):
        raise ValueError("duplicate manifest ids")
    if len({entry["source"] for entry in entries}) != len(entries):
        raise ValueError("duplicate manifest sources")
    moving = [entry for entry in entries if entry["action"] in {"git-move", "local-move"}]
    conflicts = [target for target, count in Counter(entry["target"] for entry in moving).items() if count > 1]
    if conflicts:
        raise ValueError(f"duplicate physical targets: {conflicts[:10]}")
    for entry in entries:
        if set(entry) != ENTRY_KEYS:
            raise ValueError(f"entry properties differ from migration-manifest.schema.json: {entry['id']}")
        if not re.fullmatch(r"M[0-9]{4}", entry["id"]):
            raise ValueError(f"invalid id: {entry['id']}")
        if not entry["source"] or not entry["target"] or not entry["rollback"]:
            raise ValueError(f"empty required string: {entry['id']}")
        if entry["workpackage"] is not None and not isinstance(entry["workpackage"], str):
            raise ValueError(f"invalid workpackage: {entry['id']}")
        if not isinstance(entry["references"], list) or not all(isinstance(item, str) for item in entry["references"]):
            raise ValueError(f"invalid references: {entry['id']}")
        if entry["action"] not in ALLOWED_ACTIONS:
            raise ValueError(f"invalid action: {entry}")
        if entry["tracking_policy"] not in ALLOWED_TRACKING:
            raise ValueError(f"invalid tracking policy: {entry}")
        if entry["retention_class"] not in ALLOWED_RETENTION:
            raise ValueError(f"invalid retention class: {entry}")
        if entry["sha256"] is not None and not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"invalid sha256: {entry['source']}")
        if not re.match(r"^(00|01|02|03|04|05|06)-", entry["stage"]):
            raise ValueError(f"invalid stage: {entry}")
        if entry["status"] not in {"draft", "prechecked", "approved", "moved", "verified", "rollback-required", "rolled-back"}:
            raise ValueError(f"invalid status: {entry}")


def markdown(entries: list[dict[str, Any]], sizes: dict[str, int | None], exceptions: list[str]) -> str:
    lines = [
        "# 045 逐资产迁移清单",
        "",
        "**状态**：`awaiting-approval`",
        "",
        "> 本清单只描述拟执行动作。当前未移动、复制、取消跟踪或删除任何既有资产。缓存和日志也不会因确认目录结构而自动删除。",
        "",
        "## 汇总",
        "",
        f"- 条目总数：{len(entries)}",
        f"- 物理移动候选：{sum(entry['action'] in {'git-move', 'local-move'} for entry in entries)}",
        f"- 原位兼容/保留：{sum(entry['action'] in {'compatibility-entry', 'keep'} for entry in entries)}",
        f"- 043 受保护规格条目：{sum(entry['source'].startswith('specs/043-') for entry in entries)}",
        f"- 日志条目：{sum(entry['retention_class'] == 'diagnostic-log' for entry in entries)}",
        f"- 缓存/临时条目：{sum(entry['retention_class'] in {'cache', 'temporary'} for entry in entries)}",
        f"- 删除动作：0",
        "",
    ]
    for title, key in (("按阶段", "stage"), ("按动作", "action"), ("按跟踪策略", "tracking_policy"), ("按保留等级", "retention_class")):
        lines.extend([f"### {title}", "", "| 值 | 数量 |", "| --- | ---: |"])
        lines.extend(f"| `{name}` | {count} |" for name, count in sorted(Counter(entry[key] for entry in entries).items()))
        lines.append("")
    lines.extend(["## 例外与保护边界", ""])
    lines.extend(f"- {item}" for item in exceptions)
    lines.extend(
        [
            "",
            "## 完整条目",
            "",
            "| ID | 源路径 | 目标路径 | 阶段 | 工作包 | 动作 | 跟踪 | 保留等级 | 大小 | 状态 |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for entry in entries:
        size = sizes.get(entry["id"])
        size_text = "-" if size is None else str(size)
        values = [
            entry["id"], entry["source"], entry["target"], entry["stage"], entry["workpackage"] or "-",
            entry["action"], entry["tracking_policy"], entry["retention_class"], size_text, entry["status"],
        ]
        escaped = [str(value).replace("|", "\\|") for value in values]
        lines.append("| " + " | ".join(f"`{value}`" if position not in {8} else value for position, value in enumerate(escaped)) + " |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    protected = json.loads(PROTECTED.read_text(encoding="utf-8"))
    records = current_repository_records() + local_records(baseline)
    entries, sizes = build_entries(records)
    validate(entries)
    exceptions = [
        "T019 未完成：所有条目均等待第二次明确确认。",
        "`specs/043-unified-workpoint-structure/` 必须在确认中单独点明，不能由其他规格的批准推定。",
        "`.local.env` 只记录路径、大小和哈希并保持原位，真实内容不会复制到治理资产。",
        "依赖、虚拟环境和工具缓存按忽略入口聚合；原位保留项不代表永久保留，后续仅进入清理 dry-run。",
        "日志移动前必须再次确认活动进程；任何变化都会停止日志批次。",
        f"保护登记包含 {len(protected['protected_scopes'])} 个规格范围和 {len(protected['assets'])} 个保护资产；本清单不包含删除动作。",
        "清单自身两个输出文件为避免自引用而不列为迁移条目；它们随 045 规格目录整体移动。",
    ]
    payload = {
        "feature": "045-lifecycle-workspace-governance",
        "status": "awaiting-approval",
        "entries": entries,
        "exceptions": exceptions,
    }
    if set(payload) != {"feature", "status", "entries", "exceptions"}:
        raise ValueError("manifest top-level properties differ from migration-manifest.schema.json")
    json_output = args.json_output if args.json_output.is_absolute() else ROOT / args.json_output
    md_output = args.markdown_output if args.markdown_output.is_absolute() else ROOT / args.markdown_output
    json_output.parent.mkdir(parents=True, exist_ok=True)
    md_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_output.write_text(markdown(entries, sizes, exceptions), encoding="utf-8")
    print(json.dumps({
        "entries": len(entries),
        "git_moves": sum(entry["action"] == "git-move" for entry in entries),
        "local_moves": sum(entry["action"] == "local-move" for entry in entries),
        "compatibility": sum(entry["action"] == "compatibility-entry" for entry in entries),
        "keep": sum(entry["action"] == "keep" for entry in entries),
        "status": payload["status"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
