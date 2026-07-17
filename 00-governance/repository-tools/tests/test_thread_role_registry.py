from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ROLE_ROOT = ROOT / "00-governance/asset-policy/thread-roles"
REGISTRY = ROLE_ROOT / "registry.yaml"
EXPECTED_ROLE_IDS = {
    "G00",
    "L01",
    "L02",
    "L03",
    "L05",
    "L06",
    "D01",
    "D02",
    "D03",
    "D04",
    "D05",
    "D06",
    "D07",
}


def registry_text() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def test_registry_has_one_unique_binding_for_every_resident_role() -> None:
    text = registry_text()
    role_ids = re.findall(r"^  - id: ([GLD]\d{2})$", text, flags=re.MULTILINE)
    thread_ids = re.findall(
        r'^    thread_id: "([0-9a-f-]{36})"$', text, flags=re.MULTILINE
    )
    contracts = re.findall(
        r'^    contract: "([GLD]\d{2}\.md)"$', text, flags=re.MULTILINE
    )

    assert set(role_ids) == EXPECTED_ROLE_IDS
    assert len(role_ids) == len(set(role_ids))
    assert len(thread_ids) == len(role_ids) == len(set(thread_ids))
    assert set(contracts) == {f"{role_id}.md" for role_id in EXPECTED_ROLE_IDS}


def test_every_registered_role_has_a_matching_contract() -> None:
    for role_id in EXPECTED_ROLE_IDS:
        contract = ROLE_ROOT / f"{role_id}.md"
        assert contract.is_file(), f"missing role contract: {contract}"
        text = contract.read_text(encoding="utf-8")
        assert text.startswith(f"# {role_id}｜")
        assert "registry.yaml" in text
        assert "本契约优先于旧对话" in text


def test_repository_entrypoint_points_to_the_role_registry() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    governance = (ROOT / "00-governance/README.md").read_text(encoding="utf-8")
    assert "00-governance/asset-policy/thread-roles/registry.yaml" in agents
    assert "asset-policy/thread-roles/" in governance
    assert "仓库角色契约优先于 thread 标题和旧对话上下文" in registry_text()
