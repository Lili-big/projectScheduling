from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_042 = ROOT / "03-requirements/specs/042-repo-architecture-modernization/asset-migration-manifest.json"
MANIFEST_045 = ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/asset-migration-manifest.json"
CUSTOMER_VALIDATION_REDIRECTS = {
    "05-validation/reports/AI参数输入助手验证说明.md": "01-customer-validation/ai-assistants/validation-results/AI参数输入助手验证说明.md",
    "05-validation/reports/AI资源配置与排程优化助手验证说明.md": "01-customer-validation/ai-assistants/validation-results/AI资源配置与排程优化助手验证说明.md",
    "01-discovery/workpackages/lugu-customer-research/results/泸古项目7月15日上午调研验证记录_20260715.docx": "01-customer-validation/泸古1标/validation-results/泸古项目7月15日上午调研验证记录_20260715.docx",
    "01-discovery/workpackages/lugu-customer-research/results/泸古项目7月16日前期工期策划思路分析_20260715.docx": "01-customer-validation/泸古1标/validation-results/泸古项目7月16日前期工期策划思路分析_20260715.docx",
    "01-discovery/workpackages/lugu-customer-research/inputs/泸古项目客户访谈提纲_20260715.md": "01-customer-validation/泸古1标/validation-plans/泸古项目客户访谈提纲_20260715.md",
    "05-validation/workpackages/lugu-validation-material/plans/泸古项目客户验证计划_20260715.md": "01-customer-validation/泸古1标/validation-plans/泸古项目客户验证计划_20260715.md",
    "01-discovery/workpackages/lugu-customer-research/scripts/build_planning_logic_report.py": "01-customer-validation/泸古1标/validation-results/_scripts/build_planning_logic_report.py",
    "01-discovery/workpackages/lugu-customer-research/scripts/build_report.py": "01-customer-validation/泸古1标/validation-results/_scripts/build_report.py",
    "01-discovery/workpackages/lugu-customer-research/scripts/check_planning_logic_report.py": "01-customer-validation/泸古1标/validation-results/_scripts/check_planning_logic_report.py",
    "01-discovery/workpackages/lugu-customer-research/scripts/extract_planning_transcript.py": "01-customer-validation/泸古1标/validation-results/_scripts/extract_planning_transcript.py",
    "05-validation/workpackages/lugu-validation-material/scripts/build_validation_workbook.mjs": "01-customer-validation/泸古1标/validation-plans/_scripts/build_validation_workbook.mjs",
    "05-validation/workpackages/lugu-validation-material/scripts/verify_validation_workbook.mjs": "01-customer-validation/泸古1标/validation-plans/_scripts/verify_validation_workbook.mjs",
}


def current_target(source: str) -> str:
    entries = json.loads(MANIFEST_045.read_text(encoding="utf-8"))["entries"]
    migrated = {entry["source"]: entry["target"] for entry in entries}
    target = migrated.get(source, source)
    return CUSTOMER_VALIDATION_REDIRECTS.get(target, target)


def test_manifest_hashes_match_every_post_migration_binary_target() -> None:
    entries = json.loads(MANIFEST_042.read_text(encoding="utf-8"))["entries"]
    for entry in entries:
        path = ROOT / current_target(entry["target"])
        assert path.is_file(), entry["target"]
        if entry["binary"]:
            assert path.stat().st_size == entry["size_bytes"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_formal_deliverables_remain_tracked_and_binary_assets_have_hashes() -> None:
    entries = json.loads(MANIFEST_042.read_text(encoding="utf-8"))["entries"]
    formal = [entry for entry in entries if entry["category"] == "formal_deliverable"]
    assert formal
    assert all(current_target(entry["target"]).startswith("06-delivery/deliverables/") for entry in formal)
    assert all(entry["tracking_action"] == "git_mv_keep_tracked" and entry["tracked_after"] for entry in formal)
    assert all(len(entry["sha256"]) == 64 for entry in entries if entry["binary"])
