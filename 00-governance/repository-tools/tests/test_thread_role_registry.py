from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROLE_ROOT = ROOT / "00-governance/asset-policy/thread-roles"
REGISTRY = ROLE_ROOT / "registry.yaml"
RESIDENT_IDS = {"G00", "L01"}
CAPABILITY_IDS = {
    "L02",
    "L03",
    "L06",
    "D01",
    "D02",
    "D03",
    "D04",
    "D05",
    "D06",
    "D07",
}
ALL_CONTRACT_IDS = RESIDENT_IDS | CAPABILITY_IDS


def registry_text() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def registry_section(start: str, end: str | None = None) -> str:
    text = registry_text().split(f"{start}:\n", 1)[1]
    return text.split(f"\n{end}:\n", 1)[0] if end else text


def test_registry_has_only_two_unique_resident_thread_bindings() -> None:
    residents = registry_section("resident_threads", "capabilities")
    resident_ids = re.findall(r"^  - id: ([GLD]\d{2})$", residents, re.MULTILINE)
    thread_ids = re.findall(
        r'^    thread_id: "([0-9a-f-]{36})"$', residents, re.MULTILINE
    )

    assert set(resident_ids) == RESIDENT_IDS
    assert len(resident_ids) == len(set(resident_ids)) == 2
    assert len(thread_ids) == len(set(thread_ids)) == 2
    assert "thread_id:" not in registry_section("capabilities")


def test_former_l_and_d_roles_are_capabilities_with_contracts() -> None:
    capabilities = registry_section("capabilities")
    capability_ids = re.findall(
        r"^  - id: ([LD]\d{2})$", capabilities, re.MULTILINE
    )
    assert set(capability_ids) == CAPABILITY_IDS

    for capability_id in CAPABILITY_IDS:
        contract = ROLE_ROOT / f"{capability_id}.md"
        assert contract.is_file(), f"missing capability contract: {contract}"
        text = contract.read_text(encoding="utf-8")
        assert text.startswith(f"# {capability_id}｜")
        assert "这是能力契约，不绑定常驻 Thread" in text
        assert "registry.yaml" in text
        assert "本契约优先于旧对话" in text


def test_resident_contracts_and_l01_closed_loop() -> None:
    residents = registry_section("resident_threads", "capabilities")
    assert 'title: "G00｜项目治理与工作项协调"' in residents
    assert 'title: "L01｜需求发现与验证闭环"' in residents
    assert 'covered_stages: ["01-discovery", "05-validation"]' in residents
    assert '"01-discovery/workpackages/"' in residents
    assert '"05-validation/workpackages/"' in residents

    for resident_id in RESIDENT_IDS:
        text = (ROLE_ROOT / f"{resident_id}.md").read_text(encoding="utf-8")
        assert text.startswith(f"# {resident_id}｜")
        assert "这是常驻 Thread 契约" in text

    assert "\n  - id: L05\n" not in registry_text()
    assert not (ROLE_ROOT / "L05.md").exists()


def test_registry_defines_one_requirement_one_thread() -> None:
    text = registry_text()
    template = (ROLE_ROOT / "REQUIREMENT_THREAD_TEMPLATE.md").read_text(
        encoding="utf-8"
    )

    assert "version: 7" in text
    assert 'execution_model: "one_requirement_one_thread"' in text
    assert "work_id_required: true" in text
    assert 'template: "REQUIREMENT_THREAD_TEMPLATE.md"' in text
    assert 'user_facing_owner: "work_item_thread"' in text
    assert 'lifecycle_coverage: "discovery_through_closeout"' in text
    assert 'capability_loading: "load_required_capabilities_in_same_thread"' in text
    assert 'final_accountability: "work_item_thread"' in text

    for required_field in (
        'work_id: "<唯一需求或规格编号>"',
        "objective:",
        "source_paths:",
        "acceptance:",
        "risk_level:",
        "required_capabilities:",
        "close_conditions:",
    ):
        assert required_field in template

    retired_template = "HANDOFF_" + "TEMPLATE.md"
    assert not (ROLE_ROOT / retired_template).exists()


def test_subagents_are_explicitly_allowed_without_role_or_count_bans() -> None:
    registry = registry_text()
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    contracts = "\n".join(
        (ROLE_ROOT / f"{contract_id}.md").read_text(encoding="utf-8")
        for contract_id in ALL_CONTRACT_IDS
    )
    all_governance_text = "\n".join((registry, agents, contracts))

    assert "subagent_policy:" in registry
    assert "  enabled: true" in registry
    assert 'authorization: "project_contract"' in registry
    assert 'orchestrator: "work_item_thread"' in registry
    assert 'capability_named_agents: "allowed"' in registry
    assert 'concurrency: "platform_limit"' in registry
    assert "minimum_useful_fanout: true" in registry
    assert 'write_policy: "disjoint_paths_or_isolated_worktree"' in registry
    assert 'result_flow: "summarize_to_parent"' in registry
    assert 'durable_authority: "parent_work_item_thread"' in registry

    assert "项目契约明确允许工作项 Thread 自行创建、管理和结束 Subagent" in agents
    assert "能力型临时名称" in agents
    assert "数量不设固定项目上限" in agents
    assert "互不重叠的 `allowed_paths`" in agents
    assert "隔离 Worktree" in agents

    retired_rules = (
        "forbid_role_named_" + "subagents",
        "role_internal_" + "subagents",
        "子智能体只允许由实际承接任务的" + "常驻 thread",
        "禁止 `G00` " + "创建或使用",
        "只能一个 " + "Subagent",
        "Subagent " + "只能只读",
    )
    for retired_rule in retired_rules:
        assert retired_rule not in all_governance_text


def test_review_policy_keeps_r0_to_r3_without_a_resident_reviewer() -> None:
    text = registry_text()
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    d06 = (ROLE_ROOT / "D06.md").read_text(encoding="utf-8")

    assert "default_full_suite_runs: 1" in text
    assert 'reviewer_execution: "parent_or_temporary_subagents_based_on_risk"' in text
    assert "dedicated_resident_reviewer_required: false" in text
    assert '"R0-self-check"' in text
    assert '"R3-full-independent-release-gate"' in text
    assert "R2/R3 可由一个或多个临时审查 Subagent 执行" in agents
    assert "可以由主 Thread 或一个或多个临时审查 Subagent 承担" in d06


def test_policy_layers_and_repository_navigation_are_current() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    governance = (ROOT / "00-governance/README.md").read_text(encoding="utf-8")
    directory_readme = (ROLE_ROOT / "README.md").read_text(encoding="utf-8")
    registry = registry_text()

    assert "00-governance/asset-policy/thread-roles/" in agents
    assert "公共流程的唯一权威源" in agents
    assert 'common_execution_rules: "AGENTS.md"' in registry
    assert 'capability_contract_scope: "reusable_domain_responsibilities_paths_and_boundaries_only"' in registry
    assert "forbid_common_rule_duplication_in_contracts: true" in registry
    assert "单需求工作项、能力契约与 Subagent 策略" in governance
    assert "当前常驻 Thread" in directory_readme
    assert "当前能力" in directory_readme
