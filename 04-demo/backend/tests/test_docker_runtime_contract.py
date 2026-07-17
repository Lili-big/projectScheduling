from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.importing.bridge import default_local_bridge_workbook


ROOT = Path(__file__).resolve().parents[3]


def test_dockerfile_preserves_python_api_runtime_and_sample_compatibility() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "COPY requirements.txt" in dockerfile
    assert "COPY 04-demo/backend ./backend" in dockerfile
    assert "COPY *.xlsx ./" not in dockerfile
    assert "COPY 04-demo/examples ./examples" in dockerfile
    assert "EXPOSE 8000" in dockerfile
    assert "uvicorn app.main:app" in dockerfile
    assert "--app-dir backend" in dockerfile


def test_default_sample_exists_in_lifecycle_examples_location() -> None:
    name = "渠溪河特大桥结构设计表.xlsx"
    assert (ROOT / "04-demo/examples" / "bridge-import" / name).is_file()


def test_default_sample_search_supports_legacy_and_examples_paths(tmp_path: Path) -> None:
    name = "渠溪河特大桥结构设计表.xlsx"
    examples = tmp_path / "examples" / "bridge-import"
    examples.mkdir(parents=True)
    new_path = examples / name
    new_path.write_bytes(b"new")
    assert default_local_bridge_workbook(tmp_path) == new_path

    legacy_path = tmp_path / name
    legacy_path.write_bytes(b"legacy")
    assert default_local_bridge_workbook(tmp_path) == legacy_path
