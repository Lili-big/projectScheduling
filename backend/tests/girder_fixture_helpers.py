from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.girder_planning.fingerprints import stable_fingerprint


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "girder_planning"


def load_girder_fixture(name: str) -> dict[str, Any]:
    path = (FIXTURE_ROOT / name).resolve()
    if FIXTURE_ROOT.resolve() not in path.parents:
        raise ValueError("夹具路径必须位于 girder_planning 目录。")
    return json.loads(path.read_text(encoding="utf-8"))


def fixture_fingerprint(value: Any) -> str:
    return stable_fingerprint(value, prefix="fixture")
