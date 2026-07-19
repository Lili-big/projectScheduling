from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROLE_ROOT = ROOT / "00-governance/asset-policy/thread-roles"
REGISTRY = ROLE_ROOT / "registry.yaml"
RESIDENT_IDS = {"G00", "L01"}
REMOVED_CAPABILITIES = {"L02", "L03", "L06", "D01", "D02", "D03", "D04", "D05", "D06", "D07"}


def registry_text() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def resident_records() -> dict[str, str]:
    section = registry_text().split("resident_threads:\n", 1)[1]
    matches = list(re.finditer(r"^  - id: ([GLD]\d{2})$", section, re.MULTILINE))
    return {
        match.group(1): section[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(section)]
        for index, match in enumerate(matches)
    }


def field(block: str, name: str) -> str:
    match = re.search(rf'^    {re.escape(name)}: "?([^"\n]+)"?$', block, re.MULTILINE)
    assert match, f"missing {name}: {block}"
    return match.group(1)


def test_registry_contains_only_live_resident_threads() -> None:
    text = registry_text()
    assert set(re.findall(r"^([a-z_]+):", text, re.MULTILINE)) == {"version", "updated_at", "resident_threads"}
    assert "version: 10" in text
    assert "capabilities:" not in text
    assert "requirement_template:" not in text

    records = resident_records()
    assert set(records) == RESIDENT_IDS
    thread_ids = [field(block, "thread_id") for block in records.values()]
    assert len(thread_ids) == len(set(thread_ids)) == 2
    assert all(re.fullmatch(r"[0-9a-f-]{36}", value) for value in thread_ids)
    for role_id, block in records.items():
        assert field(block, "contract") == f"{role_id}.md"
        contract = ROLE_ROOT / f"{role_id}.md"
        assert contract.is_file()
        assert contract.read_text(encoding="utf-8").startswith(f"# {role_id}｜")


def test_default_execution_path_is_single_and_concise() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert len(agents) <= 1500
    for step in (
        "读取目标文件、邻近测试",
        "完成最小修改",
        "运行一次与风险匹配的最小验证",
        "然后停止",
    ):
        assert step in agents
    assert "默认不创建工作项、不路由角色、不加载 Thread 注册表、不写计划" in agents
    assert "同一状态不重复读取，同一测试不重复运行" in agents
    assert "可逆、权限范围内且验收明确的操作直接执行" in agents


def test_formal_workflow_has_four_skills_and_one_confirmation() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    expected = "$speckit-specify → $speckit-plan → $speckit-tasks → 用户确认 → $speckit-implement"
    assert expected in agents
    for removed in ("$speckit-clarify", "$speckit-analyze", "$speckit-converge"):
        assert removed not in agents
    assert not (ROOT / ".specify/workflows/speckit/workflow.yml").exists()
    assert not (ROOT / ".specify/workflows/workflow-registry.json").exists()


def test_removed_roles_and_work_item_layer_stay_absent() -> None:
    for role_id in REMOVED_CAPABILITIES:
        assert not (ROLE_ROOT / f"{role_id}.md").exists()
    for removed in ("README.md", "REQUIREMENT_THREAD_TEMPLATE.md", "L05.md", "HANDOFF_TEMPLATE.md"):
        assert not (ROLE_ROOT / removed).exists()


def test_project_skill_set_has_no_redundant_stages_or_compatibility_entry() -> None:
    skill_files = sorted((ROOT / ".agents/skills").glob("*/SKILL.md"))
    assert {path.parent.name for path in skill_files} == {
        "demo-algorithm-explainer",
        "speckit-checklist",
        "speckit-constitution",
        "speckit-implement",
        "speckit-plan",
        "speckit-specify",
        "speckit-tasks",
    }
    for skill in skill_files:
        match = re.search(r'^name:\s*["\']?([^"\'\n]+)', skill.read_text(encoding="utf-8"), re.MULTILINE)
        assert match and match.group(1) == skill.parent.name
    assert not (ROOT / ".agents/skills/README.md").exists()
    assert not (ROOT / "04-demo/skills/demo-algorithm-explainer/SKILL.md").exists()
    assert not (ROOT / ".specify/integrations/codex.manifest.json").exists()


def test_merged_speckit_stages_own_one_check_each() -> None:
    skill_root = ROOT / ".agents/skills"
    specify = (skill_root / "speckit-specify/SKILL.md").read_text(encoding="utf-8")
    tasks = (skill_root / "speckit-tasks/SKILL.md").read_text(encoding="utf-8")
    implement = (skill_root / "speckit-implement/SKILL.md").read_text(encoding="utf-8")

    assert "create-new-feature.ps1 -Json" in specify
    assert "ask one concise question at a time, at most three" in specify
    assert "Do not create a separate clarification artifact or stage" in specify
    assert "Perform one consistency check" in tasks
    assert "Ask the user to confirm `tasks.md` and this result" in tasks
    assert "run the validation commands defined by the tasks once" in implement
    assert "Do not mechanically reload every design file" in implement
    assert "$speckit-clarify" not in specify
    assert "$speckit-analyze" not in tasks
    assert "$speckit-converge" not in implement


def test_spec_kit_constitution_points_to_merged_gates() -> None:
    constitution = (ROOT / ".specify/memory/constitution.md").read_text(encoding="utf-8")
    assert "Version**: 1.2.2" in constitution
    assert "$speckit-tasks` 的一致性检查" in constitution
    assert "$speckit-implement` 的验证" in constitution
    for removed in ("$speckit-clarify", "$speckit-analyze", "$speckit-converge"):
        assert removed not in constitution
