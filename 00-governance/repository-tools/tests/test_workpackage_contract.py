from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
STAGE_PATTERN = re.compile(r"^(00|01|02|03|04|05|06)-")
REQUIRED = {"id", "stage", "purpose", "status", "inputs", "entrypoints", "results", "owner", "tracking_policy", "retention_policy"}


def schema_path() -> Path:
    return ROOT / "03-requirements/specs/045-lifecycle-workspace-governance/contracts/workpackage.schema.json"


def test_workpackage_schema_requires_tracking_and_retention_policies() -> None:
    schema = json.loads(schema_path().read_text(encoding="utf-8"))
    assert REQUIRED <= set(schema["required"])
    assert schema["properties"]["tracking_policy"]["enum"] == ["tracked", "ignored", "local-only"]


def test_every_workpackage_has_one_stage_and_complete_input_command_result_links() -> None:
    packages = sorted(
        path
        for stage in ROOT.glob("0[0-6]-*")
        for path in stage.rglob("workpackage.json")
        if "templates" not in path.parts
    )
    assert packages, "target lifecycle workspace must contain at least one workpackage.json"
    ids: set[str] = set()
    for path in packages:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert REQUIRED <= set(data), f"{path} missing required fields"
        assert STAGE_PATTERN.match(data["stage"])
        assert data["id"] not in ids
        ids.add(data["id"])
        assert isinstance(data["inputs"], list)
        assert isinstance(data["entrypoints"], list)
        assert isinstance(data["results"], list)
        assert data["tracking_policy"] in {"tracked", "ignored", "local-only"}
