from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGES = [
    "00-governance",
    "01-customer-validation",
    "02-solution-analysis",
    "03-requirements",
    "04-demo",
    "06-delivery",
]
REQUIRED_HEADINGS = ["目的", "进入条件", "退出条件", "权威资产", "工作包索引", "相邻阶段", "禁止内容", "维护触发条件"]


def test_each_stage_readme_has_the_required_contract_sections() -> None:
    for stage in STAGES:
        readme = ROOT / stage / "README.md"
        content = readme.read_text(encoding="utf-8")
        missing = [heading for heading in REQUIRED_HEADINGS if heading not in content]
        assert missing == [], f"{stage} missing headings: {missing}"


def test_each_stage_readme_exposes_workpackages_within_two_hops() -> None:
    for index, stage in enumerate(STAGES):
        content = (ROOT / stage / "README.md").read_text(encoding="utf-8")
        assert "workpackage" in content.lower() or "工作包" in content
        neighbours = {STAGES[item] for item in (index - 1, index + 1) if 0 <= item < len(STAGES)}
        assert neighbours <= {name for name in STAGES if name in content}

