from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = SKILL_ROOT / "assets"
TEMPLATE_ROOT = ASSET_ROOT / "project-skills"
MANIFEST_PATH = ASSET_ROOT / "manifest.json"


def _load_manifest() -> dict[str, object]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    skills = data.get("skills")
    if not isinstance(skills, list) or not skills or not all(isinstance(item, str) for item in skills):
        raise RuntimeError("assets/manifest.json 必须包含名为 skills 的非空字符串列表")
    return data


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _select_skills(manifest: dict[str, object], requested: list[str] | None) -> list[str]:
    available = list(manifest["skills"])
    if not requested:
        return available
    unknown = sorted(set(requested) - set(available))
    if unknown:
        raise RuntimeError(f"未知 Skill 名称：{', '.join(unknown)}")
    return [name for name in available if name in requested]


def _resolve_project_root(raw: str) -> Path:
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"项目根目录不存在：{root}")
    if not (root / ".specify").is_dir():
        raise RuntimeError(f"缺少 Spec Kit 项目标记：{root / '.specify'}")
    return root


def _paths(project_root: Path, name: str) -> tuple[Path, Path]:
    source = TEMPLATE_ROOT / name / "SKILL.md"
    target = project_root / ".agents" / "skills" / name / "SKILL.md"
    if not source.is_file():
        raise RuntimeError(f"缺少工具包模板：{source}")
    return source, target


def _status(project_root: Path, names: list[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for name in names:
        source, target = _paths(project_root, name)
        if not target.is_file():
            state = "缺失"
        elif _digest(source) == _digest(target):
            state = "一致"
        else:
            state = "存在差异"
        result.append({"skill": name, "status": state, "target": str(target)})
    return result


def _print_status(items: list[dict[str, str]]) -> None:
    for item in items:
        print(f"{item['status']:<9} {item['skill']} -> {item['target']}")


def _initialize(project_root: Path, names: list[str], write: bool) -> int:
    changed = 0
    for name in names:
        source, target = _paths(project_root, name)
        if target.exists():
            print(f"已跳过    {name} -> 项目副本已存在")
            continue
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            print(f"已创建    {name} -> {target}")
            changed += 1
        else:
            print(f"计划创建  {name} -> {target}")
    if not write:
        print("预览完成：添加 --write 后才会创建缺失的项目副本")
    return changed


def _upgrade(project_root: Path, names: list[str], write: bool) -> int:
    states = {item["skill"]: item["status"] for item in _status(project_root, names)}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = project_root / ".codex-tmp" / "speckit-skill-backups" / stamp
    changed = 0
    for name in names:
        source, target = _paths(project_root, name)
        state = states[name]
        if state == "一致":
            print(f"无需变更  {name}")
            continue
        if not write:
            action = "计划创建" if state == "缺失" else "计划升级"
            print(f"{action:<13} {name} -> {target}")
            continue
        if target.is_file():
            backup = backup_root / name / "SKILL.md"
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, backup)
            print(f"已备份    {name} -> {backup}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        print(f"已升级    {name} -> {target}")
        changed += 1
    if not write:
        print("预览完成：请审查项目差异，明确确认后再添加 --write")
    elif changed and backup_root.exists():
        print(f"备份目录  {backup_root}")
    return changed


def _build_parser(manifest: dict[str, object]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="从工具包模板初始化或升级项目本地 Spec Kit Skill 副本。"
    )
    parser.add_argument("command", choices=("status", "initialize", "upgrade"))
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--skill", action="append", choices=list(manifest["skills"]))
    parser.add_argument("--write", action="store_true", help="实际执行初始化或升级写入。")
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="执行 status 时，Skill 缺失或存在差异则返回退出码 1。",
    )
    return parser


def main() -> int:
    try:
        manifest = _load_manifest()
        args = _build_parser(manifest).parse_args()
        project_root = _resolve_project_root(args.project_root)
        names = _select_skills(manifest, args.skill)
        if args.command == "status":
            items = _status(project_root, names)
            _print_status(items)
            if args.fail_on_drift and any(item["status"] != "一致" for item in items):
                return 1
            return 0
        if args.command == "initialize":
            _initialize(project_root, names, args.write)
            return 0
        _upgrade(project_root, names, args.write)
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
