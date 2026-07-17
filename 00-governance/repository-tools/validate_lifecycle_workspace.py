"""Validate lifecycle ownership, root hygiene, and work-package contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "00-governance/asset-policy"
SCRIPT_SUFFIXES = {".py", ".js", ".mjs", ".mts", ".ts", ".tsx", ".ps1", ".cmd"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_beneath(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate() -> dict[str, Any]:
    placement = load_json(POLICY_DIR / "placement-rules.json")
    compatibility = load_json(POLICY_DIR / "root-compatibility.json")
    index = load_json(POLICY_DIR / "workpackages.json")
    stages = placement["allowed_stage_roots"]
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    def fail(code: str, path: str, message: str) -> None:
        violations.append({"code": code, "path": path, "message": message})

    declared_root = {entry["path"] for entry in compatibility["entries"]}
    declared_root.update(stages)
    declared_root.add(".git")
    for path in ROOT.iterdir():
        if path.name.startswith(".git-"):
            continue
        if path.name not in declared_root:
            fail("unknown-root-entry", path.name, "根目录入口未在兼容契约登记")

    forbidden = set(placement["forbidden_business_roots"])
    compatibility_by_path = {entry["path"]: entry for entry in compatibility["entries"]}
    for name in sorted(forbidden):
        if (ROOT / name).exists():
            entry = compatibility_by_path.get(name, {})
            if entry.get("status") == "retained-local-cache":
                warnings.append(
                    {
                        "code": "retained-local-cache-root",
                        "path": name,
                        "message": "仅允许已登记缓存原位保留，禁止新增业务资产",
                    }
                )
            else:
                fail("legacy-business-root", name, "业务资产必须进入生命周期阶段目录")

    allowed_root_files = {
        entry["path"]
        for entry in compatibility["entries"]
        if (ROOT / entry["path"]).is_file()
    }
    forbidden_suffixes = set(placement["forbidden_root_file_suffixes"])
    for path in ROOT.iterdir():
        if path.is_file() and path.suffix.lower() in forbidden_suffixes and path.name not in allowed_root_files:
            fail("orphan-root-file", path.name, "根目录脚本或生成物没有阶段/工作包主归属")

    indexed = {entry["id"]: entry for entry in index["packages"]}
    registered_dirs: dict[str, Path] = {}
    for package_id, entry in indexed.items():
        directory = ROOT / entry["path"]
        registered_dirs[package_id] = directory
        descriptor = directory / "workpackage.json"
        readme = directory / "README.md"
        if not descriptor.is_file() or not readme.is_file():
            fail("incomplete-workpackage", entry["path"], "缺少 README.md 或 workpackage.json")
            continue
        data = load_json(descriptor)
        if data["id"] != package_id or data["stage"] != entry["stage"]:
            fail("workpackage-index-drift", entry["path"], "索引与工作包 ID/阶段不一致")
        for field in ("inputs", "entrypoints", "results"):
            for item in data[field]:
                target = (directory / item).resolve(strict=False)
                try:
                    target.relative_to(directory.resolve())
                except ValueError:
                    fail("workpackage-path-escape", f"{entry['path']}/{item}", "引用越出工作包")
                    continue
                if not target.exists():
                    fail("missing-workpackage-reference", f"{entry['path']}/{item}", f"{field} 引用不存在")

    for descriptor in ROOT.glob("0[0-6]-*/**/workpackage.json"):
        if "templates" in descriptor.parts:
            continue
        data = load_json(descriptor)
        expected = indexed.get(data.get("id", ""))
        if expected is None or (ROOT / expected["path"]).resolve() != descriptor.parent.resolve():
            fail("unknown-workpackage", relative(descriptor.parent), "工作包未进入全仓索引或路径不一致")

    code_roots = [
        ROOT / "00-governance/repository-tools",
        ROOT / "04-demo/backend",
        ROOT / "04-demo/frontend",
        ROOT / "04-demo/runtime",
        ROOT / "04-demo/tools",
        ROOT / "06-delivery/presentations",
        *registered_dirs.values(),
    ]
    for stage in stages:
        stage_root = ROOT / stage
        readme = stage_root / "README.md"
        if not readme.is_file():
            fail("missing-stage-readme", stage, "阶段缺少 README.md")
        for path in stage_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SCRIPT_SUFFIXES:
                continue
            if "templates" in path.parts:
                continue
            if not any(is_beneath(path, root) for root in code_roots):
                fail("orphan-script", relative(path), "脚本不在治理工具、Demo 组件或已登记工作包内")

    status = "pass" if not violations else "fail"
    return {
        "status": status,
        "stages": len(stages),
        "workpackages": len(indexed),
        "violations": violations,
        "warnings": warnings,
        "counts": {"violations": len(violations), "warnings": len(warnings)},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit compact JSON")
    parser.add_argument("--output", type=Path, help="write the report without changing validation semantics")
    args = parser.parse_args()
    report = validate()
    rendered = json.dumps(report, ensure_ascii=False, indent=None if args.json else 2)
    if args.output:
        destination = args.output if args.output.is_absolute() else ROOT / args.output
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
