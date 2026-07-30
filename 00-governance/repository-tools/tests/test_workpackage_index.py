from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EXPECTED = {
    "json-task-viewer",
    "schedule-result-viewer",
    "json-schedule-review",
    "lugu",
    "zhongtie23ju-organization",
    "dianfengwu-tj03",
    "dianfengwu-tj08",
    "jiangluyi-tj01",
    "huyu-dianchangduan-3fenbu",
    "ai-assistants",
    "ai-case-summary",
    "ai-ppt-system",
    "product-agent-practice-kit",
}
REQUIRED_README_TEXT = ["目的", "输入", "运行", "成果", "跟踪与保留"]


def workpackages() -> dict[str, tuple[Path, dict]]:
    result: dict[str, tuple[Path, dict]] = {}
    for path in ROOT.glob("0[0-6]-*/**/workpackage.json"):
        if "templates" in path.parts:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        result[data["id"]] = (path.parent, data)
    return result


def test_expected_independent_workpackages_are_registered_once() -> None:
    packages = workpackages()
    assert EXPECTED <= set(packages)
    assert len(packages) == len({data["id"] for _, data in packages.values()})


def test_workpackage_readmes_explain_input_command_result_and_retention() -> None:
    for package_id in EXPECTED:
        directory, _ = workpackages()[package_id]
        readme = (directory / "README.md").read_text(encoding="utf-8")
        missing = [text for text in REQUIRED_README_TEXT if text not in readme]
        assert missing == [], f"{package_id} README missing {missing}"


def test_registered_file_references_resolve_inside_each_workpackage() -> None:
    for package_id, (directory, data) in workpackages().items():
        for field in ("inputs", "entrypoints", "results"):
            for relative in data[field]:
                path = (directory / relative).resolve(strict=False)
                path.relative_to(directory.resolve())
                assert path.exists(), f"{package_id}.{field} missing {relative}"


def test_workpackage_tracking_and_retention_are_explicit() -> None:
    for package_id, (_, data) in workpackages().items():
        assert data["tracking_policy"] in {"tracked", "ignored", "local-only"}
        assert data["retention_policy"].strip(), package_id


def test_product_agent_practice_kit_has_reproducible_initializer() -> None:
    directory, data = workpackages()["product-agent-practice-kit"]
    initializer = "scripts/init-product-agent-project.ps1"
    assert initializer in data["entrypoints"]
    assert (directory / initializer).is_file()
