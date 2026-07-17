"""Move empty legacy root directory shells to local migration archive.

This helper never deletes directories. It refuses any legacy root containing a
file or link, then moves the empty directory tree intact under .local-data.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / ".local-data/archive/migration-empty-shells"
LEGACY_ROOTS = [
    "artifacts",
    "backend",
    "deliverables",
    "docs",
    "examples",
    "frontend",
    "local-json-task-review",
    "logs",
    "output",
    "specs",
    "tools",
]
PRESERVED_ROOTS = {
    "outputs": "批准清单要求原位保留 outputs/lugu-validation-20260715 外部依赖目录联接",
}


def main() -> int:
    moved: list[str] = []
    already_archived: list[str] = []
    for name in LEGACY_ROOTS:
        source = ROOT / name
        target = ARCHIVE / name
        if not source.exists():
            if target.exists():
                already_archived.append(name)
            continue
        unsafe = [
            item
            for item in source.rglob("*")
            if item.is_file() or item.is_symlink()
        ]
        if unsafe:
            raise RuntimeError(f"legacy root is not empty: {name}: {unsafe[:5]}")
        if target.exists():
            raise FileExistsError(f"empty-shell archive target exists: {target}")
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        moved.append(name)
    print(
        json.dumps(
            {
                "mode": "move-only",
                "moved": moved,
                "already_archived": already_archived,
                "preserved": PRESERVED_ROOTS,
                "deleted_count": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
