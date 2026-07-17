"""Build the per-file, pre-approval asset migration manifest for feature 042."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "03-requirements/specs/042-repo-architecture-modernization/asset-migration-manifest.json"

ROOT_PRODUCT_DOCS = {"LLM+CPSAT融合方案.md", "MVP方案_工程化落地版.md", "系统整体长期目标.md"}
DOC_PRODUCT = {
    "任务视图页面需求文档_v1.0.md", "基建智能计划管控中枢整体产品方案_v1.0.md", "施工工艺及工效库需求文档_v1.1.md",
    "模拟求解-MVP页面需求文档_v1.2.md", "计划发布与审批入口需求文档_v1.0.md", "资源配置页面需求文档_v1.2.md",
    "里程碑页面需求文档_v1.0.md", "项目排程系统整体说明_v1.1.md",
}
DOC_ENGINEERING = {"墩柱按高度计算工期算法需求文档_v1.0.md", "工艺逻辑约束需求文档_v1.1.md", "排程算法当前实现交底文档_v1.2.md", "现浇连续梁结构排程_PRD算法_v1.10.md"}
DOC_VALIDATION = {"AI参数输入助手验证说明.md", "AI资源配置与排程优化助手验证说明.md", "泸古项目客户验证计划_20260715.md"}
DOC_RESEARCH = {"泸古项目上午调研验证记录_20260715.docx", "泸古项目前期工期策划思路分析_20260715.docx", "泸古项目客户访谈提纲_20260715.md"}
VIEWER_FILES = {"cpsat-result-third-version.json", "cpsat-result-viewer.html", "fixed-resource-shortest-duration-20260707-134506.json", "fixed-resource-shortest-duration-viewer.html"}
BINARY_SUFFIXES = {".xlsx", ".xlsm", ".docx", ".pptx", ".pdf", ".png", ".jpg", ".jpeg"}


def tracked_files() -> list[str]:
    result = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.splitlines()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_for(source: str) -> tuple[str, str, str]:
    path = Path(source)
    name = path.name
    if "/" not in source and name.endswith(".log"):
        return f".local-data/logs/legacy/{name}", "runtime_log", "move_local_only"
    if source in ROOT_PRODUCT_DOCS:
        return f"docs/product/{name}", "product_document", "git_mv_keep_tracked"
    if source == "渠溪河特大桥结构设计表.xlsx":
        return f"examples/bridge-import/{name}", "reproducible_sample", "git_mv_keep_tracked"
    if source.startswith("docs/"):
        if name.startswith("~$"):
            return f"artifacts/local-locks/{name}", "temporary_lock", "move_then_untrack"
        if name in VIEWER_FILES:
            return f"examples/result-viewer/{name}", "reproducible_sample", "git_mv_keep_tracked"
        if name in DOC_PRODUCT:
            return f"docs/product/{name}", "product_document", "git_mv_keep_tracked"
        if name in DOC_ENGINEERING:
            return f"docs/engineering/{name}", "engineering_document", "git_mv_keep_tracked"
        if name in DOC_VALIDATION:
            return f"docs/validation/{name}", "validation_document", "git_mv_keep_tracked"
        if name in DOC_RESEARCH:
            return f"docs/research/{name}", "research_document", "git_mv_keep_tracked"
        if name.startswith("AI驱动Demo快速验证与研发交付案例"):
            return f"docs/archive/application-case/{name}", "historical_document", "git_mv_keep_tracked"
        raise ValueError(f"unclassified docs asset: {source}")
    if source.startswith("ai-ppt-system/output/"):
        relative = source.removeprefix("ai-ppt-system/output/")
        return f"artifacts/ai-ppt-system/output/{relative}", "generated_artifact", "move_then_untrack"
    if source.startswith("ai-ppt-system/"):
        return f"tools/ai-ppt-system/{source.removeprefix('ai-ppt-system/')}", "reusable_tool", "git_mv_keep_tracked"
    if source.startswith("netlify/demo-functions/"):
        return f"tools/demo-api-mirror/{source.removeprefix('netlify/demo-functions/')}", "reference_tool", "git_mv_keep_tracked"
    if source.startswith("outputs/019f5a26-"):
        return f"deliverables/awards/2026/{name}", "formal_deliverable", "git_mv_keep_tracked"
    if source.startswith("outputs/lugu-report-20260715/"):
        return f"tools/delivery-builders/lugu-report/{name}", "delivery_builder", "git_mv_keep_tracked"
    if source.startswith("outputs/lugu-validation-20260715/"):
        if name in {"build_validation_workbook.mjs", "verify_validation_workbook.mjs"}:
            return f"tools/delivery-builders/lugu-validation/{name}", "delivery_builder", "git_mv_keep_tracked"
        if name == "泸古项目验证材料_20260715.xlsx":
            return f"deliverables/validation/lugu/{name}", "formal_deliverable", "git_mv_keep_tracked"
        return f"artifacts/lugu-validation/{name}", "generated_artifact" if not name.startswith("~$") else "temporary_lock", "move_then_untrack"
    if source.startswith(".netlify-cli-runtime/"):
        relative = source.removeprefix(".netlify-cli-runtime/")
        return f"artifacts/netlify-cli/{relative}", "local_runtime", "move_then_untrack"
    raise ValueError(f"unclassified asset: {source}")


def candidates(tracked: list[str]) -> list[str]:
    return [
        path for path in tracked
        if path in ROOT_PRODUCT_DOCS
        or path == "渠溪河特大桥结构设计表.xlsx"
        or path.startswith(("docs/", "ai-ppt-system/", "netlify/demo-functions/", "outputs/", ".netlify-cli-runtime/"))
        and path not in {"docs/README.md"}
        and not path.startswith("docs/architecture/")
    ]


def local_root_logs(tracked: list[str]) -> list[str]:
    """Return ignored/untracked runtime logs that currently clutter the repo root."""
    tracked_set = set(tracked)
    return sorted(
        path.name
        for path in ROOT.glob("*.log")
        if path.is_file() and path.name not in tracked_set
    )


def main() -> int:
    tracked = tracked_files()
    entries = []
    sources = [(source, True) for source in sorted(candidates(tracked))]
    sources.extend((source, False) for source in local_root_logs(tracked))
    for source, tracked_before in sources:
        target, category, action = target_for(source)
        path = ROOT / source
        entries.append({
            "source": source,
            "target": target,
            "category": category,
            "tracking_action": action,
            "tracked_before": tracked_before,
            "tracked_after": action == "git_mv_keep_tracked",
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "binary": path.suffix.lower() in BINARY_SUFFIXES,
            "approval_status": "pending_second_confirmation",
            "rollback": f"move {target} back to {source}" + (
                " and restore tracking"
                if action == "move_then_untrack"
                else " with git mv"
                if action == "git_mv_keep_tracked"
                else " without changing Git tracking"
            ),
        })
    payload = {
        "format_version": 1,
        "generated_at": "2026-07-16",
        "approval_gate": "T122 second explicit user confirmation required before any entry is moved or untracked",
        "entry_count": len(entries),
        "entries": entries,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
